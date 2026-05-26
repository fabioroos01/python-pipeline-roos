"""
Modul 1: Ordnet Fotos den richtigen M4A-Aufnahmen per Zeitstempel zu.
Ablauf:
  1. Startzeitpunkt jeder M4A-Datei aus dem Dateinamen lesen
     Erwartet Format: YYYYMMDD-HHMMSS.m4a (z.B. 20260526-000723.m4a)
     Fallback: Dateisystem-mtime (mit Warnung)
  2. EXIF-Zeitstempel aller Fotos lesen
  3. Jedes Foto der zeitlich passenden Audio-Datei zuordnen
"""

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from mutagen.mp4 import MP4
from PIL import Image
from PIL.ExifTags import TAGS

# HEIC/HEIF-Unterstuetzung aktivieren (iPhone-Standardformat seit iOS 11)
# pillow-heif registriert sich als Pillow-Plugin → danach oeffnet Image.open()
# auch .heic/.heif-Dateien inkl. EXIF-Daten
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass  # Ohne pillow-heif werden HEIC-Dateien uebersprungen


# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

# Maximale Abweichung in Sekunden, damit ein Foto noch als "nah genug" gilt
TOLERANZ_SEKUNDEN = 10

# Typ-Alias fuer die drei Konfidenz-Stufen des Matchings
Konfidenz = Literal["exakt", "innerhalb_toleranz", "nicht_zuordenbar"]

AUDIO_ENDUNGEN = ("*.m4a", "*.M4A")
FOTO_ENDUNGEN  = ("*.jpg", "*.jpeg", "*.JPG", "*.JPEG", "*.heic", "*.HEIC", "*.heif", "*.HEIF")

# ---------------------------------------------------------------------------
# Datenklassen
# ---------------------------------------------------------------------------

@dataclass
class AudioInfo:
    """Metadaten einer M4A-Audiodatei."""
    pfad: Path
    startzeitpunkt: datetime
    dauer_sekunden: float
    startzeitpunkt_zuverlaessig: bool  # False = Dateisystem-Fallback verwendet


@dataclass
class FotoInfo:
    """Metadaten eines Fotos (EXIF-Zeitstempel)."""
    pfad: Path
    aufnahmezeitpunkt: datetime


@dataclass
class FotoMapping:
    """Ergebnis der Zuordnung eines Fotos zu einer Audio-Datei."""
    foto_pfad: str
    foto_zeitpunkt: str
    audio_datei: str | None      # None wenn nicht zuordenbar
    position_sekunden: float | None  # Sekunden ab Audio-Start
    konfidenz: Konfidenz


# ---------------------------------------------------------------------------
# M4A-Zeitstempel aus Dateinamen lesen
# ---------------------------------------------------------------------------

def _lese_dateiname_zeitpunkt(pfad: Path) -> datetime | None:
    """
    Parst den Aufnahmestartzeitpunkt direkt aus dem Dateinamen.
    Erwartet Format: YYYYMMDD-HHMMSS (z.B. 20260526-000723.m4a).
    Die ersten 15 Zeichen des Dateinamens (ohne Endung) werden ausgewertet.
    Gibt None zurueck wenn das Format nicht passt.
    """
    try:
        return datetime.strptime(pfad.stem[:15], "%Y%m%d-%H%M%S")
    except ValueError:
        return None


def lese_audio_info(pfad: Path) -> AudioInfo:
    """
    Liest Startzeitpunkt und Dauer einer M4A-Datei.
    Zeitquelle: Dateiname im Format YYYYMMDD-HHMMSS.m4a.
    Fallback: Dateisystem-mtime (mit Warnung, wenn Format nicht passt).
    Args:
        pfad: Pfad zur M4A-Datei.
    Returns:
        AudioInfo mit Startzeitpunkt, Dauer und Zuverlaessigkeits-Flag.
    """
    audio = MP4(pfad)
    dauer_sekunden = float(audio.info.length)

    # Zeitstempel aus Dateinamen (YYYYMMDD-HHMMSS)
    zeitpunkt = _lese_dateiname_zeitpunkt(pfad)
    if zeitpunkt:
        return AudioInfo(
            pfad=pfad,
            startzeitpunkt=zeitpunkt,
            dauer_sekunden=dauer_sekunden,
            startzeitpunkt_zuverlaessig=True,
        )

    # Fallback: Dateisystem mtime (Warnung ausgeben)
    mtime = datetime.fromtimestamp(os.path.getmtime(pfad))
    print(
        f"  Warnung: '{pfad.name}' — Dateinamen-Format nicht erkannt "
        f"(erwartet: YYYYMMDD-HHMMSS.m4a).\n"
        "    Verwende Dateisystem-mtime als Fallback."
    )
    return AudioInfo(
        pfad=pfad,
        startzeitpunkt=mtime,
        dauer_sekunden=dauer_sekunden,
        startzeitpunkt_zuverlaessig=False,
    )


