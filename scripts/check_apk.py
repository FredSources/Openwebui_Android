#!/usr/bin/env python3
"""check_apk.py — vérifie qu'un APK livré contient bien la chaîne attendue.

Contrôles (chacun correspond à un incident réel du projet) :
  1. Modules Python critiques présents dans les bundles (typst, pycrdt, msgspec,
     pydantic_core, jiter, orjson, rpds, uuid_utils, searx, open_webui).
  2. Shims présents (tiktoken, re2) et STUB pycrdt absent (il masquerait le natif).
  3. SearXNG complet : searx/settings.yml + searx/version_frozen.py (piège git).
  4. Noms de `.so` valides (SOABI Android ou .abi3) — piège pycrdt
     « aarch64-android-android ».
  5. Liaison bionic des natifs (aucun `libc.so.6`/`libm.so.6` = glibc) — piège msgspec.
  6. Frontend : `_app/` complet (piège ignoreAssetsPattern), index.html, pyodide
     (execute_code), et le bouton /fm (navigateur de fichiers).
  7. Routage embarqué : fm_browser (route /fm) présent dans main.
  8. Taille d'APK plausible.
  9. Nom d'APK cohérent avec le tag poussé (P93 : versionName == tag).

Usage : python3 scripts/check_apk.py dist/*.apk   (code retour != 0 si échec)
"""
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import zipfile

MODULES_PIP = ["typst", "pycrdt", "msgspec", "pydantic_core", "jiter", "orjson",
               "rpds", "uuid_utils", "asyncssh", "aiohttp", "multidict", "yarl",
               "frozenlist", "propcache", "aiohappyeyeballs"]  # P152 : asyncssh ; R165 : aiohttp 3.14.5
MODULES_APP = ["open_webui", "searx", "tiktoken", "re2"]
VERSION_AMONT = b"## [0.13.5]"  # P152 : changelog embarqué = version amont réellement livrée
SUFFIXES_VALIDES = (".abi3.so", ".cpython-313-aarch64-linux-android.so", ".so")
GLIBC = re.compile(r"lib(c|m|dl)\.so\.[0-9]")

erreurs: list[str] = []
avertissements: list[str] = []


def err(msg: str) -> None:
    erreurs.append(msg)


def warn(msg: str) -> None:
    avertissements.append(msg)


def lire(archive: zipfile.ZipFile, nom: str) -> bytes | None:
    try:
        return archive.read(nom)
    except KeyError:
        return None


def check_modules(bundle: zipfile.ZipFile, label: str, attendus: list[str]) -> None:
    noms = bundle.namelist()
    for m in attendus:
        if not any(n.startswith(m + "/") or n.startswith(m + ".") for n in noms):
            err(f"{label} : module « {m} » absent")
    if any(n.startswith("pycrdt.") for n in noms):
        err(f"{label} : stub pycrdt présent (masquerait le module natif)")


def check_noms_so(bundle: zipfile.ZipFile, label: str) -> None:
    for n in bundle.namelist():
        if not n.endswith(".so"):
            continue
        base = n.split("/")[-1]
        stem = base.split(".")[0]
        if not any(base == stem + suffix for suffix in SUFFIXES_VALIDES):
            err(f"{label} : nom de .so non importable : {base} "
                f"(attendu : {stem}.cpython-313-aarch64-linux-android.so ou {stem}.abi3.so)")


def check_bionic(fichiers_so: list[pathlib.Path]) -> None:
    for so in fichiers_so:
        try:
            out = subprocess.run(["readelf", "-d", str(so)],
                                 capture_output=True, text=True, timeout=60).stdout
        except Exception as exc:
            warn(f"readelf impossible sur {so.name} : {exc}")
            continue
        for lib in re.findall(r"\[([^\]]+)\]", out):
            if GLIBC.search(lib):
                err(f"{so.name} : lie la glibc ({lib}) — non chargeable sur Android")


