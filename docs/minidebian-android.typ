#import "@preview/ilm:2.1.0": *
#import "helpers.typ": *
#import "@preview/merman:0.3.0": show-mermaid-blocks

#set text(lang: "fr")
#set heading(numbering: "1.1")
#set par(justify: true)
#show figure.where(kind: table): set block(breakable: true)
#show raw.where(lang: "mermaid"): show-mermaid-blocks(
  width: 100%,
  document-context: true,
)

#show: ilm.with(
  title: [Open Terminal et mini-Debian embarqués],
  authors: "Équipe projet openwebui-android",
  date: datetime.today(),
  date-format: "[day padding:none]/[month padding:none]/[year]",
  abstract: [Note technique de l'intégration d'*Open Terminal* dans l'APK Open WebUI Android. Un rootfs Debian trixie arm64, un binaire `proot` et deux bibliothèques Android sont embarqués dans l'APK ; le service local `127.0.0.1:8889` est piloté depuis les onglets « Service » et « Shell root » de `/fm`. Le document fixe les versions, décrit le flux de démarrage, le relais HTTP qui protège la clé API, les deux modes de réinitialisation et les vérifications automatisées. La validation matérielle (`ptrace`, PTY) reste à réaliser sur une build release.],
  table-of-contents: outline(title: "Sommaire"),
)

= Objet

L'objectif est d'offrir un shell root réel dans l'APK, sans serveur externe ni
accès réseau sortant obligatoire, en conservant le modèle déjà utilisé pour
SearXNG : un service local lancé en thread daemon, piloté depuis la page `/fm`.
Open WebUI reste servi sur le port `8080`, SearXNG sur `8888`, Open Terminal
sur `8889` ; les tests locaux utilisent exclusivement le port `8090`.

#figure(
  caption: [Services locaux et chemin de la saisie xterm.js vers le mini-Debian.],
  ```mermaid
  flowchart LR
    W["WebView"] -->|"/fm"| F["Open WebUI :8080"]
    F -->|"/fm/ot/*"| P["Relais HTTP local"]
    P -->|"Authorization: Bearer + clé"| T["Open Terminal :8889"]
    T -->|"pty.openpty()"| R["proot"]
    R --> D["Debian trixie"]
    D --> Wk["/root/work ↔ data/work"]
  ```
)

= Versions figées

#figure(
  caption: [Composants ajoutés et versions retenues.],
  table(
    columns: (24fr, 19fr, 57fr),
    inset: 6pt,
    table.header([*Composant*], [*Version*], [*Rôle*]),
    [Open Terminal], [v0.18.8],
      [Service FastAPI local ; MIT ; empreinte `1413e9be11677266a400744480dc2e8c0de69916`],
    [proot-distro], [5.10.3],
      [Orchestrateur Python GPL-3.0-only ; empreinte `737306f53fc86213db0ce0ac3e76aa3fda8dcb90`],
    [proot], [binaire Termux], [Exécution du rootfs ; nécessite `ptrace` et deux bibliothèques bionic],
    [Debian], [trixie arm64], [Rootfs minimal avec `bash`, `apt`, `git`, `ca-certificates`],
    [xterm.js], [6.0.0], [Émulateur de terminal réel, servi depuis `/static/xterm/`],
    [addon-fit], [0.11.0], [Ajustement de la taille du PTY à la fenêtre],
    [addon-web-links], [0.12.0], [Liens cliquables dans le terminal],
  )
)

Les fichiers xterm sont versionnés dans `static/xterm/` avec leur SHA-256 dans
`manifest.json`. Les URL d'origine ont été vérifiées en HTTP 200 avant
téléchargement. Le rootfs est reconstruit dans `minidebian/` avec son manifest
(suite, architecture, date, paquets, version de glibc, taille et empreinte).
La limite de 100 Mo par fichier imposée par GitHub est vérifiée avant livraison.

= Démarrage

