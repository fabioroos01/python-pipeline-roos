"""
Modul 4: Erstellt einen strukturierten Word-Bericht aus Befunden und Fotos.
Ablauf:
  1. Titelseite mit Logo, Baustelle, Datum und Aufnehmer
  2. Notizseiten: chronologisch gemischt
     - Pro Audio-Aufnahme: Unterueberschrift + Stichpunkte
     - Fotos erscheinen direkt nach dem Abschnitt, in dem sie zeitlich liegen
  3. Fotos vor dem ersten Audio erscheinen am Seitenanfang
"""

from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

from docx import Document
from PIL import Image

# HEIC/HEIF-Unterstuetzung aktivieren (gleich wie in match.py)
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

# Pfad zum Logo (relativ zum Projektverzeichnis)
_LOGO_PFAD = Path("templates/Logo_Emch_Berger.png")

_FOOTER_TEXT = (
    "Emch+Berger WSB AG  |  "
    "Emmenbrücke – Cham – Kriens – Sarnen  |  "
    "ebwsb@emchberger.ch  |  www.emchberger.ch"
)

# Breite eines Fotos in der 2-spaltige Galerie
# A4 (21cm) - linker Rand (3cm) - rechter Rand (2cm) = 16cm Nutzbreite
# 2 × 7.5cm = 15cm + ~1cm Zellenabstand = 16cm
_FOTO_BREITE = Cm(7.5)


# ---------------------------------------------------------------------------
# Hilfsfunktionen fuer Word-XML
# ---------------------------------------------------------------------------

def _keine_rahmen(table) -> None:
    """Entfernt alle sichtbaren Rahmen einer Tabelle via XML-Manipulation."""
    for row in table.rows:
        for cell in row.cells:
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            tcBorders = OxmlElement("w:tcBorders")
            for edge in ("top", "bottom", "left", "right", "insideH", "insideV"):
                tag = OxmlElement(f"w:{edge}")
                tag.set(qn("w:val"), "none")
                tcBorders.append(tag)
            tcPr.append(tcBorders)


def _linie_unter_absatz(paragraph) -> None:
    """Fuegt eine horizontale Linie unterhalb eines Absatzes ein."""
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "auto")
    pBdr.append(bottom)
    pPr.append(pBdr)


def _linie_ueber_absatz(paragraph) -> None:
    """Fuegt eine horizontale Linie oberhalb eines Absatzes ein (fuer Footer)."""
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    top = OxmlElement("w:top")
    top.set(qn("w:val"), "single")
    top.set(qn("w:sz"), "4")
    top.set(qn("w:space"), "1")
    top.set(qn("w:color"), "AAAAAA")
    pBdr.append(top)
    pPr.append(pBdr)


def _format_zeit(sekunden: float) -> str:
    """Formatiert Sekunden als MM:SS-String. Beispiel: 90.0 → '01:30'"""
    minuten = int(sekunden) // 60
    sek = int(sekunden) % 60
    return f"{minuten:02d}:{sek:02d}"


# ---------------------------------------------------------------------------
# Fotogalerie
# ---------------------------------------------------------------------------

def _foto_fuer_word(pfad: Path) -> str | BytesIO:
    """
    Bereitet ein Foto fuer das Einfuegen ins Word-Dokument vor.
    JPEG/PNG: Pfad direkt weitergeben.
    HEIC/HEIF: als JPEG konvertieren, da Word auf Windows HEIC nicht anzeigt.
    Returns:
        Pfad-String (JPEG/PNG) oder BytesIO-Objekt (HEIC konvertiert).
    """
    if pfad.suffix.lower() in (".heic", ".heif"):
        img = Image.open(pfad).convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        return buf
    return str(pfad)


