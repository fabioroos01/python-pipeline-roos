# Audio-Foto-Pipeline

Audio- und Foto-Verarbeitungs-Pipeline für Gebäudebegehungen.  
HSLU — Python for Beginners FS26 — Fabio Roos

---

## Überblick

Das Tool nimmt iPhone-Sprachaufnahmen (M4A) und Fotos einer Begehung entgegen und erzeugt daraus automatisch ein strukturiertes Word-Protokoll.

```
Audio-Dateien (M4A) + Fotos (JPEG/HEIC)
              ↓
[Modul 1]  Zeitstempel einlesen  →  output/mapping.json
              ↓
[Modul 2]  Speech-to-Text        →  output/transkript.json
              ↓
[Modul 3]  Textformatierung      →  output/befunde.json
              ↓
[Modul 4]  Word-Export           →  output/bericht.docx
```

---

## Voraussetzungen

- Python >= 3.10
- OpenAI API Key

---

## Setup

```bash
# Repository klonen
git clone https://github.com/fabioroos01/python-pipeline-roos.git
cd python-pipeline-roos

# Virtuelle Umgebung erstellen und aktivieren
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows

# Abhängigkeiten installieren
pip install -r requirements.txt

# API Key eintragen: config.json öffnen und openai_api_key setzen
```

Für die Abgabe kann der API-Key direkt in `config.json` unter `openai_api_key` stehen,
damit das Projekt ohne zusätzliche Einrichtung geprüft werden kann. Für die Entwicklung
kann der Key alternativ in einer `.env`-Datei als `OPENAI_API_KEY=...` abgelegt werden.
Das Programm prüft zuerst `config.json` und nutzt `.env` als Fallback.

---

## Verwendung

```bash
# Hilfe
python ./main.py -h

# Pipeline starten (interaktiv — empfohlen)
python ./main.py

# Pipeline mit direkten Pfad-Argumenten
python ./main.py --audio data/audio --fotos data/fotos
```

Die Pipeline fragt Ordner, Projektname, Projektnummer und Aufnehmer interaktiv ab.  
Mit Punkt (`.`) wird ein Schritt übersprungen (z.B. nur Fotos ohne Audio).
Die Argumente `--audio` und `--fotos` erwarten jeweils einen Ordnerpfad, keine einzelne Datei.

---

## Tests

```bash
python -m pytest tests/
```

---

## Projektstruktur

```
python-pipeline-roos/
├── main.py               # CLI-Einstiegspunkt
├── match.py              # Modul 1: Audio- und Foto-Zeitstempel lesen
├── transcribe.py         # Modul 2: Speech-to-Text (Whisper API)
├── format.py             # Modul 3: Textformatierung
├── export.py             # Modul 4: Word-Export
├── config.json           # Konfiguration (openai_api_key hier eintragen)
├── requirements.txt
├── tests/
│   └── test_pipeline.py
├── templates/
│   └── Logo_Emch_Berger.png
└── data/
    ├── audio/            # M4A-Aufnahmen (Beispieldaten enthalten)
    └── fotos/            # JPEG/HEIC-Fotos (Beispieldaten enthalten)
```

---

## Abhängigkeiten

| Bibliothek | Verwendung |
|------------|------------|
| `openai` | Whisper API (Speech-to-Text) |
| `python-docx` | Word-Dokument erstellen |
| `Pillow` | EXIF-Daten aus Fotos lesen, HEIC konvertieren |
| `pillow-heif` | HEIC/HEIF-Unterstützung (iPhone-Fotos) |
| `mutagen` | M4A-Metadaten lesen |
