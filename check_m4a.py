"""
Diagnose-Script: Zeigt alle verfuegbaren Zeitstempel einer M4A-Datei.

Aufruf:
    python ./check_m4a.py pfad/zur/datei.m4a
"""

import os
import struct
import sys
from datetime import datetime
from pathlib import Path

from mutagen.mp4 import MP4

_MAC_EPOCH_OFFSET = 2082844800


def _lese_mvhd(pfad: Path) -> datetime | None:
    with open(pfad, "rb") as f:
        data = f.read()
    idx = data.find(b"mvhd")
    if idx == -1:
        return None
    pos = idx + 4
    version = data[pos]
    pos += 4
    raw = struct.unpack(">I", data[pos:pos + 4])[0] if version == 0 else struct.unpack(">Q", data[pos:pos + 8])[0]
    return datetime.fromtimestamp(raw - _MAC_EPOCH_OFFSET) if raw else None


def check(pfad: Path) -> None:
    print(f"Datei : {pfad.name}")
    print(f"Groesse: {pfad.stat().st_size / 1024:.1f} KB")
    print()

    audio = MP4(pfad)
    print(f"Dauer : {audio.info.length:.1f} Sekunden  ({audio.info.length / 60:.1f} Minuten)")
    print()

    # Quelle 1: day-Tag
    day_tag = audio.tags.get("\xa9day") if audio.tags else None
    if day_tag:
        print(f"[1] day-Tag (Metadaten):  {day_tag[0]}  => ZUVERLAESSIG")
    else:
        print("[1] day-Tag (Metadaten):  nicht vorhanden")

    # Quelle 2: mvhd creation_time
    mvhd_dt = _lese_mvhd(pfad)
    if mvhd_dt:
        print(f"[2] mvhd Container-Zeit:  {mvhd_dt}  => ZUVERLAESSIG (im Dateiinhalt)")
    else:
        print("[2] mvhd Container-Zeit:  nicht lesbar")

    # Quelle 3: Dateisystem
    stat = os.stat(pfad)
    mtime = datetime.fromtimestamp(stat.st_mtime)
    btime = datetime.fromtimestamp(getattr(stat, "st_birthtime", stat.st_mtime))
    print(f"[3] Dateisystem mtime:    {mtime}  => unzuverlaessig nach Kopieren")
    print(f"    Dateisystem birthtime: {btime}")

    print()
    if day_tag or mvhd_dt:
        quelle = "day-Tag" if day_tag else "mvhd-Container-Zeit"
        zeitpunkt = day_tag[0] if day_tag else str(mvhd_dt)
        print(f"ERGEBNIS: Matching moeglich via {quelle}: {zeitpunkt}")
    else:
        print("ERGEBNIS: Kein zuverlässiger Zeitstempel gefunden — Matching funktioniert nicht!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Aufruf: python ./check_m4a.py pfad/zur/datei.m4a")
        sys.exit(1)
    check(Path(sys.argv[1]))