def _zeige_fotos_galerie(doc: Document, foto_pfade: list[Path]) -> None:
    """
    Fuegt Fotos als Galerie mit 2 Fotos pro Zeile ein.
    Layout: Tabelle ohne Rahmen, 2 Spalten je 7.5 cm.
    Jedes Foto wird zentriert angezeigt, darunter der Dateiname als Beschriftung.
    Bei ungerader Anzahl bleibt die letzte Zelle leer.
    Args:
        doc:        Das Word-Dokument.
        foto_pfade: Liste der Foto-Pfade in der gewuenschten Reihenfolge.
    """
    if not foto_pfade:
        return

    # Fotos paarweise gruppieren (je 2 pro Tabellenzeile)
    paare = [foto_pfade[i:i + 2] for i in range(0, len(foto_pfade), 2)]

    tbl = doc.add_table(rows=len(paare), cols=2)
    _keine_rahmen(tbl)

    for zeile_idx, paar in enumerate(paare):
        for spalte_idx, pfad in enumerate(paar):
            cell = tbl.cell(zeile_idx, spalte_idx)

            # Foto einfuegen (HEIC wird automatisch zu JPEG konvertiert)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if pfad.exists():
                p.add_run().add_picture(_foto_fuer_word(pfad), width=_FOTO_BREITE)
            else:
                r = p.add_run(f"[nicht gefunden: {pfad.name}]")
                r.font.size = Pt(8)
                r.font.italic = True

            # Dateiname als kleine Bildunterschrift
            caption = cell.add_paragraph(pfad.name)
            caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
            caption.runs[0].font.size = Pt(7)
            caption.runs[0].font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)
            caption.runs[0].italic = True

        # Leere Zelle wenn Foto-Anzahl ungerade
        if len(paar) == 1:
            tbl.cell(zeile_idx, 1).paragraphs[0].add_run("")

    doc.add_paragraph()  # Abstand nach Galerie


# ---------------------------------------------------------------------------
# Header / Footer
# ---------------------------------------------------------------------------

def _setze_header_footer(doc: Document) -> None:
    """
    Setzt Header (Logo) und Footer (Adresse) fuer alle Seiten ab Seite 2.
    Die Titelseite (Seite 1) bekommt keinen Header/Footer,
    weil different_first_page_header_footer=True gesetzt wird.
    """
    section = doc.sections[0]
    section.different_first_page_header_footer = True

    # --- Regulaerer Header (ab Seite 2) ---
    header = section.header
    hp = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    hp.clear()
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    if _LOGO_PFAD.exists():
        hp.add_run().add_picture(str(_LOGO_PFAD), height=Cm(0.8))
    else:
        r = hp.add_run("Emch+Berger WSB AG")
        r.font.size = Pt(9)
        r.font.bold = True

    _linie_unter_absatz(hp)

    # --- Regulaerer Footer (ab Seite 2) ---
    footer = section.footer
    fp = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    fp.clear()
    _linie_ueber_absatz(fp)

    r = fp.add_run(_FOOTER_TEXT)
    r.font.size = Pt(8)
    r.font.color.rgb = RGBColor(0x60, 0x60, 0x60)


# ---------------------------------------------------------------------------
# Titelseite
# ---------------------------------------------------------------------------

def _titelseite(
    doc: Document,
    baustelle: str,
    datum: str,
    aufnehmer: str,
    projektnummer: str = "",
) -> None:
    """
    Erstellt die Titelseite mit Logo, Baustellenname, Datum und Aufnehmer.
    Layout: Logo oben rechts, Label, Haupttitel, Trennlinie,
    Infotabelle (Projektnummer, Datum, Aufgenommen von).
    """
    # Logo oben rechts
    logo_p = doc.add_paragraph()
    logo_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if _LOGO_PFAD.exists():
        logo_p.add_run().add_picture(str(_LOGO_PFAD), height=Cm(2.0))
    else:
        r = logo_p.add_run("Emch+Berger WSB AG")
        r.font.size = Pt(14)
        r.font.bold = True

    # Abstand
    for _ in range(4):
        doc.add_paragraph()

    # Label
    label_p = doc.add_paragraph("Begehungsprotokoll")
    label_p.runs[0].font.size = Pt(12)
    label_p.runs[0].font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    # Haupttitel: Baustelle
    titel_text = baustelle if baustelle else "< Baustelle >"
    titel_p = doc.add_paragraph(titel_text)
    titel_p.runs[0].font.size = Pt(26)
    titel_p.runs[0].font.bold = True

    # Trennlinie
    trenn = doc.add_paragraph()
    _linie_unter_absatz(trenn)

    doc.add_paragraph()

    # Datum formatieren (Fallback: heutiges Datum auf Deutsch)
    if datum:
        datum_text = datum
    else:
        _monate_de = [
            "", "Januar", "Februar", "März", "April", "Mai", "Juni",
            "Juli", "August", "September", "Oktober", "November", "Dezember",
        ]
        heute = datetime.today()
        datum_text = f"{heute.day}. {_monate_de[heute.month]} {heute.year}"

    # Infotabelle: Projektnummer (nur wenn angegeben), Datum, Aufgenommen von
    zeilen = []
    if projektnummer:
        zeilen.append(("Projektnummer:", projektnummer))
    zeilen.append(("Datum:", datum_text))
    zeilen.append(("Aufgenommen von:", aufnehmer if aufnehmer else "–"))

    tbl = doc.add_table(rows=len(zeilen), cols=2)
    _keine_rahmen(tbl)

    for row_idx, (label, wert) in enumerate(zeilen):
        lbl = tbl.cell(row_idx, 0).paragraphs[0].add_run(label)
        lbl.font.bold = True
        lbl.font.size = Pt(10)
        tbl.cell(row_idx, 0).width = Cm(5)
        val = tbl.cell(row_idx, 1).paragraphs[0].add_run(wert)
        val.font.size = Pt(10)
        tbl.cell(row_idx, 1).width = Cm(12)

    # Hinweis am Ende der Titelseite
    for _ in range(3):
        doc.add_paragraph()

    hinweis_p = doc.add_paragraph("Automatisch erstellt durch Audio-Foto-Pipeline")
    hinweis_p.runs[0].font.size = Pt(9)
    hinweis_p.runs[0].font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)

    doc.add_page_break()


