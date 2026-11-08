#!/usr/bin/env python3
"""fix-pycrdt-suffix.py — renomme le .so de pycrdt vers le SOABI Android attendu.

maturin produit `_pycrdt.cpython-313-aarch64-android-android.so` ; l'import
Python sur Android cherche `cpython-313-aarch64-linux-android.so` (SOABI de
Chaquopy) — sans renommage, « No module named 'pycrdt._pycrdt' » au démarrage.
Le wheel est rezipé et le RECORD mis à jour (hash inchangés : contenu identique).
"""
import csv
import io
import pathlib
import re
import sys
import zipfile

WANT = "_pycrdt.cpython-313-aarch64-linux-android.so"
BAD_RE = re.compile(r"_pycrdt\.cpython-313-[A-Za-z0-9_-]+\.so$")


def fix_wheel(whl: pathlib.Path) -> bool:
    with zipfile.ZipFile(whl) as z:
        names = z.namelist()
        bad = [n for n in names if BAD_RE.search(n.split("/")[-1]) and not n.endswith(WANT)]
        if not bad:
            return False
        old = bad[0]
        new = old[: -len(old.split("/")[-1])] + WANT
        print(f"[fix-pycrdt] {whl.name} : {old.split('/')[-1]} → {WANT}")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
            for item in z.infolist():
                data = z.read(item.filename)
                if item.filename == old:
                    info = zipfile.ZipInfo(new, date_time=item.date_time)
                    info.external_attr = item.external_attr
                    out.writestr(info, data)
                elif item.filename.endswith("RECORD"):
                    text = data.decode("utf-8").replace(old, new)
                    out.writestr(item, text)
                else:
                    out.writestr(item, data)
    whl.write_bytes(buf.getvalue())
    return True


if __name__ == "__main__":
    fixed = False
    for p in pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "wheels").glob("pycrdt-*.whl"):
        fixed = fix_wheel(p) or fixed
    print("[fix-pycrdt] OK" if fixed else "[fix-pycrdt] rien à corriger")
