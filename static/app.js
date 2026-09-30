/* Azimut - suivi de candidatures de stage.
   Interface 100 % locale : toutes les écritures passent par l'API du serveur,
   qui elle-même passe par les fonctions métier (jamais de SQL direct). */

"use strict";

/* ========================================================================
   État global et utilitaires
   ======================================================================== */

const etat = {
  valeurs: null,          // listes de valeurs autorisées (chargées au démarrage)
  ia: null,               // état des réglages IA (clé définie ou non)
  langue: "fr",           // langue de l'interface, chargée depuis /api/reglages
  modeCandidatures: "liste",
  filtres: { statut: "", sous_domaine: "", texte: "" },
  rechercheTexte: "",
  focusRecherche: false,
  propositionEntreprise: null,  // infos entreprise proposées par l'IA, écrites après validation
  selectionComparaison: new Set(),  // ids cochés en vue liste, pour le comparateur
  versionDb: null,        // dernier mtime de la base connu, pour détecter les écritures externes
  filtresPieces: { lettres: { recherche: "" }, fiches: { recherche: "" }, documents: { recherche: "" } },
  filtresNotes: { recherche: "" },
  noteEnCours: null,      // éditeur de note ouvert : { enregistrer } pour vider l'enregistrement en attente
};

/* Couleurs par type d'objet (recherche), toujours accompagnées d'un libellé
   texte, jamais la couleur seule. */
const COULEURS_TYPE = {
  candidature: "var(--accent)",
  entreprise: "var(--st-reponse)",
  note: "var(--violet)",
  document: "var(--encre-2)",
  lettre: "var(--st-entretien)",
  fiche: "var(--st-accepte)",
};

/* Icônes SVG des états vides (aucun emoji dans l'interface). */
const ICONES = {
  boussole:
    '<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"></polygon></svg>',
  candidatures:
    '<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="5" height="16" rx="1.5"/><rect x="10" y="4" width="5" height="10" rx="1.5"/><rect x="17" y="4" width="5" height="13" rx="1.5"/></svg>',
  entreprises:
    '<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M5 21V5a1.5 1.5 0 0 1 1.5-1.5H13A1.5 1.5 0 0 1 14.5 5v16"/><path d="M14.5 9H18a1.5 1.5 0 0 1 1.5 1.5V21"/><path d="M8 7.5h3M8 11h3M8 14.5h3"/></svg>',
  fiches:
    '<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1"/><path d="M9 11h6M9 15h4"/></svg>',
  entretiens:
    '<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17z"/><path d="m14 8 3 3"/></svg>',
  lettres:
    '<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/></svg>',
  documents:
    '<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h6"/></svg>',
  cv:
    '<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="3" width="16" height="18" rx="2"/><circle cx="12" cy="10" r="2.5"/><path d="M7.5 17c.8-2 2.4-3 4.5-3s3.7 1 4.5 3"/></svg>',
};

const COULEURS_STATUT = {
  "À préparer": "var(--st-a-preparer)",
  "Envoyée": "var(--st-envoyee)",
  "Réponse reçue": "var(--st-reponse)",
  "Entretien": "var(--st-entretien)",
  "Refus": "var(--st-refus)",
  "Accepté": "var(--st-accepte)",
};

/* Traduction : t("section.cle", {parametre: valeur}) cherche dans
   window.LANGUES[etat.langue], retombe sur le français si la clé manque
   dans une autre langue, puis retourne la clé telle quelle en dernier
   recours (jamais un crash pour une traduction oubliée). Les fichiers de
   langue vivent dans static/langues/ (un fichier par langue + un registre -
   voir static/langues/registre.js pour en ajouter, modifier ou retirer une). */
function t(cle, parametres) {
  const chemin = cle.split(".");
  const chercher = (dico) => chemin.reduce((valeur, morceau) => (valeur && typeof valeur === "object" ? valeur[morceau] : undefined), dico);
  const langues = window.LANGUES || {};
  let texte = chercher(langues[etat.langue]) ?? chercher(langues.fr) ?? cle;
  if (parametres) {
    for (const [nom, valeur] of Object.entries(parametres)) {
      texte = texte.split(`{${nom}}`).join(valeur);
    }
  }
  return texte;
}

/* Traduit toute la partie statique du HTML (barre latérale : jamais
   régénérée par rendre()) - appelée au démarrage et à chaque changement de
   langue dans Réglages. */
function traduireStatique() {
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAria));
  });
}

/* Traduit une VALEUR de donnée (statut, sous-domaine...) pour
   l'affichage - jamais pour ce qui part vers l'API ou vit dans
   value="..." d'une <option>, qui restent toujours la valeur canonique en
   français (voir valeurs.py côté serveur). Absente de la table de la
   langue courante -> le français lui-même, donc jamais un blanc. */
function tv(valeur) {
  if (valeur === null || valeur === undefined || valeur === "") return valeur;
  const table = (window.LANGUES && window.LANGUES[etat.langue] && window.LANGUES[etat.langue].valeurs) || {};
  return table[valeur] ?? valeur;
}

/* « 1 candidature » / « 3 candidatures » : deux clés par mot (_singulier,
   _pluriel) pour que chaque langue accorde comme il se doit. Zéro suit le
   singulier en français (« 0 candidature »), comme le fait l'usage. */
function pluriel(cle, n) {
  return t(`${cle}_${n > 1 ? "pluriel" : "singulier"}`, { n });
}

function echapper(texte) {
  const div = document.createElement("div");
  div.textContent = texte == null ? "" : String(texte);
  return div.innerHTML;
}

/* echapper() protège le contenu texte (<, >, &) mais pas les guillemets,
   sans conséquence tant qu'on écrit dans du texte, mais une valeur insérée
   dans un attribut HTML="..." doit AUSSI échapper " (sinon l'attribut se
   referme prématurément au premier guillemet, ex. du JSON stringifié). */
