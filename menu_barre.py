"""Widget de barre de menus macOS pour Azimut : un résumé (relances du jour,
prochain entretien) sans ouvrir la fenêtre complète. Lit directement la base
SQLite - fonctionne même si l'appli principale n'est pas lancée.

Se lance via double-clic sur « Azimut Widget.app » (pas d'icône dans le Dock,
juste la barre de menus). Peut être ajouté aux éléments de connexion pour
démarrer automatiquement (Réglages Système → Général → Ouverture).
"""

import subprocess
from pathlib import Path

import rumps

import agenda
import candidatures
import notifications_macos

DOSSIER_PROJET = Path(__file__).parent
ICONE = str(DOSSIER_PROJET / "docs" / "icone_barre_menu.png")
CHEMIN_AZIMUT_APP = DOSSIER_PROJET / "Azimut.app"
INTERVALLE_ACTUALISATION = 600  # secondes (10 minutes)


def _date_fr(iso):
    try:
        annee, mois, jour = str(iso).split("-")
        return f"{jour}/{mois}/{annee}"
    except (ValueError, AttributeError):
        return str(iso)


class WidgetAzimut(rumps.App):
    def __init__(self):
        super().__init__("Azimut", icon=ICONE, template=True, quit_button="Quitter")
        self.item_relances = rumps.MenuItem("Relances aujourd'hui : …")
        self.item_entretien = rumps.MenuItem("Prochain entretien : …")
        self.menu = [
            self.item_relances,
            self.item_entretien,
            None,
            rumps.MenuItem("Ouvrir Azimut", callback=self.ouvrir_azimut),
            rumps.MenuItem("Actualiser", callback=self.actualiser),
        ]
        self.actualiser(None)

    def actualiser(self, _sender):
        try:
            relances = candidatures.lister_relances_a_faire()
            entretiens = [e for e in agenda.lister_echeances() if e["type"] == "entretien"]
        except Exception:
            self.item_relances.title = "Relances : base introuvable"
            self.item_entretien.title = ""
            self.title = None
            return
        notifications_macos.verifier_et_notifier()
        self.item_relances.title = (
            f"Relances à faire : {len(relances)}" if relances else "Aucune relance à faire"
        )
        if entretiens:
            prochain = entretiens[0]
            self.item_entretien.title = (
                f"Prochain entretien : {prochain['entreprise']} - {_date_fr(prochain['date'])}"
            )
        else:
            self.item_entretien.title = "Aucun entretien planifié"
        self.title = str(len(relances)) if relances else None

    def ouvrir_azimut(self, _sender):
        subprocess.run(["open", str(CHEMIN_AZIMUT_APP)])

    @rumps.timer(INTERVALLE_ACTUALISATION)
    def actualisation_automatique(self, sender):
        self.actualiser(sender)


if __name__ == "__main__":
    WidgetAzimut().run()
