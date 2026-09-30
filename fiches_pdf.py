"""Rendu PDF d'une fiche de préparation d'entretien (reportlab - pur Python,
mêmes PDF sur macOS, Windows et Linux, aucune dépendance système).

Les données d'entrée sont un dictionnaire de ce format (toutes les clés sont
du texte déjà prêt à afficher ; les champs `html` n'acceptent que <p>, <b>, <i>,
<ul>, <li>, <br> - le reste est ignoré) :

    {
      "meta": {"company": "Atelier Boréal",                # obligatoire
               "subtitle", "candidate_line", "interview_date", "location",
               "mode", "website", "footer_name", "footer_context"},   # optionnels
      "company_overview": {                              # optionnel
          "stats": [{"big": "~200", "label": "Collaborateurs"}],
          "card_left":  {"title", "html", "tags": ["..."]},
          "card_right": {"title", "html"},
          "source_note": "Sources : ..."},
      "postes": [{"title",                               # obligatoire, 1 à N
                  "code_label", "subdomaine", "lead", "stack",
                  "missions": ["..."], "link", "color_key": "c1".."c8"}],
      "postes_heading", "questions_heading",             # optionnels
      "question_blocks": [{"theme": "...",
                           "questions": [{"text": "...", "why": "..."}]}],
      "footer_tip": "..."
    }

Les cartes sont empilées (jamais côte à côte) et découpées ligne par ligne :
une carte longue passe simplement sur la page suivante, sans jamais perdre de
contenu.
"""

import re
from html.parser import HTMLParser

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from exceptions import ValeurNonAutorisee
from pdf_commun import compatible_police_pdf, echapper_xml

PALETTE = {
    "c1": "#C0392B", "c2": "#1B3A6B", "c3": "#0E6E5D", "c4": "#7B4FA6",
    "c5": "#B8860B", "c6": "#2E86AB", "c7": "#A23E48", "c8": "#4C6E4C",
}
ORDRE_PALETTE = list(PALETTE)
MARINE, VERT, ENCRE, GRIS, FILET = "#1B3A6B", "#0E6E5D", "#23303F", "#6B7785", "#DDE3EA"
LARGEUR_UTILE = A4[0] - 30 * mm

_S = {
    "corps": ParagraphStyle("corps", fontName="Helvetica", fontSize=9.3, leading=12.6,
                            textColor=colors.HexColor(ENCRE)),
    "puce": ParagraphStyle("puce", fontName="Helvetica", fontSize=9.3, leading=12.6,
                           leftIndent=10, bulletIndent=1, textColor=colors.HexColor(ENCRE)),
    "petit": ParagraphStyle("petit", fontName="Helvetica-Oblique", fontSize=8, leading=10.5,
                            textColor=colors.HexColor(GRIS)),
    "section": ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=13, leading=16,
                              textColor=colors.HexColor(MARINE), spaceBefore=10, spaceAfter=6),
    "carte_titre": ParagraphStyle("carte_titre", fontName="Helvetica-Bold", fontSize=11, leading=14),
    "etiquette": ParagraphStyle("etiquette", fontName="Helvetica-Bold", fontSize=7.5, leading=9.5),
    "entete_marque": ParagraphStyle("entete_marque", fontName="Helvetica-Bold", fontSize=7.5,
                                    leading=10, textColor=colors.HexColor("#9FD8C6")),
    "entete_nom": ParagraphStyle("entete_nom", fontName="Helvetica-Bold", fontSize=22, leading=26,
                                 textColor=colors.white),
    "entete_sous": ParagraphStyle("entete_sous", fontName="Helvetica", fontSize=9.5, leading=12.5,
                                  textColor=colors.HexColor("#D7E3F0")),
    "entete_meta": ParagraphStyle("entete_meta", fontName="Helvetica", fontSize=9, leading=12.5,
                                  textColor=colors.HexColor("#D7E3F0"), alignment=TA_RIGHT),
    "stat_chiffre": ParagraphStyle("stat_chiffre", fontName="Helvetica-Bold", fontSize=17, leading=20,
                                   textColor=colors.HexColor(MARINE), alignment=TA_LEFT),
    "stat_libelle": ParagraphStyle("stat_libelle", fontName="Helvetica", fontSize=8, leading=10,
                                   textColor=colors.HexColor(GRIS)),
    "question": ParagraphStyle("question", fontName="Helvetica", fontSize=9.4, leading=12.8,
                               leftIndent=12, bulletIndent=0, textColor=colors.HexColor(ENCRE)),
    "pourquoi": ParagraphStyle("pourquoi", fontName="Helvetica-Oblique", fontSize=8.4, leading=11,
                               leftIndent=12, textColor=colors.HexColor(GRIS)),
}


