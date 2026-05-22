# CLAUDE.md

Diese Datei gibt Claude Code den Kontext für dieses Repository.

---

## Projekt-Kontext

**Projektname:** Audio- und Foto-Verarbeitungs-Pipeline
**Kurs:** Python for Beginners, FS 26
**Hochschule:** HSLU
**Dozent:** Sami Hassanein
**Student:** Fabio Roos (Einzelprojekt)
**Abgabedatum:** 29. Mai 2026 (via Ilias, "Leistungsnachweise und Kommunikation" > "Abgabeorder für Projekte")

---

## Problemstellung

Ein Techniker erfasst auf einer Begehung Audiodiktate und Fotos der Befunde. Danach müssen die Aufnahmen manuell ausgewertet und in ein strukturiertes Dokument überführt werden — zeitaufwändig und fehleranfällig. Ziel ist eine automatisierte Python-Pipeline, die diese Schritte übernimmt.

---

## MUST-Bedingungen (aus Prüfungsunterlagen)

1. Kein GUI — alles via Command Line Interface
2. Einstiegspunkt: `python ./main.py` (main.py im Root des Projekts)
3. Help verfügbar: `python ./main.py -h`
4. OS-unabhängig: Windows, Linux, macOS, Python >= 3.10
5. Keine Sonderzeichen in Variablen- und Funktionsnamen
6. Alle nötigen credentials und config im Code oder in config-Files
7. Input- und config-Daten müssen im Projektordner vorhanden sein
8. Vollständig auf der Maschine des Dozenten ausführbar (Linux/macOS)

---

## Beurteilungs-Kriterien

| Kriterium         | Gewichtung |
|-------------------|------------|
| Lauffähigkeit     | 40%        |
| Fehleranfälligkeit| 20%        |
| Klarheit/Struktur | 20%        |
| Dokumentation     | 20%        |

---

## Abgabe-Dokumente

1. PDF-Dokument (max. 2 A4-Seiten): Problembeschreibung, Lösungsansatz, Herausforderungen & Erfahrungen
2. Python source code files (keine runtime files, keine libraries)
3. `requirements.txt` erstellt mit `pipreqs --force <project_root_path>`

---

## Pipeline-Architektur (5 Scripts)

```
main.py       Einstiegspunkt, koordiniert Ablauf, argparse     python ./main.py -h
match.py      Fotos/Audio per Zeitstempel zuordnen             Pillow (EXIF), ±10s Toleranz
transcribe.py Audiodatei transkribieren                        openai-whisper (lokal, kein API-Key)
format.py     Rohtext strukturieren                            Textformatierung, kein LLM
export.py     Ausgabe als .docx                                python-docx
```

### Aufruf-Beispiele

```bash
# Komplette Pipeline
python ./main.py --audio data/audio --fotos data/fotos --output output/

# Einzelne Schritte (optional, für Debugging)
python ./main.py match --audio data/audio --fotos data/fotos
python ./main.py transcribe --audio data/audio
python ./main.py format --transkript data/transkript.json
python ./main.py export --befunde data/befunde.json --output output/
```

---

## Tech-Stack

| Zweck              | Library              | Anmerkung                          |
|--------------------|----------------------|------------------------------------|
| EXIF-Daten         | `Pillow`             | Foto-Timestamps                    |
| M4A-Metadaten      | `mutagen` (MP4)      | ©day-Tag = eingebetteter Aufnahmezeitpunkt |
| STT                | `openai` (Whisper API) | Kein lokaler Download nötig       |
| Textformatierung   | Standard Python      | Kein LLM, regelbasiert             |
| Word-Export        | `python-docx`        |                                    |

**Sprache:** Python >= 3.10
**Umgebung:** venv

---

## Projektstruktur (Soll)

```
python-pipeline-roos/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── config.json          # API-Key + Einstellungen (openai_api_key eintragen)
├── main.py              # Einstiegspunkt — python ./main.py
├── match.py             # Modul 1: Timestamp-Matching
├── transcribe.py        # Modul 2: Speech-to-Text via OpenAI Whisper API
├── format.py            # Modul 3: Regelbasierte Textformatierung
├── export.py            # Modul 4: Word-Export
└── data/
    ├── audio/           # Testdaten Audio (MP3, WAV, M4A)
    └── fotos/           # Testdaten Fotos (JPG mit EXIF)
```

---

## Arbeitsweise

1. Kurz erklären was geändert wird, bevor grosse Dateien überschrieben werden
2. Immer zuerst: läuft es? Erst dann: ist es schön?
3. Kein Over-Engineering — kein Code "für später"
4. Kein GUI, keine tkinter-Imports, keine Webbrowser-Ausgaben
5. Antworten auf Deutsch, prägnant

---

## Konventionen

- PEP 8
- Type Hints wo sinnvoll
- Keine Sonderzeichen in Namen (kein ä, ö, ü, ß in Variablen/Funktionen)
- Docstrings auf Deutsch
- Keine API-Keys committen
