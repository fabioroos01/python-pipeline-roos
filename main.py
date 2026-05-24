"""
Audio- und Foto-Verarbeitungs-Pipeline
HSLU Python for Beginners FS26 — Fabio Roos

Verarbeitet Audio-Diktate und Fotos einer Begehung und erstellt
automatisch einen strukturierten Word-Bericht.

Aufruf:
    python ./main.py -h
    python ./main.py run --audio data/audio --fotos data/fotos
"""

import argparse
import json
import sys
from pathlib import Path

AUDIO_ENDUNGEN = ("*.m4a", "*.M4A")


def _lese_env(env_pfad: Path = Path(".env")) -> dict:
    """Liest Schluessel-Wert-Paare aus einer .env-Datei."""
    env = {}
    if not env_pfad.exists():
        return env
    for zeile in env_pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if zeile and not zeile.startswith("#") and "=" in zeile:
            schluessel, _, wert = zeile.partition("=")
            env[schluessel.strip()] = wert.strip().strip('"').strip("'")
    return env


def lade_config(config_pfad: Path = Path("config.json")) -> dict:
    """
    Liest Konfiguration aus config.json und API-Key aus .env.

    Der OPENAI_API_KEY wird aus der .env-Datei geladen (nicht aus config.json),
    damit er nicht versehentlich geteilt oder committed wird.
    """
    if not config_pfad.exists():
        print(f"Fehler: '{config_pfad}' nicht gefunden.")
        sys.exit(1)
    with open(config_pfad, encoding="utf-8") as f:
        config = json.load(f)

    env = _lese_env()
    api_key = env.get("OPENAI_API_KEY", "")
    if not api_key:
        print("Fehler: OPENAI_API_KEY nicht gefunden.")
        print("Bitte .env-Datei erstellen (Vorlage: .env.example):")
        print("  echo 'OPENAI_API_KEY=sk-...' > .env")
        sys.exit(1)

    config["openai_api_key"] = api_key
    return config


def _finde_audiodateien(ordner: Path) -> list[Path]:
    """Gibt alle unterstuetzten Audio-Dateien in einem Ordner zurueck."""
    dateien = []
    for endung in AUDIO_ENDUNGEN:
        dateien.extend(ordner.rglob(endung))
    return sorted(dateien)


def _frage(prompt: str, standard: str = "") -> str:
    """
    Fragt den Benutzer interaktiv nach einer Eingabe.

    Zeigt den Standardwert in eckigen Klammern an.
    Leere Eingabe (nur Enter) uebernimmt den Standardwert.
    """
    anzeige = f"{prompt} [{standard}]: " if standard else f"{prompt}: "
    antwort = input(anzeige).strip()
    return antwort if antwort else standard


def _frage_ordner(prompt: str, standard: str = "") -> str:
    """
    Fragt nach einem Pflicht-Ordnerpfad und wiederholt bis ein gueltiger Pfad kommt.

    Verhindert, dass die Pipeline mit einem ungültigen Pfad gestartet wird.
    """
    while True:
        pfad = _frage(prompt, standard)
        if Path(pfad).is_dir():
            return pfad
        print(f"  Fehler: Ordner '{pfad}' nicht gefunden. Bitte erneut eingeben.")


def _frage_ordner_optional(prompt: str, standard: str = "") -> str:
    """
    Fragt nach einem optionalen Ordnerpfad.

    Leere Eingabe oder ungültiger Pfad → leerer String (kein Fehler).
    Wird fuer den Foto-Ordner verwendet, da Fotos nicht zwingend benoetigt werden.
    """
    anzeige = f"{prompt} [{standard}] (Enter = ohne Fotos): "
    antwort = input(anzeige).strip()
    pfad = antwort if antwort else standard
    if not pfad or not Path(pfad).is_dir():
        if pfad:
            print(f"  Hinweis: '{pfad}' nicht gefunden — Pipeline laeuft ohne Fotos.")
        else:
            print("  Kein Foto-Ordner angegeben — Pipeline laeuft ohne Fotos.")
        return ""
    return pfad


