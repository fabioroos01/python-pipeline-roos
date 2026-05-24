"""
Tests fuer die Audio-Foto-Pipeline.
HSLU Python for Beginners FS26 — Fabio Roos

Getestet werden die wichtigsten Kernfunktionen ohne API-Aufrufe:
  - format.py:    Textbereinigung, Segmentgruppierung, Ortskennung
  - match.py:     Matching-Algorithmus mit simulierten Zeitstempeln
  - export.py:    Zeitformatierung
  - main.py:      .env-Parser

Ausfuehren:
    pip install pytest
    pytest tests/
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# format.py — Textverarbeitung
# ---------------------------------------------------------------------------

from format import _bereinige_text, _erkenne_ort, _gruppiere_segmente, formatiere


class TestBereinigungText:
    """Prueft das Entfernen von Fuellwoertern und Normalisierung."""

    def test_entfernt_hm(self):
        assert _bereinige_text("Das ist hm ein Test") == "Das ist ein Test"

    def test_entfernt_aeh(self):
        assert _bereinige_text("Das ist aeh richtig") == "Das ist richtig"

    def test_entfernt_umlaut_aeh(self):
        # Whisper transkribiert echtes "äh" mit Umlaut
        assert _bereinige_text("Das ist äh richtig") == "Das ist richtig"

    def test_normalisiert_leerzeichen(self):
        # Nach Entfernung von Fuellwoertern koennen Doppelleerzeichen entstehen
        result = _bereinige_text("viel    leerzeichen")
        assert "  " not in result

    def test_leerer_text_bleibt_leer(self):
        assert _bereinige_text("") == ""

    def test_text_ohne_fuellwoerter_unveraendert(self):
        text = "Der Boden ist aus Holz."
        assert _bereinige_text(text) == text


class TestOrtskennung:
    """Prueft die automatische Erkennung von Ortsbezeichnungen."""

    def test_findet_kueche(self):
        raum = _erkenne_ort("Ich befinde mich jetzt in der Kueche")
        assert raum is not None
        assert "kueche" in raum.lower() or "Kueche" in raum

    def test_findet_keller(self):
        raum = _erkenne_ort("Im Keller sehe ich eine Abplatzung")
        assert raum is not None

    def test_kein_raum_erkannt(self):
        assert _erkenne_ort("Das Wetter ist heute sehr schoen") is None

    def test_gibt_none_bei_leerem_text(self):
        assert _erkenne_ort("") is None


class TestSegmentgruppierung:
    """Prueft die Zusammenfassung von Whisper-Segmenten nach Pausen."""

    def test_eine_gruppe_bei_kleiner_pause(self):
        # Pause von 1s < Schwellenwert 2s → eine Gruppe
        segmente = [
            {"start": 0.0,  "ende": 5.0,  "text": "Erster Satz"},
            {"start": 6.0,  "ende": 10.0, "text": "Zweiter Satz"},
        ]
        gruppen = _gruppiere_segmente(segmente, pause_sekunden=2.0)
        assert len(gruppen) == 1
        assert "Erster Satz" in gruppen[0]["text"]
        assert "Zweiter Satz" in gruppen[0]["text"]

    def test_zwei_gruppen_bei_grosser_pause(self):
        # Pause von 5s > Schwellenwert 2s → zwei Gruppen
        segmente = [
            {"start": 0.0,  "ende": 5.0,  "text": "Erster Satz"},
            {"start": 10.0, "ende": 15.0, "text": "Zweiter Satz"},
        ]
        gruppen = _gruppiere_segmente(segmente, pause_sekunden=2.0)
        assert len(gruppen) == 2

    def test_zeitgrenzen_werden_korrekt_zusammengefuehrt(self):
        segmente = [
            {"start": 0.0, "ende": 5.0,  "text": "A"},
            {"start": 6.0, "ende": 10.0, "text": "B"},
        ]
        gruppen = _gruppiere_segmente(segmente, pause_sekunden=2.0)
        assert gruppen[0]["start"] == 0.0
        assert gruppen[0]["ende"]  == 10.0

    def test_leere_liste_gibt_leere_liste(self):
        assert _gruppiere_segmente([]) == []

    def test_einzelnes_segment(self):
        segmente = [{"start": 5.0, "ende": 10.0, "text": "Einzel"}]
        gruppen  = _gruppiere_segmente(segmente)
        assert len(gruppen) == 1


class TestFormatiere:
    """Prueft die komplette formatiere()-Funktion end-to-end."""

    def test_erstellt_notizen_aus_transkript(self):
        transkripte = [{
            "audio_pfad": "test.m4a",
            "volltext": "Erster Satz. Zweiter Satz.",
            "segmente": [
                {"start": 0.0,  "ende": 5.0,  "text": "Erster Satz."},
                {"start": 10.0, "ende": 15.0, "text": "Zweiter Satz."},
            ],
        }]
        notizen = formatiere(transkripte)
        assert len(notizen) == 2
        assert notizen[0]["audio_pfad"] == "test.m4a"

    def test_leeres_transkript_gibt_leere_liste(self):
        assert formatiere([]) == []

    def test_transkript_ohne_segmente_nutzt_volltext(self):
        transkripte = [{
            "audio_pfad": "test.m4a",
            "volltext": "Nur Volltext vorhanden.",
            "segmente": [],
        }]
        notizen = formatiere(transkripte)
        assert len(notizen) == 1
        assert "Nur Volltext vorhanden" in notizen[0]["text"]


# ---------------------------------------------------------------------------
# match.py — Matching-Algorithmus
# ---------------------------------------------------------------------------

from match import AudioInfo, FotoInfo, matche_fotos


class TestMatcheFotos:
    """Prueft die zeitliche Zuordnung von Fotos zu Audio-Dateien."""

    def _audio(self, start: datetime, dauer: float) -> AudioInfo:
        """Hilfsfunktion: AudioInfo-Objekt erstellen."""
        return AudioInfo(
            pfad=Path("test.m4a"),
            startzeitpunkt=start,
            dauer_sekunden=dauer,
            startzeitpunkt_zuverlaessig=True,
        )

    def _foto(self, zeitpunkt: datetime) -> FotoInfo:
        """Hilfsfunktion: FotoInfo-Objekt erstellen."""
        return FotoInfo(pfad=Path("foto.jpg"), aufnahmezeitpunkt=zeitpunkt)

    def test_exakte_zuordnung(self):
        # Foto liegt innerhalb des Audio-Fensters
        audio = self._audio(datetime(2026, 5, 22, 17, 0, 0), dauer=120.0)
        foto  = self._foto(datetime(2026, 5, 22, 17, 1, 0))  # 60s nach Start
        mappings = matche_fotos([foto], [audio])
        assert mappings[0].konfidenz == "exakt"
        assert abs(mappings[0].position_sekunden - 60.0) < 1.0

    def test_innerhalb_toleranz(self):
        # Foto liegt 5s nach Ende der Aufnahme (innerhalb TOLERANZ_SEKUNDEN=10)
        audio = self._audio(datetime(2026, 5, 22, 17, 0, 0), dauer=60.0)
        foto  = self._foto(datetime(2026, 5, 22, 17, 1, 5))  # 5s nach Ende
        mappings = matche_fotos([foto], [audio])
        assert mappings[0].konfidenz == "innerhalb_toleranz"

    def test_nicht_zuordenbar(self):
        # Foto liegt 1 Stunde nach der Aufnahme
        audio = self._audio(datetime(2026, 5, 22, 17, 0, 0), dauer=60.0)
        foto  = self._foto(datetime(2026, 5, 22, 18, 0, 0))  # 1h danach
        mappings = matche_fotos([foto], [audio])
        assert mappings[0].konfidenz == "nicht_zuordenbar"
        assert mappings[0].audio_datei is None

    def test_mehrere_fotos(self):
        # Zwei Fotos, beide im selben Audio-Fenster
        audio  = self._audio(datetime(2026, 5, 22, 17, 0, 0), dauer=300.0)
        fotos  = [
            self._foto(datetime(2026, 5, 22, 17, 1, 0)),
            self._foto(datetime(2026, 5, 22, 17, 2, 0)),
        ]
        mappings = matche_fotos(fotos, [audio])
        assert len(mappings) == 2
        assert all(m.konfidenz == "exakt" for m in mappings)

    def test_leere_listen(self):
        assert matche_fotos([], []) == []


# ---------------------------------------------------------------------------
# export.py — Hilfsfunktionen
# ---------------------------------------------------------------------------

from export import _format_zeit


class TestFormatZeit:
    """Prueft die Zeitformatierung fuer Zeitstempel im Bericht."""

    def test_null_sekunden(self):
        assert _format_zeit(0.0) == "00:00"

    def test_volle_minute(self):
        assert _format_zeit(60.0) == "01:00"

    def test_neunzig_sekunden(self):
        assert _format_zeit(90.0) == "01:30"

    def test_grosse_zahl(self):
        assert _format_zeit(3661.0) == "61:01"  # Mehr als eine Stunde


# ---------------------------------------------------------------------------
# main.py — .env-Parser
# ---------------------------------------------------------------------------

from main import _lese_env


class TestLeseEnv:
    """Prueft den manuellen .env-Parser ohne externe Abhaengigkeiten."""

    def test_liest_einfachen_key(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("OPENAI_API_KEY=sk-testkey123\n")
            tmp = Path(f.name)
        env = _lese_env(tmp)
        tmp.unlink()
        assert env.get("OPENAI_API_KEY") == "sk-testkey123"

    def test_ignoriert_kommentarzeilen(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("# Das ist ein Kommentar\nOPENAI_API_KEY=sk-test\n")
            tmp = Path(f.name)
        env = _lese_env(tmp)
        tmp.unlink()
        assert "# Das ist ein Kommentar" not in env

    def test_entfernt_anfuehrungszeichen(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write('OPENAI_API_KEY="sk-mitAnfuehrung"\n')
            tmp = Path(f.name)
        env = _lese_env(tmp)
        tmp.unlink()
        assert env.get("OPENAI_API_KEY") == "sk-mitAnfuehrung"

    def test_fehlende_datei_gibt_leeres_dict(self):
        env = _lese_env(Path("existiert_nicht.env"))
        assert env == {}

    def test_ignoriert_leere_zeilen(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("\n\nOPENAI_API_KEY=sk-test\n\n")
            tmp = Path(f.name)
        env = _lese_env(tmp)
        tmp.unlink()
        assert len(env) == 1