#figure(
  caption: [Séquence de démarrage du service Open Terminal.],
  ```mermaid
  sequenceDiagram
    participant J as MainActivity
    participant A as android_main
    participant O as Open WebUI
    participant T as Open Terminal
    J->>A: start_server(dataHome, getFilesDir())
    A->>A: consommer le marqueur de reset éventuel
    A->>A: générer la clé API (0600)
    A->>A: installer le rootfs depuis l'asset
    A->>O: lancer uvicorn :8080
    O-->>A: /health = 200
    A->>T: lancer uvicorn :8889 (ws="none")
    A->>O: forcer machines.connections avec la clé
  ```
)

Le marqueur de réinitialisation est traité *avant* le service, pour éviter
qu'une ancienne connexion et une ancienne clé survivent au redémarrage.
`prepareMiniDebian()` s'inspire de `prepareFrontend()` : marqueur
`minidebian.version` dans `getFilesDir()`, extraction de l'arbre `minidebian/`
depuis les assets, puis `proot.setExecutable(true, false)` — Android ne
conserve pas le bit exécutable dans les assets. Depuis P167, cette extraction
cible la mémoire *interne* : `Android/data` est monté en `noexec` et le bit
exécutable seul ne suffit pas à lancer `proot`. L'ancienne copie externe est
supprimée au premier démarrage.

Le service désactive browser, desktop, agents et notebooks. Le shell est
`/bin/bash -l` dans le rootfs ; les commandes passent par le même préfixe
proot. Les seuls binds sont `/dev`, `/proc`, `/sys`, `resolv.conf` (quand il
existe) et `data/work` vers `/root/work`. Les options `-R` et `-S` sont
interdites : elles lieraient `$HOME`, donc tout `DATA_DIR`, exposant la base
de données et les secrets dans le conteneur.

= Interface et relais HTTP

La sidebar « Paramètres » de `/fm` contient deux entrées supplémentaires :
*Open Terminal → Service* et *Shell root*. Chacune porte un point vert
`#22c55e` quand le service est actif, rouge `#ef4444` sinon. L'onglet Service
affiche l'état, le port, les boutons démarrer/arrêter/redémarrer et les deux
boutons de réinitialisation ; aucun de ces boutons n'apparaît dans le Shell
root. Celui-ci est une iframe autonome `/fm/ot/terminal`, sur le même modèle
que le moteur de recherche SearXNG : la page isolée héberge un vrai xterm.js,
dont `fitAddon.fit()` ajuste la taille et `term.onResize` relaie le PTY via `/fm/ot/resize`. Les addons 6 sont des
espaces de noms UMD (`FitAddon.FitAddon`, `WebLinksAddon.WebLinksAddon`) : une
fonction `ctor(o,n)` résout le constructeur quelle que soit la forme exposée.
Le redémarrage du service attend la libération effective du port `8889`.

Le navigateur n'envoie jamais la clé API. Il appelle uniquement les routes
locales de `/fm` ; le relais ajoute l'en-tête `Authorization: Bearer <clé>`
lit dans `data/open-terminal-api.key`, ainsi que des en-têtes de session fixés
(`x-user-id: embedded`, `x-session-id: fm`). Le client HTTP utilise
`trust_env=False` pour éviter tout proxy système.

#figure(
  caption: [Pourquoi le relais HTTP remplace le WebSocket navigateur.],
  table(
    columns: (50fr, 50fr),
    inset: 6pt,
    table.header([*WebSocket amont*], [*Relais retenu*]),
    [Exige `x-user-id` / `x-session-id` en en-têtes],
      [En-têtes posés côté serveur, jamais par le DOM],
    [Exige un jeton en premier message], [Jeton ajouté par le relais serveur],
    [Dépendance `websockets` absente de Chaquopy],
      [HTTP seul, déjà présent dans le backend],
  )
)

= Réinitialisation

