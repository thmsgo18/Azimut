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
  modeCandidatures: "kanban",
  filtres: { statut: "", priorite: "", sous_domaine: "", texte: "" },
  agendaBase: null,       // premier jour du mois affiché dans l'agenda
  agendaMode: "mois",
  rechercheTexte: "",
  focusRecherche: false,
  propositionEntreprise: null,  // infos entreprise proposées par l'IA, écrites après validation
  selectionComparaison: new Set(),  // ids cochés en vue liste, pour le comparateur
};

/* Couleurs par type d'objet (recherche) et par type d'échéance (agenda),
   toujours accompagnées d'un libellé texte, jamais la couleur seule. */
const COULEURS_TYPE = {
  candidature: "var(--accent)",
  entreprise: "var(--st-reponse)",
  contact: "var(--violet)",
};
const COULEURS_ECHEANCE = {
  relance: "var(--st-relancee)",
  entretien: "var(--st-entretien)",
  debut: "var(--st-accepte)",
};

/* Icônes SVG des états vides (aucun emoji dans l'interface). */
const ICONES = {
  boussole:
    '<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"></polygon></svg>',
  candidatures:
    '<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="5" height="16" rx="1.5"/><rect x="10" y="4" width="5" height="10" rx="1.5"/><rect x="17" y="4" width="5" height="13" rx="1.5"/></svg>',
  entreprises:
    '<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M5 21V5a1.5 1.5 0 0 1 1.5-1.5H13A1.5 1.5 0 0 1 14.5 5v16"/><path d="M14.5 9H18a1.5 1.5 0 0 1 1.5 1.5V21"/><path d="M8 7.5h3M8 11h3M8 14.5h3"/></svg>',
  contacts:
    '<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.4"/><path d="M3.5 20c.6-3.4 2.8-5.2 5.5-5.2s4.9 1.8 5.5 5.2"/><path d="M16.5 5.4a3.4 3.4 0 0 1 0 5.2"/><path d="M17.8 14.9c1.6.8 2.7 2.6 2.9 5.1"/></svg>',
};