def check_apk(apk: pathlib.Path) -> None:
    taille = apk.stat().st_size
    if taille < 100 * 1024 * 1024:
        err(f"{apk.name} : taille suspecte ({taille / 1e6:.0f} Mo < 100 Mo)")
    if taille > 320 * 1024 * 1024:
        warn(f"{apk.name} : taille élevée ({taille / 1e6:.0f} Mo)")

    # P93 — cohérence du nom : chaque APK livré doit porter la version du TAG
    # (incident v0.0.44 : assets « OpenWebUI_Android-0.0.43-release.apk »
    # publiés sous le tag v0.0.44 — le versionName n'avait pas été bumpé).
    # Placé AVANT l'ouverture du zip : le contrôle ne dépend que du nom du
    # fichier livré, zéro risque de couper le bloc with (leçon du run
    # 42702951060 : « ZIP archive that was already closed »).
    ref = os.environ.get("GITHUB_REF") or ""
    if ref.startswith("refs/tags/"):
        tag = ref[len("refs/tags/"):]
    else:
        _des = subprocess.run(['git', 'describe', '--tags', '--exact-match'],
                              capture_output=True, text=True,
                              cwd=pathlib.Path(__file__).resolve().parent.parent)
        tag = _des.stdout.strip() if _des.returncode == 0 else ""
    if tag:
        attendu = tag.lstrip('v')
        if attendu not in apk.name:
            err(f"tag {tag} : {apk.name} ne porte pas la version {attendu} "
                f"— versionName de build.gradle ≠ tag")

    with zipfile.ZipFile(apk) as z:
        noms = z.namelist()

        # 6. frontend
        app_count = sum(1 for n in noms if n.startswith("assets/frontend/_app/"))
        if app_count < 500:
            err(f"{apk.name} : frontend incomplet ({app_count} fichiers _app/ < 500) "
                f"— piège ignoreAssetsPattern")
        for requis in ("assets/frontend/index.html",
                       "assets/frontend/pyodide/pyodide-lock.json"):
            if requis not in noms:
                err(f"{apk.name} : absent — {requis}")
        # P47/P124 : wheels supplémentaires garantis dans l'artefact
        # (statsmodels, pymupdf, patsy, pyyaml — sha256 conformes au lock).
        for motif in ("statsmodels-", "pymupdf-", "patsy-", "pyyaml-"):
            if not any(n.startswith("assets/frontend/pyodide/") and motif in n and n.endswith(".whl")
                       for n in noms):
                err(f"{apk.name} : wheel {motif}* absente de assets/frontend/pyodide/")
        if not any("assets/frontend/index.html" == n and lire(z, n) and b"/fm" in lire(z, n) or False
                   for n in noms):
            contenu_index = lire(z, "assets/frontend/index.html") or b""
            if b"/fm" not in contenu_index:
                err(f"{apk.name} : bouton /fm absent de index.html")
        # P167 — l'extraction Java doit cibler getFilesDir() (volume interne
        # exécutable, effacé à la désinstallation), jamais Android/data.
        dex = b"".join(lire(z, n) or b"" for n in noms if n.startswith("classes")
                       and n.endswith(".dex"))
        if dex and b"getFilesDir" not in dex:
            err(f"{apk.name} : getFilesDir absent des dex — extraction du "
                f"mini-Debian sous Android/data (noexec)")
        # P123 : garde-fou contre la regression P121 — le patch 06 avait ete
        # regenere depuis une source vierge et la collecte de fichiers de
        # sortie P120 avait disparu du bundle (fichiers execute_code invisibles
        # au gestionnaire, display_file « introuvable »). Les appels fs:list /
        # fs:read doivent etre dans le noeud principal, pas seulement dans le
        # worker (qui les expose deja).
        noeuds = b"".join(
            lire(z, n) or b"" for n in noms
            if n.startswith("assets/frontend/_app/immutable/nodes/") and n.endswith(".js")
        )
        for marqueur in (b"fs:list", b"fs:read", b"/mnt/uploads"):
            if marqueur not in noeuds:
                err(f"{apk.name} : marqueur {marqueur!r} absent du noeud principal — "
                    f"pont de fichiers P120/P123 perdu")
        # P158 — la recompilation frontend depuis les sources Svelte (v2) a
        # fait disparaitre l'option du dropdown (P10 ne patchait que les chunks
        # JS précompilés). Le composant WebSearch est compilé dans un chunk
        # (chunks/SettingsModal.js), pas dans un noeud de route : la recherche
        # porte donc sur TOUS les .js de _app/immutable (faux positif du run
        # 45914805564, qui ne lisait que nodes/). Le marqueur prouve que la
        # source patchée a bien été recompilée dans l'APK livrée.
        js_immuable = b"".join(
            lire(z, n) or b"" for n in noms
            if n.startswith("assets/frontend/_app/immutable/") and n.endswith(".js")
        )
        if b"embedded-searxng" not in js_immuable:
            err(f"{apk.name} : embedded-searxng absent du frontend compilé — "
                f"moteur de recherche web indisponible dans le menu")

        # P160 — mini-Debian embarqué (proot + bibliothèques bionic + rootfs).
        # Le rootfs est extrait par MainActivity vers filesDir/minidebian ;
        # son absence rend le « Shell root » inopérant sans message d'erreur.
        for requis in ("assets/minidebian/proot",
                       "assets/minidebian/rootfs.tar.xz",
                       "assets/minidebian/manifest.json",
                       "assets/minidebian/libtalloc.so.2",
                       "assets/minidebian/libandroid-shmem.so"):
            if requis not in noms:
                err(f"{apk.name} : absent — {requis} (mini-Debian P160)")
        racine = lire(z, "assets/minidebian/rootfs.tar.xz") or b""
        if racine and len(racine) > 100_000_000:
            err(f"{apk.name} : rootfs trop volumineux ({len(racine)} octets)")

    # 4/5. natifs de lib/

        with tempfile.TemporaryDirectory() as tmp:
            so_lib = []
            for n in noms:
                if n.startswith("lib/") and n.endswith(".so"):
                    p = pathlib.Path(tmp) / n.split("/")[-1]
                    p.write_bytes(z.read(n))
                    so_lib.append(p)
            check_bionic(so_lib)

        # 1/2/3/4. bundles Python
        for bundle_nom in ("assets/chaquopy/app.imy",
                           "assets/chaquopy/requirements-common.imy",
                           "assets/chaquopy/requirements-arm64-v8a.imy"):
            donnees = lire(z, bundle_nom)
            if donnees is None:
                err(f"{apk.name} : bundle absent — {bundle_nom}")
                continue
            with tempfile.TemporaryDirectory() as tmp:
                bpath = pathlib.Path(tmp) / "b.zip"
                bpath.write_bytes(donnees)
                with zipfile.ZipFile(bpath) as bundle:
                    label = pathlib.Path(bundle_nom).name
                    if "app.imy" in bundle_nom:
                        noms_b = bundle.namelist()
                        # P160/P162 — Open Terminal, proot-distro et xterm.js
                        # sont copiés dans src/ puis embarqués dans app.imy.
                        for module in ("open_terminal/main.pyc",
                                       "proot_distro/helpers/rootfs.pyc"):
                            if not any(n.endswith(module) for n in noms_b):
                                err(f"{label} : {module} absent (service P160)")
                        # P166 — Android peut n'exposer aucun périphérique PTY
                        # utilisable (`Out of PTY devices` dès l'ouverture). Le
                        # repli shell sans PTY et sa journalisation doivent être
                        # réellement compilés dans l'APK, pas seulement présents
                        # dans les patchs du dépôt.
                        ot_pyc = [bundle.read(n) for n in noms_b
                                  if n.endswith("open_terminal/main.pyc")]
                        if ot_pyc and not any(b"P166" in o for o in ot_pyc):
                            err(f"{label} : marqueur P166 absent de "
                                f"open_terminal/main.pyc (repli sans PTY non embarqué)")
                        # P167 — Android/data est monté en noexec : sans le
                        # volume exécutable interne, proot échoue avec Errno 13
                        # dès l'ouverture du Shell root. Les trois marqueurs
                        # (Java, Python, service) doivent être compilés dans
                        # l'APK, pas seulement présents dans le dépôt.
                        if ot_pyc and not any(b"P167" in o for o in ot_pyc):
                            err(f"{label} : marqueur P167 absent de "
                                f"open_terminal/main.pyc (diagnostic proot non embarqué)")
                        am_pyc = [bundle.read(n) for n in noms_b
                                  if n.endswith("android_main.pyc")]
                        if am_pyc and not any(
                                b"OPEN_TERMINAL_MAX_SESSIONS" in o for o in am_pyc):
                            err(f"{label} : limite d'une session absente de "
                                f"android_main.pyc (accumulation des PTY possible)")
                        if am_pyc and not any(
                                b"OPENWEBUI_ANDROID_EXEC_HOME" in o for o in am_pyc):
                            err(f"{label} : volume exécutable interne absent de "
                                f"android_main.pyc (proot resterait sous noexec)")
                        for xterm in ("xterm.js", "xterm.css", "addon-fit.js",
                                      "addon-web-links.js"):
                            if not any(n.endswith("static/xterm/" + xterm)
                                       for n in noms_b):
                                err(f"{label} : static/xterm/{xterm} absent "
                                    f"(Shell root P162)")
                        for requis in ("searx/settings.yml", "searx/version_frozen.py"):
                            if requis not in noms_b:
                                err(f"{label} : absent — {requis} (piège git SearXNG)")
                        check_modules(bundle, label, MODULES_APP)
                        # P152 : le changelog sert à l'UI (pkgutil.get_data).
                        # Vérifier la version amont réellement embarquée évite de
                        # livrer une APK v0.13.4 sous une étiquette v0.13.5.
                        changelog = bundle.read("open_webui/CHANGELOG.md") \
                            if "open_webui/CHANGELOG.md" in noms_b else b""
                        if VERSION_AMONT not in changelog:
                            err(f"{label} : changelog embarqué sans {VERSION_AMONT.decode()} "
                                f"(montée amont P152 perdue)")
                        # route /fm : chercher dans les .pyc (le zip est compressé)
                        if not any(b"fm_browser" in bundle.read(n)
                                   for n in noms_b if n.endswith(".pyc")):
                            err(f"{label} : route /fm (fm_browser) absente du code embarqué")
                        # P124/P125 : le correctif doit être présent dans le
                        # .pyc embarqué, pas seulement dans les sources du dépôt.
                        outils = [bundle.read(n) for n in noms_b
                                  if n.endswith("android_tools.pyc")]
                        if not outils:
                            err(f"{label} : android_tools.pyc absent")
                        else:
                            for marqueur in (b"P124/P125 fichiers enregistres",
                                             b"P126 echec enregistrement", b"pyyaml"):
                                if not any(marqueur in o for o in outils):
                                    err(f"{label} : marqueur {marqueur!r} absent de "
                                        f"android_tools.pyc (P124/P126 perdu)")
                        # P151 : le garde-fou OCR PDF doit accompagner le .pyc embarque.
                        pdfs = [bundle.read(n) for n in noms_b if n.endswith("pdf.pyc")]
                        if not pdfs:
                            err(f"{label} : retrieval/loaders/pdf.pyc absent")
                        elif not any(b"P151 OCR PDF ignore" in o for o in pdfs):
                            err(f"{label} : marqueur P151 absent de pdf.pyc "
                                f"(garde-fou OCR PDF perdu)")
                        # P153 : v0.13.5 créait RUN_DIR dans /tmp en dur
                        # (PermissionError au démarrage sur Android). Le
                        # marqueur du docstring doit être dans le .pyc livré.
                        managed = [bundle.read(n) for n in noms_b
                                   if n.endswith("machines/managed.pyc")]
                        if not managed:
                            err(f"{label} : machines/managed.pyc absent")
                        elif not any(b"P153 : RUN_DIR suit TMPDIR" in o for o in managed):
                            err(f"{label} : marqueur P153 absent de managed.pyc "
                                f"(chemin /tmp en dur restauré)")
                        # R165 : les patchs de compatibilité 31/36/38 et le
                        # hunk de 20 ont été retirés : exiger l'absence du
                        # helper de repli P154 dans aws.pyc. Les dist-info des
                        # versions reconstruites sont, elles, dans le bundle
                        # requirements-common.imy (contrôle plus bas).
                        aws = [bundle.read(n) for n in noms_b
                               if n.endswith("utils/aws.pyc")]
                        if not aws:
                            err(f"{label} : utils/aws.pyc absent")
                        elif any(b"client_session_kwargs" in o for o in aws):
                            err(f"{label} : helper P154 encore embarqué "
                                f"(patch 38 non retiré)")
                        # P155 — demande utilisateur : /fm → SearXNG doit
                        # proposer « Service » et « Moteur de recherche ».
                        # Le marqueur du docstring prouve que le patch
                        # android_fm.py n'a pas été écrasé à la reconstruction.
                        fm = [bundle.read(n) for n in noms_b
                              if n.endswith("android_fm.pyc")]
                        if not fm:
                            err(f"{label} : android_fm.pyc absent")
                        elif not any(b"P155 : /fm SearXNG expose deux sous-onglets" in o for o in fm):
                            err(f"{label} : marqueur P155 absent de android_fm.pyc "
                                f"(sous-onglets SearXNG perdus)")
                        elif not any(b"P159 : premier niveau" in o for o in fm):
                            err(f"{label} : marqueur P159 absent de android_fm.pyc "
                                f"(barre d'onglets redondante revenue)")
                        elif any(b'<div class="tabs">' in o for o in fm):
                            err(f"{label} : barre d'onglets de premier niveau "
                                f"présente dans android_fm.pyc")
                        elif any(b'@@ONGLETS@@' in o for o in fm):
                            err(f"{label} : placeholder @@ONGLETS@@ résiduel — "
                                f"NameError sur la page Open WebUI (R161)")
                        elif any(b'Tester la recherche' in o for o in fm):
                            err(f"{label} : bouton « Tester la recherche » "
                                f"toujours embarqué (R162)")
                        elif not any(b"R163 : surlignement" in o for o in fm):
                            err(f"{label} : marqueur R163 absent de android_fm.pyc "
                                f"(surlignement Paramètres non corrigé)")
                        # P160 : la trace P101 portait encore 0.0.80_beta et
                        # faisait échouer le run 45916306148. Corrigé à la
                        # source, le contrôle reste strict : nouvelle constante
                        # présente ET ancienne absente — aucun garde-fou n'est
                        # affaibli. R166 : passage à 0.0.82_ot_beta.
                        elif not any(b"0.0.82_ot_beta" in o for o in fm) or any(
                                b"0.0.81" in o for o in fm):
                            err(f"{label} : version du pied de page /fm non à jour "
                                f"(attendu 0.0.82_ot_beta, sans 0.0.81)")
                        # P164 — régressions vues sur appareil : ';' avant
                        # .catch (SyntaxError « Unexpected token . » qui cassait
                        # tout le panneau), addons xterm 6 exposés sous forme
                        # d'espace de noms UMD (FitAddon.FitAddon), et boutons
                        # de pilotage restés dans le Shell root. Le Shell root
                        # est désormais une iframe autonome, comme SearXNG.
                        elif not any(b"P164 : Shell root isol" in o for o in fm):
                            err(f"{label} : marqueur P164 absent de android_fm.pyc "
                                f"(correctif iframe/UMD non embarqué)")
                        elif not any(b'src="/fm/ot/terminal"' in o for o in fm):
                            err(f"{label} : iframe /fm/ot/terminal absente — "
                                f"Shell root revenues dans la page /fm")
                        elif not any(b'ctor(window.FitAddon,"FitAddon")' in o
                                     for o in fm):
                            err(f"{label} : résolution UMD de FitAddon absente "
                                f"(TypeError « FitAddon is not a constructor »)")
                        elif not any(b'fitAddon.fit();' in o for o in fm):
                            err(f"{label} : FitAddon.fit() absent — "
                                f"Terminal.fit() n'existe pas, le PTY n'est pas dimensionné")
                        elif any(b'new FitAddon()' in o for o in fm) or any(
                                b'new WebLinksAddon()' in o for o in fm):
                            err(f"{label} : constructeur xterm global utilisé "
                                f"à tort (addons UMD 6)")
                        elif any(b'};.catch' in o for o in fm) or any(
                                b'});.catch' in o for o in fm):
                            err(f"{label} : relais de reset rompu avant .catch "
                                f"(SyntaxError sur /fm)")
                        # P165 — ouverture du shell à la demande : sans ce
                        # démarrage, l'iframe reste sur « service arrêté »
                        # quand le service local n'a pas été lancé au boot.
                        # (`service_control` est présent mais ses arguments
                        # sont marshalisés séparément dans le .pyc : on exige
                        # le marqueur de version P165, lui bien contigu.)
                        elif not any(b"P165" in o for o in fm):
                            err(f"{label} : marqueur P165 absent de android_fm.pyc "
                                f"(démarrage du shell à la demande non embarqué)")
                        # P166 — réutilisation du shell existant et sondage
                        # journalisé : sans ces marqueurs, chaque chargement de
                        # l'iframe ouvre un PTY supplémentaire et l'appareil
                        # renvoie « Out of PTY devices » dès le démarrage.
                        elif not any(b"P166" in o for o in fm):
                            err(f"{label} : marqueur P166 absent de android_fm.pyc "
                                f"(réutilisation du shell non embarquée)")
                        # P167 — une erreur applicative (Errno 13, PTY épuisé)
                        # ne doit pas déclencher 20 relances du service.
                        elif not any(b"P167" in o for o in fm):
                            err(f"{label} : marqueur P167 absent de android_fm.pyc "
                                f"(diagnostic immédiat non embarqué)")
                    elif "requirements-common" in bundle_nom:
                        check_modules(bundle, label, MODULES_PIP)
                        # R165 : aiohttp 3.14.5 remplace le 3.10.10 épinglé par
                        # l'index Chaquopy. Les dist-info ne sont PAS dans
                        # app.imy mais dans requirements-common.imy (piège du
                        # run #46077668862 : 12 faux positifs). Leur présence
                        # prouve que les neuf wheels cross-buildés ont été
                        # installés, et non ceux du dépôt de paquets.
                        dist_infos = {
                            "aiohttp": "3.14.5",
                            "multidict": "7.2.1",
                            "yarl": "1.25.1",
                            "frozenlist": "1.8.0",
                            "propcache": "0.5.4",
                            "aiohappyeyeballs": "2.7.1",
                        }
                        noms_comm = bundle.namelist()
                        for module, version in dist_infos.items():
                            prefixe = f"{module}-{version}.dist-info/"
                            if not any(n.startswith(prefixe) for n in noms_comm):
                                err(f"{label} : {prefixe} absent "
                                    f"(montée aiohttp R165 perdue)")
                    check_noms_so(bundle, label)
                    so_internes = []
                    with tempfile.TemporaryDirectory() as tmp2:
                        for n in bundle.namelist():
                            if n.endswith(".so"):
                                p = pathlib.Path(tmp2) / n.split("/")[-1]
                                p.write_bytes(bundle.read(n))
                                so_internes.append(p)
                        check_bionic(so_internes)




def main() -> int:
    apks = [pathlib.Path(a) for a in sys.argv[1:]]
    if not apks:
        print("usage : check_apk.py <apk>…")
        return 2
    for apk in apks:
        print(f"=== {apk.name} ({apk.stat().st_size / 1e6:.1f} Mo)")
        check_apk(apk)
    for w in avertissements:
        print(f"  AVERTISSEMENT : {w}")
    if erreurs:
        for e in erreurs:
            print(f"  ERREUR : {e}")
        print(f"\nÉCHEC : {len(erreurs)} erreur(s)")
        return 1
    print("\nOK : chaîne APK conforme ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
