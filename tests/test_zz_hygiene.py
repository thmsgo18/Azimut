"""Garde-fou d'hygiène : la suite de tests ne doit JAMAIS toucher aux vraies
données (la vraie base et ses dossiers de fichiers à côté du code).

Ce module s'importe pendant la collecte des tests - donc avant qu'aucun test
ne tourne - et note l'état des vraies données ; le test ci-dessous, lancé en
dernier (nom en « zz »), vérifie que rien n'a bougé. Un test qui fait des
écritures doit travailler sur une base temporaire (voir les autres fichiers :
tempfile.TemporaryDirectory + db.initialiser_base(chemin))."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db

PROJET = Path(db.CHEMIN_DB).resolve().parent
DOSSIERS_DONNEES = ("documents", "sauvegardes", "lettres", "fiches", "cv", "profil", "import_temp")


def _empreinte():
    """État observable des vraies données : la base (existence, taille, date) et
    la liste des fichiers de chaque dossier de données à côté du code."""
    base = Path(db.CHEMIN_DB)
    etat = {"base": (base.stat().st_size, base.stat().st_mtime_ns) if base.exists() else None}
    for nom in DOSSIERS_DONNEES:
        dossier = PROJET / nom
        etat[nom] = sorted(p.name for p in dossier.iterdir()) if dossier.is_dir() else None
    return etat


EMPREINTE_AVANT = _empreinte()


class TestVraiesDonneesIntactes(unittest.TestCase):
    def test_la_suite_n_a_touche_a_aucune_vraie_donnee(self):
        apres = _empreinte()
        differences = {cle: (EMPREINTE_AVANT[cle], apres[cle])
                       for cle in apres if apres[cle] != EMPREINTE_AVANT[cle]}
        self.assertEqual(
            differences, {},
            "Un test a modifié les vraies données du projet (base ou dossiers de fichiers) - "
            "il doit travailler sur une base temporaire. Différences (avant, après) : "
            f"{differences}",
        )


if __name__ == "__main__":
    unittest.main()