def _interaktive_eingabe(args: argparse.Namespace) -> None:
    """
    Fragt im Terminal nach allen Feldern, die noch nicht gesetzt sind.

    Wird in cmd_run aufgerufen, damit die Pipeline auch ohne CLI-Argumente
    gestartet werden kann. Audio-Ordner ist Pflicht, Foto-Ordner optional.

    Standardpfade (relativ zum Projektordner, funktioniert auf jedem Rechner):
      Audio: data/audio
      Fotos: data/fotos
    """
    print("\n" + "=" * 55)
    print("  Audio-Foto-Pipeline  —  Begehungsprotokoll")
    print("=" * 55)
    print("Bitte Angaben zur Begehung eingeben.")
    print("(Leere Eingabe = Standardwert in eckigen Klammern)\n")

    # Audio-Ordner: Pflichtfeld, wird wiederholt bis gueltiger Pfad
    if not getattr(args, "audio", "") or not Path(args.audio).is_dir():
        args.audio = _frage_ordner("Audio-Ordner", "data/audio")

    # Foto-Ordner: optional, Pipeline laeuft auch ohne Fotos
    if not getattr(args, "fotos", ""):
        args.fotos = _frage_ordner_optional("Fotos-Ordner", "data/fotos")
    elif args.fotos and not Path(args.fotos).is_dir():
        print(f"  Hinweis: '{args.fotos}' nicht gefunden — Pipeline laeuft ohne Fotos.")
        args.fotos = ""

    # Projektangaben (optional, erscheinen auf Titelseite)
    args.baustelle = _frage(
        "Projektname / Baustelle",
        getattr(args, "baustelle", "") or "",
    )
    args.projektnummer = _frage(
        "Projektnummer",
        getattr(args, "projektnummer", "") or "",
    )
    args.aufnehmer = _frage(
        "Aufgenommen von",
        getattr(args, "aufnehmer", "") or "",
    )
    print()


# ---------------------------------------------------------------------------
# Subcommands (ein Modul nach dem anderen)
# ---------------------------------------------------------------------------

def cmd_match(args: argparse.Namespace) -> None:
    """Modul 1: Ordnet Fotos den Audio-Dateien per Zeitstempel zu."""
    from match import (
        drucke_zusammenfassung,
        lese_alle_audios,
        lese_alle_fotos,
        matche_fotos,
        speichere_mapping,
    )

    audio_ordner = Path(args.audio)
    ausgabe = Path(args.ausgabe)

    if not audio_ordner.is_dir():
        print(f"Fehler: Audio-Ordner nicht gefunden: {audio_ordner}")
        sys.exit(1)

    print(f"Lese Audio-Dateien aus: {audio_ordner}")
    audios = lese_alle_audios(audio_ordner)
    print(f"  {len(audios)} Audio-Datei(en) gefunden")

    if not audios:
        print("Fehler: Keine Audio-Dateien gefunden.")
        sys.exit(1)

    for a in audios:
        quelle = "M4A-Metadaten" if a.startzeitpunkt_zuverlaessig else "Dateisystem (Fallback)"
        print(f"  {a.pfad.name}: {a.startzeitpunkt.strftime('%Y-%m-%d %H:%M:%S')} [{quelle}]")

    # Fotos sind optional — Pipeline laeuft auch ohne
    foto_pfad = getattr(args, "fotos", "") or ""
    foto_ordner = Path(foto_pfad) if foto_pfad else None

    if foto_ordner and foto_ordner.is_dir():
        print(f"\nLese Fotos aus: {foto_ordner}")
        fotos = lese_alle_fotos(foto_ordner)
        print(f"  {len(fotos)} Foto(s) gefunden")
    else:
        print("\nKein Foto-Ordner angegeben — Matching wird ohne Fotos gespeichert.")
        fotos = []

    if fotos:
        mappings = matche_fotos(fotos, audios)
        drucke_zusammenfassung(mappings)
    else:
        mappings = []

    speichere_mapping(mappings, ausgabe)
    print(f"\nMapping gespeichert: {ausgabe}")


def cmd_transcribe(args: argparse.Namespace) -> None:
    """Modul 2: Transkribiert Audio-Dateien via OpenAI Whisper API."""
    from transcribe import transkribiere

    config = lade_config()
    api_key = config.get("openai_api_key", "")
    if not api_key or "DEIN" in api_key.upper() or len(api_key) < 10:
        print("Fehler: Kein gueltiger OpenAI API-Key in config.json.")
        print("  Bitte 'openai_api_key' in config.json eintragen.")
        sys.exit(1)

    modell = config.get("whisper_modell", "whisper-1")
    audio_ordner = Path(args.audio)
    ausgabe = Path(args.ausgabe)

    audio_dateien = _finde_audiodateien(audio_ordner)
    if not audio_dateien:
        print(f"Fehler: Keine Audio-Dateien in {audio_ordner} gefunden.")
        sys.exit(1)

    print(f"Verwende Whisper-Modell: {modell}")
    alle_transkripte = []

    for pfad in audio_dateien:
        print(f"\nTranskribiere: {pfad.name}")
        try:
            t = transkribiere(pfad, api_key=api_key, modell=modell)
            alle_transkripte.append({
                "audio_pfad": str(pfad),
                "volltext": t.volltext,
                "segmente": [
                    {"start": s.start_sekunden, "ende": s.ende_sekunden, "text": s.text}
                    for s in t.segmente
                ],
            })
            print(f"  {len(t.segmente)} Segmente, {len(t.volltext)} Zeichen")
        except Exception as e:
            print(f"  Fehler: {e}")

    ausgabe.parent.mkdir(parents=True, exist_ok=True)
    with open(ausgabe, "w", encoding="utf-8") as f:
        json.dump(alle_transkripte, f, ensure_ascii=False, indent=2)
    print(f"\nTranskripte gespeichert: {ausgabe}")


