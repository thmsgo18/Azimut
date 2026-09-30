"""Données de test partagées : petits fichiers fabriqués à la volée (PDF, Word) -
aucun fichier binaire n'est versionné et aucun test ne dépend des vraies données -
et une réponse type de l'IA pour une fiche."""

import copy
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def pdf_avec_texte(*lignes):
    """Un PDF d'une page contenant ces lignes de texte (extractible)."""
    tampon = io.BytesIO()
    page = canvas.Canvas(tampon, pagesize=A4)
    page.setFont("Helvetica", 12)
    for indice, ligne in enumerate(lignes):
        page.drawString(60, 780 - 20 * indice, ligne)
    page.save()
    return tampon.getvalue()


def pdf_sans_texte():
    """Un PDF valide mais sans aucun texte (comme un scan : seulement une image/forme)."""
    tampon = io.BytesIO()
    page = canvas.Canvas(tampon, pagesize=A4)
    page.rect(50, 50, 200, 200, fill=1)
    page.save()
    return tampon.getvalue()


def docx_avec_texte(*paragraphes):
    import docx

    document = docx.Document()
    for paragraphe in paragraphes:
        document.add_paragraph(paragraphe)
    tampon = io.BytesIO()
    document.save(tampon)
    return tampon.getvalue()


FICHE_IA = {
    "meta": {"subtitle": "Entretien commun", "candidate_line": "Camille Martin, M2 IA", "footer_name": "Camille Martin"},
    "company_overview": {
        "stats": [{"big": "~200", "label": "Collaborateurs"}],
        "card_left": {"title": "Qui est AgentikCo ?", "html": "<p>Startup agents.</p>", "tags": ["IA"]},
        "card_right": {"title": "Notoriété", "html": "<p>Série A.</p>"},
        "source_note": "Sources : site officiel.",
    },
    "postes": [
        {"offre_id": None, "code_label": None, "title": "Stage agents IA", "subdomaine": None, "lead": "Accroche.",
         "stack": "Python", "missions": ["Concevoir des agents"]},
        {"offre_id": None, "code_label": None, "title": "Stage RAG", "subdomaine": "RAG / Agents de recherche",
         "lead": None, "stack": None, "missions": []},
    ],
    "question_blocks": [{"theme": "Projets", "questions": [{"text": "Quelle équipe ?", "why": None}]}],
    "footer_tip": "Insister sur le multi-agents.",
}


def fiche_ia():
    """Ce que l'IA renvoie pour une fiche (une copie neuve à chaque appel : les
    tests la modifient)."""
    return copy.deepcopy(FICHE_IA)
