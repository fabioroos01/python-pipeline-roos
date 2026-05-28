"""
Tests fuer die Audio-Foto-Pipeline.
HSLU Python for Beginners FS26 — Fabio Roos

Ausfuehren:
    python -m pytest tests/
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Absoluter Pfad zur Beispiel-Audiodatei — funktioniert unabhaengig vom Startverzeichnis
_AUDIO_BEISPIEL = Path(__file__).parent.parent / "data" / "audio" / "20260528-151120.m4a"


from format import _bereinige_text, _gruppiere_segmente
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
# match.py
# ---------------------------------------------------------------------------


def test_dateiname_zeitpunkt_korrekt():
    """Dateiname im Format YYYYMMDD-HHMMSS wird korrekt geparst."""
    from match import _lese_dateiname_zeitpunkt
    from datetime import datetime
    pfad = Path("20260526-000723.m4a")
    ergebnis = _lese_dateiname_zeitpunkt(pfad)
    assert ergebnis == datetime(2026, 5, 26, 0, 7, 23)


def test_dateiname_zeitpunkt_ungueltig():
    """Falsches Dateinamen-Format gibt None zurueck."""
    from match import _lese_dateiname_zeitpunkt
    assert _lese_dateiname_zeitpunkt(Path("aufnahme.m4a")) is None
    assert _lese_dateiname_zeitpunkt(Path("test_audio.m4a")) is None


def test_fallback_mtime_bei_falschem_dateinamen():
    """Datei mit falschem Dateinamen → Fallback auf mtime, zuverlaessig=False."""
    from match import lese_audio_info
    quelle = _AUDIO_BEISPIEL
    with tempfile.NamedTemporaryFile(suffix="_aufnahme.m4a", delete=False) as tmp:
        tmp_pfad = Path(tmp.name)
    try:
        shutil.copy(quelle, tmp_pfad)
        info = lese_audio_info(tmp_pfad)
        assert info.startzeitpunkt_zuverlaessig is False
        assert info.startzeitpunkt is not None
    finally:
        tmp_pfad.unlink()


# ---------------------------------------------------------------------------
# transcribe.py — Fehlerbehandlung
# ---------------------------------------------------------------------------

def _mock_http_response(status_code: int) -> MagicMock:
    """Erstellt eine minimale Mock-HTTP-Response fuer OpenAI-Fehlerklassen."""
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = {}
    r.headers = {}
    return r


def test_falscher_api_key_gibt_fehlermeldung():
    """Falscher API-Key → RuntimeError mit verstaendlicher Meldung."""
    from openai import AuthenticationError
    from transcribe import transkribiere
    with patch("openai.OpenAI") as mock:
        mock.return_value.audio.transcriptions.create.side_effect = AuthenticationError(
            message="invalid", response=_mock_http_response(401), body={}
        )
        try:
            transkribiere(_AUDIO_BEISPIEL, api_key="sk-falsch")
            assert False, "RuntimeError erwartet"
        except RuntimeError as e:
            assert "API-Key" in str(e)


def test_rate_limit_gibt_fehlermeldung():
    """Rate-Limit-Fehler → RuntimeError mit Hinweis zum Warten."""
    from openai import RateLimitError
    from transcribe import transkribiere
    with patch("openai.OpenAI") as mock:
        mock.return_value.audio.transcriptions.create.side_effect = RateLimitError(
            message="rate limit", response=_mock_http_response(429), body={}
        )
        try:
            transkribiere(_AUDIO_BEISPIEL, api_key="sk-test")
            assert False, "RuntimeError erwartet"
        except RuntimeError as e:
            assert "Limit" in str(e)


def test_keine_verbindung_gibt_fehlermeldung():
    """Kein Internet → RuntimeError mit Hinweis zur Internetverbindung."""
    from openai import APIConnectionError
    from transcribe import transkribiere
    with patch("openai.OpenAI") as mock:
        mock.return_value.audio.transcriptions.create.side_effect = APIConnectionError(
            request=MagicMock()
        )
        try:
            transkribiere(_AUDIO_BEISPIEL, api_key="sk-test")
            assert False, "RuntimeError erwartet"
        except RuntimeError as e:
            assert "Verbindung" in str(e)


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
