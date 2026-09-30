"""Le skill « azimut-lettre-motivation » (skills/azimut-lettre-motivation/SKILL.md) :
un seul fichier, à la fois téléchargeable pour Claude Code en local (voir
/api/lettres/skill) et utilisé tel quel comme prompt système pour la
génération via l'API (voir agent.py > generer_lettre_motivation) - un seul
texte, deux façons de le déclencher."""

import io
import zipfile
from pathlib import Path

CHEMIN_SKILL = Path(__file__).parent / "skills" / "azimut-lettre-motivation" / "SKILL.md"
NOM_SKILL = "azimut-lettre-motivation"


def contenu_skill():
    return CHEMIN_SKILL.read_text(encoding="utf-8")


def instructions_systeme():
    """Le corps du skill, sans l'entête YAML (name/description) - c'est ce
    texte qui sert de prompt système lors d'une génération via l'API."""
    texte = contenu_skill()
    if texte.startswith("---"):
        fin = texte.find("---", 3)
        if fin != -1:
            return texte[fin + 3:].strip()
    return texte.strip()


def zip_skill():
    """Zip téléchargeable (.skill) contenant NOM_SKILL/SKILL.md, prêt à
    déposer dans la librairie de skills de Claude Code."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{NOM_SKILL}/SKILL.md", contenu_skill())
    tampon.seek(0)
    return tampon
