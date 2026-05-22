"""Modul 2: Transkribiert M4A-Aufnahmen via OpenAI Whisper API mit Segment-Timestamps."""

from dataclasses import dataclass
from pathlib import Path

# OpenAI erlaubt max. 25 MB pro Datei
MAX_DATEIGROESSE_BYTES = 25 * 1024 * 1024


@dataclass
class Textsegment:
    start_sekunden: float
    ende_sekunden: float
    text: str


@dataclass
class Transkript:
    audio_pfad: str
    segmente: list[Textsegment]

    @property
    def volltext(self) -> str:
        """Gibt alle Segmente als zusammenhaengenden Text zurueck."""
        return " ".join(s.text for s in self.segmente)


def transkribiere(audio_pfad: Path, api_key: str, modell: str = "whisper-1") -> Transkript:
    """
    Transkribiert eine M4A-Datei via OpenAI Whisper API.

    Erfordert einen gueltigen OpenAI API-Key (aus config.json).
    Maximale Dateigroesse: 25 MB (OpenAI-Limit).

    Args:
        audio_pfad: Pfad zur M4A-Datei.
        api_key: OpenAI API-Key.
        modell: Whisper-Modell (default: 'whisper-1').

    Returns:
        Transkript mit Segmenten und Zeitstempeln.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai nicht installiert. Bitte: pip install openai")

    if audio_pfad.stat().st_size > MAX_DATEIGROESSE_BYTES:
        raise RuntimeError(
            f"'{audio_pfad.name}' ueberschreitet das 25 MB Limit der OpenAI API.\n"
            "  Bitte die Aufnahme kuerzen oder in mehrere Teile aufteilen."
        )

    client = OpenAI(api_key=api_key)
    with open(audio_pfad, "rb") as f:
        result = client.audio.transcriptions.create(
            model=modell,
            file=f,
            language="de",
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    segmente = [
        Textsegment(
            start_sekunden=float(s.start),
            ende_sekunden=float(s.end),
            text=s.text.strip(),
        )
        for s in result.segments
        if s.text.strip()
    ]

    return Transkript(audio_pfad=str(audio_pfad), segmente=segmente)