const COULEURS_STATUT = {
  "À préparer": "var(--st-a-preparer)",
  "Envoyée": "var(--st-envoyee)",
  "Relancée": "var(--st-relancee)",
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

/* Traduit une VALEUR de donnée (statut, priorité, sous-domaine...) pour
   l'affichage - jamais pour ce qui part vers l'API ou vit dans
   value="..." d'une <option>, qui restent toujours la valeur canonique en
   français (voir valeurs.py côté serveur). Absente de la table de la
   langue courante -> le français lui-même, donc jamais un blanc. */
function tv(valeur) {
  if (valeur === null || valeur === undefined || valeur === "") return valeur;
  const table = (window.LANGUES && window.LANGUES[etat.langue] && window.LANGUES[etat.langue].valeurs) || {};
  return table[valeur] ?? valeur;
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
  relances: vueRelances,
  agenda: vueAgenda,
  entreprises: vueEntreprises,
  contacts: vueContacts,
  documents: vueDocuments,
  statistiques: vueStats,
  recherche: vueRecherche,
  comparer: vueComparateur,
  reglages: vueReglages,
};

const ACTIVATIONS = {
  candidatures: activerCandidatures,
  relances: activerRelances,
  agenda: activerAgenda,
  recherche: activerRecherche,
  comparer: activerComparateur,
  statistiques: activerStats,
  reglages: activerReglages,
};

async function rendre() {
  const brut = location.hash.replace(/^#\//, "");
  const conteneur = document.getElementById("vue");
  try {
    if (brut.startsWith("entretien/")) {
      // Mode entretien : plein écran, hors navigation classique.
      const numero = Number(brut.split("/")[1]);
      document.querySelectorAll(".nav a").forEach((l) => l.classList.remove("actif"));
      conteneur.innerHTML = await vueModeEntretien(numero);
      activerModeEntretien(numero);
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
  if (stats.total === 0 && stats.total_contacts === 0) {
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
  const relances = stats.relances_a_faire
    .map(
      (cand) => `
      <div class="echeance" onclick="ouvrirDetailCandidature(${cand.id})">
        <span class="echeance-date">${dateFr(cand.date_relance_prevue)}</span>
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
        <div class="tuile-libelle">${t("bord.kpi_contacts")}</div>
        <div class="tuile-valeur">${stats.total_contacts}</div>
        <div class="tuile-detail">${t("bord.kpi_contacts_detail", { n: stats.contacts_par_statut["Répondu"] || 0 })}</div>
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
      <div class="carte">
        <h2>${t("bord.carte_relances")}</h2>
        ${relances || `<div class="sous-titre">${t("bord.relances_vide")}</div>`}
      </div>
      <div class="carte">
        <h2>${t("bord.carte_entretiens")}</h2>
        ${entretiens || `<div class="sous-titre">${t("bord.entretiens_vide")}</div>`}
      </div>
    </div>`;
}

function activerBord() { /* rien à brancher : liens inline */ }

/* ========================================================================
   Candidatures : kanban + liste
   ======================================================================== */

function candidatureVisible(cand) {
  const f = etat.filtres;
  if (f.statut && cand.statut !== f.statut) return false;
  if (f.priorite && cand.priorite !== f.priorite) return false;
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
  if (cand.priorite === "Haute") {
    puces.push(`<span class="puce puce-priorite-Haute">${t("candidatures.priorite_haute")}</span>`);
  }
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
      <select id="filtre-priorite">
        <option value="">${t("candidatures.toutes_priorites")}</option>
        ${v.priorites.map((p) => `<option${etat.filtres.priorite === p ? " selected" : ""}>${echapper(tv(p))}</option>`).join("")}
      </select>
      <select id="filtre-domaine">
        <option value="">${t("candidatures.tous_sous_domaines")}</option>
        ${v.sous_domaines.map((d) => `<option${etat.filtres.sous_domaine === d ? " selected" : ""}>${echapper(tv(d))}</option>`).join("")}
      </select>
    </div>`;

  let corps;
  if (liste.length === 0) {
    const filtreActif = etat.filtres.statut || etat.filtres.priorite || etat.filtres.sous_domaine || etat.filtres.texte;
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
          <th></th><th>${t("candidatures.col_entreprise")}</th><th>${t("candidatures.col_poste")}</th><th>${t("candidatures.col_statut")}</th><th>${t("candidatures.col_priorite")}</th>
          <th>${t("candidatures.col_envoyee_le")}</th><th>${t("candidatures.col_relance_prevue")}</th><th>${t("candidatures.col_ville")}</th>
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
              <td><span class="puce puce-statut" style="--couleur-statut:${COULEURS_STATUT[cand.statut]}"><span class="point"></span>${echapper(tv(cand.statut))}</span></td>
              <td class="cellule-secondaire">${echapper(tv(cand.priorite || ""))}</td>
              <td class="cellule-date">${dateFr(cand.date_envoi)}</td>
              <td class="cellule-date">${dateFr(cand.date_relance_prevue)}</td>
              <td class="cellule-secondaire">${echapper(cand.ville || "")}</td>
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
  brancherFiltre("filtre-priorite", "priorite");
  brancherFiltre("filtre-domaine", "sous_domaine");

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
   Relances : liste priorisée du jour, un clic pour marquer fait
   ======================================================================== */

async function vueRelances() {
  const liste = await api("/api/relances");
  if (!liste.length) {
    return `
      <div class="entete-vue"><h1>${t("nav.relances")}</h1></div>
      <div class="etat-vide">
        <div class="icone">${ICONES.candidatures}</div>
        <div class="titre">${t("relances.vide_titre")}</div>
        <p>${t("relances.vide_texte")}</p>
      </div>`;
  }
  const aujourdHui = dateISOLocale(new Date());
  const lignes = liste
    .map((cand) => {
      const enRetard = cand.date_relance_prevue < aujourdHui;
      return `
      <div class="ligne-relance${enRetard ? " en-retard" : ""}">
        <div class="ligne-relance-info" onclick="ouvrirDetailCandidature(${cand.id})">
          <div class="ligne-relance-titre">
            <strong>${echapper(cand.entreprise)}</strong> - ${echapper(cand.poste)}
            ${cand.priorite === "Haute" ? `<span class="puce puce-priorite-Haute">${t("candidatures.priorite_haute")}</span>` : ""}
          </div>
          <div class="cellule-secondaire">
            ${enRetard ? t("relances.en_retard_depuis", { date: dateFr(cand.date_relance_prevue) }) : t("relances.prevue_aujourdhui")}
            · ${echapper(tv(cand.statut))} · ${t("relances.relances_deja_faites", { n: cand.nb_relances || 0 })}
          </div>
        </div>
        <button type="button" class="btn btn-accent" onclick="marquerRelance(${cand.id})">${t("relances.relance_bouton")}</button>
      </div>`;
    })
    .join("");
  return `
    <div class="entete-vue">
      <div><h1>${t("nav.relances")}</h1><div class="sous-titre">${t("relances.sous_titre", { n: liste.length })}</div></div>
    </div>
    <div class="carte liste-relances">${lignes}</div>`;
}

function activerRelances() { /* liens inline */ }

async function marquerRelance(id) {
  try {
    await api(`/api/candidatures/${id}/relancer`, { methode: "POST" });
    toast(t("relances.enregistree"));
    rendre();
  } catch (erreur) {
    toast(erreur.message, true);
  }
}

/* ========================================================================
   Comparateur : plusieurs candidatures côte à côte
   ======================================================================== */

const CHAMPS_COMPARATEUR_ENUM = new Set(["statut", "priorite", "sous_domaine", "mode_travail", "convention_envoyee", "source"]);

function criteresComparateur() {
  return [
    ["statut", t("candidatures.col_statut")],
    ["priorite", t("candidatures.col_priorite")],
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
   Panneau latéral : formulaire candidature (création et édition)
   ======================================================================== */

function ouvrirPanneau(titre, corpsHTML, piedHTML) {
  document.getElementById("panneau-titre").textContent = titre;
  document.getElementById("panneau-corps").innerHTML = corpsHTML;
  document.getElementById("panneau-pied").innerHTML = piedHTML;
  document.getElementById("voile").classList.add("visible");
  const panneau = document.getElementById("panneau");
  panneau.classList.add("ouvert");
  panneau.setAttribute("aria-hidden", "false");
}

function fermerPanneau() {
  document.getElementById("voile").classList.remove("visible");
  const panneau = document.getElementById("panneau");
  panneau.classList.remove("ouvert");
  panneau.setAttribute("aria-hidden", "true");
}

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

async function ouvrirFormCandidature(cand = null) {
  const v = etat.valeurs;
  const creation = cand === null;
  cand = cand || {};
  let champEntreprise;
  if (creation) {
    const listeEntreprises = await api("/api/entreprises");
    champEntreprise = `
      <div class="champ">
        <label for="champ-entreprise">${t("formulaire.entreprise_requis")}</label>
        <input type="text" id="champ-entreprise" name="entreprise" list="liste-entreprises" required>
        <datalist id="liste-entreprises">
          ${listeEntreprises.map((ent) => `<option value="${echapper(ent.nom)}">`).join("")}
        </datalist>
      </div>`;
  } else {
    champEntreprise = `
      <div class="champ">
        <label>${t("formulaire.entreprise")}</label>
        <input type="text" value="${echapper(cand.entreprise)}" disabled>
      </div>`;
  }

  const corps = `
    <form id="form-candidature" class="grille-form" onsubmit="return false;">
      ${champEntreprise}
      ${champTexte("poste", t("formulaire.poste_requis"), cand.poste)}
      ${champSelect("statut", t("candidatures.col_statut"), v.statuts, cand.statut || "À préparer", false)}
      ${champSelect("priorite", t("candidatures.col_priorite"), v.priorites, cand.priorite || "Moyenne", false)}
      ${champSelect("sous_domaine", t("comparateur.sous_domaine"), v.sous_domaines, cand.sous_domaine)}
      ${champSelect("type_candidature", t("formulaire.type_candidature"), v.types_candidature, cand.type_candidature)}
      ${champSelect("source", t("comparateur.source"), v.sources_candidature, cand.source)}
      ${champTexte("date_envoi", t("formulaire.date_envoi"), cand.date_envoi, "date")}
      ${champTexte("date_relance_prevue", t("formulaire.relance_prevue_le"), cand.date_relance_prevue, "date")}
      ${champTexte("nb_relances", t("formulaire.nb_relances"), cand.nb_relances ?? (creation ? 0 : ""), "number")}
      ${champTexte("date_reponse", t("formulaire.reponse_recue_le"), cand.date_reponse, "date")}
      ${champTexte("date_entretien", t("comparateur.entretien_le"), cand.date_entretien, "date")}
      ${champTexte("date_debut_souhaitee", t("comparateur.debut_souhaite"), cand.date_debut_souhaitee, "date")}
      ${champTexte("duree", t("comparateur.duree"), cand.duree)}
      ${champTexte("gratification", t("comparateur.gratification"), cand.gratification, "number")}
      ${champTexte("ville", t("candidatures.col_ville"), cand.ville)}
      ${champSelect("mode_travail", t("comparateur.mode_travail"), v.modes_travail, cand.mode_travail)}
      ${champSelect("convention_envoyee", t("comparateur.convention_envoyee"), v.conventions, cand.convention_envoyee || "Non", false)}
      ${champTexte("lien_offre", t("formulaire.lien_offre"), cand.lien_offre, "url", true)}
      ${champTexte("portail_url", t("formulaire.portail_url"), cand.portail_url, "url", true)}
      ${champTexte("portail_identifiant", t("formulaire.portail_identifiant"), cand.portail_identifiant)}
      ${champMotDePasse("portail_mdp", t("formulaire.portail_mdp"), cand.portail_mdp)}
      ${champZone("texte_offre", t("formulaire.texte_offre"), cand.texte_offre)}
      ${champZone("notes", t("formulaire.notes"), cand.notes)}
      ${creation ? "" : champZone("notes_entretien", t("formulaire.notes_entretien"), cand.notes_entretien)}
    </form>`;

  // À la création : zone d'analyse IA (si une clé API est configurée dans Réglages).
  let zoneIA = "";
  if (creation) {
    zoneIA = etat.ia && etat.ia.cle_api_definie
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
        <a class="lien-detail" href="#/reglages" onclick="fermerPanneau()">${t("nav.reglages")}</a>
        ${t("formulaire.astuce_ia_fin")}</p>`;
  }

  // À la création : joindre tout de suite un ou plusieurs fichiers (offre en
  // PDF, CV, lettre…) - envoyés juste après la création de la candidature.
  let zoneDocuments = "";
  if (creation) {
    zoneDocuments = `
      <div class="zone-ia">
        <label for="fichiers-a-joindre">${t("formulaire.joindre_fichiers")}</label>
        <div class="zone-ia-actions">
          <select id="fichiers-type" style="max-width:220px;">${optionsSelect(v.types_document, "Offre (PDF)", false)}</select>
          <input type="file" id="fichiers-a-joindre" multiple style="flex:1;">
        </div>
      </div>`;
  }

  // En édition : documents et journal de la candidature.
  let sectionsSupplementaires = "";
  if (!creation) {
    const [journal, docs] = await Promise.all([
      api(`/api/candidatures/${cand.id}/evenements`),
      api(`/api/documents?candidature=${cand.id}`),
    ]);
    sectionsSupplementaires = sectionsCandidature(cand.id, journal, docs);
  }

  const pied = creation
    ? `<button class="btn" onclick="fermerPanneau()">${t("commun.annuler")}</button>
       <button class="btn btn-accent" id="btn-enregistrer">${t("formulaire.ajouter_candidature")}</button>`
    : `<button class="btn btn-danger" id="btn-supprimer">${t("commun.supprimer")}</button>
       <button class="btn" id="btn-fiche">${t("formulaire.fiche_entretien")}</button>
       <button class="btn" id="btn-mode-entretien">${t("formulaire.mode_entretien")}</button>
       <button class="btn btn-accent" id="btn-enregistrer">${t("commun.enregistrer")}</button>`;

  ouvrirPanneau(
    creation ? t("formulaire.nouvelle_candidature") : t("commun.titre_modifier", { nom: cand.entreprise }),
    zoneIA + corps + zoneDocuments + sectionsSupplementaires,
    pied
  );

  if (creation) {
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
  }

  document.getElementById("btn-enregistrer").addEventListener("click", async () => {
    const donnees = lireFormulaire(document.getElementById("form-candidature"));
    if (donnees.nb_relances !== null && donnees.nb_relances !== undefined) {
      donnees.nb_relances = donnees.nb_relances ?? 0;
    }
    try {
      if (creation) {
        // Avertissement (non bloquant) : intitulé proche ou même lien d'offre
        // qu'une candidature déjà enregistrée. Le vrai doublon (entreprise +
        // poste identiques) reste, lui, refusé net par le serveur.
        const parametres = new URLSearchParams({
          entreprise: donnees.entreprise || "",
          poste: donnees.poste || "",
          lien_offre: donnees.lien_offre || "",
        });
        const similaires = await api(`/api/candidatures/similaires?${parametres}`);
        if (similaires.length && !(await confirmerSimilaires(similaires))) {
          return;
        }
        const creee = await api("/api/candidatures", { methode: "POST", corps: donnees });
        toast(t("formulaire.candidature_ajoutee", { poste: creee.poste, entreprise: creee.entreprise }));
        // Fichiers joints (offre en PDF, CV…) : envoyés maintenant que la
        // candidature existe.
        const fichiersAJoindre = document.getElementById("fichiers-a-joindre")?.files;
        if (fichiersAJoindre && fichiersAJoindre.length) {
          await televerserDocument(
            creee.id, fichiersAJoindre, document.getElementById("fichiers-type").value, null
          );
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
      } else {
        await api(`/api/candidatures/${cand.id}`, { methode: "PATCH", corps: donnees });
        toast(t("formulaire.candidature_enregistree"));
      }
      fermerPanneau();
      rendre();
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });

  if (!creation) {
    document.getElementById("btn-supprimer").addEventListener("click", async () => {
      const accord = await confirmer(
        t("formulaire.supprimer_candidature_titre"),
        t("formulaire.supprimer_candidature_texte", { poste: cand.poste, entreprise: cand.entreprise })
      );
      if (!accord) return;
      try {
        await api(`/api/candidatures/${cand.id}`, { methode: "DELETE" });
        toast(t("formulaire.candidature_supprimee"));
        fermerPanneau();
        rendre();
      } catch (erreur) {
        toast(erreur.message, true);
      }
    });
    document.getElementById("btn-fiche").addEventListener("click", () => {
      ouvrirFicheEntretien(cand.id);
    });
    document.getElementById("btn-mode-entretien").addEventListener("click", () => {
      fermerPanneau();
      location.hash = `#/entretien/${cand.id}`;
    });
  }
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

function sectionsCandidature(numero, journal, docs) {
  const lignesDocs = docs
    .map(
      (doc) => `
    <div class="ligne-document">
      <span class="puce">${echapper(tv(doc.type_document || "Autre"))}</span>
      <a class="lien-detail" href="/api/documents/${doc.id}/telecharger">${echapper(doc.nom_fichier)}</a>
      <span class="cellule-secondaire">${dateFr(doc.date_ajout)}</span>
      <button type="button" class="btn btn-danger btn-mini" onclick="supprimerDocument(${doc.id}, ${numero})">${t("commun.supprimer")}</button>
    </div>`
    )
    .join("");
  const lignesJournal = journal
    .map(
      (evenement) => `
    <div class="ligne-journal">
      <span class="journal-date">${dateFr(evenement.horodatage.slice(0, 10))} ${echapper(evenement.horodatage.slice(11, 16))}</span>
      <span>${echapper(evenement.description)}</span>
    </div>`
    )
    .join("");
  return `
    <h3 class="section-panneau">${t("formulaire.documents_envoyes")}</h3>
    ${lignesDocs || `<p class="sous-titre">${t("formulaire.aucun_document")}</p>`}
    <div class="ajout-document">
      <select id="doc-type-panneau">${optionsSelect(etat.valeurs.types_document, null, false)}</select>
      <input type="file" id="doc-fichier-panneau" multiple>
      <button type="button" class="btn" id="btn-doc-panneau"
        onclick="televerserDocument(${numero}, document.getElementById('doc-fichier-panneau').files, document.getElementById('doc-type-panneau').value, () => ouvrirDetailCandidature(${numero}))">
        ${t("commun.ajouter_simple")}</button>
    </div>
    <h3 class="section-panneau">${t("formulaire.historique")}</h3>
    <div class="journal">${lignesJournal || `<p class="sous-titre">${t("formulaire.aucun_evenement")}</p>`}</div>`;
}

function contenuFicheCandidature(cand) {
  const lienOffre = cand.lien_offre
    ? `<a class="lien-detail" href="${echapper(cand.lien_offre)}" target="_blank" rel="noopener">${echapper(cand.lien_offre)}</a>` +
      (cand.lien_dernier_etat === "mort" ? ` <span class="puce puce-lien-mort">${t("candidatures.lien_mort")}</span>` : "")
    : null;
  const portailUrl = cand.portail_url
    ? `<a class="lien-detail" href="${echapper(cand.portail_url)}" target="_blank" rel="noopener">${echapper(cand.portail_url)}</a>`
    : null;

  return `
    <div class="fiche-entete-detail">
      <div>
        <h2>${echapper(cand.poste)}</h2>
        <p class="fiche-soustitre">${echapper(cand.entreprise)}${cand.ville ? " · " + echapper(cand.ville) : ""}</p>
      </div>
      ${cand.statut ? `<span class="puce puce-statut" style="--couleur-statut:${COULEURS_STATUT[cand.statut]}"><span class="point"></span>${echapper(tv(cand.statut))}</span>` : ""}
    </div>
    <div class="grille-form">
      ${champAffiche(t("candidatures.col_priorite"), cand.priorite ? echapper(tv(cand.priorite)) : null)}
      ${champAffiche(t("comparateur.sous_domaine"), cand.sous_domaine ? echapper(tv(cand.sous_domaine)) : null)}
      ${champAffiche(t("formulaire.type_candidature"), cand.type_candidature ? echapper(tv(cand.type_candidature)) : null)}
      ${champAffiche(t("comparateur.source"), cand.source ? echapper(tv(cand.source)) : null)}
      ${champAffiche(t("formulaire.date_envoi"), dateFr(cand.date_envoi))}
      ${champAffiche(t("formulaire.relance_prevue_le"), dateFr(cand.date_relance_prevue))}
      ${champAffiche(t("formulaire.nb_relances"), cand.nb_relances || null)}
      ${champAffiche(t("formulaire.reponse_recue_le"), dateFr(cand.date_reponse))}
      ${champAffiche(t("comparateur.entretien_le"), dateFr(cand.date_entretien))}
      ${champAffiche(t("comparateur.debut_souhaite"), dateFr(cand.date_debut_souhaitee))}
      ${champAffiche(t("comparateur.duree"), cand.duree ? echapper(cand.duree) : null)}
      ${champAffiche(t("formulaire.gratification_label"), cand.gratification ? `${echapper(cand.gratification)} €/mois` : null)}
      ${champAffiche(t("comparateur.mode_travail"), cand.mode_travail ? echapper(tv(cand.mode_travail)) : null)}
      ${champAffiche(t("comparateur.convention_envoyee"), cand.convention_envoyee ? echapper(tv(cand.convention_envoyee)) : null)}
      ${champAffiche(t("formulaire.lien_offre"), lienOffre, true)}
      ${portailUrl ? champAffiche(t("formulaire.portail_candidature"), portailUrl, true) : ""}
      ${cand.portail_identifiant ? champAffiche(t("formulaire.portail_identifiant"), echapper(cand.portail_identifiant)) : ""}
    </div>
    ${cand.portail_mdp ? champAfficheMotDePasse("mdp-portail-affiche", t("formulaire.portail_mdp"), cand.portail_mdp) : ""}
    ${cand.texte_offre ? `<h3 class="section-panneau">${t("formulaire.texte_offre")}</h3><div class="texte-long">${echapper(cand.texte_offre)}</div>` : ""}
    ${cand.notes ? `<h3 class="section-panneau">${t("formulaire.notes")}</h3><div class="texte-long">${echapper(cand.notes)}</div>` : ""}
    ${cand.notes_entretien ? `<h3 class="section-panneau">${t("formulaire.notes_entretien")}</h3><div class="texte-long">${echapper(cand.notes_entretien)}</div>` : ""}`;
}

async function ouvrirDetailCandidature(numero) {
  try {
    const cand = await api(`/api/candidatures/${numero}`);
    const [journal, docs] = await Promise.all([
      api(`/api/candidatures/${numero}/evenements`),
      api(`/api/documents?candidature=${numero}`),
    ]);
    const corps = contenuFicheCandidature(cand) + sectionsCandidature(numero, journal, docs);
    const peutRelancerIA = etat.ia && etat.ia.cle_api_definie
      && ["Envoyée", "Relancée"].includes(cand.statut);
    const pied = `
      <button class="btn btn-danger" id="btn-supprimer">${t("commun.supprimer")}</button>
      ${peutRelancerIA ? `<button class="btn" id="btn-brouillon-relance">${t("formulaire.brouillon_relance")}</button>` : ""}
      <button class="btn" id="btn-fiche">${t("formulaire.fiche_entretien")}</button>
      <button class="btn" id="btn-mode-entretien">${t("formulaire.mode_entretien")}</button>
      <button class="btn btn-accent" id="btn-modifier">${t("commun.modifier")}</button>`;
    ouvrirPanneau(`${cand.poste} - ${cand.entreprise}`, corps, pied);

    document.getElementById("btn-modifier").addEventListener("click", () => ouvrirFormCandidature(cand));
    document.getElementById("btn-fiche").addEventListener("click", () => ouvrirFicheEntretien(cand.id));
    document.getElementById("btn-mode-entretien").addEventListener("click", () => {
      fermerPanneau();
      location.hash = `#/entretien/${cand.id}`;
    });
    const boutonRelance = document.getElementById("btn-brouillon-relance");
    if (boutonRelance) {
      boutonRelance.addEventListener("click", async () => {
        boutonRelance.disabled = true;
        boutonRelance.textContent = t("formulaire.generation_en_cours");
        try {
          const resultat = await api(`/api/agent/relance/${numero}`, { methode: "POST", corps: {} });
          ouvrirModale(
            t("formulaire.brouillon_relance"),
            `<p class="sous-titre">${t("formulaire.brouillon_relance_avertissement")}</p>
             <textarea id="texte-brouillon-relance" style="min-height:220px;" readonly>${echapper(resultat.texte)}</textarea>`,
            `<button class="btn" onclick="fermerModale()">${t("commun.fermer")}</button>
             <button class="btn btn-accent" id="btn-copier-relance">${t("formulaire.copier")}</button>`
          );
          document.getElementById("btn-copier-relance").addEventListener("click", async () => {
            await navigator.clipboard.writeText(document.getElementById("texte-brouillon-relance").value);
            toast(t("formulaire.message_copie"));
          });
        } catch (erreur) {
          toast(erreur.message, true);
        } finally {
          boutonRelance.disabled = false;
          boutonRelance.textContent = t("formulaire.brouillon_relance");
        }
      });
    }
    document.getElementById("btn-supprimer").addEventListener("click", async () => {
      const accord = await confirmer(
        t("formulaire.supprimer_candidature_titre"),
        t("formulaire.supprimer_candidature_texte", { poste: cand.poste, entreprise: cand.entreprise })
      );
      if (!accord) return;
      try {
        await api(`/api/candidatures/${numero}`, { methode: "DELETE" });
        toast(t("formulaire.candidature_supprimee"));
        fermerPanneau();
        rendre();
      } catch (erreur) {
        toast(erreur.message, true);
      }
    });
  } catch (erreur) {
    toast(erreur.message, true);
  }
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
        <span class="puce">${t("entreprises.nb_candidatures", { n: ent.nb_candidatures })}${ent.nb_candidatures > 1 ? "s" : ""}</span>
        <span class="puce">${t("entreprises.nb_contacts", { n: ent.nb_contacts })}${ent.nb_contacts > 1 ? "s" : ""}</span>
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
      <button class="btn btn-accent" onclick="ouvrirFormEntreprise()">${t("commun.ajouter")}</button>
    </div>
    ${banniereFusion}
    ${liste.length ? `<div class="grille-entreprises">${cartes}</div>` : `
      <div class="etat-vide">
        <div class="icone">${ICONES.entreprises}</div>
        <div class="titre">${t("entreprises.vide_titre")}</div>
        <p>${t("entreprises.vide_texte")}</p>
        <button class="btn btn-accent" onclick="ouvrirFormEntreprise()">${t("entreprises.ajouter_bouton")}</button>
      </div>`}`;
}

function activerEntreprises() { /* liens inline */ }

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
        <span class="cellule-secondaire">${t("entreprises.fusionner_dedans", { cand: garder.nb_candidatures ?? 0, contacts: garder.nb_contacts ?? 0, nom: echapper(fusionner.nom) })}</span>
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
            cand: resultat.candidatures_deplacees, contacts: resultat.contacts_deplaces, nom: resultat.nom,
          })
        );
        rendre();
      } catch (erreur) {
        toast(erreur.message, true);
      }
    });
  });
}

async function ouvrirFormEntreprise(numero = null) {
  const creation = numero === null;
  let ent = {};
  if (!creation) {
    const liste = await api("/api/entreprises");
    ent = liste.find((e) => e.id === numero) || {};
  }
  const corps = `
    <form id="form-entreprise" class="grille-form" onsubmit="return false;">
      ${champTexte("nom", t("entreprises.nom_requis"), ent.nom, "text", true)}
      ${champTexte("site_web", t("entreprises.site_web"), ent.site_web, "url", true)}
      ${champZone("contexte_actus", t("entreprises.contexte_label"), ent.contexte_actus)}
      ${champTexte("derniere_recherche", t("entreprises.derniere_recherche_le"), ent.derniere_recherche, "date", true)}
    </form>`;
  const pied = creation
    ? `<button class="btn" onclick="fermerPanneau()">${t("commun.annuler")}</button>
       <button class="btn btn-accent" id="btn-enregistrer">${t("entreprises.ajouter_entreprise")}</button>`
    : `<button class="btn btn-danger" id="btn-supprimer">${t("commun.supprimer")}</button>
       <button class="btn btn-accent" id="btn-enregistrer">${t("commun.enregistrer")}</button>`;
  ouvrirPanneau(creation ? t("entreprises.nouvelle_entreprise") : t("commun.titre_modifier", { nom: ent.nom }), corps, pied);

  document.getElementById("btn-enregistrer").addEventListener("click", async () => {
    const donnees = lireFormulaire(document.getElementById("form-entreprise"));
    try {
      if (creation) {
        await api("/api/entreprises", { methode: "POST", corps: donnees });
        toast(t("entreprises.entreprise_enregistree"));
      } else {
        await api(`/api/entreprises/${numero}`, { methode: "PATCH", corps: donnees });
        toast(t("entreprises.entreprise_enregistree"));
      }
      fermerPanneau();
      rendre();
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });
  if (!creation) {
    document.getElementById("btn-supprimer").addEventListener("click", async () => {
      const accord = await confirmer(
        t("entreprises.supprimer_titre"),
        t("entreprises.supprimer_texte", { nom: ent.nom })
      );
      if (!accord) return;
      try {
        await api(`/api/entreprises/${numero}`, { methode: "DELETE" });
        toast(t("entreprises.entreprise_supprimee"));
        fermerPanneau();
        rendre();
      } catch (erreur) {
        toast(erreur.message, true);
      }
    });
  }
}

async function ouvrirDetailEntreprise(numero) {
  try {
    const [listeEntreprises, listeContacts, listeCandidatures] = await Promise.all([
      api("/api/entreprises"),
      api("/api/contacts"),
      api("/api/candidatures"),
    ]);
    const ent = listeEntreprises.find((e) => e.id === numero);
    if (!ent) { toast(t("entreprises.introuvable"), true); return; }
    const contactsEnt = listeContacts.filter((c) => c.entreprise === ent.nom);
    const candidaturesEnt = listeCandidatures.filter((c) => c.entreprise === ent.nom);

    const ligneContact = (c) => {
      const coordonnee = c.email || c.telephone || c.linkedin || "";
      return `
      <div class="ligne-liee" onclick="ouvrirDetailContact(${c.id})">
        <span class="cellule-principale">${echapper(c.nom)}${c.poste ? ` <span class="cellule-secondaire">${echapper(c.poste)}</span>` : ""}</span>
        ${coordonnee ? `<span class="cellule-secondaire">${echapper(coordonnee)}</span>` : ""}
        ${c.statut_contact ? `<span class="puce">${echapper(tv(c.statut_contact))}</span>` : ""}
      </div>`;
    };
    const ligneCandidature = (c) => `
      <div class="ligne-liee" onclick="ouvrirDetailCandidature(${c.id})">
        <span class="cellule-principale">${echapper(c.poste)}</span>
        <span class="puce puce-statut" style="--couleur-statut:${COULEURS_STATUT[c.statut]}"><span class="point"></span>${echapper(tv(c.statut))}</span>
      </div>`;

    const corps = `
      <div class="fiche-entete-detail">
        <div>
          <h2>${echapper(ent.nom)}</h2>
          ${ent.site_web ? `<p class="fiche-soustitre"><a class="lien-detail" href="${echapper(ent.site_web)}" target="_blank" rel="noopener">${echapper(ent.site_web)}</a></p>` : ""}
        </div>
      </div>
      <h3 class="section-panneau">${t("entreprises.contexte_actus")}</h3>
      ${ent.contexte_actus
        ? `<div class="texte-long">${echapper(ent.contexte_actus)}</div>`
        : `<div class="valeur-affichee vide">${t("entreprises.pas_de_contexte_fiche")}</div>`}
      ${ent.derniere_recherche ? `<p class="cellule-secondaire" style="margin-top:8px;">${t("entreprises.derniere_recherche_texte", { date: dateFr(ent.derniere_recherche) })}</p>` : ""}

      <h3 class="section-panneau">${t("entreprises.contacts_titre", { n: contactsEnt.length })}</h3>
      ${contactsEnt.length ? `<div class="liste-liee">${contactsEnt.map(ligneContact).join("")}</div>` : `<p class="sous-titre">${t("entreprises.aucun_contact")}</p>`}

      <h3 class="section-panneau">${t("entreprises.candidatures_titre", { n: candidaturesEnt.length })}</h3>
      ${candidaturesEnt.length ? `<div class="liste-liee">${candidaturesEnt.map(ligneCandidature).join("")}</div>` : `<p class="sous-titre">${t("entreprises.aucune_candidature")}</p>`}`;

    const pied = `
      <button class="btn btn-danger" id="btn-supprimer">${t("commun.supprimer")}</button>
      <button class="btn btn-accent" id="btn-modifier">${t("commun.modifier")}</button>`;
    ouvrirPanneau(ent.nom, corps, pied);

    document.getElementById("btn-modifier").addEventListener("click", () => ouvrirFormEntreprise(numero));
    document.getElementById("btn-supprimer").addEventListener("click", async () => {
      const accord = await confirmer(
        t("entreprises.supprimer_titre"),
        t("entreprises.supprimer_texte", { nom: ent.nom })
      );
      if (!accord) return;
      try {
        await api(`/api/entreprises/${numero}`, { methode: "DELETE" });
        toast(t("entreprises.entreprise_supprimee"));
        fermerPanneau();
        rendre();
      } catch (erreur) {
        toast(erreur.message, true);
      }
    });
  } catch (erreur) {
    toast(erreur.message, true);
  }
}

/* ========================================================================
   Contacts
   ======================================================================== */

async function vueContacts() {
  const liste = await api("/api/contacts");
  const lignes = liste
    .map(
      (contact) => `
    <tr onclick="ouvrirDetailContact(${contact.id})">
      <td class="cellule-principale">${echapper(contact.nom)}</td>
      <td>${echapper(contact.entreprise)}</td>
      <td class="cellule-secondaire">${echapper(contact.poste || "")}</td>
      <td class="cellule-secondaire">${echapper(contact.email || "")}</td>
      <td class="cellule-secondaire">${echapper(contact.telephone || "")}</td>
      <td class="cellule-secondaire">${echapper(contact.linkedin || "")}</td>
      <td><span class="puce">${echapper(tv(contact.statut_contact || ""))}</span></td>
      <td class="cellule-date">${dateFr(contact.date_contact)}</td>
    </tr>`
    )
    .join("");

  return `
    <div class="entete-vue">
      <h1>${t("nav.contacts")}</h1>
      <button class="btn btn-accent" onclick="ouvrirFormContact()">${t("commun.ajouter")}</button>
    </div>
    ${liste.length ? `
      <div class="enveloppe-tableau"><table class="tableau">
        <thead><tr><th>${t("contacts.col_nom")}</th><th>${t("candidatures.col_entreprise")}</th><th>${t("candidatures.col_poste")}</th><th>${t("contacts.email")}</th><th>${t("contacts.telephone")}</th><th>${t("contacts.linkedin")}</th><th>${t("candidatures.col_statut")}</th><th>${t("contacts.contacte_le")}</th></tr></thead>
        <tbody>${lignes}</tbody>
      </table></div>` : `
      <div class="etat-vide">
        <div class="icone">${ICONES.contacts}</div>
        <div class="titre">${t("contacts.vide_titre")}</div>
        <p>${t("contacts.vide_texte")}</p>
        <button class="btn btn-accent" onclick="ouvrirFormContact()">${t("contacts.ajouter_bouton")}</button>
      </div>`}`;
}

function activerContacts() { /* liens inline */ }

async function ouvrirDetailContact(numero) {
  try {
    const [liste, listeEntreprises] = await Promise.all([
      api("/api/contacts"),
      api("/api/entreprises"),
    ]);
    const contact = liste.find((c) => c.id === numero);
    if (!contact) { toast(t("contacts.introuvable"), true); return; }
    const entreprise = listeEntreprises.find((e) => e.nom === contact.entreprise);

    const ligneEntreprise = entreprise
      ? `<a class="lien-detail" href="#" onclick="event.preventDefault(); ouvrirDetailEntreprise(${entreprise.id})">${echapper(contact.entreprise)}</a>`
      : echapper(contact.entreprise);

    // Un champ n'est affiché que s'il n'est pas vide (aucun email/téléphone/
    // LinkedIn) : pas de ligne vide pour une coordonnée non renseignée.
    const champsCoordonnees = [
      contact.email ? champAffiche(t("contacts.email"), `<a class="lien-detail" href="mailto:${echapper(contact.email)}">${echapper(contact.email)}</a>`) : "",
      contact.telephone ? champAffiche(t("contacts.telephone"), `<a class="lien-detail" href="tel:${echapper(contact.telephone)}">${echapper(contact.telephone)}</a>`) : "",
      contact.linkedin ? champAffiche(t("contacts.linkedin"), /^https?:\/\//i.test(contact.linkedin)
        ? `<a class="lien-detail" href="${echapper(contact.linkedin)}" target="_blank" rel="noopener">${echapper(contact.linkedin)}</a>`
        : echapper(contact.linkedin)) : "",
    ].join("");

    const corps = `
      <div class="fiche-entete-detail">
        <div>
          <h2>${echapper(contact.nom)}</h2>
          <p class="fiche-soustitre">${ligneEntreprise}${contact.poste ? " · " + echapper(contact.poste) : ""}</p>
        </div>
        ${contact.statut_contact ? `<span class="puce">${echapper(tv(contact.statut_contact))}</span>` : ""}
      </div>
      <div class="grille-form">
        ${champAffiche(t("contacts.equipe"), contact.equipe ? echapper(contact.equipe) : null)}
        ${champAffiche(t("contacts.contacte_le"), dateFr(contact.date_contact))}
        ${champsCoordonnees}
        ${champAffiche(t("contacts.trouve_via"), contact.source ? echapper(tv(contact.source)) : null)}
      </div>
      ${contact.notes ? `<h3 class="section-panneau">${t("formulaire.notes")}</h3><div class="texte-long">${echapper(contact.notes)}</div>` : ""}`;

    const pied = `
      <button class="btn btn-danger" id="btn-supprimer">${t("commun.supprimer")}</button>
      <button class="btn btn-accent" id="btn-modifier">${t("commun.modifier")}</button>`;
    ouvrirPanneau(contact.nom, corps, pied);

    document.getElementById("btn-modifier").addEventListener("click", () => ouvrirFormContact(numero));
    document.getElementById("btn-supprimer").addEventListener("click", async () => {
      const accord = await confirmer(
        t("contacts.supprimer_titre"),
        t("contacts.supprimer_texte", { nom: contact.nom, entreprise: contact.entreprise })
      );
      if (!accord) return;
      try {
        await api(`/api/contacts/${numero}`, { methode: "DELETE" });
        toast(t("contacts.contact_supprime"));
        fermerPanneau();
        rendre();
      } catch (erreur) {
        toast(erreur.message, true);
      }
    });
  } catch (erreur) {
    toast(erreur.message, true);
  }
}

async function ouvrirFormContact(numero = null) {
  const v = etat.valeurs;
  const creation = numero === null;
  let contact = {};
  const listeEntreprises = await api("/api/entreprises");
  if (!creation) {
    const liste = await api("/api/contacts");
    contact = liste.find((c) => c.id === numero) || {};
  }
  const champEntreprise = creation
    ? `<div class="champ">
        <label for="champ-entreprise">${t("formulaire.entreprise_requis")}</label>
        <input type="text" id="champ-entreprise" name="entreprise" list="liste-entreprises" required>
        <datalist id="liste-entreprises">
          ${listeEntreprises.map((ent) => `<option value="${echapper(ent.nom)}">`).join("")}
        </datalist>
      </div>`
    : `<div class="champ"><label>${t("formulaire.entreprise")}</label>
        <input type="text" value="${echapper(contact.entreprise)}" disabled></div>`;

  const corps = `
    <form id="form-contact" class="grille-form" onsubmit="return false;">
      ${champEntreprise}
      ${champTexte("nom", t("contacts.nom_requis"), contact.nom)}
      ${champTexte("poste", t("candidatures.col_poste"), contact.poste)}
      ${champTexte("equipe", t("contacts.equipe"), contact.equipe)}
      ${champTexte("email", t("contacts.email"), contact.email, "email")}
      ${champTexte("telephone", t("contacts.telephone"), contact.telephone, "tel")}
      ${champTexte("linkedin", t("contacts.linkedin"), contact.linkedin, "url")}
      ${champSelect("statut_contact", t("candidatures.col_statut"), v.statuts_contact, contact.statut_contact || "À contacter", false)}
      ${champTexte("date_contact", t("contacts.contacte_le"), contact.date_contact, "date")}
      ${champSelect("source", t("contacts.trouve_via"), v.sources_contact, contact.source)}
      ${champZone("notes", t("formulaire.notes"), contact.notes)}
    </form>`;
  const pied = creation
    ? `<button class="btn" onclick="fermerPanneau()">${t("commun.annuler")}</button>
       <button class="btn btn-accent" id="btn-enregistrer">${t("contacts.ajouter_contact")}</button>`
    : `<button class="btn btn-danger" id="btn-supprimer">${t("commun.supprimer")}</button>
       <button class="btn btn-accent" id="btn-enregistrer">${t("commun.enregistrer")}</button>`;
  ouvrirPanneau(creation ? t("contacts.nouveau_contact") : t("commun.titre_modifier", { nom: contact.nom }), corps, pied);

  document.getElementById("btn-enregistrer").addEventListener("click", async () => {
    const donnees = lireFormulaire(document.getElementById("form-contact"));
    try {
      if (creation) {
        await api("/api/contacts", { methode: "POST", corps: donnees });
        toast(t("contacts.contact_ajoute"));
      } else {
        await api(`/api/contacts/${numero}`, { methode: "PATCH", corps: donnees });
        toast(t("contacts.contact_enregistre"));
      }
      fermerPanneau();
      rendre();
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });
  if (!creation) {
    document.getElementById("btn-supprimer").addEventListener("click", async () => {
      const accord = await confirmer(
        t("contacts.supprimer_titre"),
        t("contacts.supprimer_texte", { nom: contact.nom, entreprise: contact.entreprise })
      );
      if (!accord) return;
      try {
        await api(`/api/contacts/${numero}`, { methode: "DELETE" });
        toast(t("contacts.contact_supprime"));
        fermerPanneau();
        rendre();
      } catch (erreur) {
        toast(erreur.message, true);
      }
    });
  }
}

/* ========================================================================
   Agenda : échéances en vue mois / 2 semaines, export .ics
   ======================================================================== */

function dateISOLocale(objet) {
  return `${objet.getFullYear()}-${String(objet.getMonth() + 1).padStart(2, "0")}-${String(objet.getDate()).padStart(2, "0")}`;
}

/* Lien « Ajouter à Google Agenda » pré-rempli pour une échéance (événement
   d'une journée). Google n'acceptant pas les abonnements à une adresse
   locale, ce lien par-événement est la voie recommandée pour Google Agenda. */
function lienGoogleAgenda(echeance) {
  const debut = new Date(`${echeance.date}T00:00:00`);
  const fin = new Date(debut);
  fin.setDate(fin.getDate() + 1);
  const format = (d) => dateISOLocale(d).replace(/-/g, "");
  const parametres = new URLSearchParams({
    action: "TEMPLATE",
    text: `${tv(echeance.libelle)} - ${echeance.entreprise}`,
    dates: `${format(debut)}/${format(fin)}`,
    details: echeance.poste,
  });
  return `https://www.google.com/calendar/render?${parametres}`;
}

function chipEcheance(echeance) {
  const donneesEcheance = echapperAttribut(JSON.stringify(echeance));
  const boutonRappel = etat.valeurs.plateforme_macos
    ? `<button type="button" class="chip-echeance-ajout" data-echeance="${donneesEcheance}"
              title="${t("agenda.envoyer_rappels")}"
              onclick="event.stopPropagation(); pousserRappelDepuisBouton(this)">R</button>`
    : "";
  return `
    <span class="chip-echeance-groupe" style="--couleur-statut:${COULEURS_ECHEANCE[echeance.type]}">
      <button class="chip-echeance"
              onclick="ouvrirDetailCandidature(${echeance.candidature_id})"
              title="${echapper(tv(echeance.libelle))} - ${echapper(echeance.entreprise)} (${echapper(echeance.poste)})">
        <span class="point"></span>${echapper(tv(echeance.libelle))} · ${echapper(echeance.entreprise)}
      </button>
      <a class="chip-echeance-ajout" href="${lienGoogleAgenda(echeance)}" target="_blank" rel="noopener"
         title="${t("agenda.ajouter_google")}" onclick="event.stopPropagation()">+</a>
      ${boutonRappel}
    </span>`;
}

async function pousserRappelDepuisBouton(bouton) {
  const echeance = JSON.parse(bouton.dataset.echeance);
  const texteInitial = bouton.textContent;
  bouton.textContent = "…";
  try {
    await api("/api/rappels/echeance", { methode: "POST", corps: echeance });
    toast(t("agenda.rappel_cree"));
    bouton.textContent = "✓";
    setTimeout(() => { bouton.textContent = texteInitial; }, 1500);
  } catch (erreur) {
    toast(erreur.message, true);
    bouton.textContent = texteInitial;
  }
}

async function vueAgenda() {
  const echeances = await api("/api/agenda");
  if (!etat.agendaBase) {
    const maintenant = new Date();
    etat.agendaBase = new Date(maintenant.getFullYear(), maintenant.getMonth(), 1);
  }
  const parJour = {};
  echeances.forEach((e) => (parJour[e.date] = parJour[e.date] || []).push(e));

  const localeAgenda = etat.langue === "en" ? "en-US" : "fr-FR";
  const entete = `
    <div class="entete-vue">
      <h1>${t("nav.agenda")}</h1>
      <div class="bascule">
        <button data-agenda="mois" class="${etat.agendaMode === "mois" ? "actif" : ""}">${t("agenda.mois")}</button>
        <button data-agenda="semaine" class="${etat.agendaMode === "semaine" ? "actif" : ""}">${t("agenda.deux_semaines")}</button>
      </div>
      <a class="btn" href="/api/agenda/ics" title="${t("agenda.exporter_titre")}">${t("agenda.exporter")}</a>
      <button class="btn btn-accent" onclick="ouvrirConnexionCalendrier()">${t("agenda.connecter_calendrier")}</button>
    </div>
    <div class="legende-agenda">
      <span class="puce puce-statut" style="--couleur-statut:${COULEURS_ECHEANCE.relance}"><span class="point"></span>${t("agenda.legende_relance")}</span>
      <span class="puce puce-statut" style="--couleur-statut:${COULEURS_ECHEANCE.entretien}"><span class="point"></span>${tv("Entretien")}</span>
      <span class="puce puce-statut" style="--couleur-statut:${COULEURS_ECHEANCE.debut}"><span class="point"></span>${t("agenda.legende_debut")}</span>
    </div>`;

  if (etat.agendaMode === "semaine") {
    const blocs = [];
    const curseur = new Date();
    for (let i = 0; i < 14; i++) {
      const iso = dateISOLocale(curseur);
      const jour = parJour[iso] || [];
      if (jour.length) {
        const libelle = curseur.toLocaleDateString(localeAgenda, { weekday: "long", day: "numeric", month: "long" });
        blocs.push(`
          <div class="jour-semaine">
            <div class="jour-semaine-titre">${echapper(libelle)}${i === 0 ? " - " + t("agenda.aujourdhui_minuscule") : ""}</div>
            ${jour.map(chipEcheance).join("")}
          </div>`);
      }
      curseur.setDate(curseur.getDate() + 1);
    }
    return entete + (blocs.length
      ? `<div class="carte">${blocs.join("")}</div>`
      : `<div class="etat-vide"><div class="titre">${t("agenda.vide_titre")}</div><p>${t("agenda.vide_texte")}</p></div>`);
  }

  // Vue mois
  const base = etat.agendaBase;
  const nomMois = base.toLocaleDateString(localeAgenda, { month: "long", year: "numeric" });
  const decalage = (new Date(base.getFullYear(), base.getMonth(), 1).getDay() + 6) % 7; // lundi = 0
  const joursDansMois = new Date(base.getFullYear(), base.getMonth() + 1, 0).getDate();
  const aujourdHui = dateISOLocale(new Date());
  const cellules = [];
  for (let i = 0; i < decalage; i++) cellules.push(`<div class="cellule-jour hors-mois"></div>`);
  for (let jour = 1; jour <= joursDansMois; jour++) {
    const iso = dateISOLocale(new Date(base.getFullYear(), base.getMonth(), jour));
    const evenementsJour = parJour[iso] || [];
    const visibles = evenementsJour.slice(0, 3).map(chipEcheance).join("");
    const reste = evenementsJour.length > 3 ? `<span class="sous-titre">+${evenementsJour.length - 3}</span>` : "";
    cellules.push(`
      <div class="cellule-jour${iso === aujourdHui ? " aujourdhui" : ""}">
        <div class="jour-numero">${jour}</div>
        ${visibles}${reste}
      </div>`);
  }
  return `${entete}
    <div class="agenda-nav">
      <button class="btn" id="agenda-precedent">‹</button>
      <div class="agenda-mois">${echapper(nomMois)}</div>
      <button class="btn" id="agenda-suivant">›</button>
      <button class="btn btn-discret" id="agenda-aujourdhui">${t("agenda.aujourdhui")}</button>
    </div>
    <div class="grille-agenda-entete">${t("agenda.jours_semaine").split(",").map((j) => `<div>${j}</div>`).join("")}</div>
    <div class="grille-agenda">${cellules.join("")}</div>`;
}

function activerAgenda() {
  document.querySelectorAll("[data-agenda]").forEach((bouton) => {
    bouton.addEventListener("click", () => { etat.agendaMode = bouton.dataset.agenda; rendre(); });
  });
  const decaler = (mois) => {
    etat.agendaBase = new Date(etat.agendaBase.getFullYear(), etat.agendaBase.getMonth() + mois, 1);
    rendre();
  };
  const precedent = document.getElementById("agenda-precedent");
  if (precedent) {
    precedent.addEventListener("click", () => decaler(-1));
    document.getElementById("agenda-suivant").addEventListener("click", () => decaler(1));
    document.getElementById("agenda-aujourdhui").addEventListener("click", () => {
      const maintenant = new Date();
      etat.agendaBase = new Date(maintenant.getFullYear(), maintenant.getMonth(), 1);
      rendre();
    });
  }
}

/* « S'abonner » (webcal, en direct tant qu'Azimut tourne) pour Calendrier/
   Outlook, et marche à suivre pour Google Agenda (pas d'abonnement possible
   sur une adresse locale : lien par événement ou import du fichier .ics). */
function ouvrirConnexionCalendrier() {
  const lienAbonnement = location.origin.replace(/^http/, "webcal") + "/api/agenda/abonnement.ics";
  const blocRappels = etat.valeurs.plateforme_macos
    ? `<div class="bloc-calendrier">
      <h3>${t("agenda.rappels_titre")}</h3>
      <p class="sous-titre">${t("agenda.rappels_texte")}</p>
      <button class="btn" id="btn-tout-pousser-rappels">${t("agenda.envoyer_toutes_echeances")}</button>
      <p class="sous-titre" id="resultat-rappels" style="margin-top:8px;"></p>
    </div>`
    : "";
  ouvrirModale(
    t("agenda.connecter_calendrier"),
    `
    <div class="bloc-calendrier">
      <h3>${t("agenda.calendrier_mac_titre")}</h3>
      <p class="sous-titre">${t("agenda.calendrier_mac_texte")}</p>
      <a class="btn btn-accent" href="${lienAbonnement}">${t("agenda.sabonner")}</a>
    </div>
    <div class="bloc-calendrier">
      <h3>${t("agenda.google_titre")}</h3>
      <p class="sous-titre">${t("agenda.google_texte")}</p>
      <ul>
        <li>${t("agenda.google_option1")}</li>
        <li>${t("agenda.google_option2")}</li>
      </ul>
      <a class="btn" href="/api/agenda/ics">${t("agenda.telecharger_ics")}</a>
    </div>
    <div class="bloc-calendrier">
      <h3>${t("agenda.outlook_titre")}</h3>
      <p class="sous-titre">${t("agenda.outlook_texte")}</p>
    </div>
    ${blocRappels}`,
    `<button class="btn btn-accent" onclick="fermerModale()">${t("commun.fermer")}</button>`
  );
  const boutonToutPousser = document.getElementById("btn-tout-pousser-rappels");
  if (boutonToutPousser) {
    boutonToutPousser.addEventListener("click", async (evenement) => {
      const bouton = evenement.currentTarget;
      bouton.disabled = true;
      bouton.textContent = t("agenda.envoi_en_cours");
      try {
        const resultat = await api("/api/rappels/tout_pousser", { methode: "POST" });
        document.getElementById("resultat-rappels").textContent =
          t("agenda.rappels_crees", { n: resultat.reussies }) + (resultat.echouees ? ", " + t("agenda.rappels_echecs", { n: resultat.echouees }) : ".");
        toast(t("agenda.rappels_envoyes", { n: resultat.reussies }));
      } catch (erreur) {
        toast(erreur.message, true);
      } finally {
        bouton.disabled = false;
        bouton.textContent = t("agenda.envoyer_toutes_echeances");
      }
    });
  }
}

/* ========================================================================
   Documents : CV / lettres envoyés, par candidature
   ======================================================================== */

async function vueDocuments() {
  const liste = await api("/api/documents");
  const lignes = liste
    .map(
      (doc) => `
    <tr>
      <td class="cellule-principale">${echapper(doc.nom_fichier)}</td>
      <td><span class="puce">${echapper(tv(doc.type_document || "Autre"))}</span></td>
      <td>${echapper(doc.entreprise)} <span class="cellule-secondaire">${echapper(doc.poste)}</span></td>
      <td class="cellule-date">${dateFr(doc.date_ajout)}</td>
      <td>
        <a class="btn btn-discret" href="/api/documents/${doc.id}/telecharger">${t("documents.telecharger")}</a>
        <button class="btn btn-danger" onclick="supprimerDocument(${doc.id}, null)">${t("commun.supprimer")}</button>
      </td>
    </tr>`
    )
    .join("");
  return `
    <div class="entete-vue">
      <h1>${t("nav.documents")}</h1>
      <button class="btn btn-accent" onclick="ouvrirFormDocument()">${t("commun.ajouter")}</button>
    </div>
    ${liste.length ? `
      <div class="enveloppe-tableau"><table class="tableau">
        <thead><tr><th>${t("documents.col_fichier")}</th><th>${t("documents.col_type")}</th><th>${t("nav.candidatures")}</th><th>${t("documents.col_ajoute_le")}</th><th></th></tr></thead>
        <tbody>${lignes}</tbody>
      </table></div>` : `
      <div class="etat-vide">
        <div class="icone">${ICONES.candidatures}</div>
        <div class="titre">${t("documents.vide_titre")}</div>
        <p>${t("documents.vide_texte")}</p>
        <button class="btn btn-accent" onclick="ouvrirFormDocument()">${t("documents.ajouter_bouton")}</button>
      </div>`}`;
}

async function ouvrirFormDocument() {
  const candidaturesListe = await api("/api/candidatures");
  if (!candidaturesListe.length) {
    toast(t("documents.ajoute_candidature_dabord"), true);
    return;
  }
  ouvrirModale(
    t("documents.ajouter_titre"),
    `<div class="grille-form">
      <div class="champ pleine-largeur">
        <label for="doc-candidature">${t("nav.candidatures")}</label>
        <select id="doc-candidature">
          ${candidaturesListe.map((c) => `<option value="${c.id}">${echapper(c.entreprise)} - ${echapper(c.poste)}</option>`).join("")}
        </select>
      </div>
      <div class="champ">
        <label for="doc-type">${t("documents.col_type")}</label>
        <select id="doc-type">${optionsSelect(etat.valeurs.types_document, null, false)}</select>
      </div>
      <div class="champ">
        <label for="doc-fichier">${t("documents.fichiers_label")}</label>
        <input type="file" id="doc-fichier" multiple>
      </div>
    </div>`,
    `<button class="btn" onclick="fermerModale()">${t("commun.annuler")}</button>
     <button class="btn btn-accent" id="btn-doc-ajouter">${t("commun.ajouter_simple")}</button>`,
    true
  );
  document.getElementById("btn-doc-ajouter").addEventListener("click", async () => {
    const fichiers = document.getElementById("doc-fichier").files;
    await televerserDocument(
      Number(document.getElementById("doc-candidature").value),
      fichiers,
      document.getElementById("doc-type").value,
      () => { fermerModale(); rendre(); }
    );
  });
}

/* Téléverse un ou plusieurs fichiers (offre en PDF, CV, lettre…) liés à une
   candidature. Accepte un seul File ou une FileList/tableau de plusieurs. */
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
    toast(reussis === 1 ? t("documents.document_ajoute") : t("documents.documents_ajoutes", { n: reussis }));
  }
  erreurs.forEach((message) => toast(message, true));
  if (reussis && apres) apres();
}

async function supprimerDocument(idDocument, idCandidature) {
  const accord = await confirmer(
    t("documents.supprimer_titre"),
    t("documents.supprimer_texte")
  );
  if (!accord) return;
  try {
    await api(`/api/documents/${idDocument}`, { methode: "DELETE" });
    toast(t("documents.document_supprime"));
    if (idCandidature) ouvrirDetailCandidature(idCandidature);
    else rendre();
  } catch (erreur) {
    toast(erreur.message, true);
  }
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
      ...resultats.contacts.map((c) =>
        resultatRecherche("contact", t("recherche.badge_contact"), `ouvrirDetailContact(${c.id})`,
          c.nom, `${c.entreprise}${c.poste ? " · " + c.poste : ""}`, c)),
    ];
    corps = rendus.length
      ? `<div class="liste-resultats">${rendus.join("")}</div>
         <p class="sous-titre">${t("recherche.resultats_compte", {
           n: rendus.length, cand: resultats.candidatures.length, ent: resultats.entreprises.length, contacts: resultats.contacts.length,
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

      ${etat.valeurs.plateforme_macos ? `<div class="carte">
        <h2>${t("reglages.notifications_titre")}</h2>
        <p class="sous-titre">${t("reglages.notifications_texte")}</p>
        <label class="case" style="margin-top:10px;">
          <input type="checkbox" id="reg-notifications" ${r.notifications_macos === "Oui" ? "checked" : ""}>
          ${t("reglages.notifications_case")}
        </label>
      </div>` : ""}

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

  const caseNotifications = document.getElementById("reg-notifications");
  if (caseNotifications) {
    caseNotifications.addEventListener("change", async (evenement) => {
      try {
        await api("/api/reglages", {
          methode: "POST",
          corps: { notifications_macos: evenement.target.checked ? "Oui" : "Non" },
        });
        toast(evenement.target.checked ? t("reglages.notifications_activees") : t("reglages.notifications_desactivees"));
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
   Mode entretien : fiche à gauche, notes en direct à droite
   ======================================================================== */

async function vueModeEntretien(numero) {
  const [fiche, cand] = await Promise.all([
    api(`/api/entretien/${numero}`),
    api(`/api/candidatures/${numero}`),
  ]);
  return `
    <div class="entete-vue">
      <button class="btn" onclick="location.hash='#/candidatures'">${t("entretien.retour")}</button>
      <div style="flex:1;">
        <h1>${echapper(cand.entreprise)}</h1>
        <div class="sous-titre">${echapper(cand.poste)} - ${t("entretien.mode_entretien_soustitre")}${cand.date_entretien ? " · " + dateFr(cand.date_entretien) : ""}</div>
      </div>
      <span class="sous-titre" id="indicateur-notes"></span>
    </div>
    <div class="mode-entretien">
      <div class="carte fiche">${rendreMarkdown(fiche.markdown)}</div>
      <div class="carte colonne-notes">
        <h2>${t("formulaire.notes_entretien")}</h2>
        <textarea id="zone-notes-entretien"
          placeholder="${t("entretien.notes_placeholder")}">${echapper(cand.notes_entretien || "")}</textarea>
      </div>
    </div>`;
}

function activerModeEntretien(numero) {
  const zone = document.getElementById("zone-notes-entretien");
  const indicateur = document.getElementById("indicateur-notes");
  if (!zone) return;
  zone.focus();
  let minuteur;
  zone.addEventListener("input", () => {
    indicateur.textContent = t("entretien.enregistrement_en_cours");
    clearTimeout(minuteur);
    minuteur = setTimeout(async () => {
      try {
        await api(`/api/candidatures/${numero}`, {
          methode: "PATCH",
          corps: { notes_entretien: zone.value },
        });
        const heure = new Date().toLocaleTimeString(etat.langue === "en" ? "en-US" : "fr-FR", { hour: "2-digit", minute: "2-digit" });
        indicateur.textContent = t("entretien.enregistre_a", { heure });
      } catch (erreur) {
        indicateur.textContent = "";
        toast(erreur.message, true);
      }
    }, 800);
  });
}

/* ========================================================================
   Modale : fiche entretien + confirmations
   ======================================================================== */

function ouvrirModale(titre, corpsHTML, piedHTML, etroite = false) {
  document.getElementById("modale-titre").textContent = titre;
  document.getElementById("modale-corps").innerHTML = corpsHTML;
  document.getElementById("modale-pied").innerHTML = piedHTML;
  document.getElementById("modale-boite").classList.toggle("etroite", etroite);
  document.getElementById("modale").classList.add("visible");
}

function fermerModale() {
  document.getElementById("modale").classList.remove("visible");
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

/* Mini-rendu Markdown (structure connue de la fiche : titres, listes, gras, italique) */
function rendreMarkdown(texte) {
  const lignes = echapper(texte).split("\n");
  const sortie = [];
  let dansListe = false;
  const fermerListe = () => {
    if (dansListe) { sortie.push("</ul>"); dansListe = false; }
  };
  const enrichir = (ligne) =>
    ligne
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>");
  for (const ligne of lignes) {
    if (ligne.startsWith("# ")) {
      fermerListe();
      sortie.push(`<h1>${enrichir(ligne.slice(2))}</h1>`);
    } else if (ligne.startsWith("## ")) {
      fermerListe();
      sortie.push(`<h2>${enrichir(ligne.slice(3))}</h2>`);
    } else if (ligne.startsWith("- ")) {
      if (!dansListe) { sortie.push("<ul>"); dansListe = true; }
      sortie.push(`<li>${enrichir(ligne.slice(2))}</li>`);
    } else if (ligne.trim() === "") {
      fermerListe();
    } else {
      fermerListe();
      sortie.push(`<p>${enrichir(ligne)}</p>`);
    }
  }
  fermerListe();
  return sortie.join("\n");
}

async function ouvrirFicheEntretien(numero) {
  try {
    const fiche = await api(`/api/entretien/${numero}`);
    ouvrirModale(
      t("entretien.fiche_titre"),
      `<div class="fiche">${rendreMarkdown(fiche.markdown)}</div>`,
      `<a class="btn" href="/api/entretien/${numero}/telecharger">${t("entretien.telecharger_md")}</a>
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
document.getElementById("panneau-fermer").addEventListener("click", fermerPanneau);
document.getElementById("voile").addEventListener("click", fermerPanneau);
document.getElementById("modale-fermer").addEventListener("click", fermerModale);
document.getElementById("modale").addEventListener("click", (evenement) => {
  if (evenement.target === document.getElementById("modale")) fermerModale();
});
document.addEventListener("keydown", (evenement) => {
  if (evenement.key === "Escape") { fermerPanneau(); fermerModale(); }
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
        cand: rapport.candidatures_ajoutees, contacts: rapport.contacts_ajoutes, ent: rapport.entreprises_ajoutees,
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
