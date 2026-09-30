/* Azimut - section CV : ses CV, où les retrouver, où les modifier.

   Chargé AVANT app.js (comme preparation.js) : ne s'exécute qu'à l'appel de ses
   fonctions, et s'appuie sur les utilitaires d'app.js (t, api, echapper, toast,
   ouvrirModale...) et de preparation.js (creerZoneDepot, copierTexte, tailleLisible).

   Un CV peut avoir un fichier (à télécharger, à envoyer), une source modifiable sur
   l'ordinateur (dossier LaTeX ou fichier Word : l'IA y lit le texte brut et sait où
   le modifier) et un texte. Le CV « principal » est celui que l'IA lit pour rédiger
   une lettre ou adapter une fiche. */

"use strict";

const ICONES_CV = {
  latex: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="m9.5 12-1.5 1.5L9.5 15M14.5 12l1.5 1.5-1.5 1.5"/></svg>',
  word: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="m8.5 12.5 1.2 4.5 1.3-3.8 1.3 3.8 1.2-4.5"/></svg>',
  fichier: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/></svg>',
  etoile: '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"><path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/></svg>',
};

function extensionCv(cv) {
  if (cv.nom_fichier) return (cv.nom_fichier.split(".").pop() || "").slice(0, 4).toUpperCase();
  if (cv.type_source === "latex") return "TEX";
  if (cv.type_source === "word") return "DOCX";
  return "TXT";
}

function ligneSourceCv(cv) {
  if (!cv.chemin_source) {
    return `
      <button type="button" class="cv-source ajouter" data-action="modifier">
        <span class="cv-source-icone">${ICONES_CV.latex}</span>
        <span class="cv-source-texte">
          <span class="cv-source-titre">${t("cv.source_ajouter_titre")}</span>
          <span class="cv-source-aide">${t("cv.source_ajouter_aide")}</span>
        </span>
      </button>`;
  }
  const latex = cv.type_source === "latex";
  const pontOuvrir = window.pywebview && window.pywebview.api && window.pywebview.api.ouvrir_chemin;
  return `
    <div class="cv-source ${cv.source_disponible ? "ok" : "absente"}">
      <span class="cv-source-icone">${latex ? ICONES_CV.latex : ICONES_CV.word}</span>
      <span class="cv-source-texte">
        <span class="cv-source-titre">${t(latex ? "cv.source_latex" : "cv.source_word")}
          <span class="cv-etat">${cv.source_disponible ? t("cv.source_accessible") : t("cv.source_introuvable")}</span>
        </span>
        <code class="cv-chemin" title="${echapperAttribut(cv.chemin_source)}">${echapper(cv.chemin_source)}</code>
      </span>
      <span class="cv-source-actions">
        <button type="button" class="btn btn-mini" data-action="copier-chemin">${t("cv.copier_chemin")}</button>
        ${pontOuvrir && cv.source_disponible ? `<button type="button" class="btn btn-mini" data-action="ouvrir-chemin">${t(latex ? "cv.ouvrir_dossier" : "cv.ouvrir_fichier")}</button>` : ""}
      </span>
    </div>`;
}

