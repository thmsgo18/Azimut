"""CV de l'utilisateur : plusieurs possibles (un par langue, par axe de
recherche...), dont un « principal » - celui que l'IA lit pour adapter une
lettre de motivation ou une fiche d'entretien (voir generation.py).

Un CV peut avoir, au choix ou ensemble :
- un FICHIER (PDF, Word, texte) téléversé, copié dans le dossier cv/ du dossier
  de données (voir reglages.py) : c'est ce qu'on télécharge ou qu'on envoie ;
- une SOURCE modifiable sur la machine : le dossier d'un projet LaTeX (ou un
  fichier .tex) ou un fichier Word. Elle est relue à chaque fois (le CV évolue
  entre deux lettres) et dit à une IA où lire le texte brut ET où aller le
  modifier si l'utilisateur le demande ;
- un TEXTE collé, quand il n'y a rien d'autre.

Le texte lisible est gardé en base (`contenu`) : celui du fichier (PDF, Word), à
défaut celui de la source, à défaut le texte collé. Il sert à l'aperçu, à la copie
et à la recherche, et de repli quand la source n'est plus accessible (autre
machine, dossier déplacé). C'est en revanche la SOURCE qui est lue en priorité
pour l'IA (texte_du_cv) : elle est toujours à jour.

Toute écriture passe par ces fonctions - jamais de SQL direct depuis l'extérieur.
"""

import uuid
from datetime import datetime
from pathlib import Path

import db
import reglages
from exceptions import EntiteIntrouvable, ValeurNonAutorisee
from extraction import EXTENSIONS_TEXTE as EXTENSIONS_FICHIER
from extraction import extraire_texte

TAILLE_MAX = 15 * 1024 * 1024  # 15 Mo
TAILLE_MAX_TEXTE = 40000  # caractères envoyés à l'IA - évite un CV démesuré
TYPES_SOURCE = ("latex", "word")
LONGUEUR_APERCU = 260


def dossier_cv(chemin_db=None):
    """Dossier où ranger les fichiers CV : celui choisi dans Réglages, sinon
    cv/ à côté de la base (même logique que documents.py)."""
    return reglages.dossier_donnees_pour("cv", chemin_db=chemin_db)


def _maintenant():
    return datetime.now().isoformat(timespec="seconds")


# --- lecture du texte -------------------------------------------------------

