"""
Modul 3: Strukturiert Transkripte durch regelbasierte Textverarbeitung.
Kein LLM — die Formatierung erfolgt rein durch Textanalyse:
  1. Fuellwoerter entfernen (äh, hm, ...)
  2. Segmente nach Sprachpausen gruppieren (>2s = neuer Bullet-Point)
"""

import re


# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

# Regex-Muster fuer Fuellwoerter die entfernt werden sollen.
# Whisper transkribiert echte Umlaute (äh, ähm), daher beide Schreibweisen.
FUELLWORT_MUSTER = [
    r"\b(aeh+|aehm+|hm+|mhm+|äh+|ähm+|uh+|uhm+)\b",
]


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _bereinige_text(text: str) -> str:
    """
    Entfernt Fuellwoerter und normalisiert mehrfache Leerzeichen.
    Beispiel: "Das ist äh ein Test" -> "Das ist ein Test"
    """
    for muster in FUELLWORT_MUSTER:
        text = re.sub(muster, "", text, flags=re.IGNORECASE)
    # Mehrfache Leerzeichen (entstehen durch Fuellwort-Entfernung) normalisieren
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _gruppiere_segmente(segmente: list[dict], pause_sekunden: float = 2.0) -> list[dict]:
    """
    Gruppiert aufeinanderfolgende Whisper-Segmente zu Absaetzen.
    Whisper liefert kurze Segmente (meist 5-15s). Diese Funktion fasst
    zusammenhaengende Segmente zusammen, sofern die Pause dazwischen
    kleiner als pause_sekunden ist.
    Beispiel bei pause_sekunden=2.0:
      [0-5s] [6-10s] [15-20s]  ->  Gruppe 1: [0-10s], Gruppe 2: [15-20s]
      (Pause 6->10 = 1s < 2s, Pause 10->15 = 5s > 2s)
    Args:
        segmente:        Liste von Segment-Dicts mit start, ende, text.
        pause_sekunden:  Schwellenwert fuer Sprachpause in Sekunden.
    Returns:
        Liste von gruppierten Segmenten (start, ende, text zusammengefuehrt).
    """
    if not segmente:
        return []

    gruppen = []

    # Erste Gruppe mit dem ersten Segment initialisieren
    aktuelle_gruppe = {
        "start": segmente[0]["start"],
        "ende":  segmente[0]["ende"],
        "text":  segmente[0]["text"],
    }

    for seg in segmente[1:]:
        # Pause zwischen Ende der aktuellen Gruppe und Start des naechsten Segments
        pause = seg["start"] - aktuelle_gruppe["ende"]

        if pause > pause_sekunden:
            # Pause zu gross: aktuelle Gruppe abschliessen, neue beginnen
            gruppen.append(aktuelle_gruppe)
            aktuelle_gruppe = {
                "start": seg["start"],
                "ende":  seg["ende"],
                "text":  seg["text"],
            }
        else:
            # Segment zur aktuellen Gruppe hinzufuegen
            aktuelle_gruppe["ende"]  = seg["ende"]
            aktuelle_gruppe["text"] += " " + seg["text"]

    # Letzte offene Gruppe noch hinzufuegen
    gruppen.append(aktuelle_gruppe)
    return gruppen


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------

def formatiere(transkripte: list[dict]) -> list[dict]:
    """
    Verarbeitet Whisper-Transkripte in strukturierte Notizen.
    Ablauf fuer jede Audio-Datei:
      1. Segmente nach Sprachpausen gruppieren (>2s = neuer Bullet-Point)
      2. Fuellwoerter aus dem Text entfernen
    Args:
        transkripte: Liste von Transkript-Dicts aus Modul 2.
                     Jeder Dict enthaelt: audio_pfad, volltext, segmente.
    Returns:
        Liste von Notiz-Dicts mit: audio_pfad, text.
        Leere Texte werden uebersprungen.
    """
    alle_notizen = []

    for transkript in transkripte:
        audio_pfad = transkript.get("audio_pfad", "")
        segmente   = transkript.get("segmente", [])

        # Sonderfall: Transkript ohne Segment-Timestamps (nur Volltext)
        if not segmente:
            volltext = transkript.get("volltext", "").strip()
            if volltext:
                alle_notizen.append({
                    "audio_pfad": audio_pfad,
                    "text":       _bereinige_text(volltext),
                })
            continue

        # Segmente zu Absaetzen zusammenfassen
        absaetze = _gruppiere_segmente(segmente, pause_sekunden=2.0)

        for absatz in absaetze:
            text = _bereinige_text(absatz["text"])
            if not text:
                # Leere Absaetze (nur Fuellwoerter) ueberspringen
                continue
            alle_notizen.append({
                "audio_pfad": audio_pfad,
                "text":       text,
            })

    return alle_notizen
