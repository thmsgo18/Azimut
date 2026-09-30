"""Rendu PDF d'une lettre de motivation (reportlab - pur Python, aucune
dépendance LaTeX : fonctionne sur les 3 OS sans rien installer de plus que
requirements.txt). Une lettre déjà faite par l'utilisateur n'est jamais
re-rendue : elle est conservée telle quelle (voir pieces_liees.importer)."""

from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from pdf_commun import compatible_police_pdf, echapper_xml

STYLE_CORPS = ParagraphStyle(
    "corps", fontName="Helvetica", fontSize=11, leading=16,
    alignment=TA_JUSTIFY, spaceAfter=14,
)


def _paragraphe_html(texte):
    """Échappe le texte pour reportlab (mini-HTML) et convertit les retours
    à la ligne internes en <br/> - jamais les doubles retours, qui
    séparent déjà les paragraphes en amont."""
    return echapper_xml(texte).replace("\n", "<br/>")


def generer_pdf(contenu, chemin_sortie, titre=None):
    """Écrit `contenu` (texte de la lettre, paragraphes séparés par une ligne
    vide) dans un PDF sobre à chemin_sortie. Retourne le chemin en chaîne."""
    document = SimpleDocTemplate(
        str(chemin_sortie), pagesize=A4,
        topMargin=2.5 * cm, bottomMargin=2.5 * cm, leftMargin=2.5 * cm, rightMargin=2.5 * cm,
        title=compatible_police_pdf(titre or "Lettre de motivation"),
    )
    elements = []
    for paragraphe in str(contenu).split("\n\n"):
        paragraphe = paragraphe.strip()
        if not paragraphe:
            continue
        elements.append(Paragraph(_paragraphe_html(paragraphe), STYLE_CORPS))
        elements.append(Spacer(1, 2))
    if not elements:
        elements.append(Paragraph("", STYLE_CORPS))
    document.build(elements)
    return str(chemin_sortie)
