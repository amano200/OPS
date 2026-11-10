# OPS – automatische Analyse und GitHub-Pages-Veröffentlichung

Stand: 10.11.2026 · Basis: OPS 3b.20, 46 Vereinspartien.

## Einmalige Freigabe vor dem Live-Start

Der Workflow und OPS-Code werden auf dem separaten Entwicklungszweig mit Pull Request vorgeschlagen. Nach bestandenen Prüfungen und Übernahme in `main` wird er bei neuen Partien sowie täglich um 04:25 UTC automatisch ausgeführt.

**Wichtige GitHub-Pages-Einstellung:** Unter `https://github.com/amano200/OPS/settings/pages` die Source unter **Build and deployment** auf **GitHub Actions** stellen. Der Workflow erzeugt anschließend ein GitHub-Pages-Artefakt aus den fertigen OPS-Dateien und veröffentlicht es über `actions/deploy-pages` an der alten Adresse `https://amano200.github.io/OPS/`.

Vor dem Live-Update in OPS unter **Verwaltung** einen JSON-Export der bisherigen Trainingsdaten machen. Der bisherige lokale Fortschritt wird durch die neue Version nicht bewusst gelöscht.

## Neue Partien

In GitHub im Repository `amano200/OPS` den Ordner `incoming` öffnen und eine `.pgn`-Datei hochladen. Der GitHub-Workflow wird dadurch ausgelöst, überprüft die Partien, erkennt Zugfolgen-Dubletten, ergänzt nur neue Partien in `verein.pgn`, löscht die Eingangsdateien nach erfolgreicher Übernahme und analysiert anschließend bis zu drei noch nicht analysierte Partien pro Durchlauf. Der tägliche Zeitplan arbeitet den Rückstand ab.

## Analyse & Aufgaben

- Stockfish 18 aus dem offiziellen GitHub-Release, schneller Vorscan und vertiefende Bewertung kritischer Entscheidungen mit maximaler Tiefe 30 und Zeitlimit 35 Sekunden/Stellung (Tiefe 30 nicht garantiert).
- Maximal 3 Aufgaben pro Partie, ab ungefähr 0,95 Bauerneinheiten Nachteil; bereits eindeutig verlorene beziehungsweise klar gewonnene Stellungen werden möglichst gefiltert.
- Dauerhafter Analysefortschritt: `analysis/processed.json`. Ergebnisse: `ops-auto-tasks.json`. Die Trainingsdaten bleiben lokal pro Browser/Gerät erhalten.
- Die automatisierte Analyse bewertet Züge, nicht zuverlässig Zeitnot oder psychologische Denkfehler. Unvollständige PGNs werden nur bis zum letzten vorhandenen Zug analysiert.

## Privatsphäre

Das bestehende Repository ist **öffentlich**, damit GitHub Pages OPS bereitstellen kann. Neu eingestellte PGNs, Analyse- und Trainingsaufgaben einschließlich Links sind deshalb ebenfalls öffentlich abrufbar. Keine vertraulichen Partiedaten hochladen. Bei Bedarf später auf getrenntes privates Quellen-Repo und öffentliche Website migrieren.

## Problembehandlung

Reiter **Actions** öffnen und den letzten Lauf prüfen. Wenn die automatische Pages-Veröffentlichung fehlschlägt, zuerst die Source-Einstellung **GitHub Actions** prüfen. Wenn ein Analysejob rot wird, das betroffene Protokoll und den Fehler der jeweiligen Stufe lesen. Bei beschädigtem PGN den Import korrigieren. Der aktuelle Live-Stand bleibt erhalten, solange der PR nicht übernommen wird.