function carteCv(cv) {
  const langue = (cv.langue || "").toUpperCase().slice(0, 3);
  const fichier = cv.nom_fichier
    ? `<span class="cv-fichier" title="${echapperAttribut(cv.nom_fichier)}">${echapper(cv.nom_fichier)}${cv.taille_fichier ? ` · ${tailleLisible(cv.taille_fichier)}` : ""}${cv.fichier_disponible ? "" : ` <span class="puce puce-lien-mort">${t("pieces.fichier_introuvable")}</span>`}</span>`
    : `<span class="cv-fichier vide">${t("cv.aucun_fichier")}</span>`;
  return `
    <article class="cv-carte${cv.principal ? " principal" : ""}" data-cv="${cv.id}">
      <div class="cv-feuille" aria-hidden="true">
        <div class="cv-feuille-entete"><span class="cv-feuille-pastille"></span><span class="cv-feuille-nom"></span></div>
        <div class="cv-feuille-lignes"><i></i><i class="court"></i><i></i><i></i><i class="court"></i><i></i></div>
        ${langue ? `<span class="cv-langue">${echapper(langue)}</span>` : ""}
        <span class="cv-extension">${echapper(extensionCv(cv))}</span>
      </div>
      <div class="cv-corps">
        <header class="cv-tete">
          <h2 class="cv-nom">${echapper(cv.nom)}</h2>
          ${cv.principal ? `<span class="cv-principal" title="${echapperAttribut(t("cv.principal_aide"))}">${ICONES_CV.etoile}${t("cv.principal")}</span>` : ""}
        </header>
        <div class="cv-meta">${fichier}<span class="cv-date">${t("cv.modifie_le", { date: dateFr((cv.date_modification || "").slice(0, 10)) })}</span></div>
        ${ligneSourceCv(cv)}
        ${cv.apercu ? `<p class="cv-apercu">${echapper(cv.apercu)}${cv.nb_caracteres > cv.apercu.length ? "…" : ""}</p>` : ""}
        <div class="cv-actions">
          <button type="button" class="btn btn-mini" data-action="apercu">${t("cv.apercu")}</button>
          ${cv.fichier_disponible ? `<button type="button" class="btn btn-mini" data-action="telecharger">${t("pieces.telecharger")}</button>` : ""}
          <button type="button" class="btn btn-mini" data-action="copier-texte">${t("pieces.copier_texte")}</button>
          <span class="cv-actions-espace"></span>
          ${cv.principal ? "" : `<button type="button" class="btn btn-mini" data-action="principal">${t("cv.definir_principal")}</button>`}
          <button type="button" class="btn btn-mini" data-action="modifier">${t("commun.modifier")}</button>
          <button type="button" class="btn btn-mini btn-danger" data-action="supprimer">${t("commun.supprimer")}</button>
        </div>
      </div>
    </article>`;
}

async function vueCv() {
  const cvs = await api("/api/cvs");
  const entete = `
    <div class="entete-vue">
      <div style="flex:1;"><h1>${t("nav.cv")}</h1><div class="sous-titre">${t("cv.sous_titre")}</div></div>
      <button class="btn btn-accent" onclick="ouvrirFormCv()">${t("cv.ajouter")}</button>
    </div>`;
  if (!cvs.length) {
    return `${entete}
      <div class="etat-vide">
        <div class="icone">${ICONES.cv}</div>
        <div class="titre">${t("cv.vide_titre")}</div>
        <p>${t("cv.vide_texte")}</p>
        <button class="btn btn-accent" onclick="ouvrirFormCv()">${t("cv.ajouter")}</button>
      </div>
      ${blocExplicationCv()}`;
  }
  return `${entete}
    <div class="grille-cv">${cvs.map(carteCv).join("")}</div>
    ${blocExplicationCv()}`;
}

function blocExplicationCv() {
  const point = (titre, texte) => `<div class="cv-principe"><h3>${titre}</h3><p>${texte}</p></div>`;
  return `
    <div class="cv-principes">
      ${point(t("cv.principe_fichier_titre"), t("cv.principe_fichier_texte"))}
      ${point(t("cv.principe_source_titre"), t("cv.principe_source_texte"))}
      ${point(t("cv.principe_principal_titre"), t("cv.principe_principal_texte"))}
    </div>`;
}