def _lire_latex(chemin):
    """Texte des fichiers .tex d'un dossier de projet (ou d'un seul fichier .tex)."""
    chemin = Path(chemin)
    fichiers = sorted(chemin.rglob("*.tex")) if chemin.is_dir() else [chemin]
    morceaux = []
    for fichier in fichiers:
        try:
            morceaux.append(fichier.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    texte = "\n\n".join(morceaux).strip()
    if not texte:
        raise ValeurNonAutorisee(f"Aucun fichier .tex lisible dans {chemin}.")
    return texte[:TAILLE_MAX_TEXTE]


def _lire_source(type_source, chemin):
    if type_source == "latex":
        return _lire_latex(chemin)
    texte = extraire_texte(chemin)
    if not texte:
        raise ValeurNonAutorisee(f"Aucun texte lisible dans {chemin}.")
    return texte[:TAILLE_MAX_TEXTE]


def _analyser_source(chemin_source):
    """(type, chemin normalisé) d'une source, ou une erreur claire : un dossier
    contenant du LaTeX, un fichier .tex ou un fichier Word (.docx)."""
    brut = str(chemin_source or "").strip()
    if not brut:
        raise ValeurNonAutorisee("Le chemin de la source du CV est vide.")
    chemin = Path(brut).expanduser()
    if not chemin.is_absolute():
        raise ValeurNonAutorisee(
            f"Indiquer un chemin complet (commençant par / ou par un disque, ou par ~) : {brut!r}."
        )
    if chemin.is_dir():
        if not any(chemin.rglob("*.tex")):
            raise ValeurNonAutorisee(f"Aucun fichier .tex dans le dossier {chemin}.")
        return "latex", str(chemin)
    if chemin.is_file():
        suffixe = chemin.suffix.lower()
        if suffixe == ".tex":
            return "latex", str(chemin)
        if suffixe == ".docx":
            return "word", str(chemin)
        raise ValeurNonAutorisee(
            f"Source non prise en charge : {chemin.name}. Indiquer un dossier LaTeX, "
            "un fichier .tex ou un fichier Word (.docx)."
        )
    raise ValeurNonAutorisee(f"Chemin introuvable : {chemin}.")


def _valider_fichier(nom_fichier, contenu):
    if not contenu:
        raise ValeurNonAutorisee("Le fichier reçu est vide.")
    if len(contenu) > TAILLE_MAX:
        raise ValeurNonAutorisee("Fichier trop volumineux (15 Mo maximum).")
    suffixe = Path(str(nom_fichier)).suffix.lower()
    if suffixe not in EXTENSIONS_FICHIER:
        raise ValeurNonAutorisee(
            f"Format non pris en charge : {suffixe or '(aucune extension)'}. "
            f"Formats acceptés : {', '.join(sorted(EXTENSIONS_FICHIER))}."
        )
    return suffixe


def _ranger_fichier(nom_fichier, contenu, chemin_db):
    """Écrit le fichier dans cv/ ; retourne (chemin absolu, texte extrait)."""
    suffixe = _valider_fichier(nom_fichier, contenu)
    dossier = dossier_cv(chemin_db)
    dossier.mkdir(parents=True, exist_ok=True)
    destination = dossier / f"cv-{uuid.uuid4().hex[:10]}{suffixe}"
    destination.write_bytes(contenu)
    try:
        texte = extraire_texte(destination)[:TAILLE_MAX_TEXTE]
    except ValeurNonAutorisee:
        destination.unlink(missing_ok=True)
        raise
    return destination, texte


# --- lecture -----------------------------------------------------------------

def _texte_vivant(cv):
    """Le texte lu par l'IA : la source du CV si elle est accessible (toujours à
    jour, et plus fidèle qu'un PDF), sinon le texte gardé en base. Chaîne vide
    s'il n'y a rien."""
    if cv["type_source"] and cv["chemin_source"] and Path(cv["chemin_source"]).exists():
        try:
            return _lire_source(cv["type_source"], cv["chemin_source"])
        except ValeurNonAutorisee:
            pass
    return cv["contenu"] or ""


def _enrichir(cv):
    cv = dict(cv)
    cv["principal"] = bool(cv["principal"])
    chemin = cv.get("chemin_fichier")
    fichier = reglages.chemin_reel(chemin) if chemin else None
    cv["fichier_disponible"] = bool(fichier) and fichier.exists()
    cv["taille_fichier"] = fichier.stat().st_size if cv["fichier_disponible"] else None
    cv["apercu_pdf"] = cv["fichier_disponible"] and str(chemin).lower().endswith(".pdf")
    cv["source_disponible"] = (
        bool(cv["chemin_source"]) and Path(cv["chemin_source"]).exists()
    )
    texte = cv["contenu"] or ""  # le texte lisible (fichier), pas les commandes LaTeX
    cv["apercu"] = " ".join(texte.split())[:LONGUEUR_APERCU]
    cv["nb_caracteres"] = len(texte)
    return cv


def lister_cvs(chemin_db=None):
    """Tous les CV, le principal d'abord puis les plus récents (sans le texte
    complet, seulement un aperçu)."""
    conn = db.ouvrir(chemin_db)
    try:
        lignes = conn.execute(
            "SELECT * FROM cvs ORDER BY principal DESC, date_modification DESC, id DESC"
        ).fetchall()
    finally:
        conn.close()
    return [_enrichir(ligne) for ligne in lignes]


def recuperer_cv(id_cv, chemin_db=None):
    conn = db.ouvrir(chemin_db)
    try:
        ligne = conn.execute("SELECT * FROM cvs WHERE id = ?", (id_cv,)).fetchone()
    finally:
        conn.close()
    if ligne is None:
        raise EntiteIntrouvable(f"Aucun CV avec l'id {id_cv}.")
    return _enrichir(ligne)


def texte_lisible_du_cv(id_cv, chemin_db=None):
    """Le texte lisible d'un CV, tel qu'on le copie ou l'affiche : celui de son
    fichier (PDF, Word), à défaut de sa source ou du texte collé."""
    cv = recuperer_cv(id_cv, chemin_db=chemin_db)
    if not cv["contenu"]:
        raise ValeurNonAutorisee(f"Le CV « {cv['nom']} » n'a aucun texte lisible.")
    return cv["contenu"]


def texte_du_cv(id_cv, chemin_db=None):
    """Le texte complet d'un CV pour l'IA (relu depuis sa source si elle est accessible)."""
    conn = db.ouvrir(chemin_db)
    try:
        ligne = conn.execute("SELECT * FROM cvs WHERE id = ?", (id_cv,)).fetchone()
    finally:
        conn.close()
    if ligne is None:
        raise EntiteIntrouvable(f"Aucun CV avec l'id {id_cv}.")
    texte = _texte_vivant(dict(ligne))
    if not texte:
        raise ValeurNonAutorisee(f"Le CV « {ligne['nom']} » n'a aucun texte lisible.")
    return texte


def obtenir_cv_texte(id_cv=None, chemin_db=None):
    """Le texte du CV prêt pour l'IA : celui demandé, sinon le principal. Lève
    ValeurNonAutorisee si aucun CV n'est configuré (section CV)."""
    if id_cv is None:
        principal = next((cv for cv in lister_cvs(chemin_db=chemin_db) if cv["principal"]), None)
        if principal is None:
            raise ValeurNonAutorisee(
                "Aucun CV configuré - ajouter son CV dans la section CV avant de générer une lettre."
            )
        id_cv = principal["id"]
    return texte_du_cv(id_cv, chemin_db=chemin_db)


# --- écriture ----------------------------------------------------------------

def _nom_par_defaut(nom, nom_fichier):
    nom = str(nom or "").strip()
    if nom:
        return nom
    return Path(str(nom_fichier)).stem if nom_fichier else "Mon CV"


def ajouter_cv(
    nom=None, langue=None, nom_fichier=None, contenu_fichier=None, chemin_source=None,
    texte=None, principal=None, chemin_db=None,
):
    """Ajoute un CV et retourne son id.

    Au moins une des trois formes est nécessaire : un fichier (`nom_fichier` +
    `contenu_fichier`), une source modifiable (`chemin_source` : dossier LaTeX,
    fichier .tex ou .docx) ou un texte collé. Le premier CV ajouté devient
    automatiquement le principal ; `principal=True` en désigne un autre."""
    a_fichier = contenu_fichier is not None or nom_fichier
    if not a_fichier and not (chemin_source and str(chemin_source).strip()) and not (
        texte and str(texte).strip()
    ):
        raise ValeurNonAutorisee(
            "Un CV a besoin d'un fichier, d'un chemin vers sa source (dossier LaTeX ou fichier "
            "Word) ou d'un texte collé."
        )
    # Tout est validé avant d'écrire le moindre fichier.
    type_source = chemin_normalise = texte_source = None
    if chemin_source and str(chemin_source).strip():
        type_source, chemin_normalise = _analyser_source(chemin_source)
        texte_source = _lire_source(type_source, chemin_normalise)
    if a_fichier:
        _valider_fichier(nom_fichier or "", contenu_fichier or b"")
    conn = db.ouvrir(chemin_db)
    destination = None
    try:
        texte_fichier = ""
        if a_fichier:
            destination, texte_fichier = _ranger_fichier(nom_fichier, contenu_fichier, chemin_db)
        contenu = texte_fichier or texte_source or (str(texte).strip()[:TAILLE_MAX_TEXTE] if texte else "")
        if not contenu:
            raise ValeurNonAutorisee(
                "Impossible d'extraire du texte de ce fichier (PDF scanné ?) - indiquer aussi "
                "la source du CV ou coller son texte."
            )
        premier = conn.execute("SELECT COUNT(*) FROM cvs").fetchone()[0] == 0
        est_principal = premier or bool(principal)
        if est_principal:
            conn.execute("UPDATE cvs SET principal = 0")
        maintenant = _maintenant()
        curseur = conn.execute(
            "INSERT INTO cvs (nom, langue, chemin_fichier, nom_fichier, type_source, chemin_source, "
            "contenu, principal, date_creation, date_modification) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _nom_par_defaut(nom, nom_fichier), (str(langue).strip() if langue else None) or None,
                str(destination) if destination else None,
                Path(str(nom_fichier)).name if destination else None,
                type_source, chemin_normalise, contenu, 1 if est_principal else 0, maintenant, maintenant,
            ),
        )
        conn.commit()
        return curseur.lastrowid
    except Exception:
        conn.rollback()
        if destination is not None:
            destination.unlink(missing_ok=True)  # jamais de fichier orphelin après un échec
        raise
    finally:
        conn.close()


