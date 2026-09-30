/* Azimut - préparation des candidatures : lettres de motivation, fiches
   d'entretien et notes d'entretien.

   Ce fichier est chargé AVANT app.js : il ne s'exécute qu'à l'appel de ses
   fonctions (depuis app.js, une fois tout chargé), et s'appuie sur ses
   utilitaires (t, api, echapper, toast, ouvrirModale, confirmer...). Trois
   briques réutilisables : le sélecteur d'entreprise et d'offres, la zone de
   dépôt de fichier, et l'aperçu d'une pièce. */

"use strict";

/* ========================================================================
   Utilitaires
   ======================================================================== */

/* Texte sans accents ni majuscules, pour chercher « evaluation » et trouver
   « Évaluation ». */
function normaliserTexte(texte) {
  return String(texte ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

function aujourdHuiISO() {
  const maintenant = new Date();
  const deuxChiffres = (n) => String(n).padStart(2, "0");
  return `${maintenant.getFullYear()}-${deuxChiffres(maintenant.getMonth() + 1)}-${deuxChiffres(maintenant.getDate())}`;
}

function tailleLisible(octets) {
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${Math.round(octets / 1024)} Ko`;
  return `${(octets / (1024 * 1024)).toFixed(1)} Mo`;
}

/* ========================================================================
   Sélecteur d'entreprise et d'offres
   ======================================================================== */

/* Deux modes :
   - « pieces » (lettres, fiches) : UNE entreprise et plusieurs de ses offres,
     plus une case « l'entreprise en général » ;
   - « note » : SOIT une entreprise, SOIT une offre précise.
   Options : entrepriseFixe (id : seule cette entreprise est proposée),
   entrepriseId / offreIds / generale (sélection de départ), autoriserNouvelle
   (permet de saisir une entreprise qui n'existe pas encore). */
async function creerSelecteurCible(racine, options = {}) {
  const mode = options.mode || "pieces";
  const [entreprises, offres] = await Promise.all([api("/api/entreprises"), api("/api/candidatures")]);
  const offresParEntreprise = new Map();
  offres.forEach((offre) => {
    if (!offresParEntreprise.has(offre.entreprise_id)) offresParEntreprise.set(offre.entreprise_id, []);
    offresParEntreprise.get(offre.entreprise_id).push(offre);
  });
  const entreprisesAffichees = entreprises.filter((e) => !options.entrepriseFixe || e.id === options.entrepriseFixe);

  const selection = {
    entrepriseId: options.entrepriseId ?? options.entrepriseFixe ?? null,
    nouvelleEntreprise: "",   // nom saisi pour une entreprise pas encore enregistrée
    offreIds: new Set(options.offreIds || []),
    generale: !!options.generale,
  };
  let ecouteur = null;

  const groupes = entreprisesAffichees.map((entreprise) => {
    const liste = offresParEntreprise.get(entreprise.id) || [];
    const lignesOffres = liste.map((offre) => `
      <label class="sel-offre" data-offre="${offre.id}" data-texte="${echapperAttribut(normaliserTexte(`${offre.poste} ${offre.ville || ""}`))}">
        <input type="${mode === "note" ? "radio" : "checkbox"}" name="sel-offre" value="${offre.id}">
        <span class="sel-offre-texte" title="${echapperAttribut(offre.poste)}">${echapper(offre.poste)}</span>
        <span class="cellule-secondaire">${echapper(tv(offre.statut))}</span>
      </label>`).join("");
    return `
      <div class="sel-groupe" data-entreprise="${entreprise.id}" data-nom="${echapperAttribut(normaliserTexte(entreprise.nom))}">
        <button type="button" class="sel-entreprise" data-entreprise-bouton="${entreprise.id}"${options.entrepriseFixe ? " disabled" : ""}>
          ${echapper(entreprise.nom)}
          <span class="sel-compte">${pluriel("selecteur.nb_offres", liste.length)}</span>
        </button>
        ${lignesOffres}
      </div>`;
  }).join("");

  racine.innerHTML = `
    <div class="selecteur-cible">
      ${options.entrepriseFixe ? "" : `<input type="text" class="sel-recherche" placeholder="${echapperAttribut(t("selecteur.recherche_placeholder"))}" autocomplete="off">`}
      <div class="sel-resume vide" aria-live="polite"></div>
      <div class="sel-liste">
        ${groupes || `<div class="sel-vide">${t("selecteur.aucune_entreprise")}</div>`}
        <div class="sel-vide" data-role="aucun-resultat" hidden>${t("selecteur.aucun_resultat")}</div>
        ${options.autoriserNouvelle === false || options.entrepriseFixe ? "" : `<button type="button" class="btn btn-discret sel-nouvelle" hidden></button>`}
      </div>
      ${mode === "pieces" ? `
        <label class="case sel-generale inactive">
          <input type="checkbox" class="sel-generale-case" disabled>
          <span>${t("selecteur.generale_label")}</span>
        </label>` : ""}
    </div>`;

  const champRecherche = racine.querySelector(".sel-recherche");
  const resume = racine.querySelector(".sel-resume");
  const caseGenerale = racine.querySelector(".sel-generale-case");
  const libelleGenerale = racine.querySelector(".sel-generale");
  const boutonNouvelle = racine.querySelector(".sel-nouvelle");
  const vide = racine.querySelector('[data-role="aucun-resultat"]');

  const entrepriseParId = (id) => entreprises.find((e) => e.id === id);
  const offreParId = (id) => offres.find((o) => o.id === id);
  const aUneCible = () => selection.entrepriseId !== null || !!selection.nouvelleEntreprise;

  function nomEntreprise() {
    return selection.entrepriseId !== null
      ? (entrepriseParId(selection.entrepriseId) || {}).nom || ""
      : selection.nouvelleEntreprise;
  }

  function notifier() { if (ecouteur) ecouteur(lire()); }

  function synchroniser() {
    racine.querySelectorAll("[data-entreprise-bouton]").forEach((bouton) => {
      bouton.classList.toggle("actif", Number(bouton.dataset.entrepriseBouton) === selection.entrepriseId);
    });
    racine.querySelectorAll(".sel-offre input").forEach((champ) => {
      champ.checked = selection.offreIds.has(Number(champ.value));
    });

    const nombre = selection.offreIds.size;
    if (!aUneCible()) {
      resume.className = "sel-resume vide";
      resume.textContent = t(mode === "note" ? "selecteur.aucune_selection_note" : "selecteur.aucune_selection_pieces");
    } else {
      resume.className = "sel-resume";
      let phrase;
      if (mode === "note") {
        const offre = nombre ? offreParId([...selection.offreIds][0]) : null;
        phrase = offre
          ? t("selecteur.note_sur_offre", { offre: `<strong>${echapper(offre.poste)}</strong>`, entreprise: echapper(nomEntreprise()) })
          : t("selecteur.note_sur_entreprise", { entreprise: `<strong>${echapper(nomEntreprise())}</strong>` });
      } else {
        phrase = `<strong>${echapper(nomEntreprise())}</strong>` + (nombre
          ? ` · ${pluriel("selecteur.nb_offres_choisies", nombre)}`
          : ` · ${t("selecteur.entreprise_en_general")}`);
        if (selection.nouvelleEntreprise) phrase += ` <span class="puce">${t("selecteur.nouvelle_entreprise")}</span>`;
      }
      resume.innerHTML = phrase + (options.entrepriseFixe ? "" : `<button type="button" class="btn btn-mini btn-discret sel-effacer">${t("selecteur.effacer")}</button>`);
    }

    if (caseGenerale) {
      // Sans offre cochée, la pièce porte forcément sur l'entreprise en général ; avec des
      // offres, c'est un choix.
      const forcee = aUneCible() && nombre === 0;
      caseGenerale.disabled = !aUneCible() || forcee;
      caseGenerale.checked = forcee ? true : (aUneCible() && selection.generale);
      libelleGenerale.classList.toggle("inactive", caseGenerale.disabled);
    }
    notifier();
  }

  function definirEntreprise(id) {
    if (selection.entrepriseId !== id) selection.offreIds.clear();
    selection.entrepriseId = id;
    selection.nouvelleEntreprise = "";
    if (mode === "note" && selection.offreIds.size) selection.offreIds.clear();
  }

  function effacer() {
    selection.entrepriseId = options.entrepriseFixe ?? null;
    selection.nouvelleEntreprise = "";
    selection.offreIds.clear();
    selection.generale = false;
  }

  racine.addEventListener("click", (evenement) => {
    const bouton = evenement.target.closest("[data-entreprise-bouton]");
    if (bouton) {
      const id = Number(bouton.dataset.entrepriseBouton);
      if (selection.entrepriseId === id && selection.offreIds.size === 0) selection.entrepriseId = null;
      else definirEntreprise(id);
      synchroniser();
      return;
    }
    if (evenement.target.closest(".sel-effacer")) { effacer(); synchroniser(); return; }
    if (evenement.target.closest(".sel-nouvelle")) {
      selection.entrepriseId = null;
      selection.offreIds.clear();
      selection.nouvelleEntreprise = champRecherche.value.trim();
      synchroniser();
    }
  });

  racine.addEventListener("change", (evenement) => {
    if (evenement.target.matches(".sel-generale-case")) {
      selection.generale = evenement.target.checked;
      notifier();
      return;
    }
    if (!evenement.target.matches(".sel-offre input")) return;
    const offre = offreParId(Number(evenement.target.value));
    if (!offre) return;
    if (mode === "note") {
      selection.offreIds = new Set([offre.id]);
      selection.entrepriseId = offre.entreprise_id;
      selection.nouvelleEntreprise = "";
    } else if (evenement.target.checked) {
      if (selection.entrepriseId !== offre.entreprise_id) {
        if (aUneCible() && selection.offreIds.size) toast(t("selecteur.une_seule_entreprise"));
        selection.offreIds.clear();
      }
      selection.entrepriseId = offre.entreprise_id;
      selection.nouvelleEntreprise = "";
      selection.offreIds.add(offre.id);
    } else {
      selection.offreIds.delete(offre.id);
    }
    synchroniser();
  });

  function filtrer() {
    const requete = normaliserTexte(champRecherche ? champRecherche.value : "");
    let visibles = 0;
    racine.querySelectorAll(".sel-groupe").forEach((groupe) => {
      const nomCorrespond = !requete || groupe.dataset.nom.includes(requete);
      let offresVisibles = 0;
      groupe.querySelectorAll(".sel-offre").forEach((ligne) => {
        const visible = nomCorrespond || ligne.dataset.texte.includes(requete);
        ligne.hidden = !visible;
        if (visible) offresVisibles += 1;
      });
      const visible = nomCorrespond || offresVisibles > 0;
      groupe.hidden = !visible;
      if (visible) visibles += 1;
    });
    vide.hidden = visibles > 0 || !racine.querySelector(".sel-groupe");
    if (boutonNouvelle) {
      const brut = champRecherche.value.trim();
      const existeDeja = entreprises.some((e) => normaliserTexte(e.nom) === requete);
      boutonNouvelle.hidden = !brut || existeDeja;
      boutonNouvelle.textContent = t("selecteur.utiliser_nouvelle", { nom: brut });
    }
  }
  if (champRecherche) champRecherche.addEventListener("input", filtrer);

  function lire() {
    return {
      entrepriseId: selection.entrepriseId,
      entrepriseNom: nomEntreprise(),
      offreIds: [...selection.offreIds],
      generale: caseGenerale ? caseGenerale.checked : false,
      offres: [...selection.offreIds].map(offreParId).filter(Boolean),
    };
  }

  synchroniser();
  if (champRecherche) champRecherche.focus();
  return {
    lire,
    entreprises,
    definirEntreprise: (id) => {
      definirEntreprise(id);
      synchroniser();
      const groupe = racine.querySelector(`.sel-groupe[data-entreprise="${id}"]`);
      if (groupe) groupe.scrollIntoView({ block: "nearest" });
    },
    surChangement: (fonction) => { ecouteur = fonction; fonction(lire()); },
  };
}

/* ========================================================================
   Zone de dépôt d'un fichier (glisser-déposer ou parcourir)
   ======================================================================== */

function creerZoneDepot(racine, options = {}) {
  const extensions = options.extensions || [".pdf", ".docx", ".txt", ".md"];
  const tailleMax = options.tailleMax || 15 * 1024 * 1024;
  let fichier = null;

  racine.innerHTML = `
    <div class="zone-depot" tabindex="0" role="button" aria-label="${echapperAttribut(t("depot.titre"))}">
      <div class="icone"><svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V4"/><path d="m7 9 5-5 5 5"/><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/></svg></div>
      <div class="zone-depot-titre">${t("depot.titre")}</div>
      <div class="zone-depot-sous">${t("depot.sous_titre")}</div>
      <div class="zone-depot-fichier" hidden></div>
      <input type="file" accept="${extensions.join(",")}" hidden>
    </div>`;
  const zone = racine.querySelector(".zone-depot");
  const champ = racine.querySelector('input[type="file"]');
  const infos = racine.querySelector(".zone-depot-fichier");

  function afficher() {
    const rempli = fichier !== null;
    zone.classList.toggle("rempli", rempli);
    racine.querySelector(".zone-depot-titre").hidden = rempli;
    racine.querySelector(".zone-depot-sous").hidden = rempli;
    infos.hidden = !rempli;
    infos.innerHTML = rempli
      ? `<span class="nom">${echapper(fichier.name)}</span><span class="taille">${tailleLisible(fichier.size)}</span>
         <button type="button" class="btn btn-mini" data-role="retirer">${t("depot.changer")}</button>`
      : "";
  }

  function accepter(nouveau) {
    if (!nouveau) return;
    const extension = (nouveau.name.match(/\.[^.]+$/) || [""])[0].toLowerCase();
    if (!extensions.includes(extension)) {
      toast(t("depot.format_refuse", { ext: extension || "?" }), true);
      return;
    }
    if (nouveau.size > tailleMax) {
      toast(t("depot.trop_gros", { taille: tailleLisible(tailleMax) }), true);
      return;
    }
    fichier = nouveau;
    afficher();
    if (options.surFichier) options.surFichier(nouveau);
  }

  zone.addEventListener("click", (evenement) => {
    if (evenement.target.closest('[data-role="retirer"]')) {
      fichier = null;
      champ.value = "";
      afficher();
      champ.click();
      return;
    }
    if (!fichier) champ.click();
  });
  zone.addEventListener("keydown", (evenement) => {
    if ((evenement.key === "Enter" || evenement.key === " ") && !fichier) {
      evenement.preventDefault();
      champ.click();
    }
  });
  champ.addEventListener("change", () => accepter(champ.files[0]));
  ["dragenter", "dragover"].forEach((nom) => {
    zone.addEventListener(nom, (evenement) => {
      evenement.preventDefault();
      zone.classList.add("survol");
    });
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("survol"));
  zone.addEventListener("drop", (evenement) => {
    evenement.preventDefault();
    zone.classList.remove("survol");
    const fichiers = evenement.dataTransfer && evenement.dataTransfer.files;
    if (fichiers && fichiers.length > 1) toast(t("depot.un_seul_fichier"), true);
    accepter(fichiers && fichiers[0]);
  });

  afficher();
  return { fichier: () => fichier };
}

/* ========================================================================
   Lettres de motivation et fiches d'entretien : listes, aperçu, actions
   ======================================================================== */

function puceOrigine(section, source) {
  const cle = source === "api" ? "origine_api" : source === "claude_code" ? "origine_claude_code" : "origine_manuelle";
  return `<span class="puce">${echapper(t(`${section}.${cle}`))}</span>`;
}

function offresLiees(piece) {
  const puces = piece.candidatures.map(
    (c) => `<span class="puce" title="${echapperAttribut(c.poste)}">${echapper(c.poste)}</span>`
  );
  if (piece.generale) puces.push(`<span class="puce puce-cible entreprise">${t("selecteur.entreprise_en_general")}</span>`);
  return puces.length ? `<div class="offres-liees">${puces.join("")}</div>` : "";
}

async function vuePieces(section) {
  const filtre = etat.filtresPieces[section].recherche;
  const liste = await api(`/api/${section}` + (filtre ? `?recherche=${encodeURIComponent(filtre)}` : ""));
  const lignes = liste
    .map((piece) => `
    <tr onclick="ouvrirApercuPiece('${section}', ${piece.id})">
      <td class="cellule-principale cellule-titre" title="${echapperAttribut(piece.titre)}">${echapper(piece.titre)}
        ${piece.chemin_fichier && !piece.fichier_disponible ? `<span class="puce puce-lien-mort" title="${echapperAttribut(t("pieces.fichier_introuvable_titre"))}">${t("pieces.fichier_introuvable")}</span>` : ""}
      </td>
      <td>${echapper(piece.entreprise)}</td>
      <td>${offresLiees(piece)}</td>
      <td>${puceOrigine(section, piece.source)}</td>
      <td class="cellule-date">${dateFr(piece.date_creation)}</td>
      <td onclick="event.stopPropagation()"><div class="actions-ligne">
        ${piece.fichier_disponible ? `<a class="btn btn-discret btn-mini" href="/api/${section}/${piece.id}/telecharger">${t("pieces.telecharger")}</a>` : ""}
        <button class="btn btn-danger btn-mini" onclick="supprimerPiece('${section}', ${piece.id})">${t("commun.supprimer")}</button>
      </div></td>
    </tr>`)
    .join("");
  const boutons = `
    <button class="btn" onclick="ouvrirImportPiece('${section}')">${t(`${section}.ajouter_la_mienne`)}</button>
    <button class="btn btn-accent" onclick="${section === "lettres" ? "ouvrirNouvelleLettre()" : "ouvrirNouvelleFiche()"}">${t(`${section}.nouvelle`)}</button>`;
  return `
    <div class="entete-vue">
      <h1>${t(`nav.${section}`)}</h1>
      ${boutons}
    </div>
    <div class="filtres">
      <input type="text" id="filtre-pieces" class="champ-filtre-large" placeholder="${echapperAttribut(t(`${section}.rechercher_placeholder`))}" value="${echapperAttribut(filtre)}">
    </div>
    ${liste.length ? `
      <div class="enveloppe-tableau"><table class="tableau">
        <thead><tr>
          <th>${t("pieces.col_titre")}</th><th>${t("pieces.col_entreprise")}</th>
          <th>${t("pieces.col_offres")}</th><th>${t("pieces.col_origine")}</th>
          <th>${t("pieces.col_creee_le")}</th><th></th>
        </tr></thead>
        <tbody>${lignes}</tbody>
      </table></div>` : `
      <div class="etat-vide">
        <div class="icone">${ICONES[section]}</div>
        <div class="titre">${filtre ? t(`${section}.vide_filtre_titre`) : t(`${section}.vide_titre`)}</div>
        <p>${filtre ? t("pieces.vide_filtre_texte") : t(`${section}.vide_texte`)}</p>
        ${filtre ? "" : `<div class="actions-reglages" style="justify-content:center;">${boutons}</div>`}
      </div>`}`;
}

function activerPieces(section) {
  const champ = document.getElementById("filtre-pieces");
  if (!champ) return;
  let minuteur;
  champ.addEventListener("input", () => {
    clearTimeout(minuteur);
    minuteur = setTimeout(() => {
      etat.filtresPieces[section].recherche = champ.value;
      const position = champ.selectionStart;
      rendre().then(() => {
        const nouveau = document.getElementById("filtre-pieces");
        if (nouveau) { nouveau.focus(); nouveau.setSelectionRange(position, position); }
      });
    }, 250);
  });
}

async function supprimerPiece(section, id, apres) {
  const accord = await confirmer(t(`${section}.supprimer_titre`), t(`${section}.supprimer_texte`));
  if (!accord) return;
  try {
    await api(`/api/${section}/${id}`, { methode: "DELETE" });
    toast(t(`${section}.supprimee`));
    if (apres) apres();
    rendre();
  } catch (erreur) {
    toast(erreur.message, true);
  }
}

/* Aperçu : le PDF affiché dans la fenêtre (ou, à défaut, le texte), avec de quoi le
   télécharger, le modifier ou le supprimer. */
async function ouvrirApercuPiece(section, id) {
  try {
    const piece = await api(`/api/${section}/${id}`);
    const meta = `
      <div class="apercu-meta">
        <span class="puce">${echapper(piece.entreprise)}</span>
        ${piece.candidatures.map((c) => `<span class="puce">${echapper(c.poste)}</span>`).join("")}
        ${piece.generale ? `<span class="puce puce-cible entreprise">${t("selecteur.entreprise_en_general")}</span>` : ""}
        ${puceOrigine(section, piece.source)}
        <span class="cellule-secondaire">${dateFr(piece.date_creation)}</span>
      </div>`;
    let contenu;
    if (piece.apercu_pdf) {
      contenu = `<iframe class="apercu-cadre" src="/api/${section}/${piece.id}/apercu" title="${echapperAttribut(piece.titre)}"></iframe>`;
    } else if (piece.contenu) {
      contenu = `<div class="apercu-texte">${echapper(piece.contenu)}</div>`;
    } else {
      contenu = `<p class="sous-titre">${t("pieces.aucun_apercu")}</p>`;
    }
    ouvrirModale(
      piece.titre,
      meta + contenu,
      `<button class="btn btn-danger" id="btn-piece-supprimer" style="margin-right:auto;">${t("commun.supprimer")}</button>
       <button class="btn" id="btn-piece-modifier">${t("commun.modifier")}</button>
       ${piece.contenu ? `<a class="btn" href="/api/${section}/${piece.id}/telecharger?format=texte">${t("pieces.telecharger_texte")}</a>` : ""}
       ${piece.fichier_disponible ? `<a class="btn btn-accent" href="/api/${section}/${piece.id}/telecharger">${t("pieces.telecharger")}</a>` : ""}
       <button class="btn" onclick="fermerModale()">${t("commun.fermer")}</button>`,
      false, true
    );
    document.getElementById("btn-piece-modifier").addEventListener("click", () => ouvrirModifierPiece(section, piece));
    document.getElementById("btn-piece-supprimer").addEventListener("click", () => {
      fermerModale();
      supprimerPiece(section, piece.id);
    });
  } catch (erreur) {
    toast(erreur.message, true);
  }
}

async function ouvrirModifierPiece(section, piece) {
  ouvrirModale(
    t("pieces.modifier_titre"),
    `<div class="grille-form">
       <div class="champ pleine-largeur">
         <label for="piece-titre">${t("pieces.champ_titre")}</label>
         <input type="text" id="piece-titre" value="${echapperAttribut(piece.titre)}">
       </div>
       <div class="champ pleine-largeur">
         <label>${t("pieces.champ_offres")} - ${echapper(piece.entreprise)}</label>
         <div id="piece-selecteur"></div>
       </div>
     </div>`,
    `<button class="btn" onclick="fermerModale()">${t("commun.annuler")}</button>
     <button class="btn btn-accent" id="btn-piece-enregistrer">${t("commun.enregistrer")}</button>`,
    false, true
  );
  const selecteur = await creerSelecteurCible(document.getElementById("piece-selecteur"), {
    mode: "pieces", entrepriseFixe: piece.entreprise_id, offreIds: piece.candidatures.map((c) => c.id),
    generale: piece.generale,
  });
  document.getElementById("btn-piece-enregistrer").addEventListener("click", async () => {
    const choix = selecteur.lire();
    try {
      await api(`/api/${section}/${piece.id}`, {
        methode: "PATCH",
        corps: {
          titre: document.getElementById("piece-titre").value,
          candidature_ids: choix.offreIds,
          generale: choix.generale,
        },
      });
      toast(t("pieces.enregistree"));
      fermerModale();
      rendre();
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });
}

/* ------------------------------------------------------------------------
   Ajouter sa propre lettre / fiche : glisser-déposer un fichier
   ------------------------------------------------------------------------ */

async function ouvrirImportPiece(section) {
  ouvrirModale(
    t(`${section}.ajouter_la_mienne_titre`),
    `<p class="sous-titre" style="margin-top:0;">${t(`${section}.ajouter_la_mienne_texte`)}</p>
     <div id="depot"></div>
     <h2 style="font-size:13px;margin:18px 0 8px;">${t("pieces.rattacher_a")}</h2>
     <div id="import-selecteur"></div>
     <p class="sous-titre" id="suggestion-fichier" style="margin:6px 0 0;" hidden></p>
     <div class="grille-form" style="margin-top:14px;">
       <div class="champ">
         <label for="import-titre">${t("pieces.champ_titre_facultatif")}</label>
         <input type="text" id="import-titre" placeholder="${echapperAttribut(t("pieces.titre_par_defaut"))}">
       </div>
       <div class="champ">
         <label for="import-langue">${t("pieces.champ_langue")}</label>
         <input type="text" id="import-langue" placeholder="${echapperAttribut(t("pieces.langue_placeholder"))}">
       </div>
     </div>`,
    `<button class="btn" onclick="fermerModale()">${t("commun.annuler")}</button>
     <button class="btn btn-accent" id="btn-import-piece" disabled>${t("pieces.ajouter")}</button>`,
    false, true
  );

  let selecteur;
  const bouton = document.getElementById("btn-import-piece");
  const suggestion = document.getElementById("suggestion-fichier");
  const actualiserBouton = () => {
    const choix = selecteur.lire();
    bouton.disabled = !depot.fichier() || !(choix.entrepriseId !== null || choix.entrepriseNom);
  };
  const depot = creerZoneDepot(document.getElementById("depot"), {
    surFichier: (fichier) => {
      // Le nom du fichier suggère souvent l'entreprise (« lettre-motivation-CEA.pdf ») :
      // on la propose, sans jamais écraser un choix déjà fait.
      if (selecteur && selecteur.lire().entrepriseNom === "") {
        const nom = normaliserTexte(fichier.name);
        const candidates = selecteur.entreprises
          .filter((e) => e.nom.length >= 3 && nom.includes(normaliserTexte(e.nom)))
          .sort((a, b) => b.nom.length - a.nom.length);
        if (candidates.length) {
          selecteur.definirEntreprise(candidates[0].id);
          suggestion.textContent = t("pieces.entreprise_suggeree", { nom: candidates[0].nom });
          suggestion.hidden = false;
        }
      }
      actualiserBouton();
    },
  });
  selecteur = await creerSelecteurCible(document.getElementById("import-selecteur"), { mode: "pieces" });
  selecteur.surChangement(actualiserBouton);

  bouton.addEventListener("click", async () => {
    const choix = selecteur.lire();
    const formulaire = new FormData();
    formulaire.append("fichier", depot.fichier());
    formulaire.append("entreprise", choix.entrepriseNom);
    formulaire.append("candidature_ids", JSON.stringify(choix.offreIds));
    formulaire.append("generale", choix.generale ? "1" : "0");
    formulaire.append("titre", document.getElementById("import-titre").value);
    formulaire.append("langue", document.getElementById("import-langue").value);
    bouton.disabled = true;
    try {
      etat.versionDb = null;
      const reponse = await fetch(`/api/${section}/importer`, { method: "POST", body: formulaire });
      const donnees = await reponse.json();
      if (!reponse.ok) throw new Error(donnees.erreur || t("commun.erreur_inattendue"));
      toast(t(`${section}.ajoutee`));
      fermerModale();
      rendre();
    } catch (erreur) {
      toast(erreur.message, true);
      bouton.disabled = false;
    }
  });
}

/* ------------------------------------------------------------------------
   Créer avec l'IA
   ------------------------------------------------------------------------ */

async function lancerGeneration(section, corps, boutons, statut) {
  boutons.forEach((b) => { b.disabled = true; });
  statut.textContent = t(`${section}.generation_en_cours`);
  try {
    const piece = await api(`/api/${section}/generer`, { methode: "POST", corps });
    toast(t(`${section}.generee`));
    (piece.avertissements || []).forEach((message) => toast(message, true));
    fermerModale();
    await rendre();
    ouvrirApercuPiece(section, piece.id);
  } catch (erreur) {
    statut.textContent = "";
    boutons.forEach((b) => { b.disabled = false; });
    toast(erreur.message, true);
  }
}

async function ouvrirNouvelleLettre() {
  const [cv, reglagesIa] = await Promise.all([api("/api/profil/cv"), api("/api/reglages")]);
  const peutGenererApi = reglagesIa.cle_api_definie && reglagesIa.fournisseur_ia !== "openai_compatible";
  ouvrirModale(
    t("lettres.creer_titre"),
    `<h2 style="font-size:13px;margin:0 0 8px;">${t("pieces.pour_qui")}</h2>
     <div id="creation-selecteur"></div>
     <div class="champ" style="margin-top:12px;">
       <label for="lettre-langue">${t("lettres.langue_label")}</label>
       <input type="text" id="lettre-langue" placeholder="${echapperAttribut(t("lettres.langue_placeholder"))}">
     </div>
     ${!cv.defini ? `<p class="sous-titre" style="color:var(--danger);margin-top:10px;">${t("lettres.cv_manquant")}</p>` : ""}
     <div class="carte bloc-methode">
       <h2>${t("lettres.methode_skill_titre")}</h2>
       <p class="sous-titre">${t("lettres.methode_skill_texte")}</p>
       <div class="actions-reglages"><a class="btn btn-accent" href="/api/lettres/skill">${t("lettres.telecharger_skill")}</a></div>
     </div>
     <div class="carte bloc-methode">
       <h2>${t("lettres.methode_api_titre")}</h2>
       <p class="sous-titre">${t("lettres.methode_api_texte")}</p>
       ${!peutGenererApi ? `<p class="sous-titre">${t("lettres.methode_api_indisponible")}</p>` : ""}
       <div class="actions-reglages"><button class="btn btn-accent" id="btn-generer" disabled>${t("lettres.generer")}</button></div>
       <div id="generation-statut" class="sous-titre" style="margin-top:8px;"></div>
     </div>
     <div class="carte bloc-methode">
       <h2>${t("lettres.methode_fichier_titre")}</h2>
       <p class="sous-titre">${t("lettres.methode_fichier_texte")}</p>
       <div class="actions-reglages"><button class="btn" id="btn-vers-import">${t("lettres.ajouter_la_mienne")}</button></div>
     </div>`,
    `<button class="btn" onclick="fermerModale()">${t("commun.fermer")}</button>`,
    false, true
  );
  const selecteur = await creerSelecteurCible(document.getElementById("creation-selecteur"), { mode: "pieces" });
  const bouton = document.getElementById("btn-generer");
  selecteur.surChangement((choix) => {
    bouton.disabled = !(peutGenererApi && cv.defini && (choix.entrepriseId !== null || choix.entrepriseNom));
  });
  bouton.addEventListener("click", () => {
    const choix = selecteur.lire();
    lancerGeneration("lettres", {
      entreprise: choix.entrepriseNom,
      candidature_ids: choix.offreIds,
      generale: choix.generale,
      langue: document.getElementById("lettre-langue").value.trim() || null,
    }, [bouton], document.getElementById("generation-statut"));
  });
  document.getElementById("btn-vers-import").addEventListener("click", () => {
    fermerModale();
    ouvrirImportPiece("lettres");
  });
}

async function ouvrirNouvelleFiche() {
  const [cv, reglagesIa] = await Promise.all([api("/api/profil/cv"), api("/api/reglages")]);
  const peutGenerer = reglagesIa.cle_api_definie;
  ouvrirModale(
    t("fiches.creer_titre"),
    `<h2 style="font-size:13px;margin:0 0 8px;">${t("fiches.pour_quelles_offres")}</h2>
     <div id="creation-selecteur"></div>
     <div class="grille-form" style="margin-top:12px;">
       <div class="champ">
         <label for="fiche-date">${t("fiches.date_entretien")}</label>
         <input type="date" id="fiche-date">
       </div>
       <div class="champ">
         <label for="fiche-langue">${t("pieces.champ_langue")}</label>
         <input type="text" id="fiche-langue" placeholder="${echapperAttribut(t("pieces.langue_placeholder"))}">
       </div>
     </div>
     ${!cv.defini ? `<p class="sous-titre" style="margin-top:10px;">${t("fiches.cv_conseille")}</p>` : ""}
     <div class="carte bloc-methode">
       <h2>${t("fiches.methode_api_titre")}</h2>
       <p class="sous-titre">${t("fiches.methode_api_texte")}</p>
       ${!peutGenerer ? `<p class="sous-titre">${t("fiches.methode_api_indisponible")}</p>` : ""}
       <div class="actions-reglages"><button class="btn btn-accent" id="btn-generer" disabled>${t("fiches.generer")}</button></div>
       <div id="generation-statut" class="sous-titre" style="margin-top:8px;"></div>
     </div>
     <div class="carte bloc-methode">
       <h2>${t("fiches.methode_fichier_titre")}</h2>
       <p class="sous-titre">${t("fiches.methode_fichier_texte")}</p>
       <div class="actions-reglages"><button class="btn" id="btn-vers-import">${t("fiches.ajouter_la_mienne")}</button></div>
     </div>`,
    `<button class="btn" onclick="fermerModale()">${t("commun.fermer")}</button>`,
    false, true
  );
  const selecteur = await creerSelecteurCible(document.getElementById("creation-selecteur"), {
    mode: "pieces", autoriserNouvelle: false,
  });
  const bouton = document.getElementById("btn-generer");
  selecteur.surChangement((choix) => {
    // Une fiche prépare l'entretien pour des postes précis : au moins une offre.
    bouton.disabled = !(peutGenerer && choix.offreIds.length > 0);
    bouton.title = choix.offreIds.length ? "" : t("fiches.choisir_une_offre");
    const champDate = document.getElementById("fiche-date");
    if (champDate && !champDate.value) {
      const avecDate = choix.offres.find((o) => o.date_entretien);
      if (avecDate) champDate.value = avecDate.date_entretien;
    }
  });
  bouton.addEventListener("click", () => {
    const choix = selecteur.lire();
    lancerGeneration("fiches", {
      entreprise: choix.entrepriseNom,
      candidature_ids: choix.offreIds,
      generale: choix.generale,
      date_entretien: document.getElementById("fiche-date").value || null,
      langue: document.getElementById("fiche-langue").value.trim() || null,
    }, [bouton], document.getElementById("generation-statut"));
  });
  document.getElementById("btn-vers-import").addEventListener("click", () => {
    fermerModale();
    ouvrirImportPiece("fiches");
  });
}

/* Section « Préparation » d'une candidature ou d'une entreprise : ce qui est
   déjà prêt (lettres, fiches, notes d'entretien), cliquable. */
function sectionPreparation(lettres, fiches, notes) {
  const ligne = (type, titre, clic) => `
    <div class="ligne-liee" onclick="${clic}">
      <span class="puce">${t(`preparation.type_${type}`)}</span>
      <span class="cellule-principale">${echapper(titre)}</span>
    </div>`;
  const lignes = [
    ...lettres.map((l) => ligne("lettre", l.titre, `ouvrirApercuPiece('lettres', ${l.id})`)),
    ...fiches.map((f) => ligne("fiche", f.titre, `ouvrirApercuPiece('fiches', ${f.id})`)),
    ...notes.map((n) => ligne("note", n.titre, `fermerPanneau(); location.hash='#/entretiens/${n.id}'`)),
  ];
  return `
    <h3 class="section-panneau">${t("preparation.titre")}</h3>
    ${lignes.length ? `<div class="liste-liee">${lignes.join("")}</div>` : `<p class="sous-titre">${t("preparation.aucune")}</p>`}`;
}

/* ========================================================================
   Notes d'entretien
   ======================================================================== */

function puceCible(note) {
  return note.candidature_id
    ? `<span class="puce puce-cible offre" title="${echapperAttribut(note.poste)}">${t("entretiens.cible_offre")} · ${echapper(note.poste)}</span>`
    : `<span class="puce puce-cible entreprise">${t("entretiens.cible_entreprise")}</span>`;
}

async function vueNotes() {
  const filtres = etat.filtresNotes;
  const parametres = new URLSearchParams();
  if (filtres.recherche) parametres.set("recherche", filtres.recherche);
  if (filtres.candidature) parametres.set("candidature", filtres.candidature);
  if (filtres.entreprise) parametres.set("entreprise", filtres.entreprise);
  const [notes, offres] = await Promise.all([
    api(`/api/notes?${parametres}`),
    filtres.candidature ? api("/api/candidatures") : Promise.resolve([]),
  ]);
  const offreFiltree = filtres.candidature ? offres.find((o) => o.id === filtres.candidature) : null;
  const puceFiltre = offreFiltree
    ? `<span class="puce filtre-actif">${t("entretiens.filtre_offre", { offre: echapper(offreFiltree.poste) })}
        <button class="btn btn-mini btn-discret" id="retirer-filtre-offre" title="${echapperAttribut(t("entretiens.retirer_filtre"))}">×</button></span>`
    : "";
  const lignes = notes.map((note) => `
    <tr onclick="location.hash='#/entretiens/${note.id}'">
      <td class="cellule-principale cellule-titre" title="${echapperAttribut(note.titre)}">${echapper(note.titre)}
        ${note.contenu.trim() ? `<div class="ligne-extrait">${echapper(note.contenu.trim().replace(/\s+/g, " ").slice(0, 140))}</div>` : `<div class="ligne-extrait">${t("entretiens.note_vide")}</div>`}
      </td>
      <td>${puceCible(note)}<div class="cellule-secondaire" style="margin-top:2px;">${echapper(note.entreprise)}</div></td>
      <td class="cellule-date">${dateFr(note.date_entretien || note.date_creation.slice(0, 10))}</td>
      <td class="cellule-date">${dateFr(note.date_modification.slice(0, 10))}</td>
    </tr>`).join("");
  return `
    <div class="entete-vue">
      <div style="flex:1;"><h1>${t("nav.entretiens")}</h1><div class="sous-titre">${t("entretiens.sous_titre")}</div></div>
      <button class="btn btn-accent" onclick="ouvrirNouvelleNote()">${t("entretiens.nouvelle")}</button>
    </div>
    <div class="filtres">
      <input type="text" id="filtre-notes" class="champ-filtre-large" placeholder="${echapperAttribut(t("entretiens.rechercher_placeholder"))}" value="${echapperAttribut(filtres.recherche)}">
      ${puceFiltre}
    </div>
    ${notes.length ? `
      <div class="enveloppe-tableau"><table class="tableau">
        <thead><tr>
          <th>${t("entretiens.col_note")}</th><th>${t("entretiens.col_cible")}</th>
          <th>${t("entretiens.col_entretien_le")}</th><th>${t("entretiens.col_modifiee_le")}</th>
        </tr></thead>
        <tbody>${lignes}</tbody>
      </table></div>` : `
      <div class="etat-vide">
        <div class="icone">${ICONES.entretiens}</div>
        <div class="titre">${filtres.recherche || filtres.candidature ? t("entretiens.vide_filtre_titre") : t("entretiens.vide_titre")}</div>
        <p>${filtres.recherche || filtres.candidature ? t("pieces.vide_filtre_texte") : t("entretiens.vide_texte")}</p>
        ${filtres.recherche ? "" : `<button class="btn btn-accent" onclick="ouvrirNouvelleNote()">${t("entretiens.nouvelle")}</button>`}
      </div>`}`;
}

function activerNotes() {
  const champ = document.getElementById("filtre-notes");
  if (champ) {
    let minuteur;
    champ.addEventListener("input", () => {
      clearTimeout(minuteur);
      minuteur = setTimeout(() => {
        etat.filtresNotes.recherche = champ.value;
        const position = champ.selectionStart;
        rendre().then(() => {
          const nouveau = document.getElementById("filtre-notes");
          if (nouveau) { nouveau.focus(); nouveau.setSelectionRange(position, position); }
        });
      }, 250);
    });
  }
  const retirer = document.getElementById("retirer-filtre-offre");
  if (retirer) {
    retirer.addEventListener("click", () => {
      etat.filtresNotes.candidature = null;
      rendre();
    });
  }
}

/* Depuis une candidature : les notes de cette offre (liste filtrée, avec « Nouvelle note »
   déjà réglée sur elle). */
function ouvrirNotesDeLOffre(candidatureId) {
  etat.filtresNotes = { recherche: "", candidature: candidatureId, entreprise: null };
  fermerPanneau();
  if (location.hash === "#/entretiens") rendre();
  else location.hash = "#/entretiens";
}

async function ouvrirNouvelleNote() {
  ouvrirModale(
    t("entretiens.nouvelle_titre"),
    `<h2 style="font-size:13px;margin:0 0 8px;">${t("entretiens.sur_quoi")}</h2>
     <div id="note-selecteur"></div>
     <div class="grille-form" style="margin-top:14px;">
       <div class="champ">
         <label for="note-nouveau-titre">${t("pieces.champ_titre_facultatif")}</label>
         <input type="text" id="note-nouveau-titre" placeholder="${echapperAttribut(t("entretiens.titre_par_defaut"))}">
       </div>
       <div class="champ">
         <label for="note-nouvelle-date">${t("entretiens.date_entretien")}</label>
         <input type="date" id="note-nouvelle-date" value="${aujourdHuiISO()}">
       </div>
     </div>`,
    `<button class="btn" onclick="fermerModale()">${t("commun.annuler")}</button>
     <button class="btn btn-accent" id="btn-creer-note" disabled>${t("entretiens.commencer")}</button>`,
    false, true
  );
  const filtres = etat.filtresNotes;
  const selecteur = await creerSelecteurCible(document.getElementById("note-selecteur"), {
    mode: "note",
    offreIds: filtres.candidature ? [filtres.candidature] : [],
    entrepriseId: filtres.entreprise || undefined,
  });
  const bouton = document.getElementById("btn-creer-note");
  selecteur.surChangement((choix) => {
    bouton.disabled = !(choix.entrepriseId !== null || choix.entrepriseNom);
  });
  bouton.addEventListener("click", async () => {
    const choix = selecteur.lire();
    bouton.disabled = true;
    try {
      const note = await api("/api/notes", {
        methode: "POST",
        corps: {
          entreprise: choix.offreIds.length ? null : choix.entrepriseNom,
          candidature_id: choix.offreIds[0] || null,
          titre: document.getElementById("note-nouveau-titre").value,
          date_entretien: document.getElementById("note-nouvelle-date").value || null,
        },
      });
      fermerModale();
      location.hash = `#/entretiens/${note.id}`;
    } catch (erreur) {
      toast(erreur.message, true);
      bouton.disabled = false;
    }
  });
}

