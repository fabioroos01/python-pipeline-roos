"""Modul 3: Strukturiert Transkripte durch textbasierte Verarbeitung (kein LLM)."""

import re


# Bekannte Raumbezeichnungen fuer automatische Erkennung
RAUMKEYWORDS = [
    "wohnzimmer", "schlafzimmer", "kinderzimmer", "esszimmer",
    "kueche", "kueche", "bad", "badezimmer", "wc", "toilette",
    "keller", "kellerraum", "estrich", "dachgeschoss", "dachboden",
    "korridor", "gang", "flur", "eingang", "treppenhaus", "treppe",
    "garage", "balkon", "terrasse", "veranda",
    "fassade", "aussenbereich", "vorplatz", "garten",
    "buero", "arbeitszimmer", "hobbyraum", "waschkueche",
]

# Muster fuer Fuellwoerter (werden entfernt)
FUELLWORT_MUSTER = [
    r"\b(aeh+|aehm+|hm+|mhm+)\b",
]


def _bereinige_text(text: str) -> str:
    """Entfernt Fuellwoerter und normalisiert Leerzeichen."""
    for muster in FUELLWORT_MUSTER:
        text = re.sub(muster, "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _erkenne_raum(text: str) -> str | None:
    """
    Erkennt Raumbezeichnungen im Text.

    Gibt den erkannten Raum als String zurueck, oder None wenn keiner gefunden.
    """
    text_lower = text.lower()
    for raum in RAUMKEYWORDS:
        if raum in text_lower:
            idx = text_lower.find(raum)
            # Raum mit Kontext extrahieren (max. 30 Zeichen um das Keyword)
            anfang = max(0, idx - 5)
            ende = min(len(text), idx + len(raum) + 15)
            return text[anfang:ende].strip().capitalize()
    return None


def _gruppiere_segmente(segmente: list[dict], pause_sekunden: float = 2.0) -> list[dict]:
    """
    Gruppiert aufeinanderfolgende Segmente zu Absaetzen.

    Eine neue Gruppe beginnt, wenn die Pause zwischen zwei Segmenten
    groesser als pause_sekunden ist.
    """
    if not segmente:
        return []

    gruppen = []
    aktuelle_gruppe = {
        "start": segmente[0]["start"],
        "ende": segmente[0]["ende"],
        "text": segmente[0]["text"],
    }

    for seg in segmente[1:]:
        pause = seg["start"] - aktuelle_gruppe["ende"]
        if pause > pause_sekunden:
            gruppen.append(aktuelle_gruppe)
            aktuelle_gruppe = {
                "start": seg["start"],
                "ende": seg["ende"],
                "text": seg["text"],
            }
        else:
            aktuelle_gruppe["ende"] = seg["ende"]
            aktuelle_gruppe["text"] += " " + seg["text"]

    gruppen.append(aktuelle_gruppe)
    return gruppen


def formatiere(transkripte: list[dict]) -> list[dict]:
    """
    Strukturiert Transkript-Segmente in lesbare Befunde.

    Gruppiert Segmente nach Zeitpausen und bereinigt den Text.
    Erkennt automatisch Raumbezeichnungen.

    Args:
        transkripte: Liste von Transkript-Dicts (Ausgabe von Modul 2).
                     Jeder Dict hat: audio_pfad, volltext, segmente.

    Returns:
        Liste von Befund-Dicts mit audio_pfad, start, ende, text, raum_hinweis.
    """
    alle_befunde = []

    for transkript in transkripte:
        audio_pfad = transkript.get("audio_pfad", "")
        segmente = transkript.get("segmente", [])

        if not segmente:
            volltext = transkript.get("volltext", "").strip()
            if volltext:
                alle_befunde.append({
                    "audio_pfad": audio_pfad,
                    "start": 0.0,
                    "ende": 0.0,
                    "text": _bereinige_text(volltext),
                    "raum_hinweis": _erkenne_raum(volltext),
                })
            continue

        absaetze = _gruppiere_segmente(segmente, pause_sekunden=2.0)

        for absatz in absaetze:
            text = _bereinige_text(absatz["text"])
            if not text:
                continue
            alle_befunde.append({
                "audio_pfad": audio_pfad,
                "start": absatz["start"],
                "ende": absatz["ende"],
                "text": text,
                "raum_hinweis": _erkenne_raum(text),
            })

    return alle_befunde