function echapperAttribut(texte) {
  return echapper(texte).replace(/"/g, "&quot;");
}

function dateFr(iso) {
  if (!iso) return "";
  const [annee, mois, jour] = String(iso).split("-");
  return jour && mois ? `${jour}/${mois}/${annee}` : String(iso);
}

function toast(message, erreur = false) {
  const zone = document.getElementById("toasts");
  const element = document.createElement("div");
  element.className = "toast" + (erreur ? " erreur" : "");
  element.textContent = message;
  zone.appendChild(element);
  setTimeout(() => element.remove(), erreur ? 6000 : 3200);
}

async function api(chemin, options = {}) {
  let reponse;
  // Une écriture faite depuis cette fenêtre change la base : on oublie la version
  // connue pour que le prochain contrôle l'adopte au lieu de la prendre pour une
  // modification venue d'ailleurs (sinon « Actualiser » s'allume à chaque frappe
  // enregistrée automatiquement).
  if (options.methode && options.methode !== "GET") etat.versionDb = null;
  try {
    reponse = await fetch(chemin, {
      headers: options.corps ? { "Content-Type": "application/json" } : undefined,
      method: options.methode || "GET",
      body: options.corps ? JSON.stringify(options.corps) : undefined,
    });
  } catch {
    throw new Error(t("commun.erreur_serveur_indisponible"));
  }
  let donnees = null;
  try { donnees = await reponse.json(); } catch { /* réponse vide */ }
  if (!reponse.ok) {
    throw new Error((donnees && donnees.erreur) || t("commun.erreur_inattendue"));
  }
  return donnees;
}

/* ========================================================================
   Navigation
   ======================================================================== */

const VUES = {
  bord: vueBord,
  candidatures: vueCandidatures,
  entreprises: vueEntreprises,
  documents: () => vuePieces("documents"),
  lettres: () => vuePieces("lettres"),
  fiches: () => vuePieces("fiches"),
  entretiens: vueNotes,
  statistiques: vueStats,
  recherche: vueRecherche,
  cv: vueCv,
  comparer: vueComparateur,
  reglages: vueReglages,
};

const ACTIVATIONS = {
  candidatures: activerCandidatures,
  recherche: activerRecherche,
  comparer: activerComparateur,
  statistiques: activerStats,
  reglages: activerReglages,
  documents: () => activerPieces("documents"),
  lettres: () => activerPieces("lettres"),
  fiches: () => activerPieces("fiches"),
  entretiens: activerNotes,
  cv: activerCv,
};

async function rendre() {
  const brut = location.hash.replace(/^#\//, "");
  const conteneur = document.getElementById("vue");
  try {
    // Ce qu'on vient de taper dans une note ne doit jamais se perdre en changeant de page.
    if (etat.noteEnCours) await etat.noteEnCours.enregistrer();
    etat.noteEnCours = null;
    if (brut.startsWith("entretiens/")) {
      // Éditeur d'une note d'entretien : une page à part, sous l'entrée « Entretiens ».
      const numero = Number(brut.split("/")[1]);
      document.querySelectorAll(".nav a").forEach((lien) => {
        lien.classList.toggle("actif", lien.dataset.vue === "entretiens");
      });
      conteneur.innerHTML = await vueEditeurNote(numero);
      activerEditeurNote(numero);
      return;
    }
    const nom = VUES[brut] ? brut : "bord";
    document.querySelectorAll(".nav a").forEach((lien) => {
      lien.classList.toggle("actif", lien.dataset.vue === nom);
    });
    conteneur.innerHTML = await VUES[nom]();
    if (ACTIVATIONS[nom]) ACTIVATIONS[nom]();
  } catch (erreur) {
    conteneur.innerHTML = `<div class="etat-vide"><div class="titre">${echapper(t("commun.page_illisible_titre"))}</div><p>${echapper(erreur.message)}</p></div>`;
  }
}

window.addEventListener("hashchange", rendre);

/* ========================================================================
   Suivi de la base
   Détecte les écritures faites hors de l'appli en cours (script, IA,
   import lancé ailleurs...) pour que l'affichage suive sans avoir à
   fermer/rouvrir Azimut. On compare le mtime de suivi_candidatures.db :
   si une saisie est en cours (fenêtre ouverte ou champ actif), on se
   contente d'allumer le bouton "Actualiser" plutôt que de recharger
   sous les pieds de l'utilisateur.
   ======================================================================== */

function saisieEnCours() {
  if (pileModales.length) return true;
  const actif = document.activeElement;
  return !!actif && ["INPUT", "TEXTAREA", "SELECT"].includes(actif.tagName);
}

async function actualiser() {
  const bouton = document.getElementById("btn-actualiser");
  if (bouton) bouton.classList.remove("a-du-nouveau");
  try {
    const { version } = await api("/api/version");
    etat.versionDb = version;
  } catch { /* on retentera au prochain cycle de vérification */ }
  await rendre();
}

async function verifierVersionDb() {
  let version;
  try {
    ({ version } = await api("/api/version"));
  } catch {
    return; // serveur momentanément indisponible : on réessaiera plus tard
  }
  if (etat.versionDb === null) {
    etat.versionDb = version;
    return;
  }
  if (version === etat.versionDb) return;

  if (saisieEnCours()) {
    // On ne touche pas à ce que l'utilisateur est en train de faire :
    // on signale juste qu'une actualisation manuelle apportera du neuf.
    document.getElementById("btn-actualiser")?.classList.add("a-du-nouveau");
    return;
  }
  etat.versionDb = version;
  await rendre();
}

document.getElementById("btn-actualiser").addEventListener("click", actualiser);
setInterval(verifierVersionDb, 8000);

/* ========================================================================
   Tableau de bord
   ======================================================================== */

function barres(donnees, ordre) {
  const entrees = ordre
    ? ordre.map((libelle) => [libelle, donnees[libelle] || 0])
    : Object.entries(donnees).sort((a, b) => b[1] - a[1]);
  const maximum = Math.max(1, ...entrees.map(([, valeur]) => valeur));
  return entrees
    .map(
      ([libelle, valeur]) => `
      <div class="ligne-barre">
        <span class="libelle" title="${echapper(libelle)}">${echapper(libelle)}</span>
        <div class="piste"><div class="remplissage${valeur === 0 ? " vide" : ""}" style="width:${(valeur / maximum) * 100}%"></div></div>
        <span class="valeur">${valeur}</span>
      </div>`
    )
    .join("");
}

async function vueBord() {
  const stats = await api("/api/stats");
  if (stats.total === 0) {
    return `
      <div class="entete-vue"><h1>${t("bord.titre")}</h1></div>
      <div class="etat-vide">
        <div class="icone">${ICONES.boussole}</div>
        <div class="titre">${t("bord.bienvenue_titre")}</div>
        <p>${t("bord.bienvenue_texte")}</p>
        <button class="btn btn-accent" onclick="ouvrirFormCandidature()">${t("bord.ajouter_premiere")}</button>
      </div>`;
  }

  const entretiens = stats.entretiens_a_venir
    .map(
      (cand) => `
      <div class="echeance" onclick="ouvrirDetailCandidature(${cand.id})">
        <span class="echeance-date">${dateFr(cand.date_entretien)}</span>
        <div class="echeance-texte">
          <div class="principal">${echapper(cand.entreprise)}</div>
          <div class="secondaire">${echapper(cand.poste)}</div>
        </div>
      </div>`
    )
    .join("");

  return `
    <div class="entete-vue">
      <div>
        <h1>${t("bord.titre")}</h1>
        <div class="sous-titre">${t("bord.sous_titre")}</div>
      </div>
    </div>
    <div class="rangee-kpi">
      <div class="tuile">
        <div class="tuile-libelle">${t("bord.kpi_candidatures")}</div>
        <div class="tuile-valeur">${stats.total}</div>
        <div class="tuile-detail">${t("bord.kpi_candidatures_detail", { n: stats.en_cours })}</div>
      </div>
      <div class="tuile">
        <div class="tuile-libelle">${t("bord.kpi_taux_reponse")}</div>
        <div class="tuile-valeur">${stats.taux_reponse}<span style="font-size:18px;">%</span></div>
        <div class="tuile-detail">${t("bord.kpi_taux_reponse_detail")}</div>
      </div>
      <div class="tuile">
        <div class="tuile-libelle">${t("bord.kpi_entretiens")}</div>
        <div class="tuile-valeur">${stats.entretiens_a_venir.length}</div>
        <div class="tuile-detail">${t("bord.kpi_entretiens_detail", { n: stats.par_statut["Entretien"] })}</div>
      </div>
      <div class="tuile">
        <div class="tuile-libelle">${t("bord.kpi_preparation")}</div>
        <div class="tuile-valeur">${stats.total_lettres}</div>
        <div class="tuile-detail">${t("bord.kpi_preparation_detail", { fiches: stats.total_fiches, notes: stats.total_notes })}</div>
      </div>
    </div>
    <div class="grille-bord">
      <div class="carte">
        <h2>${t("bord.carte_par_statut")}</h2>
        ${barres(stats.par_statut, etat.valeurs.statuts)}
      </div>
      <div class="carte">
        <h2>${t("bord.carte_par_domaine")}</h2>
        ${Object.keys(stats.par_domaine).length ? barres(stats.par_domaine) : `<div class="sous-titre">${t("bord.par_domaine_vide")}</div>`}
      </div>
      <div class="carte carte-large">
        <h2>${t("bord.carte_entretiens")}</h2>
        ${entretiens || `<div class="sous-titre">${t("bord.entretiens_vide")}</div>`}
      </div>
    </div>`;
}

/* ========================================================================
   Candidatures : kanban + liste
   ======================================================================== */

function candidatureVisible(cand) {
  const f = etat.filtres;
  if (f.statut && cand.statut !== f.statut) return false;
  if (f.sous_domaine && cand.sous_domaine !== f.sous_domaine) return false;
  if (f.texte) {
    const aiguille = f.texte.toLowerCase();
    const botte = `${cand.entreprise} ${cand.poste} ${cand.ville || ""}`.toLowerCase();
    if (!botte.includes(aiguille)) return false;
  }
  return true;
}

function carteCandidature(cand) {
  const puces = [];
  if (cand.sous_domaine) {
    puces.push(`<span class="puce">${echapper(tv(cand.sous_domaine))}</span>`);
  }
  return `
    <article class="carte-cand" data-id="${cand.id}">
      <div class="entreprise">${echapper(cand.entreprise)}</div>
      <div class="poste">${echapper(cand.poste)}</div>
      <div class="meta">
        ${puces.join("")}
        <span class="date">${dateFr(cand.date_envoi)}</span>
      </div>
    </article>`;
}

/* Statut modifiable directement depuis la liste : la puce reste visible et
   un <select> natif transparent posé par-dessus ouvre le menu des statuts
   au clic (clavier et lecteurs d'écran compris). */
function selecteurStatut(cand) {
  return `
    <span class="selecteur-statut puce puce-statut" style="--couleur-statut:${COULEURS_STATUT[cand.statut]}">
      <span class="point"></span>${echapper(tv(cand.statut))}
      <svg class="chevron" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
      <select class="select-statut" data-id="${cand.id}" aria-label="${echapperAttribut(t("candidatures.changer_statut"))}">
        ${optionsSelect(etat.valeurs.statuts, cand.statut, false)}
      </select>
    </span>`;
}

function boutonLienOffre(cand) {
  if (!cand.lien_offre) return `<span class="cellule-secondaire">-</span>`;
  return `
    <a class="btn-lien-offre" href="${echapperAttribut(cand.lien_offre)}" target="_blank" rel="noopener"
       title="${echapperAttribut(cand.lien_offre)}">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
      ${t("candidatures.voir_offre")}
    </a>`;
}

function optionsSelect(liste, selection, avecVide = true) {
  const vide = avecVide ? `<option value="">-</option>` : "";
  return vide + liste
    .map((v) => `<option value="${echapper(v)}"${v === selection ? " selected" : ""}>${echapper(tv(v))}</option>`)
    .join("");
}

async function vueCandidatures() {
  const liste = (await api("/api/candidatures")).filter(candidatureVisible);
  const v = etat.valeurs;
  const filtres = `
    <div class="filtres">
      <input type="text" id="filtre-texte" placeholder="${t("candidatures.rechercher_placeholder")}" value="${echapper(etat.filtres.texte)}">
      <select id="filtre-statut">
        <option value="">${t("candidatures.tous_statuts")}</option>
        ${v.statuts.map((s) => `<option${etat.filtres.statut === s ? " selected" : ""}>${echapper(tv(s))}</option>`).join("")}
      </select>
      <select id="filtre-domaine">
        <option value="">${t("candidatures.tous_sous_domaines")}</option>
        ${v.sous_domaines.map((d) => `<option${etat.filtres.sous_domaine === d ? " selected" : ""}>${echapper(tv(d))}</option>`).join("")}
      </select>
    </div>`;

  let corps;
  if (liste.length === 0) {
    const filtreActif = etat.filtres.statut || etat.filtres.sous_domaine || etat.filtres.texte;
    corps = `
      <div class="etat-vide">
        <div class="icone">${ICONES.candidatures}</div>
        <div class="titre">${filtreActif ? t("candidatures.vide_filtre_titre") : t("candidatures.vide_titre")}</div>
        <p>${filtreActif ? t("candidatures.vide_filtre_texte") : t("candidatures.vide_texte")}</p>
        ${filtreActif ? "" : `<button class="btn btn-accent" onclick="ouvrirFormCandidature()">${t("candidatures.ajouter_bouton")}</button>`}
      </div>`;
  } else if (etat.modeCandidatures === "kanban") {
    corps = `<div class="kanban">${v.statuts
      .map((statut) => {
        const cartes = liste.filter((cand) => cand.statut === statut);
        return `
        <section class="colonne" data-statut="${echapper(statut)}" style="--couleur-statut:${COULEURS_STATUT[statut]}">
          <div class="colonne-entete">
            <span class="point"></span>${echapper(tv(statut))}
            <span class="compte">${cartes.length}</span>
          </div>
          <div class="colonne-cartes">${cartes.map(carteCandidature).join("")}</div>
        </section>`;
      })
      .join("")}</div>`;
  } else {
    // Une sélection ne survit que si les candidatures existent encore dans la liste affichée.
    const idsVisibles = new Set(liste.map((c) => c.id));
    for (const id of etat.selectionComparaison) {
      if (!idsVisibles.has(id)) etat.selectionComparaison.delete(id);
    }
    corps = `
      <div class="enveloppe-tableau"><table class="tableau">
        <thead><tr>
          <th></th><th>${t("candidatures.col_entreprise")}</th><th>${t("candidatures.col_poste")}</th><th>${t("candidatures.col_statut")}</th>
          <th>${t("candidatures.col_envoyee_le")}</th><th>${t("candidatures.col_ville")}</th><th>${t("candidatures.col_offre")}</th>
        </tr></thead>
        <tbody>
          ${liste
            .map(
              (cand) => `
            <tr onclick="ouvrirDetailCandidature(${cand.id})">
              <td onclick="event.stopPropagation()">
                <input type="checkbox" class="case-comparaison" data-id="${cand.id}"
                       ${etat.selectionComparaison.has(cand.id) ? "checked" : ""}>
              </td>
              <td class="cellule-principale">${echapper(cand.entreprise)}
                ${cand.lien_dernier_etat === "mort" ? `<span class="puce puce-lien-mort" title="${t("candidatures.lien_mort_titre")}">${t("candidatures.lien_mort")}</span>` : ""}
              </td>
              <td>${echapper(cand.poste)}</td>
              <td onclick="event.stopPropagation()">${selecteurStatut(cand)}</td>
              <td class="cellule-date">${dateFr(cand.date_envoi)}</td>
              <td class="cellule-secondaire">${echapper(cand.ville || "")}</td>
              <td onclick="event.stopPropagation()">${boutonLienOffre(cand)}</td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table></div>`;
  }

  const barreComparaison = etat.modeCandidatures === "liste" && etat.selectionComparaison.size >= 2
    ? `<div class="barre-comparaison">
        <span>${t("candidatures.selectionnees", { n: etat.selectionComparaison.size })}</span>
        <button class="btn btn-accent" onclick="location.hash='#/comparer'">${t("candidatures.comparer")}</button>
       </div>`
    : "";

  return `
    <div class="entete-vue">
      <h1>${t("nav.candidatures")}</h1>
      <div class="bascule">
        <button data-mode="kanban" class="${etat.modeCandidatures === "kanban" ? "actif" : ""}">${t("candidatures.pipeline")}</button>
        <button data-mode="liste" class="${etat.modeCandidatures === "liste" ? "actif" : ""}">${t("candidatures.liste")}</button>
      </div>
      <button class="btn btn-accent" onclick="ouvrirFormCandidature()">${t("commun.ajouter")}</button>
    </div>
    ${filtres}
    ${barreComparaison}
    ${corps}`;
}

function activerCandidatures() {
  document.querySelectorAll(".bascule button").forEach((bouton) => {
    bouton.addEventListener("click", () => {
      etat.modeCandidatures = bouton.dataset.mode;
      rendre();
    });
  });
  const brancherFiltre = (id, cle, evenement = "change") => {
    const champ = document.getElementById(id);
    if (champ) champ.addEventListener(evenement, () => {
      etat.filtres[cle] = champ.value;
      rendre();
    });
  };
  brancherFiltre("filtre-statut", "statut");
  brancherFiltre("filtre-domaine", "sous_domaine");

  document.querySelectorAll(".select-statut").forEach((select) => {
    select.addEventListener("change", async () => {
      const statut = select.value;
      try {
        await api(`/api/candidatures/${select.dataset.id}`, { methode: "PATCH", corps: { statut } });
        toast(t("candidatures.statut_mis_a_jour", { statut: tv(statut) }));
      } catch (erreur) {
        toast(erreur.message, true);
      }
      rendre();
    });
  });

  document.querySelectorAll(".case-comparaison").forEach((case_) => {
    case_.addEventListener("change", () => {
      const id = Number(case_.dataset.id);
      if (case_.checked) etat.selectionComparaison.add(id);
      else etat.selectionComparaison.delete(id);
      rendre();
    });
  });
  const recherche = document.getElementById("filtre-texte");
  if (recherche) {
    let minuteur;
    recherche.addEventListener("input", () => {
      clearTimeout(minuteur);
      minuteur = setTimeout(() => {
        etat.filtres.texte = recherche.value;
        const position = recherche.selectionStart;
        rendre().then(() => {
          const champ = document.getElementById("filtre-texte");
          if (champ) { champ.focus(); champ.setSelectionRange(position, position); }
        });
      }, 250);
    });
  }

  // Glisser-déposer entre colonnes du kanban (Pointer Events : fiable à la
  // souris comme au trackpad ; un simple clic ouvre le détail).
  document.querySelectorAll(".carte-cand").forEach((carte) => {
    carte.addEventListener("pointerdown", (depart) => {
      if (depart.button !== 0) return;
      const numero = Number(carte.dataset.id);
      const statutActuel = carte.closest(".colonne")?.dataset.statut;
      let fantome = null;
      let colonneSurvolee = null;

      const surMouvement = (mouvement) => {
        const dx = mouvement.clientX - depart.clientX;
        const dy = mouvement.clientY - depart.clientY;
        if (!fantome) {
          if (Math.hypot(dx, dy) < 6) return;
          const rect = carte.getBoundingClientRect();
          fantome = carte.cloneNode(true);
          fantome.style.cssText =
            `position:fixed;left:${rect.left}px;top:${rect.top}px;width:${rect.width}px;` +
            "margin:0;pointer-events:none;z-index:100;opacity:0.92;" +
            "box-shadow:0 12px 32px rgba(0,0,0,0.28);";
          document.body.appendChild(fantome);
          carte.classList.add("en-glisse");
        }
        fantome.style.transform = `translate(${dx}px, ${dy}px) rotate(1.5deg)`;
        const dessous = document.elementFromPoint(mouvement.clientX, mouvement.clientY);
        const colonne = dessous ? dessous.closest(".colonne") : null;
        if (colonneSurvolee && colonneSurvolee !== colonne) {
          colonneSurvolee.classList.remove("survol-depot");
        }
        colonneSurvolee = colonne;
        if (colonne) colonne.classList.add("survol-depot");
      };

      const surFin = async () => {
        document.removeEventListener("pointermove", surMouvement);
        document.removeEventListener("pointerup", surFin);
        if (!fantome) {
          ouvrirDetailCandidature(numero); // simple clic, pas un glissement
          return;
        }
        fantome.remove();
        carte.classList.remove("en-glisse");
        if (colonneSurvolee) {
          colonneSurvolee.classList.remove("survol-depot");
          const statut = colonneSurvolee.dataset.statut;
          if (statut && statut !== statutActuel) {
            try {
              await api(`/api/candidatures/${numero}`, { methode: "PATCH", corps: { statut } });
              toast(t("candidatures.statut_mis_a_jour", { statut: tv(statut) }));
              rendre();
            } catch (erreur) {
              toast(erreur.message, true);
            }
          }
        }
      };

      document.addEventListener("pointermove", surMouvement);
      document.addEventListener("pointerup", surFin);
    });
  });
}

/* ========================================================================
   Comparateur : plusieurs candidatures côte à côte
   ======================================================================== */

const CHAMPS_COMPARATEUR_ENUM = new Set(["statut", "sous_domaine", "mode_travail", "convention_envoyee", "source"]);

function criteresComparateur() {
  return [
    ["statut", t("candidatures.col_statut")],
    ["sous_domaine", t("comparateur.sous_domaine")],
    ["ville", t("candidatures.col_ville")],
    ["mode_travail", t("comparateur.mode_travail")],
    ["duree", t("comparateur.duree")],
    ["gratification", t("comparateur.gratification")],
    ["date_debut_souhaitee", t("comparateur.debut_souhaite")],
    ["convention_envoyee", t("comparateur.convention_envoyee")],
    ["source", t("comparateur.source")],
    ["date_envoi", t("candidatures.col_envoyee_le")],
    ["date_entretien", t("comparateur.entretien_le")],
  ];
}

async function vueComparateur() {
  const ids = [...etat.selectionComparaison];
  if (ids.length < 2) {
    return `
      <div class="entete-vue"><h1>${t("comparateur.titre")}</h1></div>
      <div class="etat-vide">
        <div class="icone">${ICONES.candidatures}</div>
        <div class="titre">${t("comparateur.vide_titre")}</div>
        <p>${t("comparateur.vide_texte")}</p>
        <button class="btn btn-accent" onclick="location.hash='#/candidatures'">${t("comparateur.aller_aux_candidatures")}</button>
      </div>`;
  }
  const toutes = await api("/api/candidatures");
  const selection = ids.map((id) => toutes.find((c) => c.id === id)).filter(Boolean);
  const formater = (cle, valeur) => {
    if (valeur === null || valeur === undefined || valeur === "") return "-";
    if (cle === "gratification") return `${valeur} €/mois`;
    if (cle.startsWith("date_")) return dateFr(valeur);
    if (CHAMPS_COMPARATEUR_ENUM.has(cle)) return echapper(tv(valeur));
    return echapper(valeur);
  };
  const lignes = criteresComparateur()
    .map(
      ([cle, libelle]) => `
      <tr>
        <th>${libelle}</th>
        ${selection.map((cand) => `<td>${formater(cle, cand[cle])}</td>`).join("")}
      </tr>`
    )
    .join("");
  return `
    <div class="entete-vue">
      <h1>${t("comparateur.titre")}</h1>
      <button class="btn" onclick="viderComparateur()">${t("comparateur.vider_selection")}</button>
    </div>
    <div class="enveloppe-tableau"><table class="tableau tableau-comparateur">
      <thead><tr>
        <th>${t("comparateur.critere")}</th>
        ${selection.map((cand) => `<th>${echapper(cand.entreprise)}<div class="cellule-secondaire">${echapper(cand.poste)}</div></th>`).join("")}
      </tr></thead>
      <tbody>${lignes}</tbody>
    </table></div>`;
}

function activerComparateur() { /* liens inline */ }

function viderComparateur() {
  etat.selectionComparaison.clear();
  location.hash = "#/candidatures";
}

/* ========================================================================
   Champs de formulaire
   ======================================================================== */

function champTexte(nom, libelle, valeur = "", type = "text", pleineLargeur = false) {
  return `
    <div class="champ${pleineLargeur ? " pleine-largeur" : ""}">
      <label for="champ-${nom}">${libelle}</label>
      <input type="${type}" id="champ-${nom}" name="${nom}" value="${echapper(valeur ?? "")}">
    </div>`;
}

function champSelect(nom, libelle, liste, valeur, avecVide = true) {
  return `
    <div class="champ">
      <label for="champ-${nom}">${libelle}</label>
      <select id="champ-${nom}" name="${nom}">${optionsSelect(liste, valeur, avecVide)}</select>
    </div>`;
}

function champMotDePasse(nom, libelle, valeur = "") {
  return `
    <div class="champ">
      <label for="champ-${nom}">${libelle}</label>
      <div class="champ-mdp">
        <input type="password" id="champ-${nom}" name="${nom}" value="${echapper(valeur ?? "")}" autocomplete="off">
        <button type="button" class="btn btn-discret btn-oeil" data-cible="champ-${nom}">${t("commun.afficher")}</button>
      </div>
    </div>`;
}

function champZone(nom, libelle, valeur = "") {
  return `
    <div class="champ pleine-largeur">
      <label for="champ-${nom}">${libelle}</label>
      <textarea id="champ-${nom}" name="${nom}">${echapper(valeur ?? "")}</textarea>
    </div>`;
}

function champAffiche(libelle, contenuHTML, pleineLargeur = false) {
  const vide = contenuHTML === null || contenuHTML === undefined || contenuHTML === "";
  return `
    <div class="champ${pleineLargeur ? " pleine-largeur" : ""}">
      <label>${libelle}</label>
      <div class="valeur-affichee${vide ? " vide" : ""}">${vide ? "-" : contenuHTML}</div>
    </div>`;
}

function champAfficheMotDePasse(nom, libelle, valeur) {
  return `
    <div class="champ">
      <label>${libelle}</label>
      <div class="champ-mdp">
        <input type="password" id="champ-${nom}" value="${echapper(valeur ?? "")}" readonly>
        <button type="button" class="btn btn-discret btn-oeil" data-cible="champ-${nom}">${t("commun.afficher")}</button>
      </div>
    </div>`;
}

function lireFormulaire(conteneur) {
  const donnees = {};
  conteneur.querySelectorAll("input[name], select[name], textarea[name]").forEach((champ) => {
    donnees[champ.name] = champ.value === "" ? null : champ.value;
  });
  return donnees;
}

/* ------------------------------------------------------------------------
   Nouvelle candidature : une fenêtre centrée (avec, si une clé API est
   configurée, le pré-remplissage à partir du texte d'une offre)
   ------------------------------------------------------------------------ */

async function ouvrirFormCandidature() {
  const v = etat.valeurs;
  const listeEntreprises = await api("/api/entreprises");
  const champEntreprise = `
    <div class="champ">
      <label for="champ-entreprise">${t("formulaire.entreprise_requis")}</label>
      <input type="text" id="champ-entreprise" name="entreprise" list="liste-entreprises" required>
      <datalist id="liste-entreprises">
        ${listeEntreprises.map((ent) => `<option value="${echapper(ent.nom)}">`).join("")}
      </datalist>
    </div>`;

  const corps = `
    <form id="form-candidature" class="grille-form" onsubmit="return false;">
      ${champEntreprise}
      ${champTexte("poste", t("formulaire.poste_requis"), "")}
      ${champSelect("statut", t("candidatures.col_statut"), v.statuts, "À préparer", false)}
      ${champSelect("sous_domaine", t("comparateur.sous_domaine"), v.sous_domaines, null)}
      ${champSelect("type_candidature", t("formulaire.type_candidature"), v.types_candidature, null)}
      ${champSelect("source", t("comparateur.source"), v.sources_candidature, null)}
      ${champTexte("date_envoi", t("formulaire.date_envoi"), "", "date")}
      ${champTexte("date_reponse", t("formulaire.reponse_recue_le"), "", "date")}
      ${champTexte("date_entretien", t("comparateur.entretien_le"), "", "date")}
      ${champTexte("date_debut_souhaitee", t("comparateur.debut_souhaite"), "", "date")}
      ${champTexte("duree", t("comparateur.duree"), "")}
      ${champTexte("gratification", t("comparateur.gratification"), "", "number")}
      ${champTexte("ville", t("candidatures.col_ville"), "")}
      ${champSelect("mode_travail", t("comparateur.mode_travail"), v.modes_travail, null)}
      ${champSelect("convention_envoyee", t("comparateur.convention_envoyee"), v.conventions, "Non", false)}
      ${champTexte("lien_offre", t("formulaire.lien_offre"), "", "url", true)}
      ${champTexte("portail_url", t("formulaire.portail_url"), "", "url", true)}
      ${champTexte("portail_identifiant", t("formulaire.portail_identifiant"), "")}
      ${champMotDePasse("portail_mdp", t("formulaire.portail_mdp"), "")}
      ${champZone("texte_offre", t("formulaire.texte_offre"), "")}
      ${champZone("notes", t("formulaire.notes"), "")}
    </form>`;

  // Zone d'analyse IA (si une clé API est configurée dans Réglages).
  const zoneIA = etat.ia && etat.ia.cle_api_definie
    ? `
    <div class="zone-ia">
      <label for="ia-texte">${t("formulaire.ia_prerempli_label")}</label>
      <textarea id="ia-texte" placeholder="${t("formulaire.ia_placeholder")}"></textarea>
      <div class="zone-ia-actions">
        <input type="url" id="ia-lien" placeholder="${t("formulaire.lien_offre_optionnel")}">
        <button type="button" class="btn btn-accent" id="btn-analyser">${t("formulaire.analyser")}</button>
      </div>
    </div>`
    : `
    <p class="astuce-ia">${t("formulaire.astuce_ia_debut")}
      <a class="lien-detail" href="#/reglages" onclick="fermerModale()">${t("nav.reglages")}</a>
      ${t("formulaire.astuce_ia_fin")}</p>`;

  // Joindre tout de suite un ou plusieurs fichiers (offre en PDF, CV, lettre…) :
  // envoyés juste après la création de la candidature.
  const zoneDocuments = `
    <div class="zone-ia">
      <label for="fichiers-a-joindre">${t("formulaire.joindre_fichiers")}</label>
      <div class="zone-ia-actions">
        <select id="fichiers-type" style="max-width:220px;">${optionsSelect(v.types_document, "Offre (PDF)", false)}</select>
        <input type="file" id="fichiers-a-joindre" multiple style="flex:1;">
      </div>
    </div>`;

  ouvrirModale(
    t("formulaire.nouvelle_candidature"),
    zoneIA + corps + zoneDocuments,
    `<button class="btn" onclick="fermerModale()">${t("commun.annuler")}</button>
     <button class="btn btn-accent" id="btn-enregistrer">${t("formulaire.ajouter_candidature")}</button>`,
    false, true
  );

  etat.propositionEntreprise = null;
  const boutonAnalyser = document.getElementById("btn-analyser");
  if (boutonAnalyser) {
    boutonAnalyser.addEventListener("click", async () => {
      const texte = document.getElementById("ia-texte").value;
      if (!texte.trim()) { toast(t("formulaire.coller_texte_offre_erreur"), true); return; }
      boutonAnalyser.disabled = true;
      boutonAnalyser.textContent = t("formulaire.analyse_en_cours");
      try {
        const proposition = await api("/api/agent/analyser", {
          methode: "POST",
          corps: { texte, lien: document.getElementById("ia-lien").value || null },
        });
        remplirDepuisProposition(proposition);
        etat.propositionEntreprise = proposition.entreprise && proposition.entreprise.nom
          ? proposition.entreprise : null;
        toast(t("formulaire.pre_rempli"));
        if (proposition.avertissement) toast(proposition.avertissement, true);
      } catch (erreur) {
        toast(erreur.message, true);
      } finally {
        boutonAnalyser.disabled = false;
        boutonAnalyser.textContent = t("formulaire.analyser");
      }
    });
  }

  document.getElementById("btn-enregistrer").addEventListener("click", async () => {
    const donnees = lireFormulaire(document.getElementById("form-candidature"));
    try {
      // Avertissement (non bloquant) : intitulé proche ou même lien d'offre
      // qu'une candidature déjà enregistrée. Le vrai doublon (entreprise +
      // poste identiques) reste, lui, refusé net par le serveur.
      const parametres = new URLSearchParams({
        entreprise: donnees.entreprise || "",
        poste: donnees.poste || "",
        lien_offre: donnees.lien_offre || "",
      });
      const similaires = await api(`/api/candidatures/similaires?${parametres}`);
      if (similaires.length && !(await confirmerSimilaires(similaires))) return;
      const creee = await api("/api/candidatures", { methode: "POST", corps: donnees });
      toast(t("formulaire.candidature_ajoutee", { poste: creee.poste, entreprise: creee.entreprise }));
      // Fichiers joints : envoyés maintenant que la candidature existe.
      const fichiersAJoindre = document.getElementById("fichiers-a-joindre")?.files;
      if (fichiersAJoindre && fichiersAJoindre.length) {
        await televerserDocument(creee.id, fichiersAJoindre, document.getElementById("fichiers-type").value, null);
      }
      // Infos entreprise proposées par l'IA : écrites seulement maintenant,
      // après validation (les champs déjà remplis ne sont jamais écrasés).
      const proposition = etat.propositionEntreprise;
      etat.propositionEntreprise = null;
      if (proposition && (proposition.site_web || proposition.contexte_actus)) {
        try {
          await api("/api/entreprises", { methode: "POST", corps: proposition });
        } catch (erreurEntreprise) {
          toast(erreurEntreprise.message, true);
        }
      }
      fermerModale();
      rendre();
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });
}

function remplirDepuisProposition(proposition) {
  const fixer = (nom, valeur) => {
    const champ = document.getElementById(`champ-${nom}`);
    if (champ && valeur !== null && valeur !== undefined && valeur !== "") champ.value = valeur;
  };
  if (proposition.entreprise && proposition.entreprise.nom) {
    fixer("entreprise", proposition.entreprise.nom);
  }
  const cand = proposition.candidature || {};
  [
    "poste", "sous_domaine", "type_candidature", "ville", "mode_travail", "duree",
    "gratification", "date_debut_souhaitee", "source", "lien_offre", "texte_offre",
  ].forEach((nom) => fixer(nom, cand[nom]));
}

/* ------------------------------------------------------------------------
   Détail d'une candidature : une fenêtre centrée dont chaque champ se modifie
   directement - pas de bouton « Modifier » à presser d'abord : chaque
   changement est enregistré tout de suite (les textes, un instant après la
   dernière frappe).
   ------------------------------------------------------------------------ */

/* Édition directe d'une fenêtre de détail (candidature, entreprise) : chaque champ portant
   `data-champ` est enregistré tout de suite (listes et dates au changement, textes un instant
   après la dernière frappe) ; rien à valider. `options` :
     donnees()             l'objet affiché (relu à chaque enregistrement) ;
     envoyer(nom, valeur)  écrit un champ et retourne l'objet mis à jour ;
     fusionner(misAJour)   met à jour l'objet affiché ;
     verifier(nom, valeur) message d'erreur à afficher (et valeur refusée), sinon rien ;
     apres(nom)            réaction à un champ enregistré (rafraîchir un bloc lié...).
   Retourne { signaler, envoyerEnAttente, annulerEnAttente, aModifie, marquerModifie }. */
function editionDirecte(zone, options) {
  let modifie = false;
  const enAttente = new Map(); // champ -> minuteur d'un texte en cours de frappe
  const indicateur = zone.racine.querySelector(".modale-etat");
  let minuteurIndicateur = null;
  const signaler = (texte) => {
    indicateur.textContent = texte;
    indicateur.classList.toggle("visible", !!texte);
    clearTimeout(minuteurIndicateur);
    if (texte) minuteurIndicateur = setTimeout(() => { indicateur.classList.remove("visible"); }, 2400);
  };

  async function enregistrerChamp(nom, brut) {
    const champ = zone.racine.querySelector(`[data-champ="${nom}"]`);
    const donnees = options.donnees();
    const valeur = brut === "" ? null : brut;
    const actuelle = donnees[nom] === undefined ? null : donnees[nom];
    if (String(valeur ?? "") === String(actuelle ?? "")) return;
    const refus = options.verifier ? options.verifier(nom, valeur) : null;
    if (refus) {
      champ.value = actuelle ?? "";
      toast(refus, true);
      return;
    }
    signaler(t("formulaire.enregistrement_en_cours"));
    try {
      options.fusionner(await options.envoyer(nom, valeur));
      modifie = true;
      signaler(t("formulaire.enregistre"));
      if (options.apres) await options.apres(nom);
    } catch (erreur) {
      signaler("");
      champ.value = actuelle ?? "";
      toast(erreur.message, true);
    }
  }

  function annulerEnAttente() {
    enAttente.forEach((minuteur) => clearTimeout(minuteur));
    enAttente.clear();
  }

  async function envoyerEnAttente() {
    const noms = [...enAttente.keys()];
    annulerEnAttente();
    for (const nom of noms) {
      const champ = zone.racine.querySelector(`[data-champ="${nom}"]`);
      if (champ) await enregistrerChamp(nom, champ.value);
    }
  }

  zone.corps.addEventListener("change", (evenement) => {
    const nom = evenement.target.dataset && evenement.target.dataset.champ;
    if (!nom) return;
    clearTimeout(enAttente.get(nom));
    enAttente.delete(nom);
    enregistrerChamp(nom, evenement.target.value);
  });
  zone.corps.addEventListener("input", (evenement) => {
    const cible = evenement.target;
    const nom = cible.dataset && cible.dataset.champ;
    if (!nom || !(cible.tagName === "TEXTAREA" || cible.type === "text" || cible.type === "url")) return;
    clearTimeout(enAttente.get(nom));
    enAttente.set(nom, setTimeout(() => { enAttente.delete(nom); enregistrerChamp(nom, cible.value); }, 900));
  });
  zone.corps.addEventListener("keydown", (evenement) => {
    if (evenement.key === "Enter" && evenement.target.tagName === "INPUT") evenement.target.blur();
  });

  return {
    signaler, envoyerEnAttente, annulerEnAttente,
    aModifie: () => modifie,
    marquerModifie: () => { modifie = true; },
  };
}

/* Champs de la fenêtre de détail. */
function champDetail(nom, libelle, valeur, type = "text", pleineLargeur = false) {
  return `
    <div class="champ${pleineLargeur ? " pleine-largeur" : ""}">
      <label for="detail-${nom}">${libelle}</label>
      <input type="${type}" id="detail-${nom}" data-champ="${nom}" value="${echapperAttribut(valeur ?? "")}"${type === "number" ? ' min="0" step="1"' : ""}>
    </div>`;
}

function selectDetail(nom, libelle, liste, valeur, avecVide = true) {
  return `
    <div class="champ">
      <label for="detail-${nom}">${libelle}</label>
      <select id="detail-${nom}" data-champ="${nom}">${optionsSelect(liste, valeur, avecVide)}</select>
    </div>`;
}

function zoneDetail(nom, libelle, valeur) {
  return `
    <div class="champ pleine-largeur">
      <label for="detail-${nom}">${libelle}</label>
      <textarea id="detail-${nom}" data-champ="${nom}" class="zone-longue">${echapper(valeur ?? "")}</textarea>
    </div>`;
}

function pastilleStatutDetail(statut) {
  return `
    <span class="selecteur-statut puce puce-statut grande" style="--couleur-statut:${COULEURS_STATUT[statut]}">
      <span class="point"></span>${echapper(tv(statut))}
      <svg class="chevron" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
      <select data-champ="statut" aria-label="${echapperAttribut(t("candidatures.changer_statut"))}">
        ${optionsSelect(etat.valeurs.statuts, statut, false)}
      </select>
    </span>`;
}

function annexesCandidature(numero, lettresLiees, fichesLiees, notesLiees, docs, journal) {
  const lignesDocs = docs.map((doc) => `
    <div class="ligne-liee" onclick="ouvrirApercuPiece('documents', ${doc.id})">
      <span class="puce">${echapper(tv(doc.type_document || "Autre"))}</span>
      <span class="cellule-principale">${echapper(doc.titre)}</span>
      <span class="cellule-secondaire">${dateFr(doc.date_creation)}</span>
    </div>`).join("");
  const lignesJournal = journal.map((evenement) => `
    <div class="ligne-journal">
      <span class="journal-date">${dateFr(evenement.horodatage.slice(0, 10))} ${echapper(evenement.horodatage.slice(11, 16))}</span>
      <span>${echapper(evenement.description)}</span>
    </div>`).join("");
  return `
    ${sectionPreparation(lettresLiees, fichesLiees, notesLiees, [], `nouvelleNotePourOffre(${numero})`)}
    <h3 class="section-panneau">${t("formulaire.documents_envoyes")}</h3>
    ${lignesDocs ? `<div class="liste-liee">${lignesDocs}</div>` : `<p class="sous-titre">${t("formulaire.aucun_document")}</p>`}
    <div class="actions-reglages"><button type="button" class="btn" id="btn-ajouter-document">${t("formulaire.ajouter_document")}</button></div>
    <h3 class="section-panneau">${t("formulaire.historique")}</h3>
    <div class="journal">${lignesJournal || `<p class="sous-titre">${t("formulaire.aucun_evenement")}</p>`}</div>`;
}

async function ouvrirDetailCandidature(numero) {
  let cand;
  try {
    cand = await api(`/api/candidatures/${numero}`);
  } catch (erreur) {
    toast(erreur.message, true);
    return;
  }
  const v = etat.valeurs;
  const chargerAnnexes = () => Promise.all([
    api(`/api/lettres?candidature=${numero}`),
    api(`/api/fiches?candidature=${numero}`),
    api(`/api/notes?candidature=${numero}`),
    api(`/api/documents?candidature=${numero}`),
    api(`/api/candidatures/${numero}/evenements`),
  ]);
  const annexes = await chargerAnnexes();
  let nbNotes = annexes[2].length;

  const lienOffre = () => (cand.lien_offre
    ? `<a class="btn btn-mini" id="detail-ouvrir-offre" href="${echapperAttribut(cand.lien_offre)}" target="_blank" rel="noopener">${t("candidatures.voir_offre")}</a>${cand.lien_dernier_etat === "mort" ? ` <span class="puce puce-lien-mort">${t("candidatures.lien_mort")}</span>` : ""}`
    : "");

  const corps = `
    <div class="detail-candidature">
      <div class="detail-tete">
        <div class="detail-titre">
          <input type="text" class="detail-poste" id="detail-poste" data-champ="poste" value="${echapperAttribut(cand.poste)}" aria-label="${echapperAttribut(t("formulaire.poste_requis"))}">
          <p class="fiche-soustitre"><a class="lien-detail" href="#" id="detail-entreprise">${echapper(cand.entreprise)}</a></p>
        </div>
        <span id="detail-statut">${pastilleStatutDetail(cand.statut)}</span>
      </div>

      <h3 class="section-panneau">${t("formulaire.section_suivi")}</h3>
      <div class="grille-detail">
        ${champDetail("date_envoi", t("formulaire.date_envoi"), cand.date_envoi, "date")}
        ${champDetail("date_reponse", t("formulaire.reponse_recue_le"), cand.date_reponse, "date")}
        ${champDetail("date_entretien", t("comparateur.entretien_le"), cand.date_entretien, "date")}
        ${champDetail("date_debut_souhaitee", t("comparateur.debut_souhaite"), cand.date_debut_souhaitee, "date")}
        ${selectDetail("source", t("comparateur.source"), v.sources_candidature, cand.source)}
        ${selectDetail("type_candidature", t("formulaire.type_candidature"), v.types_candidature, cand.type_candidature)}
        ${selectDetail("convention_envoyee", t("comparateur.convention_envoyee"), v.conventions, cand.convention_envoyee || "Non", false)}
      </div>

      <h3 class="section-panneau">${t("formulaire.section_poste")}</h3>
      <div class="grille-detail">
        ${selectDetail("sous_domaine", t("comparateur.sous_domaine"), v.sous_domaines, cand.sous_domaine)}
        ${champDetail("duree", t("comparateur.duree"), cand.duree)}
        ${champDetail("gratification", t("formulaire.gratification_label"), cand.gratification, "number")}
        ${champDetail("ville", t("candidatures.col_ville"), cand.ville)}
        ${selectDetail("mode_travail", t("comparateur.mode_travail"), v.modes_travail, cand.mode_travail)}
      </div>

      <h3 class="section-panneau">${t("formulaire.section_liens")}</h3>
      <div class="grille-detail">
        <div class="champ pleine-largeur">
          <label for="detail-lien_offre">${t("formulaire.lien_offre")}</label>
          <div class="champ-avec-action">
            <input type="url" id="detail-lien_offre" data-champ="lien_offre" value="${echapperAttribut(cand.lien_offre ?? "")}">
            <span id="detail-lien-actions">${lienOffre()}</span>
          </div>
        </div>
        ${champDetail("portail_url", t("formulaire.portail_url"), cand.portail_url, "url", true)}
        ${champDetail("portail_identifiant", t("formulaire.portail_identifiant"), cand.portail_identifiant)}
        <div class="champ">
          <label for="detail-portail_mdp">${t("formulaire.portail_mdp")}</label>
          <div class="champ-mdp">
            <input type="password" id="detail-portail_mdp" data-champ="portail_mdp" value="${echapperAttribut(cand.portail_mdp ?? "")}" autocomplete="off">
            <button type="button" class="btn btn-discret btn-oeil" data-cible="detail-portail_mdp">${t("commun.afficher")}</button>
          </div>
        </div>
      </div>

      <h3 class="section-panneau">${t("formulaire.texte_offre")}</h3>
      <div class="grille-detail">${zoneDetail("texte_offre", "", cand.texte_offre)}</div>
      <h3 class="section-panneau">${t("formulaire.notes")}</h3>
      <div class="grille-detail">${zoneDetail("notes", "", cand.notes)}</div>

      <div id="detail-annexes">${annexesCandidature(numero, ...annexes)}</div>
    </div>`;

  let edition = null;
  const zone = ouvrirModale(
    cand.entreprise,
    corps,
    `<button class="btn btn-danger" id="btn-supprimer" style="margin-right:auto;">${t("commun.supprimer")}</button>
     <button class="btn" id="btn-recap">${t("formulaire.recapitulatif")}</button>
     <button class="btn btn-accent" onclick="fermerModale()">${t("commun.fermer")}</button>`,
    false, true,
    {
      avecEtat: true,
      surFermeture: async () => {
        await edition.envoyerEnAttente();
        if (edition.aModifie()) rendre();
      },
    }
  );
  edition = editionDirecte(zone, {
    donnees: () => cand,
    envoyer: (nom, valeur) => api(`/api/candidatures/${numero}`, { methode: "PATCH", corps: { [nom]: valeur } }),
    fusionner: (misAJour) => { cand = { ...cand, ...misAJour }; },
    verifier: (nom, valeur) => (nom === "poste" && !valeur ? t("formulaire.poste_obligatoire") : null),
    apres: async (nom) => {
      if (nom === "statut") {
        zone.racine.querySelector("#detail-statut").innerHTML = pastilleStatutDetail(cand.statut);
        await rafraichirAnnexes();
      }
      if (nom === "lien_offre") zone.racine.querySelector("#detail-lien-actions").innerHTML = lienOffre();
      if (nom === "date_entretien") {
        // Azimut crée (ou déplace) tout seul la note d'entretien de cette date.
        const avant = nbNotes;
        await rafraichirAnnexes();
        if (nbNotes > avant) toast(t("candidatures.note_entretien_creee"));
      }
    },
  });

  async function rafraichirAnnexes() {
    const conteneur = zone.racine.querySelector("#detail-annexes");
    if (!conteneur) return;
    const donnees = await chargerAnnexes();
    nbNotes = donnees[2].length;
    conteneur.innerHTML = annexesCandidature(numero, ...donnees);
    brancherAnnexes();
  }

  function brancherAnnexes() {
    const ajouter = zone.racine.querySelector("#btn-ajouter-document");
    if (ajouter) {
      ajouter.addEventListener("click", () => ouvrirImportPiece("documents", {
        entrepriseFixe: cand.entreprise_id, offreIds: [cand.id], apres: rafraichirAnnexes,
      }));
    }
  }

  zone.racine.querySelector("#detail-entreprise").addEventListener("click", (evenement) => {
    evenement.preventDefault();
    ouvrirDetailEntreprise(cand.entreprise_id);
  });
  brancherAnnexes();

  zone.racine.querySelector("#btn-recap").addEventListener("click", () => ouvrirRecapitulatif(numero));
  zone.racine.querySelector("#btn-supprimer").addEventListener("click", async () => {
    const accord = await confirmer(
      t("formulaire.supprimer_candidature_titre"),
      t("formulaire.supprimer_candidature_texte", { poste: cand.poste, entreprise: cand.entreprise })
    );
    if (!accord) return;
    try {
      await api(`/api/candidatures/${numero}`, { methode: "DELETE" });
      toast(t("formulaire.candidature_supprimee"));
      edition.marquerModifie();
      edition.annulerEnAttente(); // plus rien à enregistrer : la candidature n'existe plus
      fermerModale(zone);
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });
}

/* ========================================================================
   Entreprises
   ======================================================================== */

async function vueEntreprises() {
  const [liste, paires] = await Promise.all([
    api("/api/entreprises"),
    api("/api/entreprises/doublons_suspects"),
  ]);
  const cartes = liste
    .map(
      (ent) => `
    <div class="carte carte-entreprise" onclick="ouvrirDetailEntreprise(${ent.id})">
      <div class="nom">${echapper(ent.nom)}</div>
      ${ent.site_web ? `<a class="site" href="${echapper(ent.site_web)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${echapper(ent.site_web)}</a>` : ""}
      <div class="contexte">${echapper(ent.contexte_actus || t("entreprises.pas_de_contexte"))}</div>
      <div class="compteurs">
        <span class="puce">${pluriel("entreprises.nb_candidatures", ent.nb_candidatures)}</span>
        ${ent.nb_documents ? `<span class="puce">${pluriel("entreprises.nb_documents", ent.nb_documents)}</span>` : ""}
        ${ent.nb_lettres ? `<span class="puce">${pluriel("entreprises.nb_lettres", ent.nb_lettres)}</span>` : ""}
        ${ent.nb_fiches ? `<span class="puce">${pluriel("entreprises.nb_fiches", ent.nb_fiches)}</span>` : ""}
        ${ent.nb_notes ? `<span class="puce">${pluriel("entreprises.nb_notes", ent.nb_notes)}</span>` : ""}
        ${ent.derniere_recherche ? `<span class="puce" title="${t("entreprises.derniere_recherche")}">${t("entreprises.recherche_du", { date: dateFr(ent.derniere_recherche) })}</span>` : ""}
      </div>
    </div>`
    )
    .join("");

  const banniereFusion = paires.length
    ? `<div class="banniere-fusion">
        <span>${t(paires.length > 1 ? "entreprises.doublons_detectes_pluriel" : "entreprises.doublons_detectes_singulier", { n: paires.length })} (ex. « ${echapper(paires[0].a.nom)} » / « ${echapper(paires[0].b.nom)} »)</span>
        <button class="btn" onclick="ouvrirFusionEntreprises()">${t("entreprises.verifier")}</button>
      </div>`
    : "";

  return `
    <div class="entete-vue">
      <h1>${t("nav.entreprises")}</h1>
      <button class="btn btn-accent" onclick="ouvrirCreationEntreprise()">${t("commun.ajouter")}</button>
    </div>
    ${banniereFusion}
    ${liste.length ? `<div class="grille-entreprises">${cartes}</div>` : `
      <div class="etat-vide">
        <div class="icone">${ICONES.entreprises}</div>
        <div class="titre">${t("entreprises.vide_titre")}</div>
        <p>${t("entreprises.vide_texte")}</p>
        <button class="btn btn-accent" onclick="ouvrirCreationEntreprise()">${t("entreprises.ajouter_bouton")}</button>
      </div>`}`;
}

async function ouvrirFusionEntreprises() {
  const [paires, liste] = await Promise.all([
    api("/api/entreprises/doublons_suspects"),
    api("/api/entreprises"),
  ]);
  const parId = Object.fromEntries(liste.map((e) => [e.id, e]));
  const ligne = (paire) => {
    const a = parId[paire.a.id] || paire.a;
    const b = parId[paire.b.id] || paire.b;
    const bouton = (garder, fusionner) => `
      <button type="button" class="btn btn-fusion" data-conserver="${garder.id}" data-supprimer="${fusionner.id}">
        ${t("entreprises.garder", { nom: echapper(garder.nom) })}
        <span class="cellule-secondaire">${t("entreprises.fusionner_dedans", { cand: garder.nb_candidatures ?? 0, prep: (garder.nb_documents ?? 0) + (garder.nb_lettres ?? 0) + (garder.nb_fiches ?? 0) + (garder.nb_notes ?? 0), nom: echapper(fusionner.nom) })}</span>
      </button>`;
    return `
      <div class="paire-fusion">
        <div class="paire-fusion-titre">
          <strong>${echapper(a.nom)}</strong> <span class="cellule-secondaire">↔</span> <strong>${echapper(b.nom)}</strong>
          <span class="puce">${t("entreprises.pourcent_proche", { p: Math.round(paire.score * 100) })}</span>
        </div>
        <div class="paire-fusion-actions">
          ${bouton(a, b)}
          ${bouton(b, a)}
        </div>
      </div>`;
  };
  ouvrirModale(
    t("entreprises.fusion_titre"),
    paires.length
      ? `<div class="liste-paires-fusion">${paires.map(ligne).join("")}</div>
         <p class="sous-titre">${t("entreprises.fusion_avertissement")}</p>`
      : `<p>${t("entreprises.aucun_doublon")}</p>`,
    `<button class="btn btn-accent" onclick="fermerModale()">${t("commun.fermer")}</button>`
  );
  document.querySelectorAll(".btn-fusion").forEach((bouton) => {
    bouton.addEventListener("click", async () => {
      const conserver = Number(bouton.dataset.conserver);
      const supprimer = Number(bouton.dataset.supprimer);
      try {
        const resultat = await api("/api/entreprises/fusionner", {
          methode: "POST",
          corps: { conserver, supprimer },
        });
        fermerModale();
        toast(
          t("entreprises.fusion_effectuee", {
            cand: resultat.candidatures_deplacees,
            prep: resultat.documents_deplaces + resultat.lettres_deplacees + resultat.fiches_deplacees + resultat.notes_deplacees,
            nom: resultat.nom,
          })
        );
        rendre();
      } catch (erreur) {
        toast(erreur.message, true);
      }
    });
  });
}

/* Création : un petit formulaire dans une fenêtre. Une fois l'entreprise créée, on ouvre tout de
   suite sa fiche, où chaque champ se modifie sur place. */
function ouvrirCreationEntreprise() {
  const zone = ouvrirModale(
    t("entreprises.nouvelle_entreprise"),
    `<form id="form-entreprise" class="grille-form" onsubmit="return false;">
      ${champTexte("nom", t("entreprises.nom_requis"), "", "text", true)}
      ${champTexte("site_web", t("entreprises.site_web"), "", "url", true)}
      ${champZone("contexte_actus", t("entreprises.contexte_label"), "")}
      ${champTexte("derniere_recherche", t("entreprises.derniere_recherche_le"), "", "date", true)}
    </form>`,
    `<button class="btn" onclick="fermerModale()">${t("commun.annuler")}</button>
     <button class="btn btn-accent" id="btn-enregistrer">${t("entreprises.ajouter_entreprise")}</button>`
  );
  const enregistrer = async () => {
    const donnees = lireFormulaire(zone.racine.querySelector("#form-entreprise"));
    const { derniere_recherche: derniere, ...creation } = donnees;
    try {
      const { id } = await api("/api/entreprises", { methode: "POST", corps: creation });
      if (derniere) await api(`/api/entreprises/${id}`, { methode: "PATCH", corps: { derniere_recherche: derniere } });
      toast(t("entreprises.entreprise_enregistree"));
      fermerModale(zone);
      rendre();
      ouvrirDetailEntreprise(id);
    } catch (erreur) {
      toast(erreur.message, true);
    }
  };
  zone.racine.querySelector("#btn-enregistrer").addEventListener("click", enregistrer);
  const nom = zone.racine.querySelector('[name="nom"]');
  if (nom) nom.focus();
}

function annexesEntreprise(numero, candidaturesEnt, lettresEnt, fichesEnt, notesEnt, docsEnt) {
  const ligneCandidature = (c) => `
    <div class="ligne-liee" onclick="ouvrirDetailCandidature(${c.id})">
      <span class="cellule-principale">${echapper(c.poste)}</span>
      <span class="puce puce-statut" style="--couleur-statut:${COULEURS_STATUT[c.statut]}"><span class="point"></span>${echapper(tv(c.statut))}</span>
    </div>`;
  return `
    <h3 class="section-panneau">${t("entreprises.candidatures_titre", { n: candidaturesEnt.length })}</h3>
    ${candidaturesEnt.length ? `<div class="liste-liee">${candidaturesEnt.map(ligneCandidature).join("")}</div>` : `<p class="sous-titre">${t("entreprises.aucune_candidature")}</p>`}
    ${sectionPreparation(lettresEnt, fichesEnt, notesEnt, docsEnt, `nouvelleNotePourEntreprise(${numero})`)}`;
}

/* Fiche d'une entreprise : une fenêtre centrée dont chaque champ se modifie sur place, comme le
   détail d'une candidature (voir editionDirecte). */
async function ouvrirDetailEntreprise(numero) {
  const chargerAnnexes = async () => {
    const [listeCandidatures, lettresEnt, fichesEnt, notesEnt, docsEnt] = await Promise.all([
      api("/api/candidatures"),
      api(`/api/lettres?entreprise=${numero}`),
      api(`/api/fiches?entreprise=${numero}`),
      api(`/api/notes?entreprise=${numero}`),
      api(`/api/documents?entreprise=${numero}`),
    ]);
    return [listeCandidatures.filter((c) => c.entreprise_id === numero), lettresEnt, fichesEnt, notesEnt, docsEnt];
  };
  let ent;
  let annexes;
  try {
    const liste = await api("/api/entreprises");
    ent = liste.find((e) => e.id === numero);
    if (!ent) { toast(t("entreprises.introuvable"), true); return; }
    annexes = await chargerAnnexes();
  } catch (erreur) {
    toast(erreur.message, true);
    return;
  }

  const lienSite = () => (ent.site_web
    ? `<a class="btn btn-mini" href="${echapperAttribut(/^https?:\/\//i.test(ent.site_web) ? ent.site_web : `https://${ent.site_web}`)}" target="_blank" rel="noopener">${t("entreprises.ouvrir_site")}</a>`
    : "");

  const corps = `
    <div class="detail-candidature">
      <div class="detail-tete">
        <div class="detail-titre">
          <input type="text" class="detail-poste" id="detail-nom" data-champ="nom" value="${echapperAttribut(ent.nom)}" aria-label="${echapperAttribut(t("entreprises.nom_requis"))}">
        </div>
      </div>

      <h3 class="section-panneau">${t("entreprises.section_infos")}</h3>
      <div class="grille-detail">
        <div class="champ pleine-largeur">
          <label for="detail-site_web">${t("entreprises.site_web")}</label>
          <div class="champ-avec-action">
            <input type="url" id="detail-site_web" data-champ="site_web" value="${echapperAttribut(ent.site_web ?? "")}">
            <span id="detail-site-actions">${lienSite()}</span>
          </div>
        </div>
        ${champDetail("derniere_recherche", t("entreprises.derniere_recherche_le"), ent.derniere_recherche, "date")}
      </div>

      <h3 class="section-panneau">${t("entreprises.contexte_actus")}</h3>
      <div class="grille-detail">${zoneDetail("contexte_actus", "", ent.contexte_actus)}</div>

      <div id="detail-annexes">${annexesEntreprise(numero, ...annexes)}</div>
    </div>`;

  let edition = null;
  const zone = ouvrirModale(
    ent.nom,
    corps,
    `<button class="btn btn-danger" id="btn-supprimer" style="margin-right:auto;">${t("commun.supprimer")}</button>
     <button class="btn btn-accent" onclick="fermerModale()">${t("commun.fermer")}</button>`,
    false, false,
    {
      avecEtat: true,
      surFermeture: async () => {
        await edition.envoyerEnAttente();
        if (edition.aModifie()) rendre();
      },
    }
  );
  edition = editionDirecte(zone, {
    donnees: () => ent,
    envoyer: (nom, valeur) => api(`/api/entreprises/${numero}`, { methode: "PATCH", corps: { [nom]: valeur } }),
    fusionner: (misAJour) => { ent = { ...ent, ...misAJour }; },
    verifier: (nom, valeur) => (nom === "nom" && !valeur ? t("entreprises.nom_obligatoire") : null),
    apres: (nom) => {
      if (nom === "nom") zone.racine.querySelector(".modale-titre").textContent = ent.nom;
      if (nom === "site_web") zone.racine.querySelector("#detail-site-actions").innerHTML = lienSite();
    },
  });

  zone.racine.querySelector("#btn-supprimer").addEventListener("click", async () => {
    const accord = await confirmer(t("entreprises.supprimer_titre"), t("entreprises.supprimer_texte", { nom: ent.nom }));
    if (!accord) return;
    try {
      await api(`/api/entreprises/${numero}`, { methode: "DELETE" });
      toast(t("entreprises.entreprise_supprimee"));
      edition.marquerModifie();
      edition.annulerEnAttente(); // plus rien à enregistrer : l'entreprise n'existe plus
      fermerModale(zone);
    } catch (erreur) {
      toast(erreur.message, true); // refusé tant qu'il reste des candidatures ou des pièces liées
    }
  });
}

/* ========================================================================
   Documents : les fichiers joints à une candidature (voir preparation.js pour la liste)
   ======================================================================== */

/* Téléverse un ou plusieurs fichiers (offre en PDF, CV, lettre…) liés à UNE
   candidature (à sa création). Accepte un seul File ou une FileList/tableau. */
async function televerserDocument(candidatureId, fichiers, type, apres) {
  const liste = fichiers instanceof FileList || Array.isArray(fichiers)
    ? Array.from(fichiers)
    : fichiers ? [fichiers] : [];
  if (!liste.length) {
    toast(t("documents.choisir_fichier_dabord"), true);
    return;
  }
  let reussis = 0;
  const erreurs = [];
  for (const fichier of liste) {
    const formulaire = new FormData();
    formulaire.append("fichier", fichier);
    formulaire.append("type", type);
    try {
      const reponse = await fetch(`/api/candidatures/${candidatureId}/documents`, {
        method: "POST", body: formulaire,
      });
      const donnees = await reponse.json();
      if (!reponse.ok) throw new Error(donnees.erreur || t("documents.envoi_impossible"));
      reussis += 1;
    } catch (erreur) {
      erreurs.push(`${fichier.name} : ${erreur.message}`);
    }
  }
  if (reussis) {
    toast(reussis === 1 ? t("documents.ajoutee") : t("documents.documents_ajoutes", { n: reussis }));
  }
  erreurs.forEach((message) => toast(message, true));
  if (reussis && apres) apres();
}

/* ========================================================================
   Statistiques avancées
   ======================================================================== */

function graphiqueHebdomadaire(serie) {
  const largeur = 600;
  const hauteur = 140;
  const marge = { haut: 10, bas: 20, cote: 6 };
  const zoneH = hauteur - marge.haut - marge.bas;
  const zoneL = largeur - marge.cote * 2;
  const maximum = Math.max(1, ...serie.map((s) => s.nombre));
  const pas = serie.length > 1 ? zoneL / (serie.length - 1) : 0;
  const points = serie.map((s, i) => ({
    ...s,
    x: marge.cote + i * pas,
    y: marge.haut + zoneH - (s.nombre / maximum) * zoneH,
  }));
  const chemin = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const base = marge.haut + zoneH;
  const aire = `${chemin} L${points[points.length - 1].x.toFixed(1)},${base} L${points[0].x.toFixed(1)},${base} Z`;
  const cercles = points
    .map((p) => `
      <circle class="point-graphique" cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="3">
        <title>${t("statistiques.semaine_info", { debut: dateFr(p.debut), fin: dateFr(p.fin), n: p.nombre })}</title>
      </circle>`)
    .join("");
  const premiere = points[0];
  const derniere = points[points.length - 1];
  return `
    <svg viewBox="0 0 ${largeur} ${hauteur}" class="graphique-ligne" preserveAspectRatio="none" role="img" aria-label="${t("statistiques.graphique_titre")}">
      <line x1="${marge.cote}" y1="${base}" x2="${largeur - marge.cote}" y2="${base}" class="axe-graphique"/>
      <path d="${aire}" class="aire-graphique"/>
      <path d="${chemin}" class="trait-graphique"/>
      ${cercles}
      <text x="${premiere.x}" y="${hauteur - 4}" class="etiquette-graphique">${dateFr(premiere.debut)}</text>
      <text x="${derniere.x}" y="${hauteur - 4}" class="etiquette-graphique" text-anchor="end">${dateFr(derniere.debut)}</text>
    </svg>`;
}

async function vueStats() {
  const stats = await api("/api/stats/avancees");
  const liens = await api("/api/liens/etat");
  const obj = stats.objectif_hebdomadaire;
  if (!stats.total) {
    return `
      <div class="entete-vue"><h1>${t("nav.statistiques")}</h1></div>
      <div class="etat-vide">
        <div class="icone">${ICONES.candidatures}</div>
        <div class="titre">${t("statistiques.pas_de_donnees")}</div>
        <p>${t("statistiques.pas_de_donnees_texte")}</p>
      </div>`;
  }
  const maximum = Math.max(1, ...stats.entonnoir.map((e) => e.nombre));
  const entonnoir = stats.entonnoir
    .map(
      (etape) => `
      <div class="ligne-barre">
        <span class="libelle">${echapper(tv(etape.etape))}</span>
        <div class="piste"><div class="remplissage${etape.nombre === 0 ? " vide" : ""}" style="width:${(etape.nombre / maximum) * 100}%"></div></div>
        <span class="valeur">${etape.nombre}<span class="taux-detail"> · ${etape.taux}%</span></span>
      </div>`
    )
    .join("");
  const sources = stats.par_source
    .map(
      (source) => `
      <tr>
        <td class="cellule-principale">${echapper(tv(source.source))}</td>
        <td>${source.envoyees}</td>
        <td>${source.reponses}</td>
        <td>
          <div class="ligne-barre ligne-barre-compacte">
            <div class="piste"><div class="remplissage${source.taux === 0 ? " vide" : ""}" style="width:${source.taux}%"></div></div>
            <span class="valeur">${source.taux}%</span>
          </div>
        </td>
      </tr>`
    )
    .join("");
  return `
    <div class="entete-vue">
      <div><h1>${t("nav.statistiques")}</h1><div class="sous-titre">${t("statistiques.sous_titre")}</div></div>
    </div>
    <div class="rangee-kpi">
      <div class="tuile">
        <div class="tuile-libelle">${t("statistiques.delai_reponse")}</div>
        <div class="tuile-valeur">${stats.delai_moyen_reponse != null ? stats.delai_moyen_reponse + `<span style="font-size:16px;"> ${t("statistiques.jours_abrev")}</span>` : "-"}</div>
        <div class="tuile-detail">${stats.nb_delais_reponse ? t("statistiques.sur_reponses_datees", { n: stats.nb_delais_reponse }) : t("statistiques.aucune_reponse_datee")}</div>
      </div>
      <div class="tuile">
        <div class="tuile-libelle">${t("statistiques.delai_entretien")}</div>
        <div class="tuile-valeur">${stats.delai_moyen_entretien != null ? stats.delai_moyen_entretien + `<span style="font-size:16px;"> ${t("statistiques.jours_abrev")}</span>` : "-"}</div>
        <div class="tuile-detail">${t("statistiques.entre_envoi_entretien")}</div>
      </div>
    </div>
    <div class="grille-bord">
      <div class="carte">
        <h2>${t("statistiques.candidatures_par_semaine")}</h2>
        ${graphiqueHebdomadaire(stats.serie_hebdomadaire)}
      </div>
      <div class="carte">
        <h2>${t("statistiques.objectif_hebdomadaire")}</h2>
        ${obj ? `
          <div class="ligne-barre">
            <span class="libelle">${t("statistiques.objectif_ratio", { n: obj.nombre, objectif: obj.objectif })}</span>
            <div class="piste"><div class="remplissage${obj.atteint ? " atteint" : ""}" style="width:${obj.pourcentage}%"></div></div>
            <span class="valeur">${obj.pourcentage}%</span>
          </div>
          <p class="sous-titre">${t("statistiques.semaine_du", { debut: dateFr(obj.debut_semaine), fin: dateFr(obj.fin_semaine) })}${obj.atteint ? " - " + t("statistiques.objectif_atteint") : "."}</p>
        ` : `<p class="sous-titre">${t("statistiques.objectif_absent_debut")} <a class="lien-detail" href="#/reglages">${t("nav.reglages")}</a> ${t("statistiques.objectif_absent_fin")}</p>`}
      </div>
      <div class="carte">
        <h2>${t("statistiques.entonnoir_titre")}</h2>
        ${entonnoir}
      </div>
      <div class="carte">
        <h2>${t("statistiques.par_source")}</h2>
        ${stats.par_source.length ? `
          <div class="enveloppe-tableau" style="border:none;"><table class="tableau" style="border:none;">
            <thead><tr><th>${t("comparateur.source")}</th><th>${t("statistiques.envoyees")}</th><th>${t("statistiques.reponses")}</th><th>${t("statistiques.taux_reponse")}</th></tr></thead>
            <tbody>${sources}</tbody>
          </table></div>` : `<div class="sous-titre">${t("statistiques.par_source_vide")}</div>`}
      </div>
      <div class="carte">
        <h2>${t("statistiques.liens_offres")}</h2>
        <p class="sous-titre">${t("statistiques.liens_offres_texte")}</p>
        <div class="rangee-kpi" style="margin:12px 0;">
          <div class="tuile"><div class="tuile-libelle">${t("statistiques.actifs")}</div><div class="tuile-valeur">${liens.actifs}</div></div>
          <div class="tuile"><div class="tuile-libelle">${t("statistiques.morts")}</div><div class="tuile-valeur">${liens.morts}</div></div>
          <div class="tuile"><div class="tuile-libelle">${t("statistiques.non_verifies")}</div><div class="tuile-valeur">${liens.non_verifies}</div></div>
        </div>
        ${liens.liens_morts.length ? liens.liens_morts.map((l) => `
          <div class="ligne-lien-mort">
            <span onclick="ouvrirDetailCandidature(${l.id})" style="cursor:pointer;">
              <strong>${echapper(l.entreprise)}</strong> - ${echapper(l.poste)}
            </span>
            <a class="lien-detail" href="${echapper(l.lien_offre)}" target="_blank" rel="noopener">${t("statistiques.voir_offre")}</a>
          </div>`).join("") : ""}
        <div class="actions-reglages">
          <button class="btn btn-accent" id="btn-verifier-liens">${t("statistiques.verifier_maintenant")}</button>
        </div>
        <p class="sous-titre" id="resultat-verification-liens" style="margin-top:8px;"></p>
      </div>
    </div>`;
}

function activerStats() {
  const bouton = document.getElementById("btn-verifier-liens");
  if (!bouton) return;
  bouton.addEventListener("click", async () => {
    bouton.disabled = true;
    bouton.textContent = t("statistiques.verification_en_cours");
    try {
      const resultat = await api("/api/liens/verifier", { methode: "POST", corps: {} });
      document.getElementById("resultat-verification-liens").textContent =
        t("statistiques.resultat_verification", {
          verifies: resultat.verifies, actifs: resultat.actifs, morts: resultat.morts, inconnus: resultat.inconnus,
        });
      toast(t("statistiques.verification_terminee"));
      rendre();
    } catch (erreur) {
      toast(erreur.message, true);
    } finally {
      bouton.disabled = false;
      bouton.textContent = t("statistiques.verifier_maintenant");
    }
  });
}

/* ========================================================================
   Recherche globale (Cmd+K)
   ======================================================================== */

function resultatRecherche(type, libelle, clic, titre, sousTitre, objet) {
  return `
    <div class="resultat" style="--couleur-type:${COULEURS_TYPE[type]}" onclick="${clic}">
      <div class="resultat-entete">
        <span class="badge-type">${libelle}</span>
        <span class="resultat-titre">${echapper(titre)}</span>
        <span class="resultat-sous">${echapper(sousTitre || "")}</span>
      </div>
      ${objet.extrait ? `<div class="resultat-extrait">${echapper(objet.extrait)}</div>` : ""}
      <div class="resultat-champs">${t("recherche.trouve_dans")} ${objet.champs_trouves.map((c) => `<span class="puce">${echapper(tv(c))}</span>`).join(" ")}</div>
    </div>`;
}

async function vueRecherche() {
  const requete = etat.rechercheTexte.trim();
  let corps = `<div class="etat-vide"><div class="icone">${ICONES.boussole}</div>
    <div class="titre">${t("recherche.accroche_titre")}</div>
    <p>${t("recherche.accroche_texte")}</p></div>`;
  if (requete) {
    const resultats = await api(`/api/recherche?q=${encodeURIComponent(requete)}`);
    const rendus = [
      ...resultats.candidatures.map((c) =>
        resultatRecherche("candidature", t("recherche.badge_candidature"), `ouvrirDetailCandidature(${c.id})`,
          `${c.entreprise} - ${c.poste}`, `${tv(c.statut)}${c.ville ? " · " + c.ville : ""}`, c)),
      ...resultats.entreprises.map((e) =>
        resultatRecherche("entreprise", t("recherche.badge_entreprise"), `ouvrirDetailEntreprise(${e.id})`,
          e.nom, e.site_web || "", e)),
      ...resultats.notes.map((n) =>
        resultatRecherche("note", t("recherche.badge_note"), `location.hash='#/entretiens/${n.id}'`,
          n.titre, `${n.entreprise}${n.poste ? " · " + n.poste : ""}`, n)),
      ...resultats.documents.map((d) =>
        resultatRecherche("document", t("recherche.badge_document"), `ouvrirApercuPiece('documents', ${d.id})`,
          d.titre, d.entreprise, d)),
      ...resultats.lettres.map((l) =>
        resultatRecherche("lettre", t("recherche.badge_lettre"), `ouvrirApercuPiece('lettres', ${l.id})`,
          l.titre, l.entreprise, l)),
      ...resultats.fiches.map((f) =>
        resultatRecherche("fiche", t("recherche.badge_fiche"), `ouvrirApercuPiece('fiches', ${f.id})`,
          f.titre, f.entreprise, f)),
    ];
    corps = rendus.length
      ? `<div class="liste-resultats">${rendus.join("")}</div>
         <p class="sous-titre">${t("recherche.resultats_compte", {
           n: rendus.length, cand: resultats.candidatures.length, ent: resultats.entreprises.length,
           notes: resultats.notes.length, docs: resultats.documents.length,
           lettres: resultats.lettres.length, fiches: resultats.fiches.length,
         })}</p>`
      : `<div class="etat-vide"><div class="titre">${t("recherche.aucun_resultat", { requete: echapper(requete) })}</div><p>${t("recherche.aucun_resultat_texte")}</p></div>`;
  }
  return `
    <div class="entete-vue"><h1>${t("nav.recherche")}</h1></div>
    <input type="text" id="champ-recherche" class="champ-recherche-grande"
           placeholder="${t("recherche.placeholder")}" value="${echapper(etat.rechercheTexte)}">
    ${corps}`;
}

function activerRecherche() {
  const champ = document.getElementById("champ-recherche");
  if (!champ) return;
  if (etat.focusRecherche) {
    champ.focus();
    champ.select();
    etat.focusRecherche = false;
  }
  let minuteur;
  champ.addEventListener("input", () => {
    clearTimeout(minuteur);
    minuteur = setTimeout(() => {
      etat.rechercheTexte = champ.value;
      const position = champ.selectionStart;
      rendre().then(() => {
        const nouveau = document.getElementById("champ-recherche");
        if (nouveau) { nouveau.focus(); nouveau.setSelectionRange(position, position); }
      });
    }, 280);
  });
}

/* ========================================================================
   Réglages : clé API, modèle, sauvegardes
   ======================================================================== */

function carteReglagesCv() {
  return `
    <div class="carte">
      <h2>${t("reglages.cv_titre")}</h2>
      <p class="sous-titre">${t("reglages.cv_texte")}</p>
      <div class="actions-reglages"><a class="btn" href="#/cv">${t("reglages.cv_ouvrir")}</a></div>
    </div>`;
}

async function vueReglages() {
  const r = await api("/api/reglages");
  etat.ia = r;
  const modelesAnthropic = ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"];
  const estAnthropic = r.fournisseur_ia !== "openai_compatible";
  return `
    <div class="entete-vue">
      <div><h1>${t("nav.reglages")}</h1><div class="sous-titre">${t("reglages.sous_titre")}</div></div>
    </div>
    <div class="grille-reglages">
      <div class="carte">
        <h2>${t("reglages.langue_titre")}</h2>
        <p class="sous-titre">${t("reglages.langue_texte")}</p>
        <div class="champ" style="margin-top:12px; max-width:220px;">
          <label for="reg-langue">${t("reglages.langue_label")}</label>
          <select id="reg-langue">
            ${(window.LANGUES_DISPONIBLES || []).map((l) => `<option value="${l.code}"${l.code === etat.langue ? " selected" : ""}>${echapper(l.nom)}</option>`).join("")}
          </select>
        </div>
      </div>

      <div class="carte">
        <h2>${t("reglages.ia_titre")}</h2>
        <p class="sous-titre">${t("reglages.ia_texte")}</p>

        <div class="champ" style="margin-top:12px; max-width:320px;">
          <label for="reg-fournisseur">${t("reglages.fournisseur")}</label>
          <select id="reg-fournisseur">
            <option value="anthropic"${estAnthropic ? " selected" : ""}>${t("reglages.fournisseur_anthropic")}</option>
            <option value="openai_compatible"${!estAnthropic ? " selected" : ""}>${t("reglages.fournisseur_generique")}</option>
          </select>
        </div>

        <div class="champ" style="margin-top:10px;">
          <label for="reg-cle">${t("reglages.cle_api")}</label>
          <div class="champ-mdp">
            <input type="password" id="reg-cle" autocomplete="off"
                   placeholder="${r.cle_api_definie ? t("reglages.cle_enregistree", { cle: echapper(r.cle_api_masquee) }) : "sk-…"}">
            <button type="button" class="btn btn-discret btn-oeil" data-cible="reg-cle">${t("commun.afficher")}</button>
          </div>
        </div>

        <div id="bloc-fournisseur-anthropic" class="champ" style="margin-top:10px; max-width:320px;"${estAnthropic ? "" : " hidden"}>
          <label for="reg-modele-anthropic">${t("reglages.modele")}</label>
          <select id="reg-modele-anthropic">
            ${modelesAnthropic.map((m) => `<option${m === r.modele_ia ? " selected" : ""}>${m}</option>`).join("")}
          </select>
        </div>

        <div id="bloc-fournisseur-generique"${estAnthropic ? " hidden" : ""}>
          <div class="champ" style="margin-top:10px;">
            <label for="reg-modele-generique">${t("reglages.nom_modele")}</label>
            <input type="text" id="reg-modele-generique"
                   placeholder="gpt-4o-mini, mistral-large-latest, gemini-2.0-flash, llama3.1 (Ollama)…"
                   value="${!estAnthropic ? echapper(r.modele_ia || "") : ""}">
          </div>
          <div class="champ" style="margin-top:10px;">
            <label for="reg-base-url">${t("reglages.url_base")}</label>
            <input type="text" id="reg-base-url"
                   placeholder="${t("reglages.url_base_placeholder")}"
                   value="${echapper(r.ia_base_url || "")}">
          </div>
          <p class="sous-titre">${t("reglages.exemples_fournisseurs")}</p>
        </div>

        <label class="case" id="ligne-recherche-web"${estAnthropic ? "" : " hidden"}>
          <input type="checkbox" id="reg-web" ${r.recherche_web === "Oui" ? "checked" : ""}>
          ${t("reglages.recherche_web_label")}
        </label>
        ${estAnthropic ? "" : `<p class="sous-titre">${t("reglages.recherche_web_indisponible")}</p>`}

        <div class="actions-reglages">
          <button class="btn btn-accent" id="reg-enregistrer">${t("commun.enregistrer")}</button>
          <button class="btn" id="reg-tester"${r.cle_api_definie ? "" : " disabled"}>${t("reglages.tester_connexion")}</button>
          ${r.cle_api_definie ? `<button class="btn btn-danger" id="reg-supprimer-cle">${t("reglages.supprimer_cle")}</button>` : ""}
        </div>
      </div>

      ${carteReglagesCv()}

      <div class="carte">
        <h2>${t("reglages.dossier_titre")}</h2>
        <p class="sous-titre">${t("reglages.dossier_texte")}</p>
        <div class="champ" style="margin-top:12px;">
          <label>${t("reglages.emplacement_actuel")}</label>
          <input type="text" value="${echapper(r.dossier_donnees || t("reglages.emplacement_defaut"))}" readonly>
        </div>
        <div class="actions-reglages">
          <button class="btn btn-accent" id="reg-choisir-dossier">${t("reglages.choisir_dossier")}</button>
          ${r.dossier_donnees ? `<button class="btn" id="reg-dossier-defaut">${t("reglages.revenir_par_defaut")}</button>` : ""}
        </div>
        <p class="sous-titre">${t("reglages.dossier_note")}</p>
      </div>

      <div class="carte">
        <h2>${t("reglages.sauvegardes_titre")}</h2>
        <p class="sous-titre">${t("reglages.sauvegardes_texte")}</p>
        <div class="actions-reglages">
          <button class="btn btn-accent" id="reg-sauvegarder">${t("reglages.sauvegarder_maintenant")}</button>
        </div>
        <div id="reg-resultat-sauvegarde" class="sous-titre" style="margin-top:8px;"></div>
      </div>

      <div class="carte">
        <h2>${t("statistiques.objectif_hebdomadaire")}</h2>
        <p class="sous-titre">${t("reglages.objectif_texte")}</p>
        <div class="champ" style="margin-top:12px; max-width:160px;">
          <label for="reg-objectif">${t("reglages.objectif_label")}</label>
          <input type="number" id="reg-objectif" min="1" step="1"
                 value="${echapper(r.objectif_hebdomadaire || "")}" placeholder="ex. 5">
        </div>
        <div class="actions-reglages">
          <button class="btn btn-accent" id="reg-enregistrer-objectif">${t("commun.enregistrer")}</button>
        </div>
      </div>

      <div class="carte">
        <h2>${t("reglages.compagnon_titre")}</h2>
        <p class="sous-titre">${t("reglages.compagnon_texte")}</p>
        <label class="case" style="margin-top:10px;">
          <input type="checkbox" id="reg-compagnon-actif" ${r.compagnon_actif === "Oui" ? "checked" : ""}>
          ${t("reglages.compagnon_case")}
        </label>
        ${r.compagnon_actif === "Oui" ? `
          <div class="champ" style="margin-top:12px;">
            <label>${t("reglages.compagnon_adresse")}</label>
            <input type="text" readonly value="http://${echapper(r.compagnon_ip)}:${r.compagnon_port}">
          </div>
          <div class="champ" style="margin-top:10px; max-width:220px;">
            <label>${t("reglages.compagnon_code")}</label>
            <input type="text" readonly value="${echapper(r.compagnon_code || "")}">
          </div>
          <div class="actions-reglages">
            <button class="btn" id="reg-regenerer-code">${t("reglages.regenerer_code")}</button>
          </div>` : ""}
      </div>

      <div class="carte">
        <h2>${t("reglages.safari_titre")}</h2>
        <p class="sous-titre">${t("reglages.safari_texte")}</p>
        <div class="bloc-raccourci">
          <ol>
            <li>${t("reglages.safari_etape1")}</li>
            <li>${t("reglages.safari_etape2", { url: echapper(location.origin) })}</li>
            <li>${t("reglages.safari_etape3")}</li>
            <li>${t("reglages.safari_etape4")}</li>
          </ol>
        </div>
        <p class="sous-titre" style="margin-top:8px;">${t("reglages.safari_note")}</p>
      </div>

      <div class="carte">
        <h2>${t("reglages.ia_dev_titre")}</h2>
        <p class="sous-titre">${t("reglages.ia_dev_texte")}</p>
      </div>
    </div>`;
}

function activerReglages() {
  const bouton = document.getElementById("reg-enregistrer");
  if (!bouton) return;

  const selectFournisseur = document.getElementById("reg-fournisseur");
  selectFournisseur.addEventListener("change", () => {
    const estAnthropic = selectFournisseur.value !== "openai_compatible";
    document.getElementById("bloc-fournisseur-anthropic").hidden = !estAnthropic;
    document.getElementById("bloc-fournisseur-generique").hidden = estAnthropic;
    document.getElementById("ligne-recherche-web").hidden = !estAnthropic;
  });

  bouton.addEventListener("click", async () => {
    const estAnthropic = selectFournisseur.value !== "openai_compatible";
    const corps = {
      fournisseur_ia: selectFournisseur.value,
      recherche_web: document.getElementById("reg-web").checked ? "Oui" : "Non",
    };
    if (estAnthropic) {
      corps.modele_ia = document.getElementById("reg-modele-anthropic").value;
      corps.ia_base_url = "";
    } else {
      corps.modele_ia = document.getElementById("reg-modele-generique").value.trim();
      corps.ia_base_url = document.getElementById("reg-base-url").value.trim();
    }
    const cle = document.getElementById("reg-cle").value.trim();
    if (cle) corps.cle_api = cle;
    try {
      etat.ia = await api("/api/reglages", { methode: "POST", corps });
      toast(t("reglages.reglages_enregistres"));
      rendre();
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });

  document.getElementById("reg-tester").addEventListener("click", async (evenement) => {
    const cible = evenement.currentTarget;
    cible.disabled = true;
    cible.textContent = t("reglages.test_en_cours");
    try {
      const resultat = await api("/api/agent/tester", { methode: "POST" });
      toast(t("reglages.connexion_reussie", { fournisseur: resultat.fournisseur, modele: resultat.modele }));
    } catch (erreur) {
      toast(erreur.message, true);
    } finally {
      cible.disabled = false;
      cible.textContent = t("reglages.tester_connexion");
    }
  });

  const supprimerCle = document.getElementById("reg-supprimer-cle");
  if (supprimerCle) {
    supprimerCle.addEventListener("click", async () => {
      const accord = await confirmer(
        t("reglages.supprimer_cle_titre"),
        t("reglages.supprimer_cle_texte")
      );
      if (!accord) return;
      try {
        etat.ia = await api("/api/reglages", { methode: "POST", corps: { cle_api: "" } });
        toast(t("reglages.cle_supprimee"));
        rendre();
      } catch (erreur) {
        toast(erreur.message, true);
      }
    });
  }

  document.getElementById("reg-sauvegarder").addEventListener("click", async () => {
    try {
      const resultat = await api("/api/sauvegarde", { methode: "POST" });
      document.getElementById("reg-resultat-sauvegarde").textContent =
        t("reglages.sauvegarde_creee", { chemin: resultat.chemin });
      toast(t("reglages.base_sauvegardee"));
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });

  // Dossier de données : sélecteur natif si l'app de bureau l'expose, sinon
  // saisie manuelle (aussi ce qui s'affiche en aperçu navigateur).
  document.getElementById("reg-choisir-dossier").addEventListener("click", async () => {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.choisir_dossier_donnees) {
      try {
        const dossier = await window.pywebview.api.choisir_dossier_donnees();
        if (dossier) {
          toast(t("reglages.dossier_mis_a_jour"));
          rendre();
        }
      } catch (erreur) {
        toast(t("reglages.selecteur_indisponible") + " " + erreur.message, true);
      }
      return;
    }
    const chemin = await demanderTexte(
      t("reglages.dossier_titre"),
      "/Users/toi/Documents/Azimut",
      etat.ia.dossier_donnees || ""
    );
    if (chemin === null) return;
    try {
      await api("/api/reglages/dossier_donnees", { methode: "POST", corps: { dossier: chemin } });
      toast(t("reglages.dossier_mis_a_jour"));
      rendre();
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });

  const boutonDefaut = document.getElementById("reg-dossier-defaut");
  if (boutonDefaut) {
    boutonDefaut.addEventListener("click", async () => {
      try {
        await api("/api/reglages/dossier_donnees", { methode: "POST", corps: { dossier: "" } });
        toast(t("reglages.retour_par_defaut"));
        rendre();
      } catch (erreur) {
        toast(erreur.message, true);
      }
    });
  }

  document.getElementById("reg-enregistrer-objectif").addEventListener("click", async () => {
    const valeur = document.getElementById("reg-objectif").value.trim();
    try {
      await api("/api/reglages", { methode: "POST", corps: { objectif_hebdomadaire: valeur } });
      toast(valeur ? t("reglages.objectif_enregistre") : t("reglages.objectif_desactive"));
      rendre();
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });

  document.getElementById("reg-compagnon-actif").addEventListener("change", async (evenement) => {
    try {
      await api("/api/reglages/compagnon", { methode: "POST", corps: { actif: evenement.target.checked } });
      toast(
        evenement.target.checked
          ? t("reglages.compagnon_active")
          : t("reglages.compagnon_desactive")
      );
      rendre();
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });

  const boutonRegenererCode = document.getElementById("reg-regenerer-code");
  if (boutonRegenererCode) {
    boutonRegenererCode.addEventListener("click", async () => {
      const accord = await confirmer(
        t("reglages.regenerer_code_titre"),
        t("reglages.regenerer_code_texte")
      );
      if (!accord) return;
      try {
        await api("/api/reglages/compagnon", { methode: "POST", corps: { regenerer_code: true } });
        toast(t("reglages.nouveau_code_genere"));
        rendre();
      } catch (erreur) {
        toast(erreur.message, true);
      }
    });
  }

  const selectLangue = document.getElementById("reg-langue");
  if (selectLangue) {
    selectLangue.addEventListener("change", async (evenement) => {
      const langue = evenement.target.value;
      try {
        await api("/api/reglages", { methode: "POST", corps: { langue } });
        etat.langue = langue;
        document.documentElement.lang = langue;
        traduireStatique();
        toast(t("reglages.langue_changee"));
        rendre();
      } catch (erreur) {
        toast(erreur.message, true);
      }
    });
  }
}

/* ========================================================================
   Modales : confirmations, saisies, récapitulatif
   ======================================================================== */

/* Les fenêtres centrées sont EMPILÉES : un aperçu ouvert depuis le détail d'une
   candidature s'affiche par-dessus, et sa fermeture ramène au détail. Chacune
   est créée à la demande ; `options.surFermeture` s'exécute à sa fermeture,
   `options.avecEtat` ajoute un petit indicateur (« Enregistré ») dans l'en-tête. */
const pileModales = [];

function ouvrirModale(titre, corpsHTML, piedHTML, etroite = false, large = false, options = {}) {
  const racine = document.createElement("div");
  racine.className = "modale visible";
  racine.setAttribute("role", "dialog");
  racine.setAttribute("aria-modal", "true");
  racine.innerHTML = `
    <div class="modale-boite${etroite ? " etroite" : ""}${large ? " large" : ""}">
      <div class="modale-entete">
        <h2 class="modale-titre"></h2>
        ${options.avecEtat ? '<span class="modale-etat" aria-live="polite"></span>' : ""}
        <button class="btn btn-discret modale-fermer" aria-label="${echapperAttribut(t("commun.fermer"))}">✕</button>
      </div>
      <div class="modale-corps"></div>
      <div class="modale-pied"></div>
    </div>`;
  racine.querySelector(".modale-titre").textContent = titre;
  const corps = racine.querySelector(".modale-corps");
  const pied = racine.querySelector(".modale-pied");
  corps.innerHTML = corpsHTML;
  pied.innerHTML = piedHTML;
  pied.hidden = !piedHTML;
  const controleur = {
    racine, corps, pied,
    surFermeture: options.surFermeture || null,
    precedentFocus: document.activeElement,
  };
  racine.querySelector(".modale-fermer").addEventListener("click", () => fermerModale(controleur));
  // mousedown (et non click) : sélectionner du texte dans un champ puis relâcher sur le
  // fond ne doit pas fermer la fenêtre.
  racine.addEventListener("mousedown", (evenement) => {
    if (evenement.target === racine) fermerModale(controleur);
  });
  document.body.appendChild(racine);
  pileModales.push(controleur);
  return controleur;
}

/* Ferme la fenêtre indiquée, sinon celle du dessus. */
function fermerModale(controleur) {
  const cible = controleur || pileModales[pileModales.length - 1];
  if (!cible) return;
  const rang = pileModales.indexOf(cible);
  if (rang === -1) return;
  pileModales.splice(rang, 1);
  cible.racine.remove();
  if (cible.precedentFocus && document.contains(cible.precedentFocus)) {
    try { cible.precedentFocus.focus({ preventScroll: true }); } catch { /* sans importance */ }
  }
  if (cible.surFermeture) {
    try {
      const suite = cible.surFermeture();
      if (suite && suite.catch) suite.catch((erreur) => toast(erreur.message, true));
    } catch (erreur) {
      toast(erreur.message, true);
    }
  }
}

function confirmer(titre, message) {
  return new Promise((resoudre) => {
    ouvrirModale(
      titre,
      `<p>${echapper(message)}</p>`,
      `<button class="btn" id="btn-annuler">${t("commun.annuler")}</button>
       <button class="btn btn-accent" id="btn-confirmer" style="background:var(--danger);border-color:var(--danger);">${t("commun.supprimer")}</button>`,
      true
    );
    document.getElementById("btn-annuler").addEventListener("click", () => {
      fermerModale();
      resoudre(false);
    });
    document.getElementById("btn-confirmer").addEventListener("click", () => {
      fermerModale();
      resoudre(true);
    });
  });
}

/* Petite saisie de texte modale (remplace prompt(), pas fiable dans une
   WKWebView) - utilisée pour la saisie manuelle du dossier de données. */
function demanderTexte(titre, placeholder, valeurInitiale = "") {
  return new Promise((resoudre) => {
    ouvrirModale(
      titre,
      `<input type="text" id="champ-demande-texte" value="${echapper(valeurInitiale)}"
              placeholder="${echapper(placeholder)}" style="width:100%;">`,
      `<button class="btn" id="btn-annuler-texte">${t("commun.annuler")}</button>
       <button class="btn btn-accent" id="btn-valider-texte">${t("entretien.valider")}</button>`,
      true
    );
    const champ = document.getElementById("champ-demande-texte");
    champ.focus();
    champ.select();
    const valider = () => {
      const valeur = champ.value;
      fermerModale();
      resoudre(valeur);
    };
    document.getElementById("btn-valider-texte").addEventListener("click", valider);
    champ.addEventListener("keydown", (evenement) => {
      if (evenement.key === "Enter") valider();
    });
    document.getElementById("btn-annuler-texte").addEventListener("click", () => {
      fermerModale();
      resoudre(null);
    });
  });
}

/* Avertissement de quasi-doublon (pas un blocage) : intitulé proche ou même
   lien d'offre qu'une candidature déjà en base. L'utilisateur tranche. */
function confirmerSimilaires(liste) {
  const lignes = liste
    .map(
      (r) => `
      <div class="ligne-similaire">
        <div><strong>${echapper(r.entreprise)}</strong> - ${echapper(r.poste)}
          <span class="cellule-secondaire">(${echapper(tv(r.statut))})</span></div>
        <div>${r.raisons.map((raison) => `<span class="puce">${echapper(raison)}</span>`).join(" ")}</div>
      </div>`
    )
    .join("");
  return new Promise((resoudre) => {
    ouvrirModale(
      t("entretien.similaires_titre"),
      `<p>${t("entretien.similaires_texte")}</p>
       <div class="liste-similaires">${lignes}</div>
       <p class="sous-titre">${t("entretien.similaires_avertissement")}</p>`,
      `<button class="btn" id="btn-annuler-similaire">${t("entretien.modifier_avant_ajout")}</button>
       <button class="btn btn-accent" id="btn-continuer-similaire">${t("entretien.creer_quand_meme")}</button>`,
      true
    );
    document.getElementById("btn-annuler-similaire").addEventListener("click", () => {
      fermerModale();
      resoudre(false);
    });
    document.getElementById("btn-continuer-similaire").addEventListener("click", () => {
      fermerModale();
      resoudre(true);
    });
  });
}

/* Markdown -> HTML : voir markdown.js (échappement complet, listes, tâches, tableaux…). */
function rendreMarkdown(texte) {
  return window.Markdown.rendre(texte);
}

async function ouvrirRecapitulatif(numero) {
  try {
    const fiche = await api(`/api/entretien/${numero}`);
    ouvrirModale(
      t("entretien.recap_titre"),
      `<div class="fiche">${rendreMarkdown(fiche.markdown)}</div>`,
      `<a class="btn" href="/api/entretien/${numero}/telecharger" data-telechargement="entretien-${echapperAttribut(fiche.entreprise)}.md">${t("entretien.telecharger_md")}</a>
       <button class="btn btn-accent" onclick="fermerModale()">${t("commun.fermer")}</button>`
    );
  } catch (erreur) {
    toast(erreur.message, true);
  }
}

/* ========================================================================
   Branchements globaux et démarrage
   ======================================================================== */

document.getElementById("btn-nouvelle").addEventListener("click", () => ouvrirFormCandidature());
document.addEventListener("keydown", (evenement) => {
  if (evenement.key === "Escape") {
    if (pileModales.length) fermerModale(); // Échap ferme la fenêtre du dessus
  }
  if ((evenement.metaKey || evenement.ctrlKey) && evenement.key.toLowerCase() === "k") {
    evenement.preventDefault();
    etat.focusRecherche = true;
    if (location.hash === "#/recherche") rendre();
    else location.hash = "#/recherche";
  }
});
document.getElementById("btn-export").addEventListener("click", () => {
  window.location.href = "/api/export/excel";
  toast(t("branchements.export_en_cours"));
});
document.getElementById("btn-import").addEventListener("click", () => {
  document.getElementById("fichier-import").click();
});
document.getElementById("fichier-import").addEventListener("change", async (evenement) => {
  const fichier = evenement.target.files[0];
  evenement.target.value = "";
  if (!fichier) return;
  const formulaire = new FormData();
  formulaire.append("fichier", fichier);
  try {
    const reponse = await fetch("/api/import/excel", { method: "POST", body: formulaire });
    const rapport = await reponse.json();
    if (!reponse.ok) throw new Error(rapport.erreur || t("branchements.import_impossible"));
    const morceaux = [
      `<p>${t("branchements.import_resume", {
        cand: rapport.candidatures_ajoutees, notes: rapport.notes_ajoutees, ent: rapport.entreprises_ajoutees,
      })}</p>`,
    ];
    if (rapport.ignores.length) {
      morceaux.push(
        `<p><strong>${t("branchements.doublons_ignores")}</strong> ${t("branchements.doublons_ignores_detail")}</p>` +
        `<ul>${rapport.ignores.map((texte) => `<li>${echapper(texte)}</li>`).join("")}</ul>`
      );
    }
    if (rapport.erreurs.length) {
      morceaux.push(
        `<p><strong>${t("branchements.lignes_non_importees")}</strong></p>` +
        `<ul>${rapport.erreurs.map((texte) => `<li>${echapper(texte)}</li>`).join("")}</ul>`
      );
    }
    ouvrirModale(
      t("branchements.rapport_import"),
      morceaux.join(""),
      `<button class="btn btn-accent" onclick="fermerModale()">${t("commun.fermer")}</button>`
    );
    rendre();
  } catch (erreur) {
    toast(erreur.message, true);
  }
});

/* Import CSV générique (LinkedIn, Indeed, ou tout autre export) : deux
   étapes - un aperçu des colonnes détectées, puis une correspondance
   colonne -> champ choisie par l'utilisateur avant d'importer. */
function libellesChampsCsv() {
  return {
    entreprise: t("formulaire.entreprise_requis"),
    poste: t("formulaire.poste_requis"),
    statut: t("candidatures.col_statut"),
    date_envoi: t("formulaire.date_envoi"),
    ville: t("candidatures.col_ville"),
    mode_travail: t("comparateur.mode_travail"),
    lien_offre: t("formulaire.lien_offre"),
    source: t("comparateur.source"),
    notes: t("formulaire.notes"),
  };
}

document.getElementById("btn-import-csv").addEventListener("click", () => {
  document.getElementById("fichier-import-csv").click();
});

document.getElementById("fichier-import-csv").addEventListener("change", async (evenement) => {
  const fichier = evenement.target.files[0];
  evenement.target.value = "";
  if (!fichier) return;
  const formulaire = new FormData();
  formulaire.append("fichier", fichier);
  try {
    const reponse = await fetch("/api/import/csv/apercu", { method: "POST", body: formulaire });
    const apercu = await reponse.json();
    if (!reponse.ok) throw new Error(apercu.erreur || "Aperçu impossible.");
    ouvrirCorrespondanceCsv(apercu);
  } catch (erreur) {
    toast(erreur.message, true);
  }
});

function ouvrirCorrespondanceCsv(apercu) {
  const v = etat.valeurs;
  const libellesChampsCsvActuels = libellesChampsCsv();
  const optionsColonnes = (selection) => `
    <option value="">${t("branchements.non_importe")}</option>
    ${apercu.entetes.map((e) => `<option value="${echapperAttribut(e)}"${e === selection ? " selected" : ""}>${echapper(e)}</option>`).join("")}`;

  // Devine une correspondance de départ par ressemblance de nom, pour éviter
  // à l'utilisateur de tout choisir à la main sur un export classique.
  const deviner = (motsClefs) => apercu.entetes.find((e) => {
    const normalise = e.toLowerCase().replace(/[^a-z]/g, "");
    return motsClefs.some((mot) => normalise.includes(mot));
  }) || "";
  const suggestions = {
    entreprise: deviner(["company", "entreprise", "employer"]),
    poste: deviner(["title", "poste", "job", "role", "intitule"]),
    statut: deviner(["status", "statut", "state"]),
    date_envoi: deviner(["date", "applied", "envoi"]),
    ville: deviner(["location", "ville", "city"]),
    lien_offre: deviner(["url", "link", "lien"]),
  };

  const lignesApercu = apercu.lignes
    .map((ligne) => `<tr>${ligne.map((cellule) => `<td class="cellule-secondaire">${echapper(cellule)}</td>`).join("")}</tr>`)
    .join("");

  const corps = `
    <p class="sous-titre">${t("branchements.associe_colonnes")}</p>
    <div class="enveloppe-tableau" style="margin-bottom:14px;max-height:160px;">
      <table class="tableau"><thead><tr>${apercu.entetes.map((e) => `<th>${echapper(e)}</th>`).join("")}</tr></thead>
      <tbody>${lignesApercu}</tbody></table>
    </div>
    <form id="form-correspondance-csv" class="grille-form" onsubmit="return false;">
      ${apercu.champs.map((champ) => `
        <div class="champ">
          <label for="csv-${champ}">${libellesChampsCsvActuels[champ] || champ}</label>
          <select id="csv-${champ}" data-champ="${champ}">${optionsColonnes(suggestions[champ] || "")}</select>
        </div>`).join("")}
    </form>
    <div class="grille-form" style="margin-top:4px;">
      <div class="champ">
        <label for="csv-statut-defaut">${t("branchements.statut_par_defaut")}</label>
        <select id="csv-statut-defaut">${optionsSelect(v.statuts, "Envoyée", false)}</select>
      </div>
      <div class="champ">
        <label for="csv-source-fixe">${t("branchements.source_fixe")}</label>
        <select id="csv-source-fixe">${optionsSelect(v.sources_candidature, "LinkedIn")}</select>
      </div>
    </div>`;

  ouvrirModale(
    t("branchements.importer_csv_titre"),
    corps,
    `<button class="btn" onclick="fermerModale()">${t("commun.annuler")}</button>
     <button class="btn btn-accent" id="btn-confirmer-import-csv">${t("commun.ajouter_simple")}</button>`
  );

  document.getElementById("btn-confirmer-import-csv").addEventListener("click", async () => {
    const correspondance = {};
    document.querySelectorAll("#form-correspondance-csv [data-champ]").forEach((select) => {
      if (select.value) correspondance[select.dataset.champ] = select.value;
    });
    if (!correspondance.entreprise || !correspondance.poste) {
      toast(t("branchements.associer_min_requis"), true);
      return;
    }
    try {
      const reponse = await fetch("/api/import/csv/confirmer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          jeton: apercu.jeton,
          correspondance,
          statut_par_defaut: document.getElementById("csv-statut-defaut").value,
          source: document.getElementById("csv-source-fixe").value,
        }),
      });
      const rapport = await reponse.json();
      if (!reponse.ok) throw new Error(rapport.erreur || t("branchements.import_impossible"));
      const morceaux = [`<p>${t("branchements.import_csv_resume", { n: rapport.candidatures_ajoutees })}</p>`];
      if (rapport.ignores.length) {
        morceaux.push(
          `<p><strong>${t("branchements.doublons_ignores")}</strong></p><ul>${rapport.ignores.map((texte) => `<li>${echapper(texte)}</li>`).join("")}</ul>`
        );
      }
      if (rapport.erreurs.length) {
        morceaux.push(
          `<p><strong>${t("branchements.lignes_non_importees")}</strong></p><ul>${rapport.erreurs.map((texte) => `<li>${echapper(texte)}</li>`).join("")}</ul>`
        );
      }
      ouvrirModale(
        t("branchements.rapport_import"),
        morceaux.join(""),
        `<button class="btn btn-accent" onclick="fermerModale()">${t("commun.fermer")}</button>`
      );
      rendre();
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });
}

/* Télécharger un fichier SANS quitter la page. Dans la fenêtre de bureau, un lien vers un
   PDF ou un texte ferait naviguer la fenêtre vers le fichier (et il faudrait fermer
   Azimut pour revenir) : on passe par la boîte « Enregistrer sous » native. Dans un
   navigateur, un lien de téléchargement classique suffit. */
async function telechargerFichier(url, nomSuggere) {
  const pont = window.pywebview && window.pywebview.api;
  if (pont && pont.enregistrer_fichier) {
    try {
      const chemin = await pont.enregistrer_fichier(url, nomSuggere || "");
      if (chemin) toast(t("commun.enregistre_sous", { chemin }));
    } catch (erreur) {
      toast(erreur.message || t("commun.erreur_inattendue"), true);
    }
    return;
  }
  const lien = document.createElement("a");
  lien.href = url;
  lien.download = nomSuggere || "";
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
}

document.addEventListener("click", (evenement) => {
  const lien = evenement.target.closest("a[data-telechargement]");
  if (!lien) return;
  evenement.preventDefault();
  telechargerFichier(lien.getAttribute("href"), lien.dataset.telechargement);
});

// Afficher / masquer les mots de passe (délégation : les formulaires sont re-rendus).
document.addEventListener("click", (evenement) => {
  const bouton = evenement.target.closest(".btn-oeil");
  if (!bouton) return;
  const champ = document.getElementById(bouton.dataset.cible);
  if (!champ) return;
  const masque = champ.type === "password";
  champ.type = masque ? "text" : "password";
  bouton.textContent = masque ? t("commun.masquer") : t("commun.afficher");
});

// Un fichier lâché en dehors d'une zone de dépôt ferait naviguer la fenêtre vers ce
// fichier (et quitter Azimut) : on annule ce comportement par défaut partout.
["dragover", "drop"].forEach((evenement) => {
  window.addEventListener(evenement, (e) => {
    if (e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files")) e.preventDefault();
  });
});

// Filet de sécurité : aucune erreur JS ne doit rester silencieuse.
window.addEventListener("error", () => {
  toast(t("commun.erreur_interface_inattendue"), true);
});
window.addEventListener("unhandledrejection", (evenement) => {
  toast((evenement.reason && evenement.reason.message) || t("commun.erreur_inattendue"), true);
  evenement.preventDefault();
});

(async function demarrer() {
  try {
    etat.valeurs = await api("/api/valeurs");
    try {
      etat.ia = await api("/api/reglages");
      etat.langue = (etat.ia && etat.ia.langue) || "fr";
    } catch { etat.ia = null; }
    document.documentElement.lang = etat.langue;
    traduireStatique();
    await rendre();
  } catch (erreur) {
    document.getElementById("vue").innerHTML =
      `<div class="etat-vide"><div class="titre">${echapper(t("commun.serveur_ne_repond_pas"))}</div><p>${echapper(erreur.message)}</p></div>`;
  }
})();