/* --- Éditeur : la note à gauche (enregistrée au fil de la frappe), son contexte à droite --- */

async function vueEditeurNote(id) {
  const note = await api(`/api/notes/${id}`);
  const [offre, entreprises, lettresLiees, fichesLiees] = await Promise.all([
    note.candidature_id ? api(`/api/candidatures/${note.candidature_id}`) : Promise.resolve(null),
    api("/api/entreprises"),
    api(note.candidature_id ? `/api/lettres?candidature=${note.candidature_id}` : `/api/lettres?entreprise=${note.entreprise_id}`),
    api(note.candidature_id ? `/api/fiches?candidature=${note.candidature_id}` : `/api/fiches?entreprise=${note.entreprise_id}`),
  ]);
  const entreprise = entreprises.find((e) => e.id === note.entreprise_id) || {};
  const ligneLiee = (type, titre, clic) => `
    <div class="ligne-liee" onclick="${clic}"><span class="puce">${t(`preparation.type_${type}`)}</span><span class="cellule-principale">${echapper(titre)}</span></div>`;
  const contexte = `
    <h3>${t("entretiens.contexte_entreprise")}</h3>
    <div><a class="lien-detail" href="#" onclick="event.preventDefault(); ouvrirDetailEntreprise(${entreprise.id})"><strong>${echapper(note.entreprise)}</strong></a>
      ${entreprise.site_web ? `<div class="cellule-secondaire">${echapper(entreprise.site_web)}</div>` : ""}</div>
    ${entreprise.contexte_actus ? `<div class="texte-long" style="margin-top:8px;">${echapper(entreprise.contexte_actus)}</div>` : ""}
    ${offre ? `
      <h3>${t("entretiens.contexte_offre")}</h3>
      <div><a class="lien-detail" href="#" onclick="event.preventDefault(); ouvrirDetailCandidature(${offre.id})"><strong>${echapper(offre.poste)}</strong></a></div>
      <div style="margin-top:4px;"><span class="puce puce-statut" style="--couleur-statut:${COULEURS_STATUT[offre.statut]}"><span class="point"></span>${echapper(tv(offre.statut))}</span></div>
      ${offre.texte_offre ? `<div class="texte-long" style="margin-top:8px;">${echapper(offre.texte_offre)}</div>` : ""}` : ""}
    ${lettresLiees.length || fichesLiees.length ? `
      <h3>${t("entretiens.contexte_preparation")}</h3>
      ${lettresLiees.map((l) => ligneLiee("lettre", l.titre, `ouvrirApercuPiece('lettres', ${l.id})`)).join("")}
      ${fichesLiees.map((f) => ligneLiee("fiche", f.titre, `ouvrirApercuPiece('fiches', ${f.id})`)).join("")}` : ""}`;
  return `
    <div class="entete-vue">
      <button class="btn" onclick="location.hash='#/entretiens'">${t("entretiens.retour")}</button>
      <div style="flex:1;"></div>
      <span class="sous-titre" id="indicateur-note"></span>
      <button class="btn btn-danger" id="btn-supprimer-note">${t("commun.supprimer")}</button>
    </div>
    <div class="editeur-note">
      <div class="carte zone-notes">
        <input type="text" class="note-titre" id="note-titre" value="${echapperAttribut(note.titre)}" aria-label="${echapperAttribut(t("pieces.champ_titre"))}">
        <div class="note-meta">
          ${puceCible(note)}<span>${echapper(note.entreprise)}</span>
          <label>${t("entretiens.date_entretien")} <input type="date" id="note-date" value="${echapperAttribut(note.date_entretien || "")}"></label>
          <button class="btn btn-mini" id="btn-changer-cible">${t("entretiens.changer_cible")}</button>
        </div>
        <textarea id="note-contenu" placeholder="${echapperAttribut(t("entretiens.notes_placeholder"))}">${echapper(note.contenu)}</textarea>
      </div>
      <aside class="carte contexte-note">${contexte}</aside>
    </div>`;
}