def modifier_cv(id_cv, chemin_db=None, **champs):
    """Modifie un CV. Champs : nom, langue, chemin_source (vide = retirer la
    source), texte (remplace le texte gardé), principal (True = en faire le CV
    principal)."""
    inconnus = set(champs) - {"nom", "langue", "chemin_source", "texte", "principal"}
    if inconnus:
        raise ValeurNonAutorisee(f"Champ non modifiable : {', '.join(sorted(inconnus))}.")
    if not champs:
        raise ValeurNonAutorisee("Aucun champ à modifier n'a été fourni.")
    cv = recuperer_cv(id_cv, chemin_db=chemin_db)
    maj = {}
    if "nom" in champs:
        nom = str(champs["nom"] or "").strip()
        if not nom:
            raise ValeurNonAutorisee("Le nom d'un CV ne peut pas être vide.")
        maj["nom"] = nom
    if "langue" in champs:
        maj["langue"] = (str(champs["langue"]).strip() if champs["langue"] else None) or None
    contenu = None
    if "chemin_source" in champs:
        if champs["chemin_source"] and str(champs["chemin_source"]).strip():
            type_source, chemin = _analyser_source(champs["chemin_source"])
            texte_source = _lire_source(type_source, chemin)  # valide aussi que la source est lisible
            if not cv["nom_fichier"]:  # sans fichier, la source est le texte lisible
                contenu = texte_source
            maj["type_source"], maj["chemin_source"] = type_source, chemin
        else:
            if not cv["contenu"]:
                raise ValeurNonAutorisee("Ce CV n'a pas d'autre texte : garder au moins sa source.")
            maj["type_source"] = maj["chemin_source"] = None
    if "texte" in champs and contenu is None:
        if not champs["texte"] or not str(champs["texte"]).strip():
            raise ValeurNonAutorisee("Le texte du CV est vide.")
        contenu = str(champs["texte"]).strip()[:TAILLE_MAX_TEXTE]
    if contenu is not None:
        maj["contenu"] = contenu
    maj["date_modification"] = _maintenant()
    conn = db.ouvrir(chemin_db)
    try:
        if champs.get("principal"):
            conn.execute("UPDATE cvs SET principal = 0")
            maj["principal"] = 1
        colonnes = ", ".join(f"{c} = ?" for c in maj)
        conn.execute(f"UPDATE cvs SET {colonnes} WHERE id = ?", (*maj.values(), id_cv))
        conn.commit()
    finally:
        conn.close()
    return recuperer_cv(id_cv, chemin_db=chemin_db)


