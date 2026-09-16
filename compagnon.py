"""Vue compagnon (lecture seule) pour iPhone/iPad - sans app native, sans
cloud : un second petit serveur Flask, séparé du serveur principal, exposé
sur le réseau local UNIQUEMENT si activé dans Réglages, et protégé par un
code d'accès généré sur cette machine.

Surface volontairement minuscule et strictement en lecture :
- aucune route d'écriture (impossible de modifier quoi que ce soit d'ici) ;
- aucun champ sensible ne transite jamais (mots de passe de portail, clé
  API, notes, texte d'offre) - seulement de quoi vérifier les relances du
  jour, le prochain entretien et la liste des candidatures, sur le même
  Wi-Fi que le Mac.

Le serveur principal (serveur.py) n'est pas concerné par ce module : il
continue de n'écouter que sur 127.0.0.1, inchangé.
"""

import secrets
import socket

from flask import Flask, Response, jsonify, request

import agenda
import candidatures
import reglages
from datetime import date
from exceptions import EntiteIntrouvable

PORT_COMPAGNON = 8767

CHAMPS_CANDIDATURE_PUBLICS = (
    "id",
    "entreprise",
    "poste",
    "statut",
    "priorite",
    "ville",
    "mode_travail",
    "date_envoi",
    "date_relance_prevue",
    "date_entretien",
    "lien_offre",
)

app_compagnon = Flask(__name__)


def _public(cand):
    return {champ: cand.get(champ) for champ in CHAMPS_CANDIDATURE_PUBLICS}


def _code_fourni_valide():
    fourni = request.args.get("code") or request.headers.get("X-Azimut-Code") or ""
    attendu = reglages.code_compagnon()
    return bool(fourni) and secrets.compare_digest(str(fourni), str(attendu))


def ip_locale():
    """Adresse IP de cette machine sur le réseau local (best effort) - pour
    afficher l'URL à taper sur le téléphone. Ne fait aucune vraie requête
    réseau : le socket UDP n'envoie rien, il sert juste à faire choisir au
    système la bonne interface réseau."""
    essai = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        essai.connect(("8.8.8.8", 80))
        return essai.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        essai.close()


@app_compagnon.before_request
def verifier_acces():
    if request.path == "/":
        return None
    if not _code_fourni_valide():
        return jsonify({"erreur": "Code d'accès invalide ou manquant."}), 401


@app_compagnon.route("/api/compagnon/tableau")
def api_tableau():
    aujourd_hui = date.today().isoformat()
    relances = candidatures.lister_relances_a_faire()
    entretiens_a_venir = sorted(
        (e for e in agenda.lister_echeances() if e["type"] == "entretien" and e["date"] >= aujourd_hui),
        key=lambda e: e["date"],
    )
    return jsonify(
        {
            "relances": [_public(c) for c in relances],
            "prochain_entretien": entretiens_a_venir[0] if entretiens_a_venir else None,
        }
    )


@app_compagnon.route("/api/compagnon/candidatures")
def api_candidatures():
    return jsonify([_public(c) for c in candidatures.lister_candidatures()])


@app_compagnon.route("/api/compagnon/candidatures/<int:numero>")
def api_candidature(numero):
    try:
        cand = candidatures.recuperer_candidature(numero)
    except EntiteIntrouvable as erreur:
        return jsonify({"erreur": str(erreur)}), 404
    return jsonify(_public(cand))


@app_compagnon.route("/")
def page():
    return Response(PAGE_HTML, mimetype="text/html")


