"""Modul 4: Erstellt einen strukturierten Word-Bericht aus Befunden und Fotos."""

from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


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


def _titelseite(doc: Document, titel: str, datum: str) -> None:
    """Erstellt die Titelseite des Berichts."""
    doc.add_paragraph()
    doc.add_paragraph()

    tp = doc.add_paragraph(titel)
    tp.runs[0].font.size = Pt(28)
    tp.runs[0].font.bold = True

    trenn = doc.add_paragraph()
    _linie_unter_absatz(trenn)

    doc.add_paragraph()

    datum_text = datum if datum else datetime.today().strftime("%d. %B %Y")
    dp = doc.add_paragraph(datum_text)
    dp.runs[0].font.size = Pt(12)

    doc.add_paragraph()

    info_p = doc.add_paragraph("Automatisch erstellt durch Audio-Foto-Pipeline")
    info_p.runs[0].font.size = Pt(10)
    info_p.runs[0].font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    doc.add_page_break()


def _befundseiten(doc: Document, befunde: list[dict], mapping: list[dict]) -> list[tuple[int, Path]]:
    """
    Schreibt die Befundseiten mit Zeitstempeln und Fotoverweisen.

    Gibt eine Liste von (Foto-Nummer, Foto-Pfad) zurueck fuer den Anhang.
    """
    foto_liste: list[tuple[int, Path]] = []
    foto_nr = 1
    aktueller_raum = None

    h = doc.add_heading("Befunde", level=1)
    h.runs[0].font.size = Pt(20)
    h.runs[0].font.bold = True
    h.runs[0].font.color.rgb = RGBColor(0, 0, 0)

    for befund in befunde:
        raum = befund.get("raum_hinweis")

        if raum and raum != aktueller_raum:
            doc.add_paragraph()
            trenn = doc.add_paragraph()
            _linie_unter_absatz(trenn)
            rh = doc.add_heading(raum, level=2)
            rh.runs[0].font.size = Pt(13)
            rh.runs[0].font.color.rgb = RGBColor(0x30, 0x30, 0x30)
            aktueller_raum = raum

        start = befund.get("start", 0.0)
        ende = befund.get("ende", 0.0)
        zeitstempel = f"[{_format_zeit(start)} – {_format_zeit(ende)}]"

        # Zweispaltiger Eintrag: Zeitstempel | Befundtext
        tbl = doc.add_table(rows=1, cols=2)
        _keine_rahmen(tbl)
        tbl.columns[0].width = Cm(3)
        tbl.columns[1].width = Cm(14)

        ts_p = tbl.cell(0, 0).paragraphs[0]
        ts_r = ts_p.add_run(zeitstempel)
        ts_r.font.size = Pt(9)
        ts_r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)

        text_p = tbl.cell(0, 1).paragraphs[0]
        text_r = text_p.add_run(befund.get("text", ""))
        text_r.font.size = Pt(10)

        foto = _suche_passendes_foto(befund, mapping)
        if foto:
            ref_p = doc.add_paragraph()
            ref_r = ref_p.add_run(f"-> Foto {foto_nr}  ({foto.name})")
            ref_r.font.size = Pt(9)
            ref_r.italic = True
            foto_liste.append((foto_nr, foto))
            foto_nr += 1

        doc.add_paragraph()

    return foto_liste


def _fotoanhang(doc: Document, fotos: list[tuple[int, Path]]) -> None:
    """Fuegt den Fotoanhang mit allen Fotos am Ende des Dokuments ein."""
    doc.add_page_break()

    h = doc.add_heading("Fotoanhang", level=1)
    h.runs[0].font.size = Pt(20)
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


def erstelle_bericht(
    befunde: list[dict],
    mapping: list[dict],
    ausgabe_pfad: Path,
    titel: str = "Begehungsprotokoll",
    datum: str = "",
) -> None:
    """
    Erstellt einen Word-Bericht mit Befunden und Fotos.

    Reihenfolge: Titelseite -> Befundseiten -> Fotoanhang.

    Args:
        befunde: Strukturierte Befunde aus format.py.
        mapping: Foto-Audio-Mapping aus match.py (kann leer sein).
        ausgabe_pfad: Pfad zur Ausgabedatei (.docx).
        titel: Titel des Berichts (erscheint auf der Titelseite).
        datum: Datum als String. Leer = heutiges Datum.
    """
    doc = Document()

    section = doc.sections[0]
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(3)
    section.right_margin = Cm(2)

    _titelseite(doc, titel, datum)
    foto_liste = _befundseiten(doc, befunde, mapping)

    if foto_liste:
        _fotoanhang(doc, foto_liste)

    ausgabe_pfad.parent.mkdir(parents=True, exist_ok=True)
    doc.save(ausgabe_pfad)
    print(f"Bericht gespeichert: {ausgabe_pfad}")
