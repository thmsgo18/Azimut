<p align="right"><b>English</b> | <a href="#sécurité-français">Français</a></p>

# Security Policy

## Supported versions

Azimut has a single rolling release on the `main` branch. Only the latest commit is supported; there are no maintained older versions. Update with `git pull` (or by downloading the latest ZIP) before reporting an issue.

## Reporting a vulnerability

If you find a security issue, please **do not open a public issue**. Instead, use [GitHub's private vulnerability reporting](https://github.com/thmsgo18/Azimut/security/advisories/new) on this repository, or open a regular issue asking for a private contact if that option is unavailable to you.

Please include: the affected file(s) or feature, steps to reproduce, and the potential impact. I'll do my best to respond and fix confirmed issues promptly, this is a solo, part time project.

## Scope and design

Azimut is a **local, single user desktop app**. There is no cloud backend and no multi user access control, so most of the usual web security concerns do not apply. A few things worth knowing:

- **Everything stays on your machine** by default. The only network calls are: the optional AI assistant (a request to the provider you configured, only when you use it), the dead job link checker (a conservative HEAD/GET to the job posting's own URL), and the optional companion view (see below).
- **Portal passwords and the AI API key are stored in cleartext** in the local SQLite database (`suivi_candidatures.db`). This is a documented, intentional trade off for a local single user tool, not an oversight, see the "Secrets" section of [`CLAUDE.md`](CLAUDE.md). Moving them to the OS keychain is tracked as a known improvement, not a vulnerability to report.
- **The companion view** (opt in, macOS only) exposes a small **read only** page on your local network, protected by a locally generated access code. It never serves portal passwords, the AI key, or any write route. Treat the access code like a PIN: anyone on the same Wi-Fi with the code and the URL can view your applications and next interview.
- **Excel exports never contain secrets**: no portal passwords, no API key. The full backup (a copy of the `.db` file) does, so treat that file with the same care as the app itself.
- Dependencies are kept minimal (`requirements.txt`); if you spot a known vulnerable version, an issue or PR bumping it is welcome.

---

<a id="sécurité-français"></a>
## Politique de sécurité (Français)

### Versions prises en charge

Azimut n'a qu'une seule version continue, sur la branche `main`. Seul le dernier commit est pris en charge, il n'y a pas d'anciennes versions maintenues. Mets à jour avec `git pull` (ou en téléchargeant le dernier ZIP) avant de signaler un problème.

### Signaler une vulnérabilité

Si tu trouves un problème de sécurité, **n'ouvre pas d'issue publique**. Utilise plutôt le [signalement privé de vulnérabilité de GitHub](https://github.com/thmsgo18/Azimut/security/advisories/new) sur ce dépôt, ou ouvre une issue classique demandant un contact privé si cette option ne t'est pas accessible.

Merci d'inclure : le ou les fichiers/fonctionnalités concernés, les étapes pour reproduire, et l'impact potentiel. Je ferai au mieux pour répondre et corriger rapidement les problèmes confirmés, c'est un projet solo, à temps partiel.

### Périmètre et choix de conception

Azimut est une **appli de bureau locale, mono-utilisateur**. Il n'y a ni backend cloud ni contrôle d'accès multi-utilisateur, donc la plupart des préoccupations habituelles de sécurité web ne s'appliquent pas. Quelques points à connaître :

- **Tout reste sur ta machine** par défaut. Les seuls appels réseau sont : l'assistant IA optionnel (une requête au fournisseur que tu as configuré, seulement quand tu l'utilises), la vérification des liens d'offres morts (un HEAD/GET conservateur vers l'URL de l'offre elle-même), et la vue compagnon optionnelle (voir plus bas).
- **Les mots de passe de portails et la clé API IA sont stockés en clair** dans la base SQLite locale (`suivi_candidatures.db`). C'est un choix documenté et assumé pour un outil local mono-utilisateur, pas un oubli, voir la section « Secrets » de [`CLAUDE.md`](CLAUDE.md). Les déplacer vers le trousseau de l'OS est une piste d'amélioration connue, pas une vulnérabilité à signaler.
- **La vue compagnon** (optionnelle, macOS uniquement) expose une petite page **en lecture seule** sur ton réseau local, protégée par un code d'accès généré localement. Elle ne sert jamais les mots de passe de portails, la clé IA, ni aucune route d'écriture. Traite ce code comme un code PIN : quiconque sur le même Wi-Fi avec le code et l'URL peut voir tes candidatures et ton prochain entretien.
- **Les exports Excel ne contiennent jamais de secrets** : ni mots de passe de portails, ni clé API. La sauvegarde complète (une copie du fichier `.db`), elle, en contient, à traiter avec la même précaution que l'appli elle-même.
- Les dépendances sont réduites au minimum (`requirements.txt`) ; si tu repères une version connue comme vulnérable, une issue ou une PR pour la mettre à jour est bienvenue.