def lese_alle_audios(ordner: Path) -> list[AudioInfo]:
    """
    Liest alle M4A-Dateien in einem Ordner.
    Defekte oder nicht lesbare Dateien werden mit einer Warnung uebersprungen,
    damit die Pipeline bei einem einzelnen Problem nicht abbricht.
    """
    audios = []
    for endung in AUDIO_ENDUNGEN:
        for pfad in ordner.glob(endung):
            try:
                audios.append(lese_audio_info(pfad))
            except Exception as e:
                print(f"  Warnung: '{pfad.name}' konnte nicht gelesen werden: {e}")

    # Nach Startzeitpunkt sortieren (chronologische Reihenfolge)
    return sorted(audios, key=lambda a: a.startzeitpunkt)


# ---------------------------------------------------------------------------
# EXIF-Zeitstempel lesen
# ---------------------------------------------------------------------------

def lese_exif_zeitpunkt(pfad: Path) -> FotoInfo:
    """
    Liest den EXIF-Aufnahmezeitpunkt (DateTimeOriginal) eines Fotos.
    Args:
        pfad: Pfad zur Foto-Datei (JPEG oder HEIC).
    Returns:
        FotoInfo mit Aufnahmezeitpunkt.
    Raises:
        ValueError: Wenn keine EXIF-Daten oder kein Zeitstempel vorhanden.
    """
    with Image.open(pfad) as img:
        # getexif() funktioniert fuer JPEG und HEIC (im Gegensatz zu _getexif())
        exif_obj = img.getexif()

    if not exif_obj:
        raise ValueError(f"Keine EXIF-Daten in '{pfad.name}'")

    exif_data = dict(exif_obj)

    # EXIF-Tag-IDs in lesbare Namen umwandeln (z.B. 36867 → "DateTimeOriginal")
    tag_map = {TAGS.get(tag, tag): wert for tag, wert in exif_data.items()}

    # DateTimeOriginal bevorzugen, DateTime als Fallback
    zeitstempel_str = tag_map.get("DateTimeOriginal") or tag_map.get("DateTime")
    if not zeitstempel_str:
        raise ValueError(f"Kein Zeitstempel-Tag in EXIF von '{pfad.name}'")

    # EXIF-Format: "YYYY:MM:DD HH:MM:SS"
    zeitpunkt = datetime.strptime(zeitstempel_str, "%Y:%m:%d %H:%M:%S")
    return FotoInfo(pfad=pfad, aufnahmezeitpunkt=zeitpunkt)


def lese_alle_fotos(ordner: Path) -> list[FotoInfo]:
    """
    Liest EXIF-Zeitstempel aller Fotos (JPG, HEIC) in einem Ordner.
    Fotos ohne gueltigen EXIF-Zeitstempel werden mit Warnung uebersprungen.
    """
    fotos = []
    for endung in FOTO_ENDUNGEN:
        for pfad in ordner.glob(endung):
            try:
                fotos.append(lese_exif_zeitpunkt(pfad))
            except ValueError as e:
                print(f"  Warnung: {e} — wird uebersprungen")

    # Nach Aufnahmezeitpunkt sortieren
    return sorted(fotos, key=lambda f: f.aufnahmezeitpunkt)


# ---------------------------------------------------------------------------
# Matching-Algorithmus
# ---------------------------------------------------------------------------

