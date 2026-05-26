"""
Modul 2: Transkribiert M4A-Aufnahmen via OpenAI Whisper API.
Die API liefert neben dem Volltext auch Segment-Timestamps (verbose_json),
die spaeter fuer die zeitliche Zuordnung von Fotos benoetigt werden.
Maximale Dateigroesse: 25 MB (OpenAI-Limit).
"""

from dataclasses import dataclass
from pathlib import Path

# OpenAI erlaubt max. 25 MB pro Anfrage
MAX_DATEIGROESSE_BYTES = 25 * 1024 * 1024


# ---------------------------------------------------------------------------
# Datenklassen
# ---------------------------------------------------------------------------

@dataclass
class Textsegment:
    """Ein einzelnes Whisper-Segment mit Start-/Endzeit und Text."""
    start_sekunden: float
    ende_sekunden: float
    text: str


@dataclass
class Transkript:
    """Ergebnis einer Transkription: Pfad der Audiodatei und alle Segmente."""
    audio_pfad: str
    segmente: list[Textsegment]

    @property
    def volltext(self) -> str:
        """Gibt alle Segmente als zusammenhaengenden Text zurueck."""
        return " ".join(s.text for s in self.segmente)


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------

def transkribiere(audio_pfad: Path, api_key: str, modell: str = "whisper-1") -> Transkript:
    """
    Transkribiert eine M4A-Datei via OpenAI Whisper API.
    Sendet die Audiodatei an die API und gibt ein Transkript-Objekt
    mit allen Segmenten und deren Zeitstempeln zurueck.
    Args:
        audio_pfad: Pfad zur M4A-Datei (muss existieren).
        api_key:    Gueltiger OpenAI API-Key (aus .env).
        modell:     Whisper-Modell (default: 'whisper-1').
    Returns:
        Transkript-Objekt mit Segmenten und Zeitstempeln.
    Raises:
        RuntimeError: Bei API-Fehlern (falscher Key, kein Internet, Limit).
        ImportError:  Wenn das openai-Paket nicht installiert ist.
    """
    # Importpruefung: openai muss installiert sein
    try:
        from openai import OpenAI, AuthenticationError, RateLimitError, APIConnectionError
    except ImportError:
        raise ImportError(
            "Das 'openai'-Paket ist nicht installiert.\n"
            "  Bitte ausfuehren: pip install openai"
        )

    # Dateigroesse pruefen bevor die API angefragt wird
    dateigroesse = audio_pfad.stat().st_size
    if dateigroesse > MAX_DATEIGROESSE_BYTES:
        raise RuntimeError(
            f"'{audio_pfad.name}' ist zu gross "
            f"({dateigroesse / 1024 / 1024:.1f} MB, max. 25 MB).\n"
            "  Bitte die Aufnahme kuerzen oder in mehrere Teile aufteilen."
        )

    # OpenAI-Client initialisieren und Transkription anfordern
    client = OpenAI(api_key=api_key)
    try:
        with open(audio_pfad, "rb") as f:
            result = client.audio.transcriptions.create(
                model=modell,
                file=f,
                language="de",            # Deutsch fuer bessere Erkennungsqualitaet
                response_format="verbose_json",  # Liefert Segment-Timestamps
                timestamp_granularities=["segment"],
            )

    except AuthenticationError:
        raise RuntimeError(
            "Ungültiger OpenAI API-Key.\n"
            "  Bitte den OPENAI_API_KEY in der .env-Datei pruefen.\n"
            "  Vorlage: .env.example"
        )
    except RateLimitError:
        raise RuntimeError(
            "OpenAI API-Limit erreicht.\n"
            "  Bitte einige Minuten warten und erneut versuchen."
        )
    except APIConnectionError:
        raise RuntimeError(
            "Keine Verbindung zur OpenAI API.\n"
            "  Bitte Internetverbindung pruefen."
        )
    except Exception as e:
        raise RuntimeError(f"Unerwarteter API-Fehler: {e}")

    # Ergebnis in eigene Datenstruktur umwandeln; leere Segmente ueberspringen
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