#figure(
  caption: [Deux actions distinctes, toutes deux suivies d'un redémarrage.],
  table(
    columns: (27fr, 39fr, 34fr),
    inset: 6pt,
    table.header([*Action*], [*Contenu du marqueur*], [*Données utilisateur*]),
    [Réinitialiser l'environnement], [`environment`], [Conservé],
    [Tout effacer], [`wipe-work`], [Supprimé avec `data/work`],
  )
)

Dans les deux cas, le service est arrêté, la clé et le journal supprimés, le
conteneur proot reconstruit depuis le tarball embarqué, l'entrée
`machines.connections` réécrite avec la nouvelle clé et le marqueur consommé.
Le marqueur `minidebian.version` n'est pas touché : les assets ne changent pas,
inutile d'extraire à nouveau le rootfs. Le bouton « Tout effacer » demande une
confirmation explicite.

= Volume exécutable et désinstallation (P167)

#figure(
  caption: [Deux racines distinctes : données persistantes et volume exécutable.],
  table(
    columns: (27fr, 39fr, 34fr),
    inset: 6pt,
    table.header([*Racine*], [*Contenu*], [*Cycle de vie*]),
    [`getExternalFilesDir()`], [Base, configuration, `data/work`],
      [Conservé aux mises à jour],
    [`getFilesDir()`], [`proot`, libs, rootfs, état proot-distro],
      [Exécutable, effacé à la désinstallation],
  )
)

Sur l'appareil qui a signalé le P166, le binaire `proot` se trouvait sous
`/storage/emulated/0/Android/data/org.openwebui.android/files/minidebian/`.
Android y monte l'espace en `noexec` : `chmod +x` réussit, l'exécution échoue
avec `Errno 13`. Le service est désormais lancé depuis le volume interne
`getFilesDir()`, exactement comme Termux installe son préfixe sous
`/data/data/<paquet>/files`. Ce choix répond aussi à la demande explicite que
ce volume soit *effacé lors de la désinstallation* : Android nettoie
automatiquement `getFilesDir()` du paquet, sans script ni permission
supplémentaire.

`android_main.py` reçoit les deux chemins via `start_server(dataHome,
getFilesDir())`. `XDG_DATA_HOME` pointe sur le volume interne afin que le
rootfs extrait par proot-distro y réside également — sans quoi les
`/bin/bash` du conteneur resteraient sous un montage `noexec`. Les deux
réinitialisations conservent leur sémantique : `environment` reconstruit le
conteneur interne en gardant `data/work`, `wipe-work` supprime aussi
`data/work`.

= Vérifications et limites

Les tests `test_p160.py` à `test_p167.py` contrôlent les empreintes,
l'absence de `-R`/`-S`, le rendu des onglets et de l'iframe, l'absence de clé
dans le HTML, les deux modes de reset, la syntaxe JavaScript (`node --check`),
la résolution UMD des addons, la libération du port au redémarrage, le
démarrage du service à la demande (P165), le repli sans PTY sous proot (P166)
et le volume exécutable interne avec l'absence de relance sur `Errno 13`
(P167). `check_apk.py` exige les assets mini-Debian, les modules Python
`open_terminal` et `proot_distro`, les fichiers xterm, les marqueurs
P164/P165/P166/P167 dans `android_fm.pyc`, les marqueurs P166/P167 dans
`open_terminal/main.pyc`, `OPENWEBUI_ANDROID_EXEC_HOME` dans
`android_main.pyc`, `getFilesDir` dans les `classes.dex` et la taille maximale
du rootfs. Aucun
serveur de test ne doit écouter sur `8080` : seule la fenêtre `8090` est
autorisée pour les tests locaux.

*Limite non levée* : la validation sur appareil d'une build release n'a pas
encore été réalisée. P167 lève le blocage `noexec` en déplaçant `proot` vers
`getFilesDir()` ; il reste à confirmer que `ptrace` est autorisé. Depuis P166, l'absence de `pty.openpty()`
n'est plus une impasse : le shell bascule en `backend=pipe`, conserve les
commandes dans le mini-Debian et l'interface l'indique clairement. Le prompt
interactif coloré reste indisponible dans ce mode ; les lignes `P166` de
`serveur.log` donnent le détail du basculement lorsque les journaux fichier
sont activés dans `/fm → Journaux`.
