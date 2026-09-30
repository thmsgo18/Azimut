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
   Zone de dépôt de fichiers (glisser-déposer ou parcourir)
   ======================================================================== */

/* Options : extensions (liste, ou null = tous les formats), tailleMax, multiple (plusieurs
   fichiers d'un coup), surFichier(premier) après chaque ajout. */
function creerZoneDepot(racine, options = {}) {
  const extensions = options.extensions === undefined ? [".pdf", ".docx", ".txt", ".md"] : options.extensions;
  const tailleMax = options.tailleMax || 15 * 1024 * 1024;
  const multiple = !!options.multiple;
  let fichiers = [];

  racine.innerHTML = `
    <div class="zone-depot" tabindex="0" role="button" aria-label="${echapperAttribut(t("depot.titre"))}">
      <div class="icone"><svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V4"/><path d="m7 9 5-5 5 5"/><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/></svg></div>
      <div class="zone-depot-titre">${t(multiple ? "depot.titre_multiple" : "depot.titre")}</div>
      <div class="zone-depot-sous">${extensions ? t("depot.sous_titre") : t("depot.sous_titre_tous")}</div>
      <div class="zone-depot-fichiers" hidden></div>
      <input type="file" ${extensions ? `accept="${extensions.join(",")}"` : ""}${multiple ? " multiple" : ""} hidden>
    </div>`;
  const zone = racine.querySelector(".zone-depot");
  const champ = racine.querySelector('input[type="file"]');
  const liste = racine.querySelector(".zone-depot-fichiers");
  if (multiple) zone.dataset.multiple = "";

  function afficher() {
    const rempli = fichiers.length > 0;
    zone.classList.toggle("rempli", rempli);
    racine.querySelector(".zone-depot-titre").hidden = rempli && !multiple;
    racine.querySelector(".zone-depot-sous").hidden = rempli && !multiple;
    liste.hidden = !rempli;
    liste.innerHTML = fichiers.map((fichier, rang) => `
      <div class="zone-depot-fichier">
        <span class="nom">${echapper(fichier.name)}</span><span class="taille">${tailleLisible(fichier.size)}</span>
        <button type="button" class="btn btn-mini" data-retirer="${rang}">${t(multiple ? "depot.retirer" : "depot.changer")}</button>
      </div>`).join("");
  }

  function accepter(nouveaux) {
    let ajoutes = false;
    for (const nouveau of nouveaux) {
      const extension = (nouveau.name.match(/\.[^.]+$/) || [""])[0].toLowerCase();
      if (extensions && !extensions.includes(extension)) {
        toast(t("depot.format_refuse", { ext: extension || "?" }), true);
        continue;
      }
      if (nouveau.size > tailleMax) {
        toast(t("depot.trop_gros", { taille: tailleLisible(tailleMax) }), true);
        continue;
      }
      if (multiple) fichiers.push(nouveau);
      else fichiers = [nouveau];
      ajoutes = true;
    }
    if (!ajoutes) return;
    afficher();
    if (options.surFichier) options.surFichier(fichiers[0]);
  }

  zone.addEventListener("click", (evenement) => {
    const retirer = evenement.target.closest("[data-retirer]");
    if (retirer) {
      fichiers.splice(Number(retirer.dataset.retirer), 1);
      champ.value = "";
      afficher();
      if (options.surFichier && fichiers.length) options.surFichier(fichiers[0]);
      if (!multiple) champ.click();
      return;
    }
    if (multiple || !fichiers.length) champ.click();
  });
  zone.addEventListener("keydown", (evenement) => {
    if ((evenement.key === "Enter" || evenement.key === " ") && (multiple || !fichiers.length)) {
      evenement.preventDefault();
      champ.click();
    }
  });
  champ.addEventListener("change", () => {
    accepter(Array.from(champ.files));
    champ.value = "";
  });
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
    const deposes = Array.from((evenement.dataTransfer && evenement.dataTransfer.files) || []);
    if (!multiple && deposes.length > 1) toast(t("depot.un_seul_fichier"), true);
    accepter(multiple ? deposes : deposes.slice(0, 1));
  });

  afficher();
  return { fichier: () => fichiers[0] || null, fichiers: () => fichiers.slice() };
}

/* ========================================================================
   Lettres de motivation, fiches d'entretien et documents : listes, aperçu, actions
   ======================================================================== */

/* Chaque section est décrite ici : la même liste, le même aperçu et la même fenêtre
   d'ajout servent aux trois. `typeLibelle` : colonne « Type » propre aux documents. */
const SECTIONS_PIECES = {
  lettres: { avecType: false, multiple: false },
  fiches: { avecType: false, multiple: false },
  documents: { avecType: true, multiple: true },
};

function offresLiees(piece) {
  const puces = piece.candidatures.map(
    (c) => `<span class="puce" title="${echapperAttribut(c.poste)}">${echapper(c.poste)}</span>`
  );
  if (piece.generale) puces.push(`<span class="puce puce-cible entreprise">${t("selecteur.entreprise_en_general")}</span>`);
  return puces.length ? `<div class="offres-liees">${puces.join("")}</div>` : "";
}

function ouvrirNouveauDepuisSection(section) {
  if (section === "lettres") return ouvrirNouvelleLettre();
  if (section === "fiches") return ouvrirNouvelleFiche();
  return ouvrirImportPiece("documents");
}

