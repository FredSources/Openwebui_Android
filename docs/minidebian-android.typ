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

= Exécutabilité et retour d'action (P168)

Sur l'appareil ayant installé la *release* P167, le relais a renvoyé
`[Errno 13] Permission denied: '/data/data/org.openwebui.android/files/minidebian/proot'`.
Ce chemin est déjà `getFilesDir()`, donc le volume interne voulu : le diagnostic
P167, qui parlait encore de `Android/data` monté en `noexec`, était trompeur.
Les assets Android ne conservent pas le bit exécutable. Si le premier
`chmod` de l'extraction a échoué, le marqueur de version empêchait toute
réparation ultérieure. Le chmod est désormais réappliqué au démarrage même sur
le chemin rapide (Java), et `android_proot_prefix()` vérifie `os.access(X_OK)`
avant chaque ouverture de shell.

Le journal P168 enregistre l'errno, le mode effectif du fichier, le résultat de
`os.access` et la racine (`interne` ou `externe(noexec)`). Si le refus
persiste malgré le bit exécutable, ces éléments distingueront une politique
SELinux d'un montage `/data` verrouillé, sans répéter le faux diagnostic. Les
boutons Démarrer, Arrêter et Redémarrer affichent maintenant l'action en cours,
désactivent la barre pendant l'action puis affichent le résultat réel renvoyé
par `service_control`. « Redémarrer l'application » affiche une confirmation
avant l'extinction.

= Stockage visible et rafraîchissement (P169)

Un dossier `storage` est créé sous `Android/data/org.openwebui.android/files/minidebian/storage` : il est visible dans le gestionnaire de fichiers et monté dans le conteneur en `/root/storage` par un bind explicite. Les fichiers que l'utilisateur y dépose persistent et sont accessibles depuis le shell root. Les binaires restent dans `getFilesDir()` (interne, exécutable) : le stockage visible n'est jamais utilisé pour exécuter `proot`, qui échouerait sous `noexec`.

L'onglet « Moteur de recherche » a un bouton *Actualiser* qui recharge l'iframe SearXNG avec un cache-buster, et « Redémarrer l'application » restaure la dernière page `/fm` visitée. L'état des services est désormais déduit du port réellement à l'écoute (8888/8889), ce qui évite l'affichage « service arrêté — démarrez-le dans l'onglet Service » alors que le service répond. Le marqueur `P167/P168/P169 exécution refusée` est écrit directement dans `serveur.log`, même sans handler fichier sur le logger `open_terminal`.

= Exécution sous Android 10+ et dossier visible via SAF (P171/P173)

Malgré `chmod 0700` et `X_OK=True`, l'appareil refusait l'exécution de
`proot` avec `errno=13` sur le volume interne. Ce n'était pas un droit Unix :
Android 10 interdit l'`execve` d'un binaire dans le répertoire de données d'une
application qui cible SDK 29 ou plus (règle W^X). Termux reste pour cette raison
en `targetSdkVersion 28` ; l'APK cible désormais 28 également, ce qui rend le
shell root possible sans rooter le téléphone. Comme l'APK n'est pas publié sur
le Play Store, le contrôle lint `ExpiredTargetSdkVersion` est désactivé : il
exigerait 33+ et ferait échouer la release GitHub (P174). Placer seulement
`proot` dans `jniLibs` ne suffirait pas : les binaires du rootfs Debian seraient
toujours exécutés depuis l'espace de l'application.

Comme Termux, l'application n'écrit pas dans un dossier public : elle expose
`getExternalFilesDir(null)/minidebian/storage` au navigateur de fichiers via un
`DocumentsProvider` SAF intitulé « Mini Debian (OpenWebUI) ». Le service Python
utilise le même chemin et le monte dans le conteneur en `/root/storage`. Les
fichiers déposés là sont visibles dans le navigateur et depuis le shell. Le
service Open Terminal démarre avant Open WebUI et la connexion machine locale
reste désactivée jusqu'à l'ouverture effective du port 8889 : la ligne
`Initialized 0 tool server(s)` et le `Connect call failed` disparaissent.

= Vérifications et limites

Les tests `test_p160.py` à `test_p168.py` contrôlent les empreintes,
l'absence de `-R`/`-S`, le rendu des onglets et de l'iframe, l'absence de clé
dans le HTML, les deux modes de reset, la syntaxe JavaScript (`node --check`),
la résolution UMD des addons, la libération du port au redémarrage, le
démarrage du service à la demande (P165), le repli sans PTY sous proot (P166)
et le volume exécutable interne avec l'absence de relance sur `Errno 13`
(P167), puis le retour visuel des boutons et la réparation automatique du bit exécutable
(P168), puis le bouton Actualiser, le storage visible, la sonde de port et le
journal direct (P169). `check_apk.py` exige les assets mini-Debian, les modules
Python `open_terminal` et `proot_distro`, les fichiers xterm, les marqueurs
P164/P165/P166/P167/P168/P169 dans `android_fm.pyc` et les marqueurs
P166/P167/P168/P169 dans `open_terminal/main.pyc`. Il exige aussi
`OPENWEBUI_ANDROID_EXEC_HOME` et `OPENWEBUI_ANDROID_STORAGE` dans
`android_main.pyc`, `getFilesDir` dans les `classes.dex` et la taille maximale
du rootfs. Aucun
serveur de test ne doit écouter sur `8080` : seule la fenêtre `8090` est
autorisée pour les tests locaux.

*Limite non levée* : l'utilisateur a confirmé installer la *release* P167 et
le chemin `/data/data/.../files/minidebian/proot` observé prouve que le volume
interne est bien utilisé ; le `noexec` externe est donc levé. Il reste à
confirmer sur appareil que le chmod P168 suffit et que `ptrace` est autorisé.
Depuis P166, l'absence de `pty.openpty()`
n'est plus une impasse : le shell bascule en `backend=pipe`, conserve les
commandes dans le mini-Debian et l'interface l'indique clairement. Le prompt
interactif coloré reste indisponible dans ce mode ; les lignes `P166` de
`serveur.log` donnent le détail du basculement lorsque les journaux fichier
sont activés dans `/fm → Journaux`.

*Livraison P167* — prerelease `v0.0.82_ot_beta` republiée le
`2026-11-28T09:47:11Z` sur le commit `cb7b29c`, CI `46131420884` verte. Les
deux APK ont été téléchargées et vérifiées (`check_apk.py`, `apksigner verify`,
empreinte release stable) ; les 16 tests passent. Le chemin interne observé sur
l'appareil confirme que le `noexec` externe est levé.

*Livraison P168* — prerelease `v0.0.82_ot_beta` republiée le
`2026-11-28T11:21:46Z` sur le commit `2de40d4`, CI `46139047935` verte en
6 min 11 s. Les deux APK ont été téléchargées et vérifiées (`check_apk.py`,
`apksigner verify`, empreinte release stable) ; les 17 tests passent. Il reste à
confirmer sur l'appareil que le chmod P168 suffit et que `ptrace` est autorisé.