# ---------------------------------------------------------------------------
# Chronologische Notizseiten
# ---------------------------------------------------------------------------

def _zeige_audio_abschnitt(
    doc: Document,
    audio_pfad: str,
    befunde: list[dict],
    nr: int,
    gesamt: int,
) -> None:
    """
    Rendert einen Audio-Abschnitt: Unterueberschrift + Bullet-Points.
    Args:
        doc:        Das Word-Dokument.
        audio_pfad: Dateipfad der Audio-Datei (fuer die Unterueberschrift).
        befunde:    Alle Befunde dieser Audio-Datei.
        nr:         Laufnummer des Abschnitts (1-basiert).
        gesamt:     Gesamtzahl der Audio-Abschnitte.
    """
    audio_name = Path(audio_pfad).stem
    doc.add_paragraph()

    # Unterueberschrift: Aufnahme 1 / 2 / ...
    titel = f"Aufnahme {nr}: {audio_name}" if gesamt > 1 else f"Aufnahme: {audio_name}"
    uh = doc.add_heading(titel, level=2)
    uh.runs[0].font.size = Pt(12)
    uh.runs[0].font.bold = True
    uh.runs[0].font.color.rgb = RGBColor(0x30, 0x30, 0x30)

    for befund in befunde:
        # Stichpunkt mit Transkript-Text
        bullet = doc.add_paragraph(style="List Bullet")
        bullet.add_run(befund.get("text", "")).font.size = Pt(10)

        # Zeitstempel (klein, grau, eingerueckt)
        start = befund.get("start", 0.0)
        ende = befund.get("ende", 0.0)
        zeit_p = doc.add_paragraph(f"       [{_format_zeit(start)} – {_format_zeit(ende)}]")
        zeit_p.runs[0].font.size = Pt(8)
        zeit_p.runs[0].font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)
        zeit_p.runs[0].italic = True
        zeit_p.paragraph_format.space_before = Pt(0)
        zeit_p.paragraph_format.space_after = Pt(2)


