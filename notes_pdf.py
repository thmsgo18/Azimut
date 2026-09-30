"""Export d'une note d'entretien en PDF (reportlab - pur Python, mêmes PDF sur macOS, Windows et Linux).

La note est écrite en Markdown (voir static/markdown.js, qui en fait le rendu à l'écran) ; ce
module en fait le rendu PDF avec la même grammaire : titres, gras, italique, barré, code, listes à
puces / numérotées / à cocher (imbriquées), citations, liens, tableaux, séparateurs. Un retour à la
ligne simple est conservé (« Entrée » = nouvelle ligne), comme à l'écran.

Le texte est échappé avant d'être mis en forme : rien de ce qui est tapé n'est interprété comme
une balise. Un lien n'est actif que s'il commence par http://, https:// ou mailto:.
"""

import io
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from pdf_commun import compatible_police_pdf, echapper_xml

ENCRE = colors.HexColor("#1c1c1e")
ENCRE_DOUCE = colors.HexColor("#6b6b73")
TRAIT = colors.HexColor("#d9d9de")
ACCENT = colors.HexColor("#3b6fd8")
FOND_CODE = colors.HexColor("#f3f3f6")

LARGEUR_UTILE = A4[0] - 4 * cm  # marges de 2 cm

STYLES = {
    "corps": ParagraphStyle("corps", fontName="Helvetica", fontSize=10.2, leading=14.4,
                            textColor=ENCRE, spaceAfter=6),
    "titre_note": ParagraphStyle("titre_note", fontName="Helvetica-Bold", fontSize=20, leading=24,
                                 textColor=ENCRE, spaceAfter=4),
    "meta": ParagraphStyle("meta", fontName="Helvetica", fontSize=9.5, leading=13, textColor=ENCRE_DOUCE),
    "code": ParagraphStyle("code", fontName="Courier", fontSize=8.6, leading=11.4, textColor=ENCRE,
                           backColor=FOND_CODE, borderPadding=(5, 6, 5, 6), spaceBefore=4, spaceAfter=10),
    "citation": ParagraphStyle("citation", fontName="Helvetica-Oblique", fontSize=10.2, leading=14.4,
                               textColor=ENCRE_DOUCE, spaceAfter=4),
    "cellule": ParagraphStyle("cellule", fontName="Helvetica", fontSize=9.2, leading=12, textColor=ENCRE),
    "cellule_entete": ParagraphStyle("cellule_entete", fontName="Helvetica-Bold", fontSize=9.2,
                                     leading=12, textColor=ENCRE),
}
TAILLES_TITRES = {1: 16, 2: 13.5, 3: 12, 4: 11, 5: 10.4, 6: 10}

SUR = re.compile(r"^(https?://|mailto:)", re.IGNORECASE)
RE_TITRE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
RE_SEPARATEUR = re.compile(r"^ {0,3}([-*_])(?:\s*\1){2,}\s*$")
RE_LISTE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
RE_TACHE = re.compile(r"^\[([ xX])\]\s+(.*)$")
RE_CITATION = re.compile(r"^\s{0,3}>\s?(.*)$")
RE_LIGNE_TABLEAU = re.compile(r"^\s*\|.*\|\s*$")
RE_SEPARATEUR_TABLEAU = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
SAUTS = re.compile(r"\r\n|\r| | |\n")


def _lignes(source):
    return SAUTS.split(str(source if source is not None else ""))


def _attribut(texte):
    return echapper_xml(texte).replace('"', "&quot;")


# --- en ligne ---------------------------------------------------------------

def en_ligne(texte):
    """Une ligne de Markdown -> texte pour Paragraph (mini-XML de reportlab)."""
    pieces = []

    def mettre_de_cote(xml):
        pieces.append(xml)
        return f"\u0000{len(pieces) - 1}\u0000"

    brut = re.sub(
        r"`([^`\n]+)`",
        lambda m: mettre_de_cote(f'<font face="Courier" size="9">{echapper_xml(m.group(1))}</font>'),
        str(texte),
    )

    def lien(m):
        libelle, url = m.group(1), m.group(2)
        if not SUR.match(url.strip()):
            return m.group(0)
        return mettre_de_cote(
            f'<a href="{_attribut(url)}" color="#3b6fd8">{en_ligne_simple(libelle)}</a>'
        )

    brut = re.sub(r"\[([^\]\n]+)\]\(([^)\s]+)\)", lien, brut)

    def adresse(m):
        url = re.sub(r"[.,;:!?]+$", "", m.group(2))
        reste = m.group(2)[len(url):]
        xml = f'<a href="{_attribut(url)}" color="#3b6fd8">{echapper_xml(url)}</a>'
        return f"{m.group(1)}{mettre_de_cote(xml)}{reste}"

    # Le texte libre est échappé APRÈS la mise de côté des liens : on découpe d'abord.
    brut = re.sub(r"(^|[\s(])(https?://[^\s<)]+)", adresse, brut)
    return _restaurer(_mise_en_forme(_echapper_hors_reserves(brut)), pieces)


