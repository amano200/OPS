"""Idempotent UI upgrade for OPS 3b.22, preserving engine, PGN and training progress."""

def once(s, old, new, name):
    n=s.count(old)
    if n!=1: raise RuntimeError(f'OPS 3b.22: {name}: anchor count {n}, expected 1')
    return s.replace(old,new,1)

def upgrade_js_322(js):
    if '// OPS 3b.22: white-perspective PV scores and live engine continuations' in js:
        return js
    old='''function shortHumanEval(ev){
 if(!ev)return '–';
 if(ev.type==='mate')return ev.mate>0?'M'+Math.abs(ev.mate):'-M'+Math.abs(ev.mate);
 const cp=ev.cp||0;return (cp>0?'+':'')+(cp/100).toFixed(1);
}'''
    new='''// OPS 3b.22: white-perspective PV scores and live engine continuations.
// Explorer scores are stored from the puzzle player's perspective; display is always White.
function shortHumanEval(ev,perspectiveSide='w'){
 if(!ev)return '–';
 const sign=perspectiveSide==='b'?-1:1;
 if(ev.type==='mate'){
  const mate=(ev.mate||0)*sign;
  return (mate>0?'+M':mate<0?'−M':'M')+Math.abs(mate);
 }
 if(ev.type==='unknown-mate')return 'Mattbewertung';
 const cp=(ev.cp||0)*sign;
 return (cp>0?'+':cp<0?'−':'')+(Math.abs(cp)/100).toFixed(1);
}'''
    js=once(js,old,new,'PV formatter')
    js=once(js,'shortHumanEval(cached.ev)',"shortHumanEval(cached.ev,currentPuzzle?.side||'w')",'PV label')
    continuation='''function showPvContinuation(fen,result,depth){
 const anchor=$('pvEval');if(!anchor)return;
 let el=$('pvContinuation');
 if(!el){
  el=document.createElement('div');el.id='pvContinuation';
  el.setAttribute('aria-live','polite');
  el.style.cssText='margin:10px 0 4px;padding:10px 12px;border:1px solid #3b4743;border-radius:9px;line-height:1.5;color:#e5eee8;font-size:0.94em;white-space:normal';
  anchor.insertAdjacentElement('afterend',el);
 }
 const moves=uciToSanLine(fen,result?.pv||[]).slice(0,12);
 el.textContent=moves.length
  ?'Beste Stockfish-Fortsetzung ab dieser Stellung (Tiefe '+depth+'): '+shortPv(moves,12)
  :'Beste Stockfish-Fortsetzung: Stockfish berechnet …';
}
'''
    js=once(js,'function renderPvLine(){',continuation+'function renderPvLine(){','continuation renderer')
    js=once(js,"$('pvEval').textContent='Aktuelle Bewertung: –'; updatePvButtons();","$('pvEval').textContent='Aktuelle Bewertung: –'; if($('pvContinuation'))$('pvContinuation').remove(); updatePvButtons();",'reset')
    a=js.index('async function runExplorerEval(fen,token){')
    b=js.index('function scheduleExplorerEval(fen){',a)
    part=js[a:b]
    part=once(part,'cached={ev:ev20,depth:r20.depth||20};','cached={ev:ev20,depth:r20.depth||20,pv:r20.pv||[]};','depth 20 PV cache')
    part=once(part,'positionEvalCache.set(key,{ev:ev30,depth:r30.depth||30});','positionEvalCache.set(key,{ev:ev30,depth:r30.depth||30,pv:r30.pv||[]});','depth 30 PV cache')
    part=once(part,'\n      renderPvLine();\n','\n      renderPvLine();showPvContinuation(fen,r20,r20.depth||20);\n','depth 20 continuation')
    part=once(part,'\n    renderPvLine();\n','\n    renderPvLine();showPvContinuation(fen,r30,r30.depth||30);\n','depth 30 continuation')
    js=js[:a]+part+js[b:]
    a=js.index('function scheduleExplorerEval(fen){')
    b=js.index('function renderPvAt(i){',a)
    part=js[a:b]
    part=once(part,'const key=fenKey(fen),cached=positionEvalCache.get(key);','''const key=fenKey(fen);
 // The engine has already analyzed the player's move during answer checking.
 if(pvMode==='user'&&pvIndex===1&&userPvData?.moves?.length>1&&lastAnalysisData?.userEval){
  positionEvalCache.set(key,{ev:lastAnalysisData.userEval,depth:userPvData.depth||30,pv:userPvData.moves.slice(1)});
 }
 const cached=positionEvalCache.get(key);''','checked move reuse')
    part=once(part,'\n   renderPvLine();\n','\n   renderPvLine();showPvContinuation(fen,cached,cached.depth);\n','cached PV display')
    part=once(part,"   $('pvEval').textContent='Aktuelle Bewertung: Stockfish Full rechnet …';","   $('pvEval').textContent='Aktuelle Bewertung: Stockfish Full rechnet …';showPvContinuation(fen,{pv:[]},null);",'pending PV display')
    js=js[:a]+part+js[b:]
    js=once(js,"syncVariationField();openPv('best');focusBoardForKeys();updateCurrentReviewInfo();","syncVariationField();openPv('user');renderPvAt(1);focusBoardForKeys();updateCurrentReviewInfo();",'auto-show after answer')
    js=once(js,"humanEval(lastAnalysisData.bestEval)","whiteDisplayEval(lastAnalysisData.bestEval,currentPuzzle?.side||'w')",'share best eval')
    js=once(js,"humanEval(lastAnalysisData.userEval)","whiteDisplayEval(lastAnalysisData.userEval,currentPuzzle?.side||'w')",'share user eval')
    return js