async function vuePieces(section) {
  const filtre = etat.filtresPieces[section].recherche;
  const avecType = SECTIONS_PIECES[section].avecType;
  const liste = await api(`/api/${section}` + (filtre ? `?recherche=${encodeURIComponent(filtre)}` : ""));
  const lignes = liste
    .map((piece) => `
    <tr onclick="ouvrirApercuPiece('${section}', ${piece.id})">
      <td class="cellule-principale cellule-titre" title="${echapperAttribut(piece.titre)}">${echapper(piece.titre)}
        ${piece.chemin_fichier && !piece.fichier_disponible ? `<span class="puce puce-lien-mort" title="${echapperAttribut(t("pieces.fichier_introuvable_titre"))}">${t("pieces.fichier_introuvable")}</span>` : ""}
      </td>
      ${avecType ? `<td><span class="puce">${echapper(tv(piece.type_document || "Autre"))}</span></td>` : ""}
      <td>${echapper(piece.entreprise)}</td>
      <td>${offresLiees(piece)}</td>
      <td class="cellule-date">${dateFr(piece.date_creation)}</td>
      <td onclick="event.stopPropagation()"><div class="actions-ligne">
        ${piece.fichier_disponible ? `<button class="btn btn-discret btn-mini" onclick="telechargerPiece('${section}', ${piece.id})">${t("pieces.telecharger")}</button>` : ""}
        <button class="btn btn-danger btn-mini" onclick="supprimerPiece('${section}', ${piece.id})">${t("commun.supprimer")}</button>
      </div></td>
    </tr>`)
    .join("");
  const boutons = `
    ${section === "documents" ? "" : `<button class="btn" onclick="ouvrirImportPiece('${section}')">${t(`${section}.ajouter_la_mienne`)}</button>`}
    <button class="btn btn-accent" onclick="ouvrirNouveauDepuisSection('${section}')">${t(`${section}.nouvelle`)}</button>`;
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
          <th>${t("pieces.col_titre")}</th>
          ${avecType ? `<th>${t("documents.col_type")}</th>` : ""}
          <th>${t("pieces.col_entreprise")}</th><th>${t("pieces.col_offres")}</th>
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
  if (!accord) return false;
  try {
    await api(`/api/${section}/${id}`, { methode: "DELETE" });
    toast(t(`${section}.supprimee`));
    if (apres) await apres();
    rendre();
    return true;
  } catch (erreur) {
    toast(erreur.message, true);
    return false;
  }
}

/* Télécharge le fichier d'une pièce SANS quitter la page (voir telechargerFichier dans app.js). */
async function telechargerPiece(section, id, format) {
  try {
    const piece = await api(`/api/${section}/${id}`);
    const nom = format === "texte"
      ? `${piece.titre}.md`
      : (piece.nom_fichier || `${piece.titre}.pdf`);
    await telechargerFichier(`/api/${section}/${id}/telecharger${format ? `?format=${format}` : ""}`, nom);
  } catch (erreur) {
    toast(erreur.message, true);
  }
}

/* Copie un texte dans le presse-papiers (API moderne, sinon repli par une zone cachée). */
async function copierTexte(texte, messageOk) {
  let reussi = false;
  try {
    await navigator.clipboard.writeText(texte);
    reussi = true;
  } catch {
    const zone = document.createElement("textarea");
    zone.value = texte;
    zone.setAttribute("readonly", "");
    zone.style.cssText = "position:fixed;left:-9999px;top:0;";
    document.body.appendChild(zone);
    zone.select();
    try { reussi = document.execCommand("copy"); } catch { reussi = false; }
    zone.remove();
  }
  toast(reussi ? (messageOk || t("commun.copie")) : t("commun.copie_impossible"), !reussi);
  return reussi;
}

/* Aperçu EN FENÊTRE : le fichier (PDF, image) et son texte, jamais une navigation
   de la page - on ferme la fenêtre et on retrouve exactement où on en était.
   `options.apres` s'exécute quand la pièce a été modifiée ou supprimée. */
async function ouvrirApercuPiece(section, id, options = {}) {
  let piece;
  try {
    piece = await api(`/api/${section}/${id}`);
  } catch (erreur) {
    toast(erreur.message, true);
    return;
  }
  const texte = (piece.contenu || "").trim();
  const vues = [];
  if (piece.type_apercu === "pdf" || piece.type_apercu === "image") vues.push("fichier");
  if (texte) vues.push("texte");
  const enMarkdown = section === "fiches" && piece.source !== "manuelle";

  const meta = `
    <div class="apercu-meta">
      <span class="puce">${echapper(piece.entreprise)}</span>
      ${section === "documents" ? `<span class="puce">${echapper(tv(piece.type_document || "Autre"))}</span>` : ""}
      ${piece.candidatures.map((c) => `<span class="puce">${echapper(c.poste)}</span>`).join("")}
      ${piece.generale ? `<span class="puce puce-cible entreprise">${t("selecteur.entreprise_en_general")}</span>` : ""}
      <span class="cellule-secondaire">${dateFr(piece.date_creation)}</span>
    </div>`;
  const barre = `
    <div class="apercu-barre">
      ${vues.length > 1 ? `
        <div class="bascule apercu-onglets">
          <button type="button" data-vue="fichier">${t("pieces.vue_apercu")}</button>
          <button type="button" data-vue="texte">${t("pieces.vue_texte")}</button>
        </div>` : "<span></span>"}
      <div class="apercu-actions"></div>
    </div>`;
  const zone = ouvrirModale(
    piece.titre,
    `${meta}${barre}<div class="apercu-zone"></div>`,
    `<button class="btn btn-danger" id="btn-piece-supprimer" style="margin-right:auto;">${t("commun.supprimer")}</button>
     <button class="btn" id="btn-piece-modifier">${t("commun.modifier")}</button>
     <button class="btn btn-accent" onclick="fermerModale()">${t("commun.fermer")}</button>`,
    false, true
  );
  const cadre = zone.racine.querySelector(".apercu-zone");
  const actions = zone.racine.querySelector(".apercu-actions");

  function afficherVue(nom) {
    zone.racine.querySelectorAll(".apercu-onglets button").forEach((b) => b.classList.toggle("actif", b.dataset.vue === nom));
    if (nom === "fichier") {
      cadre.innerHTML = piece.type_apercu === "image"
        ? `<div class="apercu-image-cadre"><img class="apercu-image" src="/api/${section}/${piece.id}/apercu" alt="${echapperAttribut(piece.titre)}"></div>`
        : `<iframe class="apercu-cadre" src="/api/${section}/${piece.id}/apercu" title="${echapperAttribut(piece.titre)}"></iframe>`;
      actions.innerHTML = piece.fichier_disponible
        ? `<button type="button" class="btn btn-mini" data-action="telecharger">${t("pieces.telecharger")}</button>` : "";
    } else if (nom === "texte") {
      cadre.innerHTML = enMarkdown
        ? `<div class="apercu-texte rendu-markdown">${rendreMarkdown(texte)}</div>`
        : `<div class="apercu-texte">${echapper(texte)}</div>`;
      actions.innerHTML = `
        <button type="button" class="btn btn-mini" data-action="copier">${t("pieces.copier_texte")}</button>
        <button type="button" class="btn btn-mini" data-action="telecharger-texte">${t("pieces.telecharger_texte")}</button>`;
    } else {
      cadre.innerHTML = `
        <div class="etat-vide compact"><p>${t("pieces.aucun_apercu")}</p></div>`;
      actions.innerHTML = piece.fichier_disponible
        ? `<button type="button" class="btn btn-mini btn-accent" data-action="telecharger">${t("pieces.telecharger")}</button>` : "";
    }
  }
  zone.racine.querySelectorAll(".apercu-onglets button").forEach((b) => b.addEventListener("click", () => afficherVue(b.dataset.vue)));
  actions.addEventListener("click", (evenement) => {
    const action = evenement.target.closest("[data-action]");
    if (!action) return;
    if (action.dataset.action === "copier") copierTexte(texte, t("pieces.texte_copie"));
    else if (action.dataset.action === "telecharger") telechargerPiece(section, piece.id);
    else if (action.dataset.action === "telecharger-texte") telechargerPiece(section, piece.id, "texte");
  });
  afficherVue(vues[0] || null);

  zone.racine.querySelector("#btn-piece-modifier").addEventListener("click", () => {
    ouvrirModifierPiece(section, piece, async () => {
      fermerModale(zone);
      if (options.apres) await options.apres();
      ouvrirApercuPiece(section, piece.id, options);
    });
  });
  zone.racine.querySelector("#btn-piece-supprimer").addEventListener("click", async () => {
    const supprimee = await supprimerPiece(section, piece.id, options.apres);
    if (supprimee) fermerModale(zone);
  });
}