def cmd_format(args: argparse.Namespace) -> None:
    """Modul 3: Strukturiert Transkripte durch textbasierte Verarbeitung."""
    from format import formatiere

    transkript_pfad = Path(args.transkript)
    ausgabe = Path(args.ausgabe)

    if not transkript_pfad.exists():
        print(f"Fehler: Transkript-Datei nicht gefunden: {transkript_pfad}")
        sys.exit(1)

    with open(transkript_pfad, encoding="utf-8") as f:
        transkripte = json.load(f)

    print(f"Strukturiere {len(transkripte)} Transkript(e)...")
    befunde = formatiere(transkripte)
    print(f"  {len(befunde)} Befunde erstellt")

    ausgabe.parent.mkdir(parents=True, exist_ok=True)
    with open(ausgabe, "w", encoding="utf-8") as f:
        json.dump(befunde, f, ensure_ascii=False, indent=2)
    print(f"Befunde gespeichert: {ausgabe}")


def cmd_export(args: argparse.Namespace) -> None:
    """Modul 4: Erstellt einen Word-Bericht aus Befunden und Fotos."""
    from export import erstelle_bericht

    befunde_pfad = Path(args.befunde)
    ausgabe = Path(args.ausgabe)

    if not befunde_pfad.exists():
        print(f"Fehler: Befunde-Datei nicht gefunden: {befunde_pfad}")
        sys.exit(1)

    with open(befunde_pfad, encoding="utf-8") as f:
        befunde = json.load(f)

    mapping = []
    if hasattr(args, "mapping") and args.mapping and Path(args.mapping).exists():
        with open(args.mapping, encoding="utf-8") as f:
            mapping = json.load(f)

    # Datum automatisch aus Audio-Metadaten lesen (falls nicht angegeben)
    datum = getattr(args, "datum", "") or ""
    if not datum and befunde:
        audio_pfad_str = befunde[0].get("audio_pfad", "")
        if audio_pfad_str and Path(audio_pfad_str).exists():
            try:
                from match import lese_audio_info
                audio_info = lese_audio_info(Path(audio_pfad_str))
                _monate_de = [
                    "", "Januar", "Februar", "März", "April", "Mai", "Juni",
                    "Juli", "August", "September", "Oktober", "November", "Dezember",
                ]
                dt = audio_info.startzeitpunkt
                datum = f"{dt.day}. {_monate_de[dt.month]} {dt.year}"
                print(f"  Datum aus Audio-Metadaten: {datum}")
            except Exception:
                pass

    print(f"Erstelle Word-Bericht mit {len(befunde)} Befunden...")
    erstelle_bericht(
        befunde=befunde,
        mapping=mapping,
        ausgabe_pfad=ausgabe,
        titel=getattr(args, "titel", "Begehungsprotokoll"),
        datum=datum,
        baustelle=getattr(args, "baustelle", ""),
        aufnehmer=getattr(args, "aufnehmer", ""),
        projektnummer=getattr(args, "projektnummer", ""),
    )


def cmd_run(args: argparse.Namespace) -> None:
    """Fuehrt die gesamte Pipeline aus: Matching -> STT -> Formatierung -> Export."""
    # Fehlende Felder interaktiv abfragen
    _interaktive_eingabe(args)

    arbeitsordner = Path(args.ausgabe_ordner)
    arbeitsordner.mkdir(parents=True, exist_ok=True)

    mapping_pfad = arbeitsordner / "mapping.json"
    transkript_pfad = arbeitsordner / "transkript.json"
    befunde_pfad = arbeitsordner / "befunde.json"
    bericht_pfad = arbeitsordner / "bericht.docx"

    print("=" * 55)
    print("Schritt 1/4: Foto-Audio-Matching")
    print("=" * 55)
    args.ausgabe = str(mapping_pfad)
    cmd_match(args)

    print("\n" + "=" * 55)
    print("Schritt 2/4: Speech-to-Text (Whisper API)")
    print("=" * 55)
    args.ausgabe = str(transkript_pfad)
    cmd_transcribe(args)

    print("\n" + "=" * 55)
    print("Schritt 3/4: Textformatierung")
    print("=" * 55)
    args.transkript = str(transkript_pfad)
    args.ausgabe = str(befunde_pfad)
    cmd_format(args)

    print("\n" + "=" * 55)
    print("Schritt 4/4: Word-Export")
    print("=" * 55)
    args.befunde = str(befunde_pfad)
    args.mapping = str(mapping_pfad)
    args.ausgabe = str(bericht_pfad)
    cmd_export(args)

    print(f"\n{'=' * 55}")
    print("Pipeline abgeschlossen.")
    print(f"Ergebnis: {bericht_pfad}")
    print("=" * 55)