def en_ligne_simple(texte):
    """Gras / italique / barré sans liens ni code (texte d'un lien)."""
    return _mise_en_forme(echapper_xml(texte))


def _echapper_hors_reserves(brut):
    """Échappe tout sauf les repères de pièces mises de côté (\\0n\\0)."""
    morceaux = re.split(r"(\u0000\d+\u0000)", brut)
    return "".join(m if m.startswith("\u0000") else echapper_xml(m) for m in morceaux)


def _mise_en_forme(brut):
    brut = re.sub(r"\*\*([^\s*](?:[^*\n]*?[^\s*])?)\*\*", r"<b>\1</b>", brut)
    brut = re.sub(r"__([^\s_](?:[^_\n]*?[^\s_])?)__", r"<b>\1</b>", brut)
    brut = re.sub(r"~~([^\s~](?:[^~\n]*?[^\s~])?)~~", r"<strike>\1</strike>", brut)
    brut = re.sub(r"(^|[^*\w])\*([^\s*](?:[^*\n]*?[^\s*])?)\*(?!\*)", r"\1<i>\2</i>", brut)
    brut = re.sub(r"(^|[^_\w])_([^\s_](?:[^_\n]*?[^\s_])?)_(?![_\w])", r"\1<i>\2</i>", brut)
    return brut


def _restaurer(brut, pieces):
    return re.sub(r"\u0000(\d+)\u0000", lambda m: pieces[int(m.group(1))], brut)


class _ParagrapheTache(Paragraph):
    """Élément de liste à cocher : la case est DESSINÉE (un carré, avec une coche si c'est fait) -
    pas de police de symboles, qui manque à certains lecteurs de PDF."""

    def __init__(self, xml, style, coche):
        try:
            super().__init__(xml, style)
        except Exception:  # noqa: BLE001 - balises mal imbriquées : le texte sans mise en forme
            super().__init__(re.sub(r"<[^>]+>", "", xml), style)
        self.coche = coche

    def draw(self):
        super().draw()
        c, taille = self.canv, self.style.fontSize
        cote = taille * 0.7
        x = self.style.bulletIndent + 1
        y = self.height - getattr(self.blPara, "ascent", taille) - 0.4
        c.saveState()
        c.setLineWidth(0.8)
        c.setStrokeColor(ACCENT if self.coche else ENCRE_DOUCE)
        if self.coche:
            c.setFillColor(ACCENT)
            c.rect(x, y, cote, cote, stroke=1, fill=1)
            c.setStrokeColor(colors.white)
            c.setLineWidth(1.3)
            trace = c.beginPath()
            trace.moveTo(x + cote * 0.2, y + cote * 0.5)
            trace.lineTo(x + cote * 0.42, y + cote * 0.24)
            trace.lineTo(x + cote * 0.82, y + cote * 0.78)
            c.drawPath(trace, stroke=1, fill=0)
        else:
            c.rect(x, y, cote, cote, stroke=1, fill=0)
        c.restoreState()


def _paragraphe(xml, style, **options):
    """Un Paragraph ; si l'imbrication des balises est invalide (ex. `**a *b** c*`), le texte
    est repris sans mise en forme plutôt que de faire échouer l'export."""
    try:
        return Paragraph(xml, style, **options)
    except Exception:  # noqa: BLE001 - reportlab lève des erreurs de plusieurs types sur du XML invalide
        return Paragraph(re.sub(r"<[^>]+>", "", xml), style, **options)  # le texte, lui, est déjà échappé


# --- blocs ------------------------------------------------------------------

def _indentation(espaces):
    return len(espaces.replace("\t", "    "))


def _cellules(ligne):
    ligne = ligne.strip()
    if ligne.startswith("|"):
        ligne = ligne[1:]
    if ligne.endswith("|"):
        ligne = ligne[:-1]
    return [c.strip() for c in ligne.split("|")]


def _style_titre(niveau):
    taille = TAILLES_TITRES[niveau]
    return ParagraphStyle(
        f"h{niveau}", parent=STYLES["corps"], fontName="Helvetica-Bold", fontSize=taille,
        leading=taille * 1.28, spaceBefore=10 if niveau <= 2 else 7, spaceAfter=4, keepWithNext=1,
    )


