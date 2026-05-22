"""Modul 1: Ordnet Fotos den richtigen M4A-Aufnahmen per Zeitstempel zu."""

import json
import os
import re
import struct
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from mutagen.mp4 import MP4
from PIL import Image
from PIL.ExifTags import TAGS

TOLERANZ_SEKUNDEN = 10

Konfidenz = Literal["exakt", "innerhalb_toleranz", "nicht_zuordenbar"]

AUDIO_ENDUNGEN = ("*.m4a", "*.M4A")
FOTO_ENDUNGEN = ("*.jpg", "*.jpeg", "*.JPG", "*.JPEG")

# Datumsformate die im day-Tag vorkommen koennen
_M4A_DATUMSFORMATE = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)

# MP4-Epoch beginnt am 1.1.1904 — Offset zu Unix-Epoch (1.1.1970) in Sekunden
_MAC_EPOCH_OFFSET = 2082844800


@dataclass
class AudioInfo:
    pfad: Path
    startzeitpunkt: datetime
    dauer_sekunden: float
    startzeitpunkt_zuverlaessig: bool


@dataclass
class FotoInfo:
    pfad: Path
    aufnahmezeitpunkt: datetime


@dataclass
class FotoMapping:
    foto_pfad: str
    foto_zeitpunkt: str
    audio_datei: str | None
    position_sekunden: float | None
    konfidenz: Konfidenz


def _lese_m4a_zeitpunkt(pfad: Path) -> datetime | None:
    """
    Liest das Aufnahmedatum aus dem eingebetteten M4A-Tag (Feld 'day').

    iPhone Voice Memos speichert das Aufnahmedatum direkt im File-Inhalt.
    Dieser Wert bleibt beim Kopieren (AirDrop, USB, iCloud) unveraendert.
    Gibt naive datetime (ohne Timezone) in Lokalzeit zurueck.
    """
    try:
        audio = MP4(pfad)
        if not audio.tags:
            return None
        day_tag = audio.tags.get("\xa9day")
        if not day_tag:
            return None
        day_str = (day_tag[0] if isinstance(day_tag, list) else str(day_tag)).strip()

        # Timezone-Offset entfernen falls vorhanden (z.B. "+0200" oder "Z")
        # Damit bleibt die Lokalzeit erhalten, die mit EXIF-Fotos verglichen wird
        import re
        day_str = re.sub(r"([+-]\d{2}:?\d{2}|Z)$", "", day_str).strip()

        for fmt in _M4A_DATUMSFORMATE:
            try:
                return datetime.strptime(day_str, fmt)
            except ValueError:
                continue
        return None
    except Exception:
        return None


def _lese_mvhd_zeitpunkt(pfad: Path) -> datetime | None:
    """
    Liest den Aufnahmezeitpunkt aus dem MP4-Container-Header (mvhd-Atom).

    Die creation_time im mvhd-Atom ist Teil des Dateiinhalts und bleibt
    beim Kopieren (AirDrop, USB) unveraendert — genau wie der day-Tag.
    Zeitzone: Mac-Epoch (1.1.1904 UTC), wird in Lokalzeit umgerechnet.
    """
    try:
        with open(pfad, "rb") as f:
            data = f.read()
        idx = data.find(b"mvhd")
        if idx == -1:
            return None
        pos = idx + 4
        version = data[pos]
        pos += 4
        if version == 0:
            creation_raw = struct.unpack(">I", data[pos:pos + 4])[0]
        else:
            creation_raw = struct.unpack(">Q", data[pos:pos + 8])[0]
        if creation_raw == 0:
            return None
        return datetime.fromtimestamp(creation_raw - _MAC_EPOCH_OFFSET)
    except Exception:
        return None


def lese_audio_info(pfad: Path) -> AudioInfo:
    """
    Liest Startzeitpunkt und Dauer einer M4A-Datei.

    Prioritaet fuer Startzeitpunkt (alle im Dateiinhalt eingebettet):
    1. day-Tag (iTunes/Voice Memos Metadaten-Tag) — direkt der Startzeitpunkt
    2. mvhd creation_time (MP4-Container-Header) — ist der ENDzeitpunkt,
       daher wird die Dauer abgezogen um den Start zu berechnen
    3. Dateisystem-Timestamp als letzter Fallback (unzuverlaessig)
    """
    from datetime import timedelta

    audio = MP4(pfad)
    dauer_sekunden = float(audio.info.length)

    zeitpunkt = _lese_m4a_zeitpunkt(pfad)
    if zeitpunkt:
        return AudioInfo(
            pfad=pfad,
            startzeitpunkt=zeitpunkt,
            dauer_sekunden=dauer_sekunden,
            startzeitpunkt_zuverlaessig=True,
        )

    endzeitpunkt = _lese_mvhd_zeitpunkt(pfad)
    if endzeitpunkt:
        startzeitpunkt = endzeitpunkt - timedelta(seconds=dauer_sekunden)
        return AudioInfo(
            pfad=pfad,
            startzeitpunkt=startzeitpunkt,
            dauer_sekunden=dauer_sekunden,
            startzeitpunkt_zuverlaessig=True,
        )

    stat = os.stat(pfad)
    ts = getattr(stat, "st_birthtime", stat.st_mtime)
    return AudioInfo(
        pfad=pfad,
        startzeitpunkt=datetime.fromtimestamp(ts),
        dauer_sekunden=dauer_sekunden,
        startzeitpunkt_zuverlaessig=False,
    )


