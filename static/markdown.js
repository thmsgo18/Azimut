/* Azimut - rendu Markdown (notes d'entretien, récapitulatif d'une candidature).

   Un petit convertisseur maison, sans dépendance ni accès réseau : l'appli reste
   100 % locale. Il gère ce qu'on utilise vraiment en prenant des notes -
   titres, gras, italique, barré, code, listes à puces / numérotées / à cocher
   (imbriquées), citations, liens, tableaux, séparateurs.

   SÛRETÉ : tout le texte est échappé AVANT d'être mis en forme ; les seuls
   éléments HTML produits sont ceux fabriqués ici, et un lien n'est cliquable que
   s'il commence par http://, https:// ou mailto:. Un retour à la ligne simple est
   conservé (on prend des notes, on n'écrit pas un article : « Entrée » = nouvelle
   ligne). Les caractères de fin de ligne exotiques (U+2028, collés depuis Notes
   ou un traitement de texte) sont traités comme des retours à la ligne. */

"use strict";

(function () {
  const SAUTS = /\r\n|\r|\u2028|\u2029|\n/;

  function echapper(texte) {
    return String(texte)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function lignesDe(source) {
    return String(source == null ? "" : source).split(SAUTS);
  }

  /* --- inline -------------------------------------------------------------- */

  function lienSur(url) {
    return /^(https?:\/\/|mailto:)/i.test(url.trim());
  }

  /* Texte d'une ligne -> HTML. Le code (`x`) est mis de côté d'abord : rien n'y est mis en forme. */
  function inline(texte) {
    const codes = [];
    let brut = String(texte).replace(/`([^`\n]+)`/g, (_, code) => {
      codes.push(`<code>${echapper(code)}</code>`);
      return `\u0000${codes.length - 1}\u0000`;
    });
    brut = echapper(brut);

    // [texte](url) : l'URL a été échappée, on la re-lit telle quelle dans l'attribut.
    brut = brut.replace(/\[([^\]\n]+)\]\(([^)\s]+)\)/g, (tout, libelle, url) => {
      const propre = url.replace(/&amp;/g, "&");
      if (!lienSur(propre)) return tout;
      return `<a href="${echapper(propre)}" target="_blank" rel="noopener noreferrer">${libelle}</a>`;
    });
    // Adresses nues (pas déjà dans un lien).
    brut = brut.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, (tout, avant, url) => {
      const propre = url.replace(/&amp;/g, "&").replace(/[.,;:!?]+$/, "");
      const reste = url.slice(url.replace(/[.,;:!?]+$/, "").length);
      return `${avant}<a href="${echapper(propre)}" target="_blank" rel="noopener noreferrer">${echapper(propre)}</a>${reste}`;
    });

    brut = brut
      .replace(/\*\*([^\s*](?:[^*\n]*?[^\s*])?)\*\*/g, "<strong>$1</strong>")
      .replace(/__([^\s_](?:[^_\n]*?[^\s_])?)__/g, "<strong>$1</strong>")
      .replace(/~~([^\s~](?:[^~\n]*?[^\s~])?)~~/g, "<del>$1</del>")
      .replace(/(^|[^*\w])\*([^\s*](?:[^*\n]*?[^\s*])?)\*(?!\*)/g, "$1<em>$2</em>")
      .replace(/(^|[^_\w])_([^\s_](?:[^_\n]*?[^\s_])?)_(?![_\w])/g, "$1<em>$2</em>");

    return brut.replace(/\u0000(\d+)\u0000/g, (_, i) => codes[Number(i)]);
  }

  /* --- blocs --------------------------------------------------------------- */

  const RE_TITRE = /^(#{1,6})\s+(.*?)\s*#*\s*$/;
  const RE_SEPARATEUR = /^ {0,3}([-*_])(?:\s*\1){2,}\s*$/;
  const RE_LISTE = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
  const RE_TACHE = /^\[([ xX])\]\s+(.*)$/;
  const RE_CITATION = /^\s{0,3}>\s?(.*)$/;
  const RE_LIGNE_TABLEAU = /^\s*\|.*\|\s*$/;
  const RE_SEPARATEUR_TABLEAU = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

  function largeurIndentation(espaces) {
    return espaces.replace(/\t/g, "    ").length;
  }

  function cellules(ligne) {
    return ligne.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
  }

  /* Liste imbriquée : chaque élément connaît son niveau d'indentation ; une pile de
     listes ouvertes suit la profondeur. `numeroLigne` sert aux cases à cocher. */
  function rendreListe(elements) {
    let html = "";
    const pile = []; // { indent, balise }
    const fermerJusqua = (indent) => {
      while (pile.length && pile[pile.length - 1].indent > indent) {
        html += `</li></${pile.pop().balise}>`;
      }
    };
    elements.forEach((element, rang) => {
      const balise = element.ordonne ? "ol" : "ul";
      const courant = pile[pile.length - 1];
      if (!courant || element.indent > courant.indent) {
        html += `<${balise}>`; // nouvelle liste (ou sous-liste : on reste dans le <li> parent)
        pile.push({ indent: element.indent, balise });
      } else {
        fermerJusqua(element.indent);
        const cible = pile[pile.length - 1];
        if (cible.balise !== balise) {
          html += `</li></${pile.pop().balise}><${balise}>`;
          pile.push({ indent: element.indent, balise });
        } else {
          html += "</li>";
        }
      }
      const tache = element.tache;
      const contenu = inline(element.texte);
      if (tache) {
        html += `<li class="tache${tache.coche ? " faite" : ""}"><label><input type="checkbox" data-ligne="${element.ligne}"${tache.coche ? " checked" : ""}> <span>${contenu}</span></label>`;
      } else {
        html += `<li>${contenu}`;
      }
      if (rang === elements.length - 1) {
        while (pile.length) html += `</li></${pile.pop().balise}>`;
      }
    });
    return html;
  }

  function rendre(source) {
    const lignes = lignesDe(source);
    const sortie = [];
    let i = 0;

    while (i < lignes.length) {
      const ligne = lignes[i];

      if (ligne.trim() === "") { i += 1; continue; }

      // Bloc de code : ```
      if (/^\s*```/.test(ligne)) {
        const code = [];
        i += 1;
        while (i < lignes.length && !/^\s*```/.test(lignes[i])) { code.push(lignes[i]); i += 1; }
        i += 1; // la clôture (ou la fin du texte)
        sortie.push(`<pre><code>${echapper(code.join("\n"))}</code></pre>`);
        continue;
      }

      const titre = RE_TITRE.exec(ligne);
      if (titre) {
        const niveau = titre[1].length;
        sortie.push(`<h${niveau}>${inline(titre[2])}</h${niveau}>`);
        i += 1;
        continue;
      }

      if (RE_SEPARATEUR.test(ligne) && !RE_LISTE.test(ligne)) {
        sortie.push("<hr>");
        i += 1;
        continue;
      }

      // Citation : lignes consécutives commençant par >
      if (RE_CITATION.test(ligne)) {
        const morceaux = [];
        while (i < lignes.length && RE_CITATION.test(lignes[i])) {
          morceaux.push(RE_CITATION.exec(lignes[i])[1]);
          i += 1;
        }
        sortie.push(`<blockquote>${rendre(morceaux.join("\n"))}</blockquote>`);
        continue;
      }

      // Tableau : une ligne d'en-tête, une ligne de séparation, des lignes de données
      if (RE_LIGNE_TABLEAU.test(ligne) && i + 1 < lignes.length && RE_SEPARATEUR_TABLEAU.test(lignes[i + 1]) && lignes[i + 1].includes("-")) {
        const entetes = cellules(ligne);
        i += 2;
        const corps = [];
        while (i < lignes.length && RE_LIGNE_TABLEAU.test(lignes[i])) { corps.push(cellules(lignes[i])); i += 1; }
        sortie.push(
          "<table><thead><tr>" + entetes.map((c) => `<th>${inline(c)}</th>`).join("") + "</tr></thead><tbody>" +
          corps.map((rangee) => "<tr>" + entetes.map((_, k) => `<td>${inline(rangee[k] || "")}</td>`).join("") + "</tr>").join("") +
          "</tbody></table>"
        );
        continue;
      }

      // Liste (à puces, numérotée, à cocher), imbriquée par l'indentation
      if (RE_LISTE.test(ligne)) {
        const elements = [];
        while (i < lignes.length) {
          const brute = lignes[i];
          const m = RE_LISTE.exec(brute);
          if (m && !(RE_SEPARATEUR.test(brute))) {
            const tache = RE_TACHE.exec(m[3]);
            elements.push({
              indent: largeurIndentation(m[1]),
              ordonne: /\d/.test(m[2]),
              texte: tache ? tache[2] : m[3],
              tache: tache ? { coche: tache[1].toLowerCase() === "x" } : null,
              ligne: i,
            });
            i += 1;
          } else if (brute.trim() !== "" && /^\s+\S/.test(brute) && elements.length && !RE_TITRE.test(brute.trim())) {
            // ligne de continuation d'un élément (indentée, sans marqueur)
            elements[elements.length - 1].texte += "\n" + brute.trim();
            i += 1;
          } else {
            break;
          }
        }
        // Un niveau d'indentation « inférieur au premier » est ramené au premier niveau.
        const minimum = Math.min(...elements.map((e) => e.indent));
        elements.forEach((e) => { if (e.indent < minimum) e.indent = minimum; });
        sortie.push(rendreListe(elements));
        continue;
      }

      // Paragraphe : lignes consécutives jusqu'à une ligne vide ou un autre bloc
      const paragraphe = [];
      while (
        i < lignes.length && lignes[i].trim() !== "" && !/^\s*```/.test(lignes[i]) &&
        !RE_TITRE.test(lignes[i]) && !RE_LISTE.test(lignes[i]) && !RE_CITATION.test(lignes[i]) &&
        !(RE_SEPARATEUR.test(lignes[i]))
      ) {
        paragraphe.push(lignes[i]);
        i += 1;
      }
      sortie.push(`<p>${paragraphe.map(inline).join("<br>")}</p>`);
    }
    return sortie.join("\n");
  }

  /* Coche ou décoche la tâche de la ligne `indice` du texte source ; retourne le nouveau texte. */
  function basculerTache(source, indice) {
    const lignes = lignesDe(source);
    if (indice < 0 || indice >= lignes.length) return String(source);
    lignes[indice] = lignes[indice].replace(/\[([ xX])\]/, (_, c) => (c === " " ? "[x]" : "[ ]"));
    return lignes.join("\n");
  }

  /* Le texte d'une note sans sa mise en forme (marqueurs retirés), pour un extrait de liste. */
  function resume(source, longueur = 140) {
    const texte = lignesDe(source)
      .map((ligne) => ligne
        .replace(/^\s{0,3}#{1,6}\s+/, "")
        .replace(/^\s*>\s?/, "")
        .replace(/^\s*([-*+]|\d+[.)])\s+(\[[ xX]\]\s+)?/, "")
        .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
        .replace(/(\*\*|__|~~|`|\*|_(?=\S))/g, ""))
      .join(" ")
      .replace(/\s+/g, " ")
      .trim();
    return texte.length > longueur ? texte.slice(0, longueur).trimEnd() + "…" : texte;
  }

  const api = { rendre, inline, echapper, basculerTache, lignesDe, resume };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window !== "undefined") window.Markdown = api;
})();
