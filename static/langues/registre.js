/* Registre des langues disponibles pour l'interface.
   Pour ajouter une langue : créer static/langues/xx.js (copier fr.js comme
   modèle, traduire chaque valeur), ajouter une ligne ici, et une balise
   <script> dans index.html juste avant ce fichier. Pour en retirer une :
   supprimer les trois (le fichier, la ligne ici, la balise <script>).
   Rien d'autre à toucher : app.js lit tout via window.LANGUES. */
window.LANGUES_DISPONIBLES = [
  { code: "fr", nom: "Français" },
  { code: "en", nom: "English" },
];
