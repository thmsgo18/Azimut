"""Extraction du texte d'un fichier (PDF, Word, texte brut) : sert à lire le
CV (profil.py) et à indexer les lettres et fiches importées (pieces_liees.py)
pour que la recherche les retrouve.

L'extraction est best effort : un PDF scanné (une image sans texte) ou une
police exotique peut donner un texte vide ou approximatif - c'est au
programme appelant de décider si c'est bloquant."""

import logging
from pathlib import Path

from exceptions import ValeurNonAutorisee

EXTENSIONS_TEXTE = {".pdf", ".docx", ".txt", ".md"}

# pypdf commente chaque anomalie d'un PDF sur la console ; l'erreur utile est
# déjà renvoyée à l'utilisateur en français (voir extraire_texte).
logging.getLogger("pypdf").setLevel(logging.ERROR)


def _texte_pdf(chemin):
    from pypdf import PdfReader

    lecteur = PdfReader(str(chemin))
    return "\n\n".join(page.extract_text() or "" for page in lecteur.pages)


def _texte_docx(chemin):
    import docx

    document = docx.Document(str(chemin))
    return "\n".join(paragraphe.text for paragraphe in document.paragraphs)


def extraire_texte(chemin):
    """Texte du fichier (chaîne vide si rien d'extractible). Un fichier
    corrompu ou d'un format invalide lève ValeurNonAutorisee avec un message
    clair, jamais une exception brute de la bibliothèque sous-jacente."""
    chemin = Path(chemin)
    suffixe = chemin.suffix.lower()
    try:
        if suffixe == ".pdf":
            texte = _texte_pdf(chemin)
        elif suffixe == ".docx":
            texte = _texte_docx(chemin)
        else:
            texte = chemin.read_text(encoding="utf-8", errors="ignore")
    except Exception as erreur:
        raise ValeurNonAutorisee(
            f"Impossible de lire « {chemin.name} » : fichier corrompu ou format invalide ({erreur})."
        )
    return texte.strip()