async function ouvrirModifierPiece(section, piece, apres) {
  const v = etat.valeurs;
  const zone = ouvrirModale(
    t("pieces.modifier_titre"),
    `<div class="grille-form">
       <div class="champ pleine-largeur">
         <label for="piece-titre">${t("pieces.champ_titre")}</label>
         <input type="text" id="piece-titre" value="${echapperAttribut(piece.titre)}">
       </div>
       ${section === "documents" ? `
       <div class="champ">
         <label for="piece-type">${t("documents.col_type")}</label>
         <select id="piece-type">${optionsSelect(v.types_document, piece.type_document || "Autre", false)}</select>
       </div>` : ""}
       <div class="champ pleine-largeur">
         <label>${t("pieces.champ_offres")} - ${echapper(piece.entreprise)}</label>
         <div id="piece-selecteur"></div>
       </div>
     </div>`,
    `<button class="btn" onclick="fermerModale()">${t("commun.annuler")}</button>
     <button class="btn btn-accent" id="btn-piece-enregistrer">${t("commun.enregistrer")}</button>`,
    false, true
  );
  const selecteur = await creerSelecteurCible(zone.racine.querySelector("#piece-selecteur"), {
    mode: "pieces", entrepriseFixe: piece.entreprise_id, offreIds: piece.candidatures.map((c) => c.id),
    generale: piece.generale,
  });
  zone.racine.querySelector("#btn-piece-enregistrer").addEventListener("click", async () => {
    const choix = selecteur.lire();
    const corps = {
      titre: zone.racine.querySelector("#piece-titre").value,
      candidature_ids: choix.offreIds,
      generale: choix.generale,
    };
    if (section === "documents") corps.type_document = zone.racine.querySelector("#piece-type").value;
    try {
      await api(`/api/${section}/${piece.id}`, { methode: "PATCH", corps });
      toast(t("pieces.enregistree"));
      fermerModale(zone);
      if (apres) await apres();
      else rendre();
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });
}

/* ------------------------------------------------------------------------
   Ajouter son propre fichier (lettre, fiche, document) : glisser-déposer
   ------------------------------------------------------------------------ */

/* options : entrepriseFixe (id) + offreIds : ajout depuis une candidature (la sélection est
   déjà faite) ; apres : rappelé une fois les fichiers ajoutés. */
async function ouvrirImportPiece(section, options = {}) {
  const documents = section === "documents";
  const v = etat.valeurs;
  const zone = ouvrirModale(
    t(`${section}.ajouter_la_mienne_titre`),
    `<p class="sous-titre" style="margin-top:0;">${t(`${section}.ajouter_la_mienne_texte`)}</p>
     <div id="depot"></div>
     <h2 class="titre-bloc">${t("pieces.rattacher_a")}</h2>
     <div id="import-selecteur"></div>
     <p class="sous-titre" id="suggestion-fichier" style="margin:6px 0 0;" hidden></p>
     <div class="grille-form" style="margin-top:14px;">
       ${documents ? `
       <div class="champ">
         <label for="import-type">${t("documents.col_type")}</label>
         <select id="import-type">${optionsSelect(v.types_document, options.type || "Autre", false)}</select>
       </div>` : `
       <div class="champ">
         <label for="import-titre">${t("pieces.champ_titre_facultatif")}</label>
         <input type="text" id="import-titre" placeholder="${echapperAttribut(t("pieces.titre_par_defaut"))}">
       </div>
       <div class="champ">
         <label for="import-langue">${t("pieces.champ_langue")}</label>
         <input type="text" id="import-langue" placeholder="${echapperAttribut(t("pieces.langue_placeholder"))}">
       </div>`}
     </div>`,
    `<button class="btn" onclick="fermerModale()">${t("commun.annuler")}</button>
     <button class="btn btn-accent" id="btn-import-piece" disabled>${t("pieces.ajouter")}</button>`,
    false, true
  );

  let selecteur;
  const bouton = zone.racine.querySelector("#btn-import-piece");
  const suggestion = zone.racine.querySelector("#suggestion-fichier");
  const actualiserBouton = () => {
    const choix = selecteur.lire();
    bouton.disabled = !depot.fichiers().length || !(choix.entrepriseId !== null || choix.entrepriseNom);
  };
  const depot = creerZoneDepot(zone.racine.querySelector("#depot"), {
    multiple: documents,
    extensions: documents ? null : [".pdf", ".docx", ".txt", ".md"],
    tailleMax: documents ? 25 * 1024 * 1024 : 15 * 1024 * 1024,
    surFichier: (fichier) => {
      // Le nom du fichier suggère souvent l'entreprise (« lettre-motivation-CEA.pdf ») :
      // on la propose, sans jamais écraser un choix déjà fait.
      if (selecteur && !options.entrepriseFixe && selecteur.lire().entrepriseNom === "") {
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
  selecteur = await creerSelecteurCible(zone.racine.querySelector("#import-selecteur"), {
    mode: "pieces", entrepriseFixe: options.entrepriseFixe, offreIds: options.offreIds,
  });
  selecteur.surChangement(actualiserBouton);

  bouton.addEventListener("click", async () => {
    const choix = selecteur.lire();
    const fichiers = depot.fichiers();
    bouton.disabled = true;
    etat.versionDb = null;
    let reussis = 0;
    for (const fichier of fichiers) {
      const formulaire = new FormData();
      formulaire.append("fichier", fichier);
      formulaire.append("entreprise", choix.entrepriseNom);
      formulaire.append("candidature_ids", JSON.stringify(choix.offreIds));
      formulaire.append("generale", choix.generale ? "1" : "0");
      if (documents) {
        formulaire.append("type_document", zone.racine.querySelector("#import-type").value);
      } else {
        formulaire.append("titre", zone.racine.querySelector("#import-titre").value);
        formulaire.append("langue", zone.racine.querySelector("#import-langue").value);
      }
      try {
        const reponse = await fetch(`/api/${section}/importer`, { method: "POST", body: formulaire });
        const donnees = await reponse.json();
        if (!reponse.ok) throw new Error(donnees.erreur || t("commun.erreur_inattendue"));
        reussis += 1;
      } catch (erreur) {
        toast(`${fichier.name} : ${erreur.message}`, true);
      }
    }
    if (!reussis) { bouton.disabled = false; return; }
    toast(reussis === 1 ? t(`${section}.ajoutee`) : t("documents.documents_ajoutes", { n: reussis }));
    fermerModale(zone);
    if (options.apres) await options.apres();
    rendre();
  });
}

/* ------------------------------------------------------------------------
   Créer avec l'IA (clé API), avec une IA installée sur l'ordinateur, ou en ajoutant son fichier
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

/* Choix du CV que l'IA lira (seulement s'il y en a plusieurs) : le principal par défaut. */
function choixCvHtml(cvs) {
  if (cvs.length < 2) return "";
  return `
    <div class="champ" style="margin-top:12px;">
      <label for="generation-cv">${t("pieces.cv_utilise")}</label>
      <select id="generation-cv">
        ${cvs.map((cv) => `<option value="${cv.id}"${cv.principal ? " selected" : ""}>${echapper(cv.nom)}${cv.langue ? ` (${echapper(cv.langue)})` : ""}${cv.principal ? ` - ${echapper(t("cv.principal"))}` : ""}</option>`).join("")}
      </select>
    </div>`;
}

function carteIaLocale(section, nomSkill) {
  return `
    <div class="carte bloc-methode">
      <h2>${t(`${section}.methode_skill_titre`)}</h2>
      <p class="sous-titre">${t(`${section}.methode_skill_texte`)}</p>
      <div class="actions-reglages">
        <a class="btn btn-accent" href="/api/skills/${nomSkill}" data-telechargement="${nomSkill}.skill">${t(`${section}.telecharger_skill`)}</a>
      </div>
    </div>`;
}

async function ouvrirNouvelleLettre() {
  const [cvs, reglagesIa] = await Promise.all([api("/api/cvs"), api("/api/reglages")]);
  const peutGenererApi = reglagesIa.cle_api_definie && reglagesIa.fournisseur_ia !== "openai_compatible";
  const zone = ouvrirModale(
    t("lettres.creer_titre"),
    `<h2 class="titre-bloc">${t("pieces.pour_qui")}</h2>
     <div id="creation-selecteur"></div>
     <div class="champ" style="margin-top:12px;">
       <label for="lettre-langue">${t("lettres.langue_label")}</label>
       <input type="text" id="lettre-langue" placeholder="${echapperAttribut(t("lettres.langue_placeholder"))}">
     </div>
     ${choixCvHtml(cvs)}
     ${!cvs.length ? `<p class="sous-titre" style="color:var(--danger);margin-top:10px;">${t("lettres.cv_manquant")} <a class="lien-detail" href="#/cv" onclick="fermerModale()">${t("lettres.aller_aux_cv")}</a></p>` : ""}
     ${carteIaLocale("lettres", "lettre-motivation")}
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
  const selecteur = await creerSelecteurCible(zone.racine.querySelector("#creation-selecteur"), { mode: "pieces" });
  const bouton = zone.racine.querySelector("#btn-generer");
  selecteur.surChangement((choix) => {
    bouton.disabled = !(peutGenererApi && cvs.length && (choix.entrepriseId !== null || choix.entrepriseNom));
  });
  bouton.addEventListener("click", () => {
    const choix = selecteur.lire();
    const choixCv = zone.racine.querySelector("#generation-cv");
    lancerGeneration("lettres", {
      entreprise: choix.entrepriseNom,
      candidature_ids: choix.offreIds,
      generale: choix.generale,
      langue: zone.racine.querySelector("#lettre-langue").value.trim() || null,
      cv_id: choixCv ? Number(choixCv.value) : null,
    }, [bouton], zone.racine.querySelector("#generation-statut"));
  });
  zone.racine.querySelector("#btn-vers-import").addEventListener("click", () => {
    fermerModale(zone);
    ouvrirImportPiece("lettres");
  });
}

async function ouvrirNouvelleFiche() {
  const [cvs, reglagesIa] = await Promise.all([api("/api/cvs"), api("/api/reglages")]);
  const peutGenerer = reglagesIa.cle_api_definie;
  const zone = ouvrirModale(
    t("fiches.creer_titre"),
    `<h2 class="titre-bloc">${t("fiches.pour_quelles_offres")}</h2>
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
     ${choixCvHtml(cvs)}
     ${!cvs.length ? `<p class="sous-titre" style="margin-top:10px;">${t("fiches.cv_conseille")} <a class="lien-detail" href="#/cv" onclick="fermerModale()">${t("lettres.aller_aux_cv")}</a></p>` : ""}
     ${carteIaLocale("fiches", "fiche-entretien")}
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
  const selecteur = await creerSelecteurCible(zone.racine.querySelector("#creation-selecteur"), {
    mode: "pieces", autoriserNouvelle: false,
  });
  const bouton = zone.racine.querySelector("#btn-generer");
  selecteur.surChangement((choix) => {
    // Une fiche prépare l'entretien pour des postes précis : au moins une offre.
    bouton.disabled = !(peutGenerer && choix.offreIds.length > 0);
    bouton.title = choix.offreIds.length ? "" : t("fiches.choisir_une_offre");
    const champDate = zone.racine.querySelector("#fiche-date");
    if (champDate && !champDate.value) {
      const avecDate = choix.offres.find((o) => o.date_entretien);
      if (avecDate) champDate.value = avecDate.date_entretien;
    }
  });
  bouton.addEventListener("click", () => {
    const choix = selecteur.lire();
    const choixCv = zone.racine.querySelector("#generation-cv");
    lancerGeneration("fiches", {
      entreprise: choix.entrepriseNom,
      candidature_ids: choix.offreIds,
      generale: choix.generale,
      date_entretien: zone.racine.querySelector("#fiche-date").value || null,
      langue: zone.racine.querySelector("#fiche-langue").value.trim() || null,
      cv_id: choixCv ? Number(choixCv.value) : null,
    }, [bouton], zone.racine.querySelector("#generation-statut"));
  });
  zone.racine.querySelector("#btn-vers-import").addEventListener("click", () => {
    fermerModale(zone);
    ouvrirImportPiece("fiches");
  });
}

/* Section « Préparation » d'une candidature ou d'une entreprise : ce qui est
   déjà prêt (documents, lettres, fiches, notes d'entretien), cliquable. */
function sectionPreparation(lettres, fiches, notes, documents = [], creerNote = null) {
  const ligne = (type, titre, clic) => `
    <div class="ligne-liee" onclick="${clic}">
      <span class="puce">${t(`preparation.type_${type}`)}</span>
      <span class="cellule-principale">${echapper(titre)}</span>
    </div>`;
  const lignes = [
    ...documents.map((d) => ligne("document", d.titre, `ouvrirApercuPiece('documents', ${d.id})`)),
    ...lettres.map((l) => ligne("lettre", l.titre, `ouvrirApercuPiece('lettres', ${l.id})`)),
    ...fiches.map((f) => ligne("fiche", f.titre, `ouvrirApercuPiece('fiches', ${f.id})`)),
    ...notes.map((n) => ligne("note", n.titre, `fermerToutesLesFenetres(); location.hash='#/entretiens/${n.id}'`)),
  ];
  return `
    <h3 class="section-panneau">${t("preparation.titre")}</h3>
    ${lignes.length ? `<div class="liste-liee">${lignes.join("")}</div>` : `<p class="sous-titre">${t("preparation.aucune")}</p>`}
    ${creerNote ? `<div class="actions-reglages"><button type="button" class="btn" onclick="${creerNote}">${t("preparation.nouvelle_note")}</button></div>` : ""}`;
}

function fermerToutesLesFenetres() {
  while (pileModales.length) fermerModale();
}

/* Une nouvelle note liée à cette offre, ouverte tout de suite dans l'éditeur. */
async function nouvelleNotePourOffre(candidatureId) {
  try {
    const note = await api("/api/notes", {
      methode: "POST",
      corps: { candidature_id: candidatureId, date_entretien: aujourdHuiISO() },
    });
    fermerToutesLesFenetres();
    location.hash = `#/entretiens/${note.id}`;
  } catch (erreur) {
    toast(erreur.message, true);
  }
}

/* Une nouvelle note liée à cette entreprise en général, ouverte tout de suite dans l'éditeur. */
async function nouvelleNotePourEntreprise(entrepriseId) {
  try {
    const ent = (await api("/api/entreprises")).find((e) => e.id === entrepriseId);
    if (!ent) throw new Error(t("entreprises.introuvable"));
    const note = await api("/api/notes", {
      methode: "POST",
      corps: { entreprise: ent.nom, date_entretien: aujourdHuiISO() },
    });
    fermerToutesLesFenetres();
    location.hash = `#/entretiens/${note.id}`;
  } catch (erreur) {
    toast(erreur.message, true);
  }
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
  const filtre = etat.filtresNotes.recherche;
  const notes = await api("/api/notes" + (filtre ? `?recherche=${encodeURIComponent(filtre)}` : ""));
  const lignes = notes.map((note) => `
    <tr onclick="location.hash='#/entretiens/${note.id}'">
      <td class="cellule-principale cellule-titre" title="${echapperAttribut(note.titre)}">${echapper(note.titre)}
        ${note.contenu.trim() ? `<div class="ligne-extrait">${echapper(Markdown.resume(note.contenu, 140))}</div>` : `<div class="ligne-extrait">${t("entretiens.note_vide")}</div>`}
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
      <input type="text" id="filtre-notes" class="champ-filtre-large" placeholder="${echapperAttribut(t("entretiens.rechercher_placeholder"))}" value="${echapperAttribut(filtre)}">
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
        <div class="titre">${filtre ? t("entretiens.vide_filtre_titre") : t("entretiens.vide_titre")}</div>
        <p>${filtre ? t("pieces.vide_filtre_texte") : t("entretiens.vide_texte")}</p>
        ${filtre ? "" : `<button class="btn btn-accent" onclick="ouvrirNouvelleNote()">${t("entretiens.nouvelle")}</button>`}
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
}

async function ouvrirNouvelleNote() {
  const zone = ouvrirModale(
    t("entretiens.nouvelle_titre"),
    `<h2 class="titre-bloc">${t("entretiens.sur_quoi")}</h2>
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
  const selecteur = await creerSelecteurCible(zone.racine.querySelector("#note-selecteur"), { mode: "note" });
  const bouton = zone.racine.querySelector("#btn-creer-note");
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
          titre: zone.racine.querySelector("#note-nouveau-titre").value,
          date_entretien: zone.racine.querySelector("#note-nouvelle-date").value || null,
        },
      });
      fermerModale(zone);
      location.hash = `#/entretiens/${note.id}`;
    } catch (erreur) {
      toast(erreur.message, true);
      bouton.disabled = false;
    }
  });
}

/* --- Éditeur : Markdown avec rendu en direct (enregistré au fil de la frappe) --- */

/* Préférences d'affichage de l'éditeur, gardées d'une note à l'autre (sans importance si le
   stockage local est indisponible). */
function preferenceNote(cle, defaut) {
  try { return window.localStorage.getItem(`azimut.note.${cle}`) || defaut; } catch { return defaut; }
}
function memoriserPreferenceNote(cle, valeur) {
  try { window.localStorage.setItem(`azimut.note.${cle}`, valeur); } catch { /* sans importance */ }
}

const ICONES_BARRE = {
  liste: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1" fill="currentColor"/><circle cx="4.5" cy="12" r="1" fill="currentColor"/><circle cx="4.5" cy="18" r="1" fill="currentColor"/></svg>',
  ordonnee: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 6h10M10 12h10M10 18h10"/><path d="M4 5.5 5.5 5v3M4 11.5h2.2L4 14h2.4M4 17.2h2.2v.8H4.6M6.2 18v1H4" stroke-width="1.4"/></svg>',
  tache: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="4" width="7" height="7" rx="1.5"/><path d="m5 7.5 1.5 1.5L9 6"/><path d="M14 7h7M14 17h7"/><rect x="3.5" y="13" width="7" height="7" rx="1.5"/></svg>',
  citation: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8h4v4c0 2-1 3.5-3 4M14 8h4v4c0 2-1 3.5-3 4"/></svg>',
  code: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m8 7-5 5 5 5M16 7l5 5-5 5"/></svg>',
  lien: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3A4 4 0 0 0 11 18.7l1-1"/></svg>',
};

function barreOutilsNote() {
  const bouton = (action, contenu, libelle, classe = "") =>
    `<button type="button" class="outil-note ${classe}" data-outil="${action}" title="${echapperAttribut(libelle)}" aria-label="${echapperAttribut(libelle)}">${contenu}</button>`;
  return `
    <div class="note-barre" role="toolbar" aria-label="${echapperAttribut(t("entretiens.barre_outils"))}">
      <div class="outils-note">
        ${bouton("gras", "B", t("entretiens.outil_gras"), "gras")}
        ${bouton("italique", "I", t("entretiens.outil_italique"), "italique")}
        ${bouton("barre", "S", t("entretiens.outil_barre"), "barre")}
        <span class="separateur-outils"></span>
        ${bouton("titre", "H", t("entretiens.outil_titre"), "titre")}
        ${bouton("liste", ICONES_BARRE.liste, t("entretiens.outil_liste"))}
        ${bouton("ordonnee", ICONES_BARRE.ordonnee, t("entretiens.outil_liste_numerotee"))}
        ${bouton("tache", ICONES_BARRE.tache, t("entretiens.outil_tache"))}
        ${bouton("citation", ICONES_BARRE.citation, t("entretiens.outil_citation"))}
        ${bouton("code", ICONES_BARRE.code, t("entretiens.outil_code"))}
        ${bouton("lien", ICONES_BARRE.lien, t("entretiens.outil_lien"))}
      </div>
      <div class="bascule note-modes">
        <button type="button" data-mode="ecrire">${t("entretiens.mode_ecrire")}</button>
        <button type="button" data-mode="duo">${t("entretiens.mode_duo")}</button>
        <button type="button" data-mode="apercu">${t("entretiens.mode_apercu")}</button>
      </div>
      <button type="button" class="btn btn-mini" id="btn-contexte">${t("entretiens.contexte_afficher")}</button>
    </div>`;
}

async function vueEditeurNote(id) {
  const note = await api(`/api/notes/${id}`);
  const [offre, entreprises, lettresLiees, fichesLiees, docsLies] = await Promise.all([
    note.candidature_id ? api(`/api/candidatures/${note.candidature_id}`) : Promise.resolve(null),
    api("/api/entreprises"),
    api(note.candidature_id ? `/api/lettres?candidature=${note.candidature_id}` : `/api/lettres?entreprise=${note.entreprise_id}`),
    api(note.candidature_id ? `/api/fiches?candidature=${note.candidature_id}` : `/api/fiches?entreprise=${note.entreprise_id}`),
    api(note.candidature_id ? `/api/documents?candidature=${note.candidature_id}` : `/api/documents?entreprise=${note.entreprise_id}`),
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
    ${lettresLiees.length || fichesLiees.length || docsLies.length ? `
      <h3>${t("entretiens.contexte_preparation")}</h3>
      ${docsLies.map((d) => ligneLiee("document", d.titre, `ouvrirApercuPiece('documents', ${d.id})`)).join("")}
      ${lettresLiees.map((l) => ligneLiee("lettre", l.titre, `ouvrirApercuPiece('lettres', ${l.id})`)).join("")}
      ${fichesLiees.map((f) => ligneLiee("fiche", f.titre, `ouvrirApercuPiece('fiches', ${f.id})`)).join("")}` : ""}`;
  const contexteOuvert = preferenceNote("contexte", "ferme") === "ouvert";
  const mode = ["ecrire", "duo", "apercu"].includes(preferenceNote("mode", "duo")) ? preferenceNote("mode", "duo") : "duo";
  return `
    <div class="entete-vue">
      <button class="btn" onclick="location.hash='#/entretiens'">${t("entretiens.retour")}</button>
      <div style="flex:1;"></div>
      <span class="sous-titre" id="indicateur-note"></span>
      <button class="btn btn-danger" id="btn-supprimer-note">${t("commun.supprimer")}</button>
    </div>
    <div class="editeur-note${contexteOuvert ? "" : " sans-contexte"}">
      <div class="carte zone-notes">
        <input type="text" class="note-titre" id="note-titre" value="${echapperAttribut(note.titre)}" aria-label="${echapperAttribut(t("pieces.champ_titre"))}">
        <div class="note-meta">
          ${puceCible(note)}<span>${echapper(note.entreprise)}</span>
          <label>${t("entretiens.date_entretien")} <input type="date" id="note-date" value="${echapperAttribut(note.date_entretien || "")}"></label>
          <button class="btn btn-mini" id="btn-changer-cible">${t("entretiens.changer_cible")}</button>
        </div>
        ${barreOutilsNote()}
        <div class="note-zones" data-mode="${mode}">
          <textarea id="note-contenu" spellcheck="true" placeholder="${echapperAttribut(t("entretiens.notes_placeholder"))}">${echapper(note.contenu)}</textarea>
          <div id="note-apercu" class="note-apercu rendu-markdown" aria-live="off"></div>
        </div>
        <p class="note-aide">${t("entretiens.aide_markdown")}</p>
      </div>
      <aside class="carte contexte-note">${contexte}</aside>
    </div>`;
}

/* --- édition Markdown : mise en forme de la sélection, listes qui se poursuivent --- */

/* Remplace [debut, fin) par `texte` en gardant l'historique d'annulation (⌘Z) quand le
   navigateur le permet ; place ensuite la sélection sur [selDebut, selFin). */
function remplacerDansZone(zone, debut, fin, texte, selDebut, selFin) {
  zone.focus();
  zone.setSelectionRange(debut, fin);
  let fait = false;
  try { fait = document.execCommand("insertText", false, texte); } catch { fait = false; }
  if (!fait || zone.value.slice(debut, debut + texte.length) !== texte) {
    zone.setRangeText(texte, debut, fin, "end");
    zone.dispatchEvent(new Event("input", { bubbles: true }));
  }
  zone.setSelectionRange(selDebut ?? debut + texte.length, selFin ?? selDebut ?? debut + texte.length);
}

/* Entoure la sélection (ou un texte d'exemple) ; si elle est déjà entourée, retire l'entourage. */
function entourerSelection(zone, avant, apres, exemple) {
  const { selectionStart: debut, selectionEnd: fin, value } = zone;
  const choisi = value.slice(debut, fin);
  if (choisi && value.slice(debut - avant.length, debut) === avant && value.slice(fin, fin + apres.length) === apres) {
    remplacerDansZone(zone, debut - avant.length, fin + apres.length, choisi, debut - avant.length, fin - avant.length);
    return;
  }
  const corps = choisi || exemple;
  remplacerDansZone(zone, debut, fin, avant + corps + apres, debut + avant.length, debut + avant.length + corps.length);
}

/* Bornes [debut, fin) des lignes touchées par la sélection. */
function lignesSelectionnees(zone) {
  const { value, selectionStart, selectionEnd } = zone;
  const debut = value.lastIndexOf("\n", selectionStart - 1) + 1;
  let fin = value.indexOf("\n", selectionEnd > selectionStart ? selectionEnd - 1 : selectionEnd);
  if (fin === -1) fin = value.length;
  return { debut, fin };
}

/* Ajoute (ou retire, si toutes les lignes l'ont déjà) un préfixe de ligne : « - », « > », « 1. »… */
function prefixerLignes(zone, prefixe, motif, numerote = false) {
  const { debut, fin } = lignesSelectionnees(zone);
  const lignes = zone.value.slice(debut, fin).split("\n");
  const toutesPrefixees = lignes.every((l) => l.trim() === "" || motif.test(l));
  const nouvelles = lignes.map((ligne, rang) => {
    if (toutesPrefixees) return ligne.replace(motif, "");
    if (ligne.trim() === "" && lignes.length > 1) return ligne;
    return (numerote ? `${rang + 1}. ` : prefixe) + ligne.replace(/^\s*([-*+]|\d+[.)])\s+(\[[ xX]\]\s+)?/, "");
  });
  const texte = nouvelles.join("\n");
  remplacerDansZone(zone, debut, fin, texte, debut, debut + texte.length);
}

function appliquerOutilNote(zone, outil) {
  if (outil === "gras") entourerSelection(zone, "**", "**", "gras");
  else if (outil === "italique") entourerSelection(zone, "*", "*", "italique");
  else if (outil === "barre") entourerSelection(zone, "~~", "~~", "barré");
  else if (outil === "code") entourerSelection(zone, "`", "`", "code");
  else if (outil === "liste") prefixerLignes(zone, "- ", /^\s*[-*+]\s+/);
  else if (outil === "ordonnee") prefixerLignes(zone, "1. ", /^\s*\d+[.)]\s+/, true);
  else if (outil === "tache") prefixerLignes(zone, "- [ ] ", /^\s*[-*+]\s+\[[ xX]\]\s+/);
  else if (outil === "citation") prefixerLignes(zone, "> ", /^\s*>\s?/);
  else if (outil === "titre") {
    // Titre : chaque appui monte d'un niveau (# → ## → ### → retour au texte simple).
    const { debut, fin } = lignesSelectionnees(zone);
    const ligne = zone.value.slice(debut, fin);
    const m = /^(#{1,3})\s+/.exec(ligne);
    const nouvelle = !m ? `# ${ligne}` : m[1].length < 3 ? `${m[1]}# ${ligne.slice(m[0].length)}` : ligne.slice(m[0].length);
    remplacerDansZone(zone, debut, fin, nouvelle, debut + nouvelle.length);
  } else if (outil === "lien") {
    const { selectionStart: debut, selectionEnd: fin, value } = zone;
    const choisi = value.slice(debut, fin) || "texte";
    const adresse = "https://";
    const texte = `[${choisi}](${adresse})`;
    remplacerDansZone(zone, debut, fin, texte, debut + choisi.length + 3, debut + choisi.length + 3 + adresse.length);
  }
}

/* Entrée dans une liste : la ligne suivante reprend le même marqueur ; sur une ligne de
   liste vide, Entrée termine la liste. Retourne true si l'événement a été géré. */
function entreeDansListe(zone) {
  if (zone.selectionStart !== zone.selectionEnd) return false;
  const position = zone.selectionStart;
  const debut = zone.value.lastIndexOf("\n", position - 1) + 1;
  const ligne = zone.value.slice(debut, position);
  const m = /^(\s*)([-*+]|(\d+)([.)]))\s+(\[[ xX]\]\s+)?(.*)$/.exec(ligne);
  if (!m) return false;
  if (m[6].trim() === "") {
    // Élément vide : on retire le marqueur (la liste se termine).
    remplacerDansZone(zone, debut, position, "", debut);
    return true;
  }
  const marqueur = m[3] ? `${Number(m[3]) + 1}${m[4]}` : m[2];
  const suite = `\n${m[1]}${marqueur} ${m[5] ? "[ ] " : ""}`;
  remplacerDansZone(zone, position, position, suite, position + suite.length);
  return true;
}

/* Tab / Maj+Tab dans une liste : imbrique ou remonte l'élément. */
function indenterListe(zone, arriere) {
  const { debut, fin } = lignesSelectionnees(zone);
  const lignes = zone.value.slice(debut, fin).split("\n");
  if (!lignes.every((l) => /^\s*([-*+]|\d+[.)])\s/.test(l))) return false;
  const nouvelles = lignes.map((l) => (arriere ? l.replace(/^( {1,2}|\t)/, "") : `  ${l}`));
  const texte = nouvelles.join("\n");
  remplacerDansZone(zone, debut, fin, texte, debut, debut + texte.length);
  return true;
}

