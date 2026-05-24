"""Modul 4: Erstellt einen strukturierten Word-Bericht aus Befunden und Fotos."""

from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

# Pfad zum Logo (relativ zum Projektverzeichnis)
_LOGO_PFAD = Path("Templates/Logo_Emch_Berger.png")

_FOOTER_TEXT = (
    "Emch+Berger WSB AG  |  "
    "Emmenbrücke – Cham – Kriens – Sarnen  |  "
    "ebwsb@emchberger.ch  |  www.emchberger.ch"
)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _keine_rahmen(table) -> None:
    """Entfernt alle sichtbaren Rahmen einer Tabelle."""
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
    """Formatiert Sekunden als MM:SS-String."""
    minuten = int(sekunden) // 60
    sek = int(sekunden) % 60
    return f"{minuten:02d}:{sek:02d}"


def _suche_passendes_foto(befund: dict, mapping: list[dict]) -> Path | None:
    """
    Sucht das zeitlich passende Foto fuer einen Befund im Mapping.

    Gibt das Foto zurueck, das am naechsten an der Befundposition liegt
    (max. 30 Sekunden Abstand).
    """
    audio_pfad = befund.get("audio_pfad", "")
    befund_start = befund.get("start", 0.0)
    befund_ende = befund.get("ende", 0.0)

    bestes_foto = None
    kleinster_abstand = float("inf")

    for eintrag in mapping:
        if eintrag.get("audio_datei") != audio_pfad:
            continue
        if eintrag.get("konfidenz") == "nicht_zuordenbar":
            continue

        position = eintrag.get("position_sekunden") or 0.0

        if befund_start <= position <= befund_ende:
            return Path(eintrag["foto_pfad"])

        abstand = min(abs(position - befund_start), abs(position - befund_ende))
        if abstand < kleinster_abstand:
            kleinster_abstand = abstand
            bestes_foto = Path(eintrag["foto_pfad"])

    return bestes_foto if kleinster_abstand < 30 else None


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
    Erstellt die Titelseite mit Logo, Baustelennamen, Datum und Aufnehmer.

    Layout (angelehnt an Emch+Berger WSB Vorlage):
      - Logo oben rechts
      - Label "Begehungsprotokoll"
      - Baustelle als Haupttitel (gross)
      - Trennlinie
      - Infotabelle: Projektnummer | Datum | Aufgenommen von
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

    # Infotabelle
    if datum:
        datum_text = datum
    else:
        _monate_de = [
            "", "Januar", "Februar", "März", "April", "Mai", "Juni",
            "Juli", "August", "September", "Oktober", "November", "Dezember",
        ]
        heute = datetime.today()
        datum_text = f"{heute.day}. {_monate_de[heute.month]} {heute.year}"

    # Zeilen: Projektnummer (nur wenn angegeben), Datum, Aufgenommen von
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

    # Abstand und Fusszeile Titelseite
    for _ in range(3):
        doc.add_paragraph()

    hinweis_p = doc.add_paragraph("Automatisch erstellt durch Audio-Foto-Pipeline")
    hinweis_p.runs[0].font.size = Pt(9)
    hinweis_p.runs[0].font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)

    doc.add_page_break()


# ---------------------------------------------------------------------------
# Befundseiten
# ---------------------------------------------------------------------------

