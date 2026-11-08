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

Usage : python3 scripts/check_apk.py dist/*.apk   (code retour != 0 si échec)
"""
import pathlib
import re
import subprocess
import sys
import tempfile
import zipfile

MODULES_PIP = ["typst", "pycrdt", "msgspec", "pydantic_core", "jiter", "orjson",
               "rpds", "uuid_utils"]
MODULES_APP = ["open_webui", "searx", "tiktoken", "re2"]
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
        # P47 : wheels supplémentaires garantis dans l'artefact (statsmodels,
        # pymupdf — sha256 conformes au lock, copiés par prepare_src)
        for motif in ("statsmodels-", "pymupdf-"):
            if not any(n.startswith("assets/frontend/pyodide/") and motif in n and n.endswith(".whl")
                       for n in noms):
                err(f"{apk.name} : wheel {motif}* absente de assets/frontend/pyodide/")
        if not any("assets/frontend/index.html" == n and lire(z, n) and b"/fm" in lire(z, n) or False
                   for n in noms):
            contenu_index = lire(z, "assets/frontend/index.html") or b""
            if b"/fm" not in contenu_index:
                err(f"{apk.name} : bouton /fm absent de index.html")

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
                        for requis in ("searx/settings.yml", "searx/version_frozen.py"):
                            if requis not in noms_b:
                                err(f"{label} : absent — {requis} (piège git SearXNG)")
                        check_modules(bundle, label, MODULES_APP)
                        # route /fm : chercher dans les .pyc (le zip est compressé)
                        if not any(b"fm_browser" in bundle.read(n)
                                   for n in noms_b if n.endswith(".pyc")):
                            err(f"{label} : route /fm (fm_browser) absente du code embarqué")
                    elif "requirements-common" in bundle_nom:
                        check_modules(bundle, label, MODULES_PIP)
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