# ------------------------------------------------------------ texte / html --

class _ExtracteurHtml(HTMLParser):
    """Convertit le mini-HTML d'un champ `html` en blocs (« p » ou « li », texte
    déjà échappé pour reportlab, avec <b>/<i> toujours équilibrés)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocs = []
        self._morceaux = []
        self._ouverts = []       # balises b/i actuellement ouvertes
        self._debut = []         # balises ouvertes au début du bloc en cours
        self._dans_li = False

    def _vider(self, genre):
        texte = "".join(self._morceaux).strip()
        if texte.replace("<br/>", "").strip():
            ouvrantes = "".join(f"<{b}>" for b in self._debut)
            fermantes = "".join(f"</{b}>" for b in reversed(self._ouverts))
            self.blocs.append((genre, ouvrantes + texte + fermantes))
        self._morceaux = []
        self._debut = list(self._ouverts)

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self._morceaux.append("<br/>")
        elif tag in ("p", "div", "ul", "ol"):
            self._vider("li" if self._dans_li else "p")
        elif tag == "li":
            self._vider("p")
            self._dans_li = True
        elif tag in ("b", "strong", "i", "em"):
            balise = "b" if tag in ("b", "strong") else "i"
            self._morceaux.append(f"<{balise}>")
            self._ouverts.append(balise)

    def handle_endtag(self, tag):
        if tag in ("b", "strong", "i", "em"):
            balise = "b" if tag in ("b", "strong") else "i"
            if balise in self._ouverts:
                self._ouverts.reverse()
                self._ouverts.remove(balise)  # retire la balise ouverte la plus récente
                self._ouverts.reverse()
                self._morceaux.append(f"</{balise}>")
        elif tag == "li":
            self._vider("li")
            self._dans_li = False
        elif tag in ("p", "div", "ul", "ol"):
            self._vider("p")

    def handle_data(self, data):
        self._morceaux.append(echapper_xml(data))

    def fin(self):
        self._vider("li" if self._dans_li else "p")
        return self.blocs


def blocs_depuis_html(html):
    """Liste de (« p » | « li », texte au format reportlab) - jamais d'exception
    sur un HTML mal formé, le texte est simplement récupéré au mieux."""
    html = str(html or "")
    if "<" not in html:  # texte simple : les lignes vides séparent les paragraphes
        return [("p", echapper_xml(p).replace("\n", " ").strip())
                for p in re.split(r"\n\s*\n", html) if p.strip()]
    extracteur = _ExtracteurHtml()
    extracteur.feed(html)
    extracteur.close()
    return extracteur.fin()


def texte_brut_depuis_html(html):
    """Le même contenu, en texte brut (pour l'indexation et la recherche)."""
    lignes = []
    for genre, texte in blocs_depuis_html(html):
        propre = re.sub(r"<[^>]+>", "", texte.replace("<br/>", " "))
        propre = propre.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
        lignes.append(("- " if genre == "li" else "") + propre)
    return "\n".join(lignes)


def _flowables_html(html, style_p=None, style_li=None):
    elements = []
    for genre, texte in blocs_depuis_html(html):
        if genre == "li":
            elements.append(Paragraph(texte, style_li or _S["puce"], bulletText="•"))
        else:
            elements.append(Paragraph(texte, style_p or _S["corps"]))
    return elements


def _t(texte):
    """Texte simple d'un champ de données, prêt pour un Paragraph."""
    return echapper_xml(str(texte or "").strip())


def _couleur(cle, indice, hex_force=None):
    if hex_force and re.fullmatch(r"#[0-9A-Fa-f]{6}", str(hex_force)):
        return colors.HexColor(hex_force)
    cle = cle if cle in PALETTE else ORDRE_PALETTE[indice % len(ORDRE_PALETTE)]
    return colors.HexColor(PALETTE[cle])


# ------------------------------------------------------------------ blocs --

def _carte(lignes, couleur_barre=None, fond="#FFFFFF"):
    """Carte = tableau à une colonne, une ligne par élément : découpable d'une
    page à l'autre sans jamais rien perdre."""
    tableau = Table([[ligne] for ligne in lignes], colWidths=[LARGEUR_UTILE], splitByRow=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fond)),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(FILET)),
        ("LEFTPADDING", (0, 0), (-1, -1), 11), ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, 0), 8), ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
    ]
    if couleur_barre is not None:
        style += [("LINEBEFORE", (0, 0), (0, -1), 3.2, couleur_barre)]
    tableau.setStyle(TableStyle(style))
    return tableau