def remplacer_fichier_cv(id_cv, nom_fichier, contenu_fichier, chemin_db=None):
    """Remplace (ou ajoute) le fichier d'un CV ; l'ancien fichier est supprimé."""
    ancien = recuperer_cv(id_cv, chemin_db=chemin_db)
    destination, texte = _ranger_fichier(nom_fichier, contenu_fichier, chemin_db)
    contenu = texte or ancien["contenu"]
    conn = db.ouvrir(chemin_db)
    try:
        conn.execute(
            "UPDATE cvs SET chemin_fichier = ?, nom_fichier = ?, contenu = ?, date_modification = ? "
            "WHERE id = ?",
            (str(destination), Path(str(nom_fichier)).name, contenu, _maintenant(), id_cv),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        destination.unlink(missing_ok=True)
        raise
    finally:
        conn.close()
    if ancien["chemin_fichier"]:
        reglages.chemin_reel(ancien["chemin_fichier"]).unlink(missing_ok=True)
    return recuperer_cv(id_cv, chemin_db=chemin_db)


def definir_cv_principal(id_cv, chemin_db=None):
    """Désigne le CV que l'IA lira par défaut (un seul à la fois)."""
    return modifier_cv(id_cv, principal=True, chemin_db=chemin_db)


def supprimer_cv(id_cv, chemin_db=None):
    """Supprime un CV (et son fichier téléversé). S'il était le principal, le CV
    le plus récent qui reste prend sa place. La source sur la machine (dossier
    LaTeX, fichier Word) n'est JAMAIS touchée : Azimut n'en garde que le chemin."""
    cv = recuperer_cv(id_cv, chemin_db=chemin_db)
    conn = db.ouvrir(chemin_db)
    try:
        conn.execute("DELETE FROM cvs WHERE id = ?", (id_cv,))
        if cv["principal"]:
            conn.execute(
                "UPDATE cvs SET principal = 1 WHERE id = ("
                "SELECT id FROM cvs ORDER BY date_modification DESC, id DESC LIMIT 1)"
            )
        conn.commit()
    finally:
        conn.close()
    if cv["chemin_fichier"]:
        reglages.chemin_reel(cv["chemin_fichier"]).unlink(missing_ok=True)
