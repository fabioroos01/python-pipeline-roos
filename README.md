# Audio-Foto-Pipeline

Audio- und Foto-Verarbeitungs-Pipeline für Gebäudebegehungen.  
HSLU — Python for Beginners FS26 — Fabio Roos

---

## Überblick

Das Tool nimmt iPhone-Sprachaufnahmen (M4A) und Fotos einer Begehung entgegen und erzeugt daraus automatisch ein strukturiertes Word-Protokoll.

```
Audio-Dateien (M4A) + Fotos (JPEG)
              ↓
[Modul 1]  Timestamp-Matching    →  output/mapping.json
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

# Abhängigkeiten installieren
pip install -r requirements.txt

# API Key konfigurieren
cp .env.example .env
# .env öffnen und OPENAI_API_KEY eintragen
```

---

## Verwendung

```bash
# Hilfe
python ./main.py -h

# Gesamte Pipeline (empfohlen)
python ./main.py run --audio data/audio --fotos data/fotos

# Einzelne Module
python ./main.py match      --audio data/audio --fotos data/fotos
python ./main.py transcribe --audio data/audio
python ./main.py format     --transkript output/transkript.json
python ./main.py export     --befunde output/befunde.json --mapping output/mapping.json
```

---

## Projektstruktur

```
python-pipeline-roos/
├── main.py           # CLI-Einstiegspunkt
├── match.py          # Modul 1: Foto-Audio-Matching
├── transcribe.py     # Modul 2: Speech-to-Text (Whisper API)
├── format.py         # Modul 3: Textformatierung
├── export.py         # Modul 4: Word-Export
├── check_m4a.py      # Hilfstool: M4A-Metadaten prüfen
├── config.json       # Konfiguration (kein API Key)
├── .env.example      # Vorlage für .env
├── requirements.txt
└── data/
    ├── audio/        # M4A-Aufnahmen hier ablegen
    └── fotos/        # JPEG-Fotos hier ablegen
```

---

## Abhängigkeiten

| Bibliothek | Verwendung |
|------------|------------|
| `openai` | Whisper API (Speech-to-Text) |
| `python-docx` | Word-Dokument erstellen |
| `Pillow` | EXIF-Daten aus Fotos lesen |
| `mutagen` | M4A-Metadaten lesen |
