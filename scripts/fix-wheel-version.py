#!/usr/bin/env python3
"""fix-wheel-version.py — corrige la version d'un wheel (setuptools_scm sans git).

Usage : fix-wheel-version.py <wheel> <version>
Réécrit le wheel : nom, dist-info/, METADATA (Version) et RECORD.
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


def fix(whl: Path, version: str) -> Path:
    m = re.match(r"([A-Za-z0-9_.]+)-([0-9][^-\s]*)", whl.name)
    if not m:
        raise SystemExit(f"nom de wheel inexploitable : {whl.name}")
    name, old = m.group(1), m.group(2)
    if old == version:
        print(f"[fix-wheel] {whl.name} déjà en {version}")
        return whl
    new_name = whl.name.replace(f"{name}-{old}-", f"{name}-{version}-", 1)
    out = whl.with_name(new_name)
    with zipfile.ZipFile(whl) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            fname = item.filename.replace(f"{name}-{old}.dist-info", f"{name}-{version}.dist-info")
            if fname.endswith("METADATA"):
                data = re.sub(rb"^Version: .*$", f"Version: {version}".encode(), data, count=1, flags=re.M)
            elif fname.endswith("RECORD"):
                text = data.decode().replace(f"{name}-{old}", f"{name}-{version}")
                data = text.encode()
            zout.writestr(fname, data)
    whl.unlink()
    print(f"[fix-wheel] {whl.name} → {new_name}")
    return out


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    fix(Path(sys.argv[1]), sys.argv[2])