PAGE_HTML = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Azimut - Compagnon</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
    background: #16161a; color: #ececec; padding: 16px 16px 40px;
  }
  h1 { font-size: 20px; margin: 8px 0 4px; }
  .sous-titre { color: #8b8b93; font-size: 13px; margin: 0 0 20px; }
  .carte {
    background: #1e1e23; border: 1px solid #2a2a30; border-radius: 12px;
    padding: 14px 16px; margin-bottom: 14px;
  }
  .carte h2 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em; color: #9a9aa2; margin: 0 0 10px; }
  .ligne { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid #2a2a30; }
  .ligne:last-child { border-bottom: none; }
  .ligne .principal { font-weight: 600; font-size: 14px; }
  .ligne .secondaire { color: #9a9aa2; font-size: 12.5px; }
  .puce { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #2a2a30; font-size: 11.5px; color: #cfcfd6; white-space: nowrap; }
  .vide { color: #8b8b93; font-size: 13.5px; padding: 6px 0; }
  #ecran-code { display: flex; flex-direction: column; gap: 12px; max-width: 320px; margin: 60px auto; }
  #ecran-code input { padding: 12px; border-radius: 10px; border: 1px solid #2a2a30; background: #1e1e23; color: #ececec; font-size: 16px; }
  #ecran-code button, .btn-actualiser { padding: 12px; border-radius: 10px; border: none; background: #3987e5; color: #fff; font-size: 15px; font-weight: 600; }
  #app { display: none; }
  .erreur { color: #ff6b6b; font-size: 13px; }
</style>
</head>
<body>
  <div id="ecran-code">
    <h1>Azimut</h1>
    <p class="sous-titre">Entre le code d'accès affiché dans Réglages, sur ton Mac.</p>
    <input type="text" id="champ-code" placeholder="Code d'accès" autocapitalize="off" autocorrect="off">
    <button onclick="connecter()">Continuer</button>
    <p class="erreur" id="erreur-code"></p>
  </div>
  <div id="app">
    <h1>Azimut</h1>
    <p class="sous-titre">Vue compagnon - lecture seule</p>
    <div class="carte">
      <h2>Relances à faire</h2>
      <div id="liste-relances"></div>
    </div>
    <div class="carte">
      <h2>Prochain entretien</h2>
      <div id="prochain-entretien"></div>
    </div>
    <div class="carte">
      <h2>Toutes les candidatures</h2>
      <div id="liste-candidatures"></div>
    </div>
    <button class="btn-actualiser" onclick="charger()">Actualiser</button>
  </div>
<script>
function dateFr(iso) {
  if (!iso) return "";
  const [a, m, j] = iso.split("-");
  return j && m ? `${j}/${m}/${a}` : iso;
}
function echapper(texte) {
  const div = document.createElement("div");
  div.textContent = texte == null ? "" : String(texte);
  return div.innerHTML;
}
function code() { return localStorage.getItem("azimut_code") || ""; }

async function api(chemin) {
  const reponse = await fetch(chemin + (chemin.includes("?") ? "&" : "?") + "code=" + encodeURIComponent(code()));
  if (reponse.status === 401) { localStorage.removeItem("azimut_code"); afficherEcranCode(); throw new Error("Code invalide"); }
  return reponse.json();
}

function ligneCandidature(c) {
  return `<div class="ligne">
    <div><div class="principal">${echapper(c.entreprise)}</div><div class="secondaire">${echapper(c.poste)}</div></div>
    <span class="puce">${echapper(c.statut)}</span>
  </div>`;
}

async function charger() {
  try {
    const tableau = await api("/api/compagnon/tableau");
    document.getElementById("liste-relances").innerHTML = tableau.relances.length
      ? tableau.relances.map(ligneCandidature).join("")
      : `<div class="vide">Aucune relance à faire.</div>`;
    const p = tableau.prochain_entretien;
    document.getElementById("prochain-entretien").innerHTML = p
      ? `<div class="ligne"><div><div class="principal">${echapper(p.entreprise)}</div><div class="secondaire">${echapper(p.poste)}</div></div><span class="puce">${dateFr(p.date)}</span></div>`
      : `<div class="vide">Aucun entretien planifié.</div>`;
    const liste = await api("/api/compagnon/candidatures");
    document.getElementById("liste-candidatures").innerHTML = liste.length
      ? liste.map(ligneCandidature).join("")
      : `<div class="vide">Aucune candidature pour l'instant.</div>`;
  } catch (erreur) { /* déjà géré par api() si code invalide */ }
}

function afficherEcranCode() {
  document.getElementById("ecran-code").style.display = "flex";
  document.getElementById("app").style.display = "none";
}

function connecter() {
  const valeur = document.getElementById("champ-code").value.trim();
  if (!valeur) return;
  localStorage.setItem("azimut_code", valeur);
  entrer();
}

function entrer() {
  document.getElementById("erreur-code").textContent = "";
  document.getElementById("ecran-code").style.display = "none";
  document.getElementById("app").style.display = "block";
  charger().catch(() => {
    document.getElementById("erreur-code").textContent = "Code invalide.";
  });
}

if (code()) { entrer(); } else { afficherEcranCode(); }
</script>
</body>
</html>"""
