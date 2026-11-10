#!/usr/bin/env python3
"""Static validation of historical PGN and the OPS shipping assets."""
import base64
import gzip
import json
import pathlib
import re
from ops_pipeline import ROOT, PGN, read_games, identity


def main():
    games = read_games(PGN.read_text(encoding='utf-8-sig'))
    if len(games) < 46:
        raise AssertionError(f'Nur {len(games)} Vereinspartien (erwartet mindestens 46).')
    if len(set(identity(g) for g in games)) != len(games):
        raise AssertionError('Doppelte Partien in verein.pgn vorhanden.')
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    blocks = re.findall(r"await gun\('([A-Za-z0-9+/=]+)'\)", html)
    if len(blocks) != 3:
        raise AssertionError('OPS enthaelt nicht die erwarteten drei eingebetteten Bloecke.')
    pgn = gzip.decompress(base64.b64decode(blocks[1])).decode('utf-8')
    if pgn.strip() != PGN.read_text(encoding='utf-8').strip():
        raise AssertionError('Eingebettete Partien sind nicht mit verein.pgn synchronisiert.')
    js = gzip.decompress(base64.b64decode(blocks[2])).decode('utf-8')
    if 'await importPreparedClubTasks();' not in js:
        raise AssertionError('Automatischer Aufgabenimport ist nicht aktiv.')
    data = json.loads((ROOT / 'ops-auto-tasks.json').read_text(encoding='utf-8'))
    if data.get('schema') != 'ops-auto-1' or not isinstance(data.get('puzzles'), list):
        raise AssertionError('Ungueltiges OPS-Aufgabenformat.')
    print(f'OK: {len(games)} legal geparste Vereinspartien, importierbare OPS-Daten.')


if __name__ == '__main__':
    main()