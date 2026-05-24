"""
Modul 1: Ordnet Fotos den richtigen M4A-Aufnahmen per Zeitstempel zu.

Ablauf:
  1. Startzeitpunkt jeder M4A-Datei aus den Metadaten lesen
     (Prioritaet: day-Tag > mvhd-Atom > Dateisystem-Fallback)
  2. EXIF-Zeitstempel aller Fotos lesen
  3. Jedes Foto der zeitlich passenden Audio-Datei zuordnen
"""

import json
import os
import re
import struct
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from mutagen.mp4 import MP4
from PIL import Image
from PIL.ExifTags import TAGS


# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

# Maximale Abweichung in Sekunden, damit ein Foto noch als "nah genug" gilt
TOLERANZ_SEKUNDEN = 10

# Typ-Alias fuer die drei Konfidenz-Stufen des Matchings
Konfidenz = Literal["exakt", "innerhalb_toleranz", "nicht_zuordenbar"]

AUDIO_ENDUNGEN = ("*.m4a", "*.M4A")
FOTO_ENDUNGEN  = ("*.jpg", "*.jpeg", "*.JPG", "*.JPEG")

# Datumsformate, die im ©day-Tag vorkommen koennen
_M4A_DATUMSFORMATE = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)

# MP4-Epoch beginnt am 1.1.1904 — Offset zur Unix-Epoch (1.1.1970) in Sekunden
_MAC_EPOCH_OFFSET = 2082844800


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
# M4A-Metadaten lesen
# ---------------------------------------------------------------------------

def _lese_m4a_zeitpunkt(pfad: Path) -> datetime | None:
    """
    Liest das Aufnahmedatum aus dem eingebetteten ©day-Tag der M4A-Datei.

    iPhone Voice Memos speichert den Aufnahmezeitpunkt direkt im Dateiinhalt.
    Dieser Wert bleibt beim Kopieren (AirDrop, USB, iCloud) unveraendert —
    im Gegensatz zu Dateisystem-Timestamps, die sich beim Kopieren aendern.

    Der Tag kann verschiedene Formate haben und optional einen Timezone-Offset
    enthalten (z.B. "2026-05-22T17:24:40+0200"). Der Offset wird entfernt,
    damit die Lokalzeit direkt mit EXIF-Zeitstempeln verglichen werden kann.

    Gibt None zurueck wenn der Tag fehlt oder nicht parsbar ist.
    """
    try:
        audio = MP4(pfad)
        if not audio.tags:
            return None

        # ©day-Tag auslesen (\xa9day = Unicode-Zeichen für ©day)
        day_tag = audio.tags.get("\xa9day")
        if not day_tag:
            return None

        day_str = (day_tag[0] if isinstance(day_tag, list) else str(day_tag)).strip()

        # Timezone-Offset entfernen (z.B. "+0200", "+02:00" oder "Z")
        # Ergebnis ist Lokalzeit, identisch mit EXIF-Zeitstempeln der Fotos
        day_str = re.sub(r"([+-]\d{2}:?\d{2}|Z)$", "", day_str).strip()

        # Verschiedene Datumsformate durchprobieren
        for fmt in _M4A_DATUMSFORMATE:
            try:
                return datetime.strptime(day_str, fmt)
            except ValueError:
                continue

        return None  # Kein Format hat gepasst
    except Exception:
        return None


