#!/usr/bin/env python3
"""OPS club-game ingestion and Stockfish analysis for GitHub Actions.

Requires python-chess for ingestion / analysis, and a Stockfish executable for analysis.
Only appends to verein.pgn, never reorders the historic club-001, ... identifiers.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PGN = ROOT / 'verein.pgn'
STATE = ROOT / 'analysis' / 'processed.json'
TASKS = ROOT / 'ops-auto-tasks.json'
INCOMING = ROOT / 'incoming'
PLAYER = 'oguzhan'


def read_games(text):
    import chess.pgn
    stream = io.StringIO(text)
    games = []
    while True:
        game = chess.pgn.read_game(stream)
        if game is None:
            break
        if game.errors:
            raise ValueError('Ungültige PGN: ' + '; '.join(str(x) for x in game.errors[:3]))
        if game.headers.get('White', '').casefold() != PLAYER and game.headers.get('Black', '').casefold() != PLAYER:
            raise ValueError('Partie ohne Oguzhan als Spieler erkannt: ' + str(game.headers))
        games.append(game)
    return games


def identity(game):
    # Move-sequence identity is stronger than a potentially missing/mis-copied chess.com link.
    return hashlib.sha256(' '.join(m.uci() for m in game.mainline_moves()).encode()).hexdigest()


def ingest():
    import chess.pgn
    text = PGN.read_text(encoding='utf-8')
    existing = read_games(text)
    ids = {identity(g) for g in existing}
    new = []
    files = sorted(INCOMING.glob('*.pgn'))
    for file in files:
        parsed = read_games(file.read_text(encoding='utf-8-sig'))
        if not parsed:
            raise ValueError(f'{file}: Keine PGN-Partie gefunden.')
        for game in parsed:
            code = identity(game)
            if code not in ids:
                ids.add(code)
                new.append(game)
    if new:
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
        additions = '\n\n'.join(g.accept(exporter) for g in new)
        PGN.write_text(text.rstrip() + '\n\n' + additions.rstrip() + '\n', encoding='utf-8')
    # Remove submitted files only after ALL have passed validation; original games stay in verein.pgn.
    for file in files:
        file.unlink()
    print(f'PGN-Import: {len(existing)} vorhanden, {len(new)} neu, {len(files)} Datei(en) verarbeitet.')
    return len(new)


def score_cp(score):
    return score.score(mate_score=100000)


def scalar_score(info, side):
    return score_cp(info['score'].pov(side))


def phase(board, ply):
    import chess
    material = sum(len(board.pieces(pt, col)) * val for col in [chess.WHITE, chess.BLACK]
                   for pt, val in [(chess.QUEEN, 9), (chess.ROOK, 5), (chess.BISHOP, 3), (chess.KNIGHT, 3)])
    if ply <= 20:
        return 'Eröffnung'
    return 'Endspiel' if material <= 18 else 'Mittelspiel'


def type_score(info, side):
    x = info['score'].pov(side)
    if x.is_mate():
        return 'mate', x.mate()
    return 'cp', None


def san_line(board, pv, n=16):
    b = board.copy()
    out = []
    for move in pv[:n]:
        if move not in b.legal_moves:
            break
        out.append(b.san(move))
        b.push(move)
    return out


def analyse_one(engine, game, game_index, settings):
    import chess
    import chess.engine
    side = chess.WHITE if game.headers['White'].casefold() == PLAYER else chess.BLACK
    board = game.board()
    candidates = []
    for ply, played in enumerate(game.mainline_moves(), 1):
        if played not in board.legal_moves:
            raise ValueError(f'Illegaler Zug in club-{game_index:03d}, Halbzug {ply}')
        if board.turn != side:
            board.push(played)
            continue
        before_board = board.copy(stack=False)
        before = engine.analyse(board, chess.engine.Limit(depth=settings.scan_depth, time=settings.scan_seconds))
        board.push(played)
        after = engine.analyse(board, chess.engine.Limit(depth=settings.scan_depth, time=settings.scan_seconds))
        good = scalar_score(before, side)
        actual = scalar_score(after, side)
        loss = good - actual
        if (loss >= settings.min_loss and not (good < -500 and actual < -550)
                and not (good > 800 and actual > 500)):
            candidates.append((loss, ply, before_board, played))
    candidates.sort(key=lambda x: x[0], reverse=True)
    selected = []
    for c in candidates:
        if any(abs(c[1] - s[1]) < 6 for s in selected):
            continue  # avoid training the same tactical episode several times
        selected.append(c)
        if len(selected) >= settings.max_tasks_per_game:
            break
    tasks = []
    for _, ply, pos, actual in selected:
        before = engine.analyse(pos, chess.engine.Limit(depth=settings.deep_depth, time=settings.deep_seconds))
        if not before.get('pv'):
            continue
        after_pos = pos.copy(stack=False)
        after_pos.push(actual)
        after = engine.analyse(after_pos, chess.engine.Limit(depth=settings.deep_depth, time=settings.deep_seconds))
        best = before['pv'][0]
        if best == actual:
            continue
        best_cp = scalar_score(before, side)
        actual_cp = scalar_score(after, side)
        loss = best_cp - actual_cp
        if loss < settings.min_loss or (best_cp < -500 and actual_cp < -550) or (best_cp > 800 and actual_cp > 500):
            continue
        val_type, val_mate = type_score(before, side)
        after_type, after_mate = type_score(after, not side)
        depth = min(int(before.get('depth', 0)), int(after.get('depth', 0)))
        moves = [m.uci() for m in before['pv'][:16]]
        url = game.headers.get('Link', '')
        phase_name = phase(pos, ply)
        tasks.append({
            'id': f'club-{game_index:03d}-{ply}', 'fen': pos.fen(),
            'side': 'w' if side else 'b', 'bestUci': best.uci()[:4], 'bestSan': pos.san(best),
            'actualUci': actual.uci()[:4], 'actualSan': pos.san(actual),
            'lossCp': int(min(99999, loss)), 'bestScoreCp': int(best_cp),
            'bestScoreType': val_type, 'bestMate': val_mate,
            'actualAfterScoreCp': int(scalar_score(after, not side)),
            'actualAfterScoreType': after_type, 'actualAfterMate': after_mate,
            'moveNumber': pos.fullmove_number, 'phase': phase_name,
            'date': game.headers.get('Date', ''), 'gameUrl': url,
            'timeControl': '90m+', 'sourceType': 'club', 'sourceLabel': 'Vereinspartie · Langpartie 90+ Min.',
            'positionClass': 'kritischer Fehler', 'priorityWeight': 1,
            'practicalReason': 'Stockfish-bestätigte kritische Entscheidung',
            'turningPoint': loss >= 180,
            'priority': min(1800, int(loss * 1.35)),
            'analysisDepth': depth,
            'bestWdl': None, 'actualAfterWdl': None,
            'bestPvUci': moves, 'bestPvSan': san_line(pos, before['pv']),
            'engine': str(engine.id.get('name', 'Stockfish')), 'targetDepth': settings.deep_depth,
        })
    return tasks


def analyse(settings):
    import chess.engine
    games = read_games(PGN.read_text(encoding='utf-8'))
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'processed': {}}
    result = json.loads(TASKS.read_text(encoding='utf-8')) if TASKS.exists() else {'schema': 'ops-auto-1', 'puzzles': [], 'processedClubIds': []}
    processed = state.setdefault('processed', {})
    undone = [(i, g) for i, g in enumerate(games, 1) if identity(g) not in processed]
    # Most recently added games first; older games can be processed in later daily runs.
    targets = list(reversed(undone))[:settings.max_games]
    if not targets:
        print('Keine unbearbeiteten Vereinspartien.')
        return
    if not pathlib.Path(settings.stockfish).exists():
        raise FileNotFoundError(f'Stockfish nicht gefunden: {settings.stockfish}')
    with chess.engine.SimpleEngine.popen_uci(settings.stockfish, timeout=settings.deep_seconds+15) as engine:
        options = {}
        if 'Threads' in engine.options: options['Threads'] = 2
        if 'Hash' in engine.options: options['Hash'] = 128
        if options: engine.configure(options)
        for n, game in targets:
            gid = f'club-{n:03d}'
            print(f'Analysiere {gid} …', flush=True)
            tasks = analyse_one(engine, game, n, settings)
            original_ids = {p['id'] for p in result['puzzles']}
            result['puzzles'].extend(p for p in tasks if p['id'] not in original_ids)
            if gid not in result['processedClubIds']:
                result['processedClubIds'].append(gid)
            processed[identity(game)] = {'id': gid, 'taskCount': len(tasks), 'completedAt': dt.datetime.now(dt.timezone.utc).isoformat()}
            print(f'  {len(tasks)} geprüfte Aufgabe(n)', flush=True)
    result.update({'schema': 'ops-auto-1', 'generatedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
                   'targetDepth': settings.deep_depth})
    TASKS.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Stand: {len(games)} Vereinspartien, {len(result["puzzles"])} automatische Aufgaben, {len(processed)} analysiert.')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['ingest', 'analyse'])
    p.add_argument('--stockfish', default=os.environ.get('STOCKFISH_PATH', '/usr/games/stockfish'))
    p.add_argument('--scan-depth', type=int, default=12)
    p.add_argument('--scan-seconds', type=float, default=0.13)
    p.add_argument('--deep-depth', type=int, default=30)
    p.add_argument('--deep-seconds', type=float, default=35)
    p.add_argument('--max-games', type=int, default=3)
    p.add_argument('--max-tasks-per-game', type=int, default=3)
    p.add_argument('--min-loss', type=int, default=95)
    a = p.parse_args()
    if a.command == 'ingest': ingest()
    else: analyse(a)

if __name__ == '__main__':
    main()