def _entete(meta):
    gauche = [Paragraph("FICHE DE PRÉPARATION D'ENTRETIEN", _S["entete_marque"]),
              Paragraph(_t(meta["company"]), _S["entete_nom"])]
    if meta.get("subtitle"):
        gauche.append(Paragraph(_t(meta["subtitle"]), _S["entete_sous"]))
    if meta.get("candidate_line"):
        gauche.append(Paragraph(_t(meta["candidate_line"]), _S["entete_sous"]))
    droite = [Paragraph(_t(meta[c]), _S["entete_meta"])
              for c in ("interview_date", "location", "mode", "website") if meta.get(c)]
    tableau = Table([[gauche, droite or ""]], colWidths=[LARGEUR_UTILE * 0.66, LARGEUR_UTILE * 0.34])
    tableau.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(MARINE)),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ("LINEBELOW", (0, 0), (-1, -1), 3, colors.HexColor(VERT)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 16), ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 14), ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    return tableau


def _tuiles(stats):
    stats = [s for s in stats if isinstance(s, dict) and s.get("big")][:6]
    if not stats:
        return None
    cellules = [[Paragraph(_t(s["big"]), _S["stat_chiffre"]),
                 Paragraph(_t(s.get("label")), _S["stat_libelle"])] for s in stats]
    tableau = Table([cellules], colWidths=[LARGEUR_UTILE / len(stats)] * len(stats))
    tableau.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F6F9")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(FILET)),
        ("LINEAFTER", (0, 0), (-2, -1), 0.6, colors.HexColor(FILET)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return tableau


def _titre_carte(titre, couleur):
    style = ParagraphStyle("t", parent=_S["carte_titre"], textColor=couleur)
    return Paragraph(_t(titre), style)


def _section_entreprise(apercu):
    elements = [Paragraph("Présentation de l'entreprise", _S["section"])]
    tuiles = _tuiles(apercu.get("stats") or [])
    if tuiles is not None:
        elements += [tuiles, Spacer(1, 7)]
    for cle, couleur in (("card_left", MARINE), ("card_right", VERT)):
        carte = apercu.get(cle)
        if not isinstance(carte, dict) or not (carte.get("html") or carte.get("title")):
            continue
        lignes = []
        if carte.get("title"):
            lignes.append(_titre_carte(carte["title"], colors.HexColor(couleur)))
        lignes += _flowables_html(carte.get("html"))
        etiquettes = [str(e) for e in (carte.get("tags") or []) if str(e).strip()]
        if etiquettes:
            lignes.append(Paragraph(" · ".join(_t(e) for e in etiquettes), _S["petit"]))
        elements += [_carte(lignes), Spacer(1, 7)]
    if apercu.get("source_note"):
        elements.append(Paragraph(_t(apercu["source_note"]), _S["petit"]))
    return elements


def _carte_poste(poste, indice):
    couleur = _couleur(poste.get("color_key"), indice, poste.get("color_hex"))
    lignes = []
    etiquette = " · ".join(x for x in (poste.get("code_label"), poste.get("subdomaine")) if x)
    if etiquette:
        lignes.append(Paragraph(_t(etiquette).upper(),
                                ParagraphStyle("e", parent=_S["etiquette"], textColor=couleur)))
    lignes.append(_titre_carte(poste.get("title") or "Poste", couleur))
    if poste.get("lead"):
        lignes.append(Paragraph(_t(poste["lead"]), _S["corps"]))
    if poste.get("stack"):
        lignes.append(Paragraph(f"<b>Stack / contexte :</b> {_t(poste['stack'])}", _S["corps"]))
    for mission in poste.get("missions") or []:
        if str(mission).strip():
            lignes.append(Paragraph(_t(mission), _S["puce"], bulletText="•"))
    if poste.get("link"):
        lien = str(poste["link"]).strip()
        lignes.append(Paragraph(
            f'<font color="{MARINE}">Offre en ligne : <a href="{echapper_xml(lien)}">{echapper_xml(lien)}</a></font>',
            _S["petit"],
        ))
    return _carte(lignes, couleur_barre=couleur)


def _section_questions(blocs, titre):
    elements = [Paragraph(_t(titre), _S["section"])]
    for indice, bloc in enumerate(blocs):
        couleur = _couleur(None, indice + 1)
        entete = Paragraph(
            _t(bloc.get("theme") or "Questions"),
            ParagraphStyle("th", parent=_S["carte_titre"], fontSize=10, textColor=couleur),
        )
        lignes = []
        for question in bloc.get("questions") or []:
            if not isinstance(question, dict) or not str(question.get("text") or "").strip():
                continue
            lignes.append(Paragraph(_t(question["text"]), _S["question"], bulletText="›"))
            if question.get("why"):
                lignes.append(Paragraph(_t(question["why"]), _S["pourquoi"]))
        if lignes:
            elements.append(KeepTogether([entete, Spacer(1, 2), lignes[0]]))
            elements += lignes[1:]
            elements.append(Spacer(1, 6))
    return elements


class _CanvasNumerote(canvas.Canvas):
    """Canvas en deux passes : le pied de page connaît le nombre total de pages."""

    def __init__(self, *args, pied="", **kwargs):
        super().__init__(*args, **kwargs)
        self._etats = []
        self._pied = pied

    def showPage(self):
        self._etats.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._etats)
        for etat in self._etats:
            self.__dict__.update(etat)
            self.setFont("Helvetica", 7.5)
            self.setFillColor(colors.HexColor("#9AA5B1"))
            texte = f"{self._pied} - page {self._pageNumber} / {total}" if self._pied else \
                f"page {self._pageNumber} / {total}"
            self.drawCentredString(A4[0] / 2, 10 * mm, texte)
            super().showPage()
        super().save()