function activerEditeurNote(id) {
  const contenu = document.getElementById("note-contenu");
  const titre = document.getElementById("note-titre");
  const date = document.getElementById("note-date");
  const indicateur = document.getElementById("indicateur-note");
  if (!contenu) return;
  let minuteur = null;
  let enAttente = false;
  let titreConnu = titre.value;

  const heure = () => new Date().toLocaleTimeString(etat.langue === "en" ? "en-US" : "fr-FR", { hour: "2-digit", minute: "2-digit" });

  async function envoyer(champs) {
    indicateur.textContent = t("entretiens.enregistrement_en_cours");
    try {
      await api(`/api/notes/${id}`, { methode: "PATCH", corps: champs });
      indicateur.textContent = t("entretiens.enregistre_a", { heure: heure() });
      return true;
    } catch (erreur) {
      indicateur.textContent = "";
      toast(erreur.message, true);
      return false;
    }
  }

  async function enregistrer() {
    clearTimeout(minuteur);
    minuteur = null;
    if (!enAttente) return;
    enAttente = false;
    if (!(await envoyer({ contenu: contenu.value }))) enAttente = true;
  }

  etat.noteEnCours = { enregistrer };
  contenu.addEventListener("input", () => {
    enAttente = true;
    indicateur.textContent = t("entretiens.enregistrement_en_cours");
    clearTimeout(minuteur);
    minuteur = setTimeout(enregistrer, 700);
  });
  contenu.addEventListener("keydown", (evenement) => {
    if ((evenement.metaKey || evenement.ctrlKey) && evenement.key.toLowerCase() === "s") {
      evenement.preventDefault();
      enregistrer();
    }
  });
  titre.addEventListener("change", async () => {
    if (!titre.value.trim()) {
      titre.value = titreConnu;
      toast(t("entretiens.titre_obligatoire"), true);
      return;
    }
    if (await envoyer({ titre: titre.value })) titreConnu = titre.value;
    else titre.value = titreConnu;
  });
  titre.addEventListener("keydown", (evenement) => {
    if (evenement.key === "Enter") { evenement.preventDefault(); titre.blur(); }
  });
  date.addEventListener("change", () => envoyer({ date_entretien: date.value || null }));

  document.getElementById("btn-supprimer-note").addEventListener("click", async () => {
    const accord = await confirmer(t("entretiens.supprimer_titre"), t("entretiens.supprimer_texte"));
    if (!accord) return;
    try {
      enAttente = false;
      await api(`/api/notes/${id}`, { methode: "DELETE" });
      toast(t("entretiens.supprimee"));
      location.hash = "#/entretiens";
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });
  document.getElementById("btn-changer-cible").addEventListener("click", () => ouvrirChangerCibleNote(id, enregistrer));
  if (!contenu.value) contenu.focus();
}

async function ouvrirChangerCibleNote(id, apresEnregistrement) {
  await apresEnregistrement();
  const note = await api(`/api/notes/${id}`);
  ouvrirModale(
    t("entretiens.changer_cible_titre"),
    `<div id="note-selecteur"></div>`,
    `<button class="btn" onclick="fermerModale()">${t("commun.annuler")}</button>
     <button class="btn btn-accent" id="btn-valider-cible" disabled>${t("commun.enregistrer")}</button>`,
    false, true
  );
  const selecteur = await creerSelecteurCible(document.getElementById("note-selecteur"), {
    mode: "note",
    entrepriseId: note.entreprise_id,
    offreIds: note.candidature_id ? [note.candidature_id] : [],
  });
  const bouton = document.getElementById("btn-valider-cible");
  selecteur.surChangement((choix) => { bouton.disabled = !(choix.entrepriseId !== null || choix.entrepriseNom); });
  bouton.addEventListener("click", async () => {
    const choix = selecteur.lire();
    try {
      await api(`/api/notes/${id}`, {
        methode: "PATCH",
        corps: choix.offreIds.length
          ? { candidature_id: choix.offreIds[0] }
          : { entreprise: choix.entrepriseNom },
      });
      toast(t("entretiens.cible_changee"));
      fermerModale();
      rendre();
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });
}
