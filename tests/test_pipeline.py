"""
Tests fuer die Audio-Foto-Pipeline.
HSLU Python for Beginners FS26 — Fabio Roos

Ausfuehren:
    pytest tests/
"""

import tempfile
from pathlib import Path

from format import _bereinige_text, _gruppiere_segmente
from export import _format_zeit
from main import _lese_env


# ---------------------------------------------------------------------------
# format.py
# ---------------------------------------------------------------------------

def test_fuellwort_wird_entfernt():
    """Prueft, ob Fuellwoerter wie 'hm' aus dem Text entfernt werden."""
    assert _bereinige_text("Das ist hm ein Test") == "Das ist ein Test"


def test_umlaut_fuellwort_wird_entfernt():
    """Whisper schreibt 'äh' mit Umlaut — auch das muss entfernt werden."""
    assert _bereinige_text("Das ist äh richtig") == "Das ist richtig"


def test_text_ohne_fuellwoerter_bleibt_unveraendert():
    text = "Der Boden ist aus Holz."
    assert _bereinige_text(text) == text


def test_segmente_mit_kleiner_pause_werden_zusammengefasst():
    """Pause von 1s < Schwellenwert 2s → eine Gruppe."""
    segmente = [
        {"start": 0.0, "ende": 5.0, "text": "Erster Satz"},
        {"start": 6.0, "ende": 10.0, "text": "Zweiter Satz"},
    ]
    gruppen = _gruppiere_segmente(segmente, pause_sekunden=2.0)
    assert len(gruppen) == 1


def test_segmente_mit_grosser_pause_werden_getrennt():
    """Pause von 5s > Schwellenwert 2s → zwei separate Gruppen."""
    segmente = [
        {"start": 0.0,  "ende": 5.0,  "text": "Erster Satz"},
        {"start": 10.0, "ende": 15.0, "text": "Zweiter Satz"},
    ]
    gruppen = _gruppiere_segmente(segmente, pause_sekunden=2.0)
    assert len(gruppen) == 2


# ---------------------------------------------------------------------------
# export.py
# ---------------------------------------------------------------------------

def test_zeitformat_minuten_sekunden():
    """90 Sekunden sollen als '01:30' formatiert werden."""
    assert _format_zeit(90.0) == "01:30"


def test_zeitformat_null():
    assert _format_zeit(0.0) == "00:00"


# ---------------------------------------------------------------------------
# main.py
# ---------------------------------------------------------------------------

def test_env_datei_wird_korrekt_gelesen():
    """Prueft den manuellen .env-Parser: Key und Wert muessen stimmen."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("# Kommentar wird ignoriert\n")
        f.write("OPENAI_API_KEY=sk-testkey123\n")
        tmp = Path(f.name)

    env = _lese_env(tmp)
    tmp.unlink()

    assert env.get("OPENAI_API_KEY") == "sk-testkey123"
    assert len(env) == 1  # Kommentar darf nicht als Eintrag erscheinen
