"""Briques communes aux PDF fabriqués par Azimut (lettres_pdf.py, fiches_pdf.py) :
reportlab est du pur Python - aucune dépendance système, mêmes PDF sur les
3 systèmes. Les polices intégrées de PDF (Helvetica...) ne couvrent que
l'alphabet latin occidental : le texte est adapté avant d'être dessiné."""

# Symboles courants absents de l'encodage des polices PDF standard.
SUBSTITUTIONS = {
    "\u2192": "->", "\u2190": "<-", "\u21d2": "=>", "\u2265": ">=", "\u2264": "<=",
    "\u2260": "!=", "\u2248": "~", "\u2713": "v", "\u2714": "v", "\u2717": "x",
    "\u2718": "x", "\u2605": "*", "\u2606": "*",
    "\u202f": " ", "\u2009": " ", "\u200b": "", "\u2010": "-", "\u2011": "-",
    "\u2012": "-", "\u2015": "-", "\u2212": "-", "\ufb01": "fi", "\ufb02": "fl",
}


def compatible_police_pdf(texte):
    """Remplace ce que les polices standard ne savent pas dessiner (sinon
    des carrés noirs) : symboles courants convertis, le reste devient « ? »."""
    texte = str(texte or "")
    for source, cible in SUBSTITUTIONS.items():
        texte = texte.replace(source, cible)
    return texte.encode("cp1252", errors="replace").decode("cp1252")


def echapper_xml(texte):
    """Échappe un texte brut pour le mini-langage de balises de reportlab."""
    return (
        compatible_police_pdf(texte)
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