function activerCv() {
  const grille = document.querySelector(".grille-cv");
  if (!grille) return;
  grille.addEventListener("click", async (evenement) => {
    const bouton = evenement.target.closest("[data-action]");
    const carte = evenement.target.closest("[data-cv]");
    if (!bouton || !carte) return;
    const id = Number(carte.dataset.cv);
    const action = bouton.dataset.action;
    try {
      if (action === "apercu") {
        ouvrirApercuCv(id);
      } else if (action === "telecharger") {
        const cv = await api(`/api/cvs/${id}`);
        await telechargerFichier(`/api/cvs/${id}/telecharger`, cv.nom_fichier || "cv");
      } else if (action === "copier-texte") {
        const { texte } = await api(`/api/cvs/${id}/texte`);
        await copierTexte(texte, t("pieces.texte_copie"));
      } else if (action === "copier-chemin") {
        const cv = await api(`/api/cvs/${id}`);
        await copierTexte(cv.chemin_source, t("cv.chemin_copie"));
      } else if (action === "ouvrir-chemin") {
        const cv = await api(`/api/cvs/${id}`);
        await window.pywebview.api.ouvrir_chemin(cv.chemin_source);
      } else if (action === "principal") {
        await api(`/api/cvs/${id}`, { methode: "PATCH", corps: { principal: true } });
        toast(t("cv.principal_change"));
        rendre();
      } else if (action === "modifier") {
        ouvrirFormCv(await api(`/api/cvs/${id}`));
      } else if (action === "supprimer") {
        const cv = await api(`/api/cvs/${id}`);
        const accord = await confirmer(t("cv.supprimer_titre"), t("cv.supprimer_texte", { nom: cv.nom }));
        if (!accord) return;
        await api(`/api/cvs/${id}`, { methode: "DELETE" });
        toast(t("cv.supprime"));
        rendre();
      }
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });
}

/* Aperçu en fenêtre : le PDF, ou à défaut le texte du CV. */
async function ouvrirApercuCv(id) {
  const cv = await api(`/api/cvs/${id}`);
  const zone = ouvrirModale(
    cv.nom,
    `<div class="apercu-barre">
       <span class="apercu-meta">${cv.langue ? `<span class="puce">${echapper(cv.langue)}</span>` : ""}${cv.principal ? `<span class="puce puce-cible entreprise">${t("cv.principal")}</span>` : ""}</span>
       <div class="apercu-actions">
         <button type="button" class="btn btn-mini" data-action="copier">${t("pieces.copier_texte")}</button>
         ${cv.fichier_disponible ? `<button type="button" class="btn btn-mini" data-action="telecharger">${t("pieces.telecharger")}</button>` : ""}
       </div>
     </div>
     <div class="apercu-zone">
       ${cv.apercu_pdf
         ? `<iframe class="apercu-cadre" src="/api/cvs/${id}/apercu" title="${echapperAttribut(cv.nom)}"></iframe>`
         : `<div class="apercu-texte" id="cv-texte-apercu"></div>`}
     </div>`,
    `<button class="btn btn-accent" onclick="fermerModale()">${t("commun.fermer")}</button>`,
    false, true
  );
  if (!cv.apercu_pdf) {
    try {
      const { texte } = await api(`/api/cvs/${id}/texte`);
      zone.racine.querySelector("#cv-texte-apercu").textContent = texte;
    } catch (erreur) {
      toast(erreur.message, true);
    }
  }
  zone.racine.querySelector(".apercu-actions").addEventListener("click", async (evenement) => {
    const action = evenement.target.closest("[data-action]");
    if (!action) return;
    try {
      if (action.dataset.action === "copier") {
        const { texte } = await api(`/api/cvs/${id}/texte`);
        await copierTexte(texte, t("pieces.texte_copie"));
      } else {
        await telechargerFichier(`/api/cvs/${id}/telecharger`, cv.nom_fichier || "cv");
      }
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });
}

/* Ajout (cv = null) ou modification d'un CV. */
async function ouvrirFormCv(cv = null) {
  const creation = cv === null;
  const pont = window.pywebview && window.pywebview.api && window.pywebview.api.choisir_chemin;
  const zone = ouvrirModale(
    creation ? t("cv.ajouter_titre") : t("cv.modifier_titre", { nom: cv.nom }),
    `<div class="grille-form">
       <div class="champ pleine-largeur">
         <label for="cv-nom">${t("cv.champ_nom")}</label>
         <input type="text" id="cv-nom" value="${echapperAttribut(creation ? "" : cv.nom)}" placeholder="${echapperAttribut(t("cv.nom_placeholder"))}">
       </div>
       <div class="champ">
         <label for="cv-langue">${t("pieces.champ_langue")}</label>
         <input type="text" id="cv-langue" list="cv-langues" value="${echapperAttribut(creation ? "" : cv.langue || "")}" placeholder="fr">
         <datalist id="cv-langues"><option value="fr"><option value="en"><option value="es"><option value="de"><option value="it"></datalist>
       </div>
       <div class="champ">
         <label>&nbsp;</label>
         <label class="case"><input type="checkbox" id="cv-principal"${!creation && cv.principal ? " checked disabled" : ""}> ${t("cv.utiliser_principal")}</label>
       </div>
     </div>

     <h2 class="titre-bloc">${t("cv.section_fichier")}</h2>
     ${!creation && cv.nom_fichier ? `<p class="sous-titre" style="margin:0 0 8px;">${t("cv.fichier_actuel", { nom: echapper(cv.nom_fichier) })}</p>` : ""}
     <div id="cv-depot"></div>

     <h2 class="titre-bloc">${t("cv.section_source")} <span class="sous-titre">${t("cv.facultatif")}</span></h2>
     <p class="sous-titre" style="margin:0 0 8px;">${t("cv.source_explication")}</p>
     <div class="champ-avec-action">
       <input type="text" id="cv-source" value="${echapperAttribut(creation ? "" : cv.chemin_source || "")}" placeholder="${echapperAttribut(t("cv.source_placeholder"))}" autocomplete="off" spellcheck="false">
       ${pont ? `<button type="button" class="btn btn-mini" id="cv-choisir-dossier">${t("cv.choisir_dossier")}</button>
                 <button type="button" class="btn btn-mini" id="cv-choisir-fichier">${t("cv.choisir_fichier")}</button>` : ""}
     </div>

     <details class="cv-texte-colle"${!creation && !cv.nom_fichier && !cv.chemin_source ? " open" : ""}>
       <summary>${t("cv.coller_texte")}</summary>
       <textarea id="cv-texte" placeholder="${echapperAttribut(t("cv.texte_placeholder"))}"></textarea>
     </details>`,
    `<button class="btn" onclick="fermerModale()">${t("commun.annuler")}</button>
     <button class="btn btn-accent" id="btn-cv-enregistrer">${creation ? t("cv.ajouter") : t("commun.enregistrer")}</button>`,
    false, true
  );
  const racine = zone.racine;
  const depot = creerZoneDepot(racine.querySelector("#cv-depot"), {
    extensions: [".pdf", ".docx", ".txt", ".md"],
    surFichier: (fichier) => {
      const champNom = racine.querySelector("#cv-nom");
      if (!champNom.value.trim()) champNom.value = fichier.name.replace(/\.[^.]+$/, "");
    },
  });
  if (pont) {
    racine.querySelector("#cv-choisir-dossier").addEventListener("click", async () => {
      const chemin = await window.pywebview.api.choisir_chemin("dossier");
      if (chemin) racine.querySelector("#cv-source").value = chemin;
    });
    racine.querySelector("#cv-choisir-fichier").addEventListener("click", async () => {
      const chemin = await window.pywebview.api.choisir_chemin("fichier");
      if (chemin) racine.querySelector("#cv-source").value = chemin;
    });
  }

  racine.querySelector("#btn-cv-enregistrer").addEventListener("click", async () => {
    const valeur = (id) => racine.querySelector(id).value.trim();
    const fichier = depot.fichier();
    const bouton = racine.querySelector("#btn-cv-enregistrer");
    bouton.disabled = true;
    try {
      if (creation) {
        const formulaire = new FormData();
        if (fichier) formulaire.append("fichier", fichier);
        formulaire.append("nom", valeur("#cv-nom"));
        formulaire.append("langue", valeur("#cv-langue"));
        formulaire.append("chemin_source", valeur("#cv-source"));
        formulaire.append("texte", valeur("#cv-texte"));
        formulaire.append("principal", racine.querySelector("#cv-principal").checked ? "1" : "0");
        etat.versionDb = null;
        const reponse = await fetch("/api/cvs", { method: "POST", body: formulaire });
        const donnees = await reponse.json();
        if (!reponse.ok) throw new Error(donnees.erreur || t("commun.erreur_inattendue"));
        toast(t("cv.ajoute"));
      } else {
        const corps = {};
        if (valeur("#cv-nom") !== cv.nom) corps.nom = valeur("#cv-nom");
        if (valeur("#cv-langue") !== (cv.langue || "")) corps.langue = valeur("#cv-langue");
        if (valeur("#cv-source") !== (cv.chemin_source || "")) corps.chemin_source = valeur("#cv-source");
        if (valeur("#cv-texte")) corps.texte = valeur("#cv-texte");
        if (racine.querySelector("#cv-principal").checked && !cv.principal) corps.principal = true;
        if (Object.keys(corps).length) {
          await api(`/api/cvs/${cv.id}`, { methode: "PATCH", corps });
        }
        if (fichier) {
          const formulaire = new FormData();
          formulaire.append("fichier", fichier);
          etat.versionDb = null;
          const reponse = await fetch(`/api/cvs/${cv.id}/fichier`, { method: "POST", body: formulaire });
          const donnees = await reponse.json();
          if (!reponse.ok) throw new Error(donnees.erreur || t("commun.erreur_inattendue"));
        }
        toast(t("cv.enregistre"));
      }
      fermerModale(zone);
      rendre();
    } catch (erreur) {
      toast(erreur.message, true);
      bouton.disabled = false;
    }
  });
}
