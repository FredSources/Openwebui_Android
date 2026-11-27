#!/usr/bin/env python3
"""Normalise les wheels cross-buildés pour Chaquopy et régénère leur RECORD.

setuptools produit `Tag: cp313-cp313-linux_aarch64` et des fichiers
`cpython-313-aarch64-linux-gnu.so`. Chaquopy attend le tag Android et, surtout,
un `RECORD` dont les chemins et les tailles correspondent *exactement* aux
fichiers du zip : un RECORD périmé fait échouer `installRequirements` avec
`ValueError: invalid literal for int() with base 10: ''` (run CI #46076329015).

Usage :
  scripts/normalize-aiohttp-wheel.py SOURCE_DIR DEST_DIR   # lot de build
  scripts/normalize-aiohttp-wheel.py --in-place wheels     # correction sur place
"""
import base64
import hashlib
import pathlib
import shutil
import sys
import zipfile


def normaliser_nom(nom: str) -> str:
    return nom.replace(
        "cpython-313-aarch64-linux-gnu.so", "cpython-313-aarch64-linux-android.so")


def empreinte(donnees: bytes) -> str:
    h = base64.urlsafe_b64encode(hashlib.sha256(donnees).digest()).rstrip(b"=")
    return "sha256=" + h.decode()


def normaliser(whl: pathlib.Path, dest: pathlib.Path) -> str:
    if "py3-none-any" in whl.name:
        return whl.name
    nouveau_nom = whl.name.replace(
        "-linux_aarch64.whl", "-android_24_arm64_v8a.whl")
    with zipfile.ZipFile(whl) as z:
        entrees = []
        for item in z.infolist():
            donnees = z.read(item.filename)
            nom = normaliser_nom(item.filename)
            if nom.endswith(".dist-info/WHEEL"):
                donnees = donnees.replace(
                    b"cp313-cp313-linux_aarch64",
                    b"cp313-cp313-android_24_arm64_v8a")
            entrees.append((nom, donnees))
    noms = [n for n, _ in entrees]
    record = next(n for n in noms if n.endswith(".dist-info/RECORD"))
    lignes = [f"{n},{empreinte(d)},{len(d)}"
              for n, d in entrees if n != record]
    lignes.append(f"{record},,")
    cible = dest / nouveau_nom
    tmp = cible.with_suffix(".whl.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for nom, donnees in entrees:
            if nom != record:
                z.writestr(nom, donnees)
        z.writestr(record, "\n".join(lignes) + "\n")
    shutil.move(tmp, cible)
    return nouveau_nom


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--in-place":
        dossier = pathlib.Path(sys.argv[2])
        for whl in sorted(dossier.glob("*.whl")):
            if "-android_24_arm64_v8a" not in whl.name:
                continue
            print("[record]", normaliser(whl, dossier))
        return
    if len(sys.argv) != 3:
        raise SystemExit("usage : normalize-aiohttp-wheel.py SOURCE DEST | --in-place DIR")
    source, dest = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    dest.mkdir(parents=True, exist_ok=True)
    for whl in sorted(source.glob("*.whl")):
        nom = normaliser(whl, dest)
        print(f"[wheel] {nom}")
        if source.resolve() != dest.resolve():
            whl.unlink()


if __name__ == "__main__":
    main()