# ---------------------------------------------------------------------------
# Argument-Parser
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description=(
            "Audio- und Foto-Verarbeitungs-Pipeline\n"
            "HSLU Python for Beginners FS26 — Fabio Roos\n\n"
            "Verarbeitet Audio-Diktate und Fotos einer Begehung\n"
            "und erstellt automatisch einen strukturierten Word-Bericht."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Beispiele:\n"
            "  python ./main.py run --audio data/audio --fotos data/fotos\n"
            "  python ./main.py match --audio data/audio --fotos data/fotos\n"
            "  python ./main.py transcribe --audio data/audio\n"
            "  python ./main.py format --transkript output/transkript.json\n"
            "  python ./main.py export --befunde output/befunde.json\n"
        ),
    )

    subparsers = parser.add_subparsers(dest="befehl", required=True)

    # --- run: gesamte Pipeline ---
    p_run = subparsers.add_parser(
        "run",
        help="Gesamte Pipeline ausfuehren (empfohlen)",
        description="Fuehrt alle 4 Module der Reihe nach aus.",
    )
    p_run.add_argument("--audio", default="", help="Ordner mit Audio-Dateien (interaktiv abgefragt wenn leer)")
    p_run.add_argument("--fotos", default="", help="Ordner mit Fotos (interaktiv abgefragt wenn leer)")
    p_run.add_argument(
        "--ausgabe-ordner", default="output", dest="ausgabe_ordner",
        help="Ausgabeordner fuer alle Zwischenresultate (default: output/)",
    )
    p_run.add_argument("--baustelle", default="", help="Name der Baustelle (Titelseite)")
    p_run.add_argument("--projektnummer", default="", help="Projektnummer (Titelseite)")
    p_run.add_argument("--aufnehmer", default="", help="Name der aufnehmenden Person (Titelseite)")
    p_run.add_argument("--datum", default="", help="Datum fuer Bericht (default: aus Audio-Metadaten)")
    p_run.set_defaults(func=cmd_run)

    # --- match: nur Modul 1 ---
    p_match = subparsers.add_parser(
        "match",
        help="Modul 1: Fotos und Audio per Zeitstempel zuordnen",
    )
    p_match.add_argument("--audio", required=True, help="Ordner mit Audio-Dateien")
    p_match.add_argument("--fotos", default="", help="Ordner mit Fotos (optional)")
    p_match.add_argument(
        "--ausgabe", default="output/mapping.json",
        help="Ausgabe-JSON (default: output/mapping.json)",
    )
    p_match.set_defaults(func=cmd_match)

    # --- transcribe: nur Modul 2 ---
    p_transcribe = subparsers.add_parser(
        "transcribe",
        help="Modul 2: Audio transkribieren via OpenAI Whisper API",
    )
    p_transcribe.add_argument("--audio", required=True, help="Ordner mit Audio-Dateien")
    p_transcribe.add_argument(
        "--ausgabe", default="output/transkript.json",
        help="Ausgabe-JSON (default: output/transkript.json)",
    )
    p_transcribe.set_defaults(func=cmd_transcribe)

    # --- format: nur Modul 3 ---
    p_format = subparsers.add_parser(
        "format",
        help="Modul 3: Transkript strukturieren",
    )
    p_format.add_argument("--transkript", required=True, help="Transkript-JSON aus Modul 2")
    p_format.add_argument(
        "--ausgabe", default="output/befunde.json",
        help="Ausgabe-JSON (default: output/befunde.json)",
    )
    p_format.set_defaults(func=cmd_format)

    # --- export: nur Modul 4 ---
    p_export = subparsers.add_parser(
        "export",
        help="Modul 4: Word-Bericht erstellen",
    )
    p_export.add_argument("--befunde", required=True, help="Befunde-JSON aus Modul 3")
    p_export.add_argument("--mapping", default=None, help="Mapping-JSON aus Modul 1 (fuer Fotos)")
    p_export.add_argument(
        "--ausgabe", default="output/bericht.docx",
        help="Ausgabe .docx (default: output/bericht.docx)",
    )
    p_export.add_argument("--baustelle", default="", help="Name der Baustelle (Titelseite)")
    p_export.add_argument("--projektnummer", default="", help="Projektnummer (Titelseite)")
    p_export.add_argument("--aufnehmer", default="", help="Name der aufnehmenden Person (Titelseite)")
    p_export.add_argument("--datum", default="", help="Datum fuer Bericht (default: aus Audio-Metadaten)")
    p_export.set_defaults(func=cmd_export)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