function activerEditeurNote(id) {
  const contenu = document.getElementById("note-contenu");
  const titre = document.getElementById("note-titre");
  const date = document.getElementById("note-date");
  const indicateur = document.getElementById("indicateur-note");
  const apercu = document.getElementById("note-apercu");
  const zones = document.querySelector(".note-zones");
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

  // Le rendu suit la frappe quasi instantanément (un seul rendu par rafale de touches).
  let rendu = null;
  const afficherRendu = () => {
    rendu = null;
    apercu.innerHTML = Markdown.rendre(contenu.value) || `<p class="apercu-vide">${t("entretiens.apercu_vide")}</p>`;
  };
  const planifierRendu = () => { if (rendu === null) rendu = setTimeout(afficherRendu, 16); };
  afficherRendu();

  etat.noteEnCours = { enregistrer };
  contenu.addEventListener("input", () => {
    enAttente = true;
    indicateur.textContent = t("entretiens.enregistrement_en_cours");
    planifierRendu();
    clearTimeout(minuteur);
    minuteur = setTimeout(enregistrer, 700);
  });
  contenu.addEventListener("keydown", (evenement) => {
    const commande = evenement.metaKey || evenement.ctrlKey;
    if (commande && evenement.key.toLowerCase() === "s") {
      evenement.preventDefault();
      enregistrer();
    } else if (commande && evenement.key.toLowerCase() === "b") {
      evenement.preventDefault();
      appliquerOutilNote(contenu, "gras");
    } else if (commande && evenement.key.toLowerCase() === "i") {
      evenement.preventDefault();
      appliquerOutilNote(contenu, "italique");
    } else if (evenement.key === "Enter" && !evenement.shiftKey && !commande && !evenement.altKey) {
      if (entreeDansListe(contenu)) evenement.preventDefault();
    } else if (evenement.key === "Tab" && !commande && !evenement.altKey) {
      if (indenterListe(contenu, evenement.shiftKey)) evenement.preventDefault();
    }
  });

  // Une case à cocher cliquée dans le rendu coche la tâche dans le texte.
  apercu.addEventListener("change", (evenement) => {
    const case_ = evenement.target;
    if (!case_.matches('input[type="checkbox"][data-ligne]')) return;
    contenu.value = Markdown.basculerTache(contenu.value, Number(case_.dataset.ligne));
    contenu.dispatchEvent(new Event("input", { bubbles: true }));
  });

  // Barre d'outils : les boutons ne volent pas le focus (la sélection reste dans le texte).
  const barre = document.querySelector(".note-barre");
  barre.addEventListener("mousedown", (evenement) => {
    if (evenement.target.closest(".outil-note")) evenement.preventDefault();
  });
  barre.addEventListener("click", (evenement) => {
    const outil = evenement.target.closest(".outil-note");
    if (outil) {
      if (zones.dataset.mode === "apercu") changerMode("duo");
      appliquerOutilNote(contenu, outil.dataset.outil);
    }
  });

  function changerMode(mode) {
    zones.dataset.mode = mode;
    barre.querySelectorAll(".note-modes button").forEach((b) => b.classList.toggle("actif", b.dataset.mode === mode));
    memoriserPreferenceNote("mode", mode);
    if (mode !== "apercu") contenu.focus({ preventScroll: true });
  }
  barre.querySelectorAll(".note-modes button").forEach((b) => b.addEventListener("click", () => changerMode(b.dataset.mode)));
  barre.querySelectorAll(".note-modes button").forEach((b) => b.classList.toggle("actif", b.dataset.mode === zones.dataset.mode));

  const editeur = document.querySelector(".editeur-note");
  const boutonContexte = document.getElementById("btn-contexte");
  const majBoutonContexte = () => {
    boutonContexte.textContent = editeur.classList.contains("sans-contexte")
      ? t("entretiens.contexte_afficher") : t("entretiens.contexte_masquer");
  };
  majBoutonContexte();
  boutonContexte.addEventListener("click", () => {
    editeur.classList.toggle("sans-contexte");
    memoriserPreferenceNote("contexte", editeur.classList.contains("sans-contexte") ? "ferme" : "ouvert");
    majBoutonContexte();
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
  if (!contenu.value && zones.dataset.mode !== "apercu") contenu.focus();
}

async function ouvrirChangerCibleNote(id, apresEnregistrement) {
  await apresEnregistrement();
  const note = await api(`/api/notes/${id}`);
  const zone = ouvrirModale(
    t("entretiens.changer_cible_titre"),
    `<div id="note-selecteur"></div>`,
    `<button class="btn" onclick="fermerModale()">${t("commun.annuler")}</button>
     <button class="btn btn-accent" id="btn-valider-cible" disabled>${t("commun.enregistrer")}</button>`,
    false, true
  );
  const selecteur = await creerSelecteurCible(zone.racine.querySelector("#note-selecteur"), {
    mode: "note",
    entrepriseId: note.entreprise_id,
    offreIds: note.candidature_id ? [note.candidature_id] : [],
  });
  const bouton = zone.racine.querySelector("#btn-valider-cible");
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
      fermerModale(zone);
      rendre();
    } catch (erreur) {
      toast(erreur.message, true);
    }
  });
}