def _liste(elements, base):
    """Éléments {indent, ordonne, texte, tache} -> paragraphes à puces, indentés par niveau."""
    if not elements:
        return []
    minimum = min(e["indent"] for e in elements)
    sortie = []
    pile = []  # {"indent", "ordonne", "compte"}
    for element in elements:
        indent = max(element["indent"], minimum)
        while pile and pile[-1]["indent"] > indent:
            pile.pop()
        if not pile or indent > pile[-1]["indent"]:
            pile.append({"indent": indent, "ordonne": element["ordonne"], "compte": 0})
        elif pile[-1]["ordonne"] != element["ordonne"]:
            pile[-1] = {"indent": indent, "ordonne": element["ordonne"], "compte": 0}
        niveau = len(pile) - 1
        pile[-1]["compte"] += 1
        retrait = 16 + 16 * niveau
        xml = "<br/>".join(en_ligne(l) for l in element["texte"].split("\n"))
        if element["tache"] is not None:
            style = ParagraphStyle(
                "tache", parent=base, leftIndent=retrait, bulletIndent=retrait - 15, spaceAfter=2,
                textColor=ENCRE_DOUCE if element["tache"] else ENCRE,
            )
            sortie.append(_ParagrapheTache(xml, style, element["tache"]))
        else:
            style = ParagraphStyle(
                "puce", parent=base, leftIndent=retrait, bulletIndent=retrait - 13,
                bulletFontName="Helvetica", bulletFontSize=10.2, spaceAfter=2,
            )
            puce = f"{pile[-1]['compte']}." if element["ordonne"] else ("\u2022" if niveau == 0 else "-")
            sortie.append(_paragraphe(xml, style, bulletText=compatible_police_pdf(puce)))
    sortie.append(Spacer(1, 4))
    return sortie


def _tableau(entetes, lignes):
    colonnes = len(entetes)
    donnees = [[_paragraphe(en_ligne(c), STYLES["cellule_entete"]) for c in entetes]]
    for rangee in lignes:
        donnees.append([_paragraphe(en_ligne(rangee[k] if k < len(rangee) else ""), STYLES["cellule"]) for k in range(colonnes)])
    # Largeurs proportionnelles à la longueur du texte (avec un minimum) : les colonnes courtes restent étroites.
    poids = [
        max(6, min(40, max([len(entetes[k])] + [len(r[k]) for r in lignes if k < len(r)])))
        for k in range(colonnes)
    ]
    total = sum(poids)
    largeurs = [LARGEUR_UTILE * p / total for p in poids]
    tableau = Table(donnees, colWidths=largeurs, repeatRows=1)
    tableau.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, TRAIT),
        ("BACKGROUND", (0, 0), (-1, 0), FOND_CODE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return [tableau, Spacer(1, 8)]


def _code(lignes):
    xml = "<br/>".join(
        re.sub(r"^( +)", lambda m: "&nbsp;" * len(m.group(1)), echapper_xml(l).replace("\t", "    "))
        for l in lignes
    )
    return [_paragraphe(xml or "&nbsp;", STYLES["code"])]


def blocs(source, base=None):
    """Le Markdown -> liste de flowables reportlab (même grammaire que static/markdown.js).
    `base` : style du texte courant (celui d'une citation est plus discret)."""
    base = base or STYLES["corps"]
    lignes = _lignes(source)
    sortie = []
    i = 0
    while i < len(lignes):
        ligne = lignes[i]
        if ligne.strip() == "":
            i += 1
            continue

        if re.match(r"^\s*```", ligne):
            code = []
            i += 1
            while i < len(lignes) and not re.match(r"^\s*```", lignes[i]):
                code.append(lignes[i])
                i += 1
            i += 1
            sortie += _code(code)
            continue

        titre = RE_TITRE.match(ligne)
        if titre:
            niveau = len(titre.group(1))
            sortie.append(_paragraphe(en_ligne(titre.group(2)), _style_titre(niveau)))
            i += 1
            continue

        if RE_SEPARATEUR.match(ligne) and not RE_LISTE.match(ligne):
            sortie.append(HRFlowable(width="100%", thickness=0.6, color=TRAIT, spaceBefore=6, spaceAfter=8))
            i += 1
            continue

        if RE_CITATION.match(ligne):
            morceaux = []
            while i < len(lignes) and RE_CITATION.match(lignes[i]):
                morceaux.append(RE_CITATION.match(lignes[i]).group(1))
                i += 1
            interieur = blocs("\n".join(morceaux), base=STYLES["citation"]) or [Spacer(1, 1)]
            cadre = Table([[interieur]], colWidths=[LARGEUR_UTILE - 6])
            cadre.setStyle(TableStyle([
                ("LINEBEFORE", (0, 0), (0, -1), 2.2, TRAIT),
                ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]))
            sortie += [cadre, Spacer(1, 6)]
            continue

        if (
            RE_LIGNE_TABLEAU.match(ligne) and i + 1 < len(lignes)
            and RE_SEPARATEUR_TABLEAU.match(lignes[i + 1]) and "-" in lignes[i + 1]
        ):
            entetes = _cellules(ligne)
            i += 2
            corps = []
            while i < len(lignes) and RE_LIGNE_TABLEAU.match(lignes[i]):
                corps.append(_cellules(lignes[i]))
                i += 1
            sortie += _tableau(entetes, corps)
            continue

        if RE_LISTE.match(ligne):
            elements = []
            while i < len(lignes):
                brute = lignes[i]
                m = RE_LISTE.match(brute)
                if m and not RE_SEPARATEUR.match(brute):
                    tache = RE_TACHE.match(m.group(3))
                    elements.append({
                        "indent": _indentation(m.group(1)),
                        "ordonne": bool(re.search(r"\d", m.group(2))),
                        "texte": tache.group(2) if tache else m.group(3),
                        "tache": (tache.group(1).lower() == "x") if tache else None,
                    })
                    i += 1
                elif brute.strip() and re.match(r"^\s+\S", brute) and elements and not RE_TITRE.match(brute.strip()):
                    elements[-1]["texte"] += "\n" + brute.strip()
                    i += 1
                else:
                    break
            sortie += _liste(elements, base)
            continue

        paragraphe = []
        while (
            i < len(lignes) and lignes[i].strip() != "" and not re.match(r"^\s*```", lignes[i])
            and not RE_TITRE.match(lignes[i]) and not RE_LISTE.match(lignes[i])
            and not RE_CITATION.match(lignes[i]) and not RE_SEPARATEUR.match(lignes[i])
        ):
            paragraphe.append(lignes[i])
            i += 1
        sortie.append(_paragraphe("<br/>".join(en_ligne(l) for l in paragraphe), base))
    return sortie


# --- document ---------------------------------------------------------------

def _date_fr(iso):
    if iso and re.match(r"^\d{4}-\d{2}-\d{2}", str(iso)):
        return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}"
    return ""