# ------------------------------------------------------------------ entrée --

def valider_donnees(donnees):
    """Vérifie le minimum vital (entreprise + au moins un poste) et retourne
    une copie sûre : les types inattendus sont ignorés plutôt que de faire échouer le rendu."""
    if not isinstance(donnees, dict):
        raise ValeurNonAutorisee("Données de fiche illisibles.")
    meta = donnees.get("meta") if isinstance(donnees.get("meta"), dict) else {}
    if not str(meta.get("company") or "").strip():
        raise ValeurNonAutorisee("La fiche doit indiquer le nom de l'entreprise (meta.company).")
    postes = [p for p in (donnees.get("postes") or []) if isinstance(p, dict)]
    if not postes:
        raise ValeurNonAutorisee("La fiche doit contenir au moins un poste (postes).")
    propre = dict(donnees)
    propre["meta"] = meta
    propre["postes"] = postes
    propre["question_blocks"] = [b for b in (donnees.get("question_blocks") or []) if isinstance(b, dict)]
    apercu = donnees.get("company_overview")
    propre["company_overview"] = apercu if isinstance(apercu, dict) else None
    return propre


def generer_pdf_fiche(donnees, chemin_sortie):
    """Écrit la fiche à chemin_sortie et retourne le chemin en chaîne."""
    donnees = valider_donnees(donnees)
    meta = donnees["meta"]
    postes = donnees["postes"]
    element_postes = [Paragraph(
        _t(donnees.get("postes_heading")
           or ("Le poste visé" if len(postes) == 1 else f"Les {len(postes)} postes visés")),
        _S["section"],
    )]
    for indice, poste in enumerate(postes):
        element_postes += [_carte_poste(poste, indice), Spacer(1, 7)]

    elements = [_entete(meta), Spacer(1, 8)]
    if donnees["company_overview"]:
        elements += _section_entreprise(donnees["company_overview"])
    elements += element_postes
    if donnees["question_blocks"]:
        elements += _section_questions(
            donnees["question_blocks"], donnees.get("questions_heading") or "Questions à poser"
        )
    if str(donnees.get("footer_tip") or "").strip():
        elements += [Spacer(1, 4), _carte(
            [Paragraph(f"<b>À retenir :</b> {_t(donnees['footer_tip'])}", _S["corps"])], fond="#EAF5F1"
        )]

    pied = " - ".join(x for x in (
        f"Fiche préparée par {meta['footer_name']}" if meta.get("footer_name") else "",
        meta.get("footer_context") or meta["company"],
    ) if x)
    document = SimpleDocTemplate(
        str(chemin_sortie), pagesize=A4,
        topMargin=16 * mm, bottomMargin=20 * mm, leftMargin=15 * mm, rightMargin=15 * mm,
        title=compatible_police_pdf(f"Fiche entretien - {meta['company']}"),
    )
    document.build(
        elements,
        canvasmaker=lambda *args, **kwargs: _CanvasNumerote(
            *args, pied=compatible_police_pdf(pied), **kwargs
        ),
    )
    return str(chemin_sortie)


