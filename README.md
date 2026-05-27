# Audio-Foto-Pipeline

Audio- und Foto-Verarbeitungs-Pipeline für Gebäudebegehungen.  
HSLU — Python for Beginners FS26 — Fabio Roos

---

## Überblick

Das Tool nimmt iPhone-Sprachaufnahmen (M4A) und Fotos einer Begehung entgegen und erzeugt daraus automatisch ein strukturiertes Word-Protokoll.

```
Audio-Dateien (M4A) + Fotos (JPEG/HEIC)
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

# API Key eintragen: config.json öffnen und openai_api_key setzen
```

---

## Verwendung

```bash
# Hilfe
python ./main.py -h

# Pipeline starten (interaktiv — empfohlen)
python ./main.py run

# Pipeline mit direkten Pfad-Argumenten
python ./main.py run --audio data/audio --fotos data/fotos
```

Die Pipeline fragt Ordner, Projektname, Projektnummer und Aufnehmer interaktiv ab.  
Mit Punkt (`.`) wird ein Schritt übersprungen (z.B. nur Fotos ohne Audio).

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
├── match.py              # Modul 1: Foto-Zeitstempel lesen
├── transcribe.py         # Modul 2: Speech-to-Text (Whisper API)
├── format.py             # Modul 3: Textformatierung
├── export.py             # Modul 4: Word-Export
├── config.json           # Konfiguration (openai_api_key hier eintragen)
├── requirements.txt
├── tests/
│   └── test_pipeline.py
├── templates/
│   ├── Logo_Emch_Berger.png
│   └── Vorlage_EBWSB.docx
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