def matche_fotos(fotos: list[FotoInfo], audios: list[AudioInfo]) -> list[FotoMapping]:
    """
    Ordnet jedes Foto der zeitlich passenden Audio-Datei zu.
    Algorithmus pro Foto:
      1. Liegt der Foto-Timestamp innerhalb [audio_start, audio_ende]?
         → Konfidenz "exakt", relative Position in Sekunden berechnen
      2. Ist der kleinste Abstand zu einem Audio-Fenster <= TOLERANZ_SEKUNDEN?
         → Konfidenz "innerhalb_toleranz"
      3. Sonst: Konfidenz "nicht_zuordenbar"
    Args:
        fotos:  Liste von FotoInfo-Objekten (mit EXIF-Zeitstempel).
        audios: Liste von AudioInfo-Objekten (mit Startzeitpunkt und Dauer).
    Returns:
        Liste von FotoMapping-Objekten, eines pro Foto.
    """
    mappings = []

    for foto in fotos:
        # Unix-Timestamp des Fotos fuer numerischen Vergleich
        foto_ts = foto.aufnahmezeitpunkt.timestamp()

        bestes_audio:   AudioInfo | None = None
        beste_position: float | None     = None
        beste_konfidenz: Konfidenz       = "nicht_zuordenbar"
        kleinster_abstand = float("inf")

        for audio in audios:
            audio_start = audio.startzeitpunkt.timestamp()
            audio_ende  = audio_start + audio.dauer_sekunden

            # Foto liegt innerhalb der Aufnahme → exakte Zuordnung
            if audio_start <= foto_ts <= audio_ende:
                bestes_audio    = audio
                beste_position  = foto_ts - audio_start
                beste_konfidenz = "exakt"
                break  # Beste moegliche Zuordnung gefunden

            # Abstand zum naechstgelegenen Rand des Audio-Fensters messen
            abstand = min(abs(foto_ts - audio_start), abs(foto_ts - audio_ende))
            if abstand < kleinster_abstand:
                kleinster_abstand = abstand
                if abstand <= TOLERANZ_SEKUNDEN:
                    bestes_audio    = audio
                    beste_position  = max(0.0, min(foto_ts - audio_start, audio.dauer_sekunden))
                    beste_konfidenz = "innerhalb_toleranz"

        mappings.append(FotoMapping(
            foto_pfad=str(foto.pfad),
            foto_zeitpunkt=foto.aufnahmezeitpunkt.isoformat(),
            audio_datei=str(bestes_audio.pfad) if bestes_audio else None,
            position_sekunden=round(beste_position, 2) if beste_position is not None else None,
            konfidenz=beste_konfidenz,
        ))

    return mappings


# ---------------------------------------------------------------------------
# Hilfsfunktionen fuer Ausgabe
# ---------------------------------------------------------------------------

def speichere_mapping(mappings: list[FotoMapping], ausgabe_pfad: Path) -> None:
    """Speichert das Foto-Audio-Mapping als JSON-Datei."""
    ausgabe_pfad.parent.mkdir(parents=True, exist_ok=True)
    daten = [asdict(m) for m in mappings]
    with open(ausgabe_pfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2)


def drucke_zusammenfassung(mappings: list[FotoMapping]) -> None:
    """Gibt eine lesbare Uebersicht des Matching-Ergebnisses auf der Konsole aus."""
    exakt    = sum(1 for m in mappings if m.konfidenz == "exakt")
    toleranz = sum(1 for m in mappings if m.konfidenz == "innerhalb_toleranz")
    nicht    = sum(1 for m in mappings if m.konfidenz == "nicht_zuordenbar")
    mit_audio = exakt + toleranz

    print(f"\nMatching-Ergebnis ({len(mappings)} Fotos):")
    print(f"  Mit Audiozuordnung (erscheinen in den Notizen):      {mit_audio}")
    print(f"    - Exakt (waehrend der Aufnahme):                   {exakt}")
    print(f"    - Nahe  (innerhalb {TOLERANZ_SEKUNDEN}s Toleranz):                 {toleranz}")
    print(f"  Ohne Audiozuordnung (chronologisch eingeordnet):     {nicht}")

    if nicht > 0:
        print("\n  Fotos ohne Audiozuordnung (werden chronologisch platziert):")
        for m in mappings:
            if m.konfidenz == "nicht_zuordenbar":
                print(f"    - {Path(m.foto_pfad).name}  ({m.foto_zeitpunkt})")