def texte_fiche(donnees):
    """La fiche en texte brut (Markdown simple) : sert à l'indexer pour la
    recherche et à en montrer un aperçu sans ouvrir le PDF."""
    donnees = valider_donnees(donnees)
    meta = donnees["meta"]
    lignes = [f"# Fiche d'entretien - {meta['company']}"]
    for cle in ("subtitle", "interview_date", "location", "mode", "website"):
        if meta.get(cle):
            lignes.append(str(meta[cle]))
    apercu = donnees["company_overview"]
    if apercu:
        lignes += ["", "## Présentation de l'entreprise"]
        for stat in apercu.get("stats") or []:
            if isinstance(stat, dict) and stat.get("big"):
                lignes.append(f"- {stat['big']} {stat.get('label') or ''}".rstrip())
        for cle in ("card_left", "card_right"):
            carte = apercu.get(cle)
            if isinstance(carte, dict):
                if carte.get("title"):
                    lignes += ["", f"### {carte['title']}"]
                if carte.get("html"):
                    lignes.append(texte_brut_depuis_html(carte["html"]))
        if apercu.get("source_note"):
            lignes += ["", str(apercu["source_note"])]
    lignes += ["", "## " + str(donnees.get("postes_heading") or "Postes visés")]
    for poste in donnees["postes"]:
        lignes += ["", f"### {poste.get('title') or 'Poste'}"]
        for cle in ("lead", "stack"):
            if poste.get(cle):
                lignes.append(str(poste[cle]))
        lignes += [f"- {m}" for m in poste.get("missions") or [] if str(m).strip()]
    if donnees["question_blocks"]:
        lignes += ["", "## " + str(donnees.get("questions_heading") or "Questions à poser")]
        for bloc in donnees["question_blocks"]:
            lignes += ["", f"### {bloc.get('theme') or 'Questions'}"]
            for question in bloc.get("questions") or []:
                if isinstance(question, dict) and question.get("text"):
                    lignes.append(f"- {question['text']}")
                    if question.get("why"):
                        lignes.append(f"  ({question['why']})")
    if str(donnees.get("footer_tip") or "").strip():
        lignes += ["", f"À retenir : {donnees['footer_tip']}"]
    return "\n".join(lignes).strip()