def _lese_mvhd_zeitpunkt(pfad: Path) -> datetime | None:
    """
    Liest den Aufnahmezeitpunkt direkt aus dem binaeren MP4-Container (mvhd-Atom).

    Das mvhd-Atom (Movie Header) ist ein fixes Dateiformat-Element jeder MP4-Datei.
    Es enthaelt eine creation_time, die als Sekunden seit der Mac-Epoch (1.1.1904)
    gespeichert ist.

    WICHTIG: Diese creation_time entspricht dem ENDzeitpunkt der Aufnahme,
    nicht dem Start. Der Startzeitpunkt muss daher durch Abzug der Dauer
    berechnet werden (geschieht in lese_audio_info).

    Vorgehen (binaere Analyse):
      1. b"mvhd" als Marker im Bytestrom suchen
      2. Version lesen (0 = 4 Byte Zeit, 1 = 8 Byte Zeit)
      3. Rohwert von Mac-Epoch (1904) auf Unix-Epoch (1970) umrechnen

    Gibt None zurueck wenn das Atom nicht gefunden wird oder der Wert 0 ist.
    """
    try:
        with open(pfad, "rb") as f:
            data = f.read()

        # mvhd-Marker im Binaerstrom suchen
        idx = data.find(b"mvhd")
        if idx == -1:
            return None

        # Bytes nach dem Marker: [4 Byte Flags] [Version] [creation_time]
        pos = idx + 4
        version = data[pos]
        pos += 4  # 4 Bytes Flags ueberspringen

        # Version 0: creation_time als 32-Bit Integer (Big Endian)
        # Version 1: creation_time als 64-Bit Integer (Big Endian)
        if version == 0:
            creation_raw = struct.unpack(">I", data[pos:pos + 4])[0]
        else:
            creation_raw = struct.unpack(">Q", data[pos:pos + 8])[0]

        if creation_raw == 0:
            return None  # Kein gueltiger Zeitstempel gesetzt

        # Mac-Epoch (1.1.1904) auf Unix-Epoch (1.1.1970) umrechnen
        return datetime.fromtimestamp(creation_raw - _MAC_EPOCH_OFFSET)

    except Exception:
        return None


def lese_audio_info(pfad: Path) -> AudioInfo:
    """
    Liest Startzeitpunkt und Dauer einer M4A-Datei.

    Versucht den Startzeitpunkt in dieser Prioritaet zu bestimmen:
      1. ©day-Tag (direkt der Startzeitpunkt, am zuverlaessigsten)
      2. mvhd creation_time minus Dauer (ENDzeitpunkt - Dauer = Start)
      3. Dateisystem-Timestamp (unzuverlaessig, aendert sich beim Kopieren)

    Args:
        pfad: Pfad zur M4A-Datei.

    Returns:
        AudioInfo mit Startzeitpunkt, Dauer und Verlaesslichkeits-Flag.
    """
    audio = MP4(pfad)
    dauer_sekunden = float(audio.info.length)

    # Versuch 1: ©day-Tag
    zeitpunkt = _lese_m4a_zeitpunkt(pfad)
    if zeitpunkt:
        return AudioInfo(
            pfad=pfad,
            startzeitpunkt=zeitpunkt,
            dauer_sekunden=dauer_sekunden,
            startzeitpunkt_zuverlaessig=True,
        )

    # Versuch 2: mvhd creation_time (= ENDzeitpunkt → Start berechnen)
    endzeitpunkt = _lese_mvhd_zeitpunkt(pfad)
    if endzeitpunkt:
        startzeitpunkt = endzeitpunkt - timedelta(seconds=dauer_sekunden)
        return AudioInfo(
            pfad=pfad,
            startzeitpunkt=startzeitpunkt,
            dauer_sekunden=dauer_sekunden,
            startzeitpunkt_zuverlaessig=True,
        )

    # Versuch 3: Dateisystem-Timestamp (Fallback, unzuverlaessig)
    # st_birthtime = Erstellungszeit (macOS), st_mtime = letzte Aenderung (Linux)
    stat = os.stat(pfad)
    ts = getattr(stat, "st_birthtime", stat.st_mtime)
    return AudioInfo(
        pfad=pfad,
        startzeitpunkt=datetime.fromtimestamp(ts),
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
        pfad: Pfad zur JPEG-Datei.

    Returns:
        FotoInfo mit Aufnahmezeitpunkt.

    Raises:
        ValueError: Wenn keine EXIF-Daten oder kein Zeitstempel vorhanden.
    """
    with Image.open(pfad) as img:
        exif_data = img._getexif()

    if not exif_data:
        raise ValueError(f"Keine EXIF-Daten in '{pfad.name}'")

    # EXIF-Tag-IDs in lesbare Namen umwandeln (z.B. 36867 -> "DateTimeOriginal")
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
    Liest EXIF-Zeitstempel aller JPG/JPEG-Fotos in einem Ordner.

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

    print(f"\nMatching-Ergebnis ({len(mappings)} Fotos):")
    print(f"  Exakt zugeordnet:     {exakt}")
    print(f"  Innerhalb Toleranz:   {toleranz}")
    print(f"  Nicht zuordenbar:     {nicht}")

    if nicht > 0:
        print("\n  Nicht zuordenbare Fotos:")
        for m in mappings:
            if m.konfidenz == "nicht_zuordenbar":
                print(f"    - {Path(m.foto_pfad).name}  ({m.foto_zeitpunkt})")