def _befundseiten(
    doc: Document,
    befunde: list[dict],
    mapping: list[dict],
) -> list[tuple[int, Path]]:
    """
    Schreibt die Befundseiten als Stichpunktliste.

    Jede Gruppe (Pause > 2s) wird ein Bullet-Point.
    Fotos werden als Verweis direkt unter dem jeweiligen Stichpunkt aufgefuehrt.
    Gibt eine Liste von (Foto-Nummer, Foto-Pfad) fuer den Anhang zurueck.
    """
    foto_liste: list[tuple[int, Path]] = []
    foto_nr = 1
    aktueller_ort = None

    h = doc.add_heading("Notizen", level=1)
    h.runs[0].font.size = Pt(18)
    h.runs[0].font.bold = True
    h.runs[0].font.color.rgb = RGBColor(0, 0, 0)

    for befund in befunde:
        ort = befund.get("raum_hinweis")

        # Neue Ortsbezeichnung als Unterueberschrift
        if ort and ort != aktueller_ort:
            doc.add_paragraph()
            uh = doc.add_heading(ort, level=2)
            uh.runs[0].font.size = Pt(12)
            uh.runs[0].font.color.rgb = RGBColor(0x30, 0x30, 0x30)
            aktueller_ort = ort

        # Stichpunkt
        bullet = doc.add_paragraph(style="List Bullet")
        bullet_r = bullet.add_run(befund.get("text", ""))
        bullet_r.font.size = Pt(10)

        # Zeitstempel (klein, grau, eingerueckt)
        start = befund.get("start", 0.0)
        ende = befund.get("ende", 0.0)
        zeit_p = doc.add_paragraph(f"       [{_format_zeit(start)} – {_format_zeit(ende)}]")
        zeit_p.runs[0].font.size = Pt(8)
        zeit_p.runs[0].font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)
        zeit_p.runs[0].italic = True
        zeit_p.paragraph_format.space_before = Pt(0)
        zeit_p.paragraph_format.space_after = Pt(2)

        # Fotoverweis
        foto = _suche_passendes_foto(befund, mapping)
        if foto:
            ref_p = doc.add_paragraph(f"       → Foto {foto_nr}  ({foto.name})")
            ref_p.runs[0].font.size = Pt(9)
            ref_p.runs[0].italic = True
            ref_p.runs[0].font.color.rgb = RGBColor(0x20, 0x20, 0x90)
            ref_p.paragraph_format.space_after = Pt(6)
            foto_liste.append((foto_nr, foto))
            foto_nr += 1

    return foto_liste


# ---------------------------------------------------------------------------
# Fotoanhang
# ---------------------------------------------------------------------------

def _fotoanhang(doc: Document, fotos: list[tuple[int, Path]]) -> None:
    """Fuegt den Fotoanhang mit allen Fotos am Ende des Dokuments ein."""
    doc.add_page_break()

    h = doc.add_heading("Fotoanhang", level=1)
    h.runs[0].font.size = Pt(18)
    h.runs[0].font.bold = True
    h.runs[0].font.color.rgb = RGBColor(0, 0, 0)

    for nr, pfad in fotos:
        nr_p = doc.add_paragraph()
        nr_r = nr_p.add_run(f"Foto {nr}")
        nr_r.font.bold = True
        nr_r.font.size = Pt(10)

        if pfad.exists():
            doc.add_picture(str(pfad), width=Inches(5.5))
            bildp = doc.add_paragraph(pfad.name)
            bildp.runs[0].font.size = Pt(8)
            bildp.runs[0].italic = True
        else:
            fehler_p = doc.add_paragraph(f"[Datei nicht gefunden: {pfad.name}]")
            fehler_p.runs[0].font.size = Pt(9)
            fehler_p.runs[0].italic = True

        doc.add_paragraph()


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------

def erstelle_bericht(
    befunde: list[dict],
    mapping: list[dict],
    ausgabe_pfad: Path,
    titel: str = "Begehungsprotokoll",
    datum: str = "",
    baustelle: str = "",
    aufnehmer: str = "",
    projektnummer: str = "",
) -> None:
    """
    Erstellt einen Word-Bericht mit Befunden und Fotos.

    Reihenfolge: Titelseite → Notizseiten (Stichpunkte) → Fotoanhang.

    Args:
        befunde:       Strukturierte Befunde aus format.py.
        mapping:       Foto-Audio-Mapping aus match.py (kann leer sein).
        ausgabe_pfad:  Pfad zur Ausgabedatei (.docx).
        titel:         Wird nicht mehr direkt verwendet (baustelle ersetzt es).
        datum:         Datum als String. Leer = aus Audio-Metadaten oder heute.
        baustelle:     Name der Baustelle fuer die Titelseite.
        aufnehmer:     Name der Person, welche die Aufnahme gemacht hat.
        projektnummer: Projektnummer fuer die Titelseite.
    """
    doc = Document()

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
    foto_liste = _befundseiten(doc, befunde, mapping)

    if foto_liste:
        _fotoanhang(doc, foto_liste)

    ausgabe_pfad.parent.mkdir(parents=True, exist_ok=True)
    doc.save(ausgabe_pfad)
    print(f"Bericht gespeichert: {ausgabe_pfad}")