def lese_alle_audios(ordner: Path) -> list[AudioInfo]:
    """Liest alle M4A-Dateien in einem Ordner."""
    audios = []
    for endung in AUDIO_ENDUNGEN:
        for pfad in ordner.glob(endung):
            audios.append(lese_audio_info(pfad))
    return sorted(audios, key=lambda a: a.startzeitpunkt)


def lese_exif_zeitpunkt(pfad: Path) -> FotoInfo:
    """
    Liest den EXIF-Aufnahmezeitpunkt (DateTimeOriginal) eines Fotos.

    Wirft ValueError wenn kein EXIF-Zeitstempel vorhanden.
    """
    with Image.open(pfad) as img:
        exif_data = img._getexif()
    if not exif_data:
        raise ValueError(f"Keine EXIF-Daten in {pfad.name}")
    tag_map = {TAGS.get(tag, tag): wert for tag, wert in exif_data.items()}
    zeitstempel_str = tag_map.get("DateTimeOriginal") or tag_map.get("DateTime")
    if not zeitstempel_str:
        raise ValueError(f"Kein Zeitstempel-Tag in EXIF von {pfad.name}")
    zeitpunkt = datetime.strptime(zeitstempel_str, "%Y:%m:%d %H:%M:%S")
    return FotoInfo(pfad=pfad, aufnahmezeitpunkt=zeitpunkt)


def lese_alle_fotos(ordner: Path) -> list[FotoInfo]:
    """Liest EXIF-Zeitstempel aller JPG/JPEG-Fotos in einem Ordner."""
    fotos = []
    for endung in FOTO_ENDUNGEN:
        for pfad in ordner.glob(endung):
            try:
                fotos.append(lese_exif_zeitpunkt(pfad))
            except ValueError as e:
                print(f"  Warnung: {e} — uebersprungen")
    return sorted(fotos, key=lambda f: f.aufnahmezeitpunkt)


def matche_fotos(fotos: list[FotoInfo], audios: list[AudioInfo]) -> list[FotoMapping]:
    """
    Ordnet jedes Foto der passenden Audio-Datei und Zeitposition zu.

    Konfidenz-Stufen:
    - exakt: Foto-Timestamp liegt innerhalb [audio_start, audio_start + dauer]
    - innerhalb_toleranz: Abstand zum naechsten Segment <= TOLERANZ_SEKUNDEN
    - nicht_zuordenbar: kein passendes Segment gefunden
    """
    mappings = []

    for foto in fotos:
        foto_ts = foto.aufnahmezeitpunkt.timestamp()
        bestes_audio: AudioInfo | None = None
        beste_position: float | None = None
        beste_konfidenz: Konfidenz = "nicht_zuordenbar"
        kleinster_abstand = float("inf")

        for audio in audios:
            audio_start = audio.startzeitpunkt.timestamp()
            audio_ende = audio_start + audio.dauer_sekunden

            if audio_start <= foto_ts <= audio_ende:
                bestes_audio = audio
                beste_position = foto_ts - audio_start
                beste_konfidenz = "exakt"
                break

            abstand = min(abs(foto_ts - audio_start), abs(foto_ts - audio_ende))
            if abstand < kleinster_abstand:
                kleinster_abstand = abstand
                if abstand <= TOLERANZ_SEKUNDEN:
                    bestes_audio = audio
                    beste_position = max(0.0, min(foto_ts - audio_start, audio.dauer_sekunden))
                    beste_konfidenz = "innerhalb_toleranz"

        mappings.append(FotoMapping(
            foto_pfad=str(foto.pfad),
            foto_zeitpunkt=foto.aufnahmezeitpunkt.isoformat(),
            audio_datei=str(bestes_audio.pfad) if bestes_audio else None,
            position_sekunden=round(beste_position, 2) if beste_position is not None else None,
            konfidenz=beste_konfidenz,
        ))

    return mappings


def speichere_mapping(mappings: list[FotoMapping], ausgabe_pfad: Path) -> None:
    """Speichert das Foto-Audio-Mapping als JSON-Datei."""
    ausgabe_pfad.parent.mkdir(parents=True, exist_ok=True)
    daten = [asdict(m) for m in mappings]
    with open(ausgabe_pfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, indent=2)


def drucke_zusammenfassung(mappings: list[FotoMapping]) -> None:
    """Gibt eine lesbare Uebersicht des Matchings aus."""
    exakt = sum(1 for m in mappings if m.konfidenz == "exakt")
    toleranz = sum(1 for m in mappings if m.konfidenz == "innerhalb_toleranz")
    nicht = sum(1 for m in mappings if m.konfidenz == "nicht_zuordenbar")

    print(f"\nMatching-Ergebnis ({len(mappings)} Fotos):")
    print(f"  Exakt zugeordnet:     {exakt}")
    print(f"  Innerhalb Toleranz:   {toleranz}")
    print(f"  Nicht zuordenbar:     {nicht}")

    if nicht > 0:
        print("\n  Nicht zuordenbare Fotos:")
        for m in mappings:
            if m.konfidenz == "nicht_zuordenbar":
                print(f"    - {Path(m.foto_pfad).name}  ({m.foto_zeitpunkt})")