def _erstelle_notizseiten(
    doc: Document,
    befunde: list[dict],
    mapping: list[dict],
) -> None:
    """
    Erstellt alle Notizseiten in chronologischer Reihenfolge.
    Algorithmus:
      1. Befunde nach Audio-Datei gruppieren
      2. Startzeitpunkte aus Dateinamen lesen (via match.lese_audio_info)
      3. Audios chronologisch sortieren
      4. Fotos in Slots einteilen: Slot i = Fotos nach dem Start von Audio i
      5. Rendern: Slot-1 | Audio 0 + Slot 0 | Audio 1 + Slot 1 | ...
    Fotos ohne Zeitstempel werden ans Ende gehaengt.
    Args:
        doc:     Das Word-Dokument.
        befunde: Strukturierte Befunde aus format.py (mit audio_pfad, start, ende).
        mapping: Foto-Audio-Mapping aus match.py als Liste von Dicts.
    """
    # 1. Befunde nach Audio-Datei gruppieren (Reihenfolge innerhalb Audio beibehalten)
    befunde_pro_audio: dict[str, list[dict]] = {}
    for b in befunde:
        ap = b.get("audio_pfad", "")
        befunde_pro_audio.setdefault(ap, []).append(b)

    # 2. Audio-Startzeiten aus den Dateinamen lesen (Format: YYYYMMDD-HHMMSS)
    audio_infos: dict[str, tuple[datetime, float]] = {}  # pfad → (start, dauer)
    for pfad_str in befunde_pro_audio:
        pfad = Path(pfad_str)
        if pfad.exists():
            try:
                from match import lese_audio_info
                info = lese_audio_info(pfad)
                audio_infos[pfad_str] = (info.startzeitpunkt, info.dauer_sekunden)
            except Exception:
                pass  # Datei nicht lesbar → Reihenfolge aus Befund-Liste

    # 3. Audios chronologisch sortieren (Fallback: Reihenfolge aus befunde_pro_audio)
    sortierte_audios = sorted(
        befunde_pro_audio.keys(),
        key=lambda ap: audio_infos.get(ap, (datetime.min, 0.0))[0],
    )
    n = len(sortierte_audios)

    # 4. Fotos chronologisch sortieren und Slots zuweisen
    #    Slot -1 = vor erstem Audio, Slot i = nach dem Start von Audio i
    alle_foto_eintraege = sorted(
        mapping,
        key=lambda m: m.get("foto_zeitpunkt", ""),
    )

    foto_slots: dict[int, list[Path]] = {i: [] for i in range(-1, n)}

    for eintrag in alle_foto_eintraege:
        try:
            foto_dt = datetime.fromisoformat(eintrag["foto_zeitpunkt"])
        except (KeyError, ValueError):
            # Kein Zeitstempel: ans Ende haengen
            foto_slots[n - 1].append(Path(eintrag["foto_pfad"]))
            continue

        foto_pfad = Path(eintrag["foto_pfad"])

        # Letzten Audio-Start suchen, der noch vor (oder gleichzeitig mit) dem Foto liegt
        slot = -1
        for i, ap in enumerate(sortierte_audios):
            if ap not in audio_infos:
                continue
            audio_start, _ = audio_infos[ap]
            if foto_dt >= audio_start:
                slot = i

        foto_slots[slot].append(foto_pfad)

    # 5. Dokument rendern
    foto_only = (n == 0)  # Kein Audio → reiner Foto-Bericht

    ueberschrift = "Fotogalerie" if foto_only else "Notizen"
    h = doc.add_heading(ueberschrift, level=1)
    h.runs[0].font.size = Pt(18)
    h.runs[0].font.bold = True
    h.runs[0].font.color.rgb = RGBColor(0, 0, 0)

    # Fotos vor dem ersten Audio (Slot -1)
    if foto_slots.get(-1):
        if not foto_only:
            # Nur Kontexthinweis anzeigen wenn es auch Audio-Abschnitte gibt
            hinweis = doc.add_paragraph("Fotos vor Beginn der Aufnahmen:")
            hinweis.runs[0].font.size = Pt(9)
            hinweis.runs[0].italic = True
            hinweis.runs[0].font.color.rgb = RGBColor(0x88, 0x88, 0x88)
        _zeige_fotos_galerie(doc, foto_slots[-1])

    # Audio-Abschnitte + zugehoerige Fotos (Slot i)
    for i, ap in enumerate(sortierte_audios):
        _zeige_audio_abschnitt(doc, ap, befunde_pro_audio[ap], i + 1, n)

        fotos_nach_audio = foto_slots.get(i, [])
        if fotos_nach_audio:
            _zeige_fotos_galerie(doc, fotos_nach_audio)


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------

def erstelle_bericht(
    befunde: list[dict],
    mapping: list[dict],
    ausgabe_pfad: Path,
    datum: str = "",
    baustelle: str = "",
    aufnehmer: str = "",
    projektnummer: str = "",
) -> None:
    """
    Erstellt einen Word-Bericht mit Befunden und Fotos.
    Reihenfolge: Titelseite, dann Notizseiten chronologisch mit eingebetteten Fotos.
    Fotos erscheinen dort, wo sie zeitlich aufgenommen wurden.
    Args:
        befunde:       Strukturierte Befunde aus format.py.
        mapping:       Foto-Audio-Mapping aus match.py (kann leer sein).
        ausgabe_pfad:  Pfad zur Ausgabedatei (.docx).
        datum:         Datum als String. Leer = aus Dateinamen oder heute.
        baustelle:     Name der Baustelle fuer die Titelseite.
        aufnehmer:     Name der Person, welche die Aufnahme gemacht hat.
        projektnummer: Projektnummer fuer die Titelseite (optional).
    """
    doc = Document()

    # Seitenraender: A4 mit 3cm links, 2cm rechts → 16cm Nutzbreite
    section = doc.sections[0]
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(3)
    section.right_margin = Cm(2)

    _setze_header_footer(doc)
    _titelseite(
        doc,
        baustelle=baustelle,
        datum=datum,
        aufnehmer=aufnehmer,
        projektnummer=projektnummer,
    )

    # Chronologische Notizseiten mit eingebetteten Fotogalerien
    _erstelle_notizseiten(doc, befunde, mapping)

    ausgabe_pfad.parent.mkdir(parents=True, exist_ok=True)
    doc.save(ausgabe_pfad)
    print(f"Bericht gespeichert: {ausgabe_pfad}")