class _CanvasNumerote(canvas.Canvas):
    """Pied de page « titre - page n / N » (le total n'est connu qu'à la fin)."""

    titre_pied = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pages = []

    def showPage(self):
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._pages)
        for etat in self._pages:
            self.__dict__.update(etat)
            self.setFont("Helvetica", 7.8)
            self.setFillColor(ENCRE_DOUCE)
            self.drawString(2 * cm, 1.1 * cm, self.titre_pied)
            self.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"{self._pageNumber} / {total}")
            super().showPage()
        super().save()


def nom_de_fichier(titre):
    """Un nom de fichier sûr (sans accents ni caractères spéciaux) pour le PDF d'une note."""
    from pieces_liees import _slugifier

    return f"{_slugifier(titre, 'note')}.pdf"


def generer_pdf(note, chemin_sortie=None):
    """Le PDF d'une note (dict de notes_entretien.recuperer_note). Écrit dans `chemin_sortie` si
    fourni, et retourne toujours le contenu (octets)."""
    titre = (note.get("titre") or "").strip() or "Note d'entretien"
    meta = [note.get("entreprise") or ""]
    if note.get("poste"):
        meta.append(note["poste"])
    date = _date_fr(note.get("date_entretien"))
    if date:
        meta.append(f"Entretien du {date}")
    elements = [
        _paragraphe(echapper_xml(titre), STYLES["titre_note"]),
        _paragraphe(echapper_xml("  ·  ".join(m for m in meta if m)), STYLES["meta"]),
        HRFlowable(width="100%", thickness=0.8, color=TRAIT, spaceBefore=8, spaceAfter=10),
    ]
    corps = blocs(note.get("contenu") or "")
    if not corps:
        corps = [_paragraphe("<i>(note vide)</i>", STYLES["meta"])]
    elements += corps

    memoire = io.BytesIO()

    class Canvas(_CanvasNumerote):
        titre_pied = compatible_police_pdf(f"{titre}  ·  Azimut")

    document = SimpleDocTemplate(
        memoire, pagesize=A4, topMargin=2.2 * cm, bottomMargin=2.2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm, title=compatible_police_pdf(titre), author="Azimut",
    )
    document.build(elements, canvasmaker=Canvas)
    octets = memoire.getvalue()
    if chemin_sortie is not None:
        with open(chemin_sortie, "wb") as fichier:
            fichier.write(octets)
    return octets
