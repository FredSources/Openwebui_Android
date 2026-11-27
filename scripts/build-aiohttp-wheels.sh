#!/usr/bin/env bash
# build-aiohttp-wheels.sh — cross-build C/Cython → Android (arm64-v8a) de
# aiohttp 3.14.5 (version exigée par requirements-slim.txt du submodule v0.13.5)
# et de ses cinq dépendances natives. Méthode validée le 2026-11-27 (R165) et
# détaillée dans docs/aiohttp-android.typ.
# Tout reste DANS le projet (isolation D5) : sdists et venv dans .tmp/aiohttp/,
# wheels signés/taggés dans wheels/. Le script est idempotent : si les neuf
# wheels attendus sont présents, il ne recompile rien.
set -euo pipefail
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJ"
export TMPDIR="$PROJ/.tmp"
PYHOST="$PROJ/.venv313/bin/python"
WRAP="$PROJ/tools/ndk-cc"
PYO3="$PROJ/tools/pyo3/prefix"
BUILD="$PROJ/.tmp/aiohttp"
WHEELS="$PROJ/wheels"
STAGE="$BUILD/out"

NATIFS=(
  aiohttp-3.14.5
  multidict-7.2.1
  yarl-1.25.1
  frozenlist-1.8.0
  propcache-0.5.4
)
PIURS=(
  aiohappyeyeballs==2.7.1
  aiosignal==1.4.0
  attrs==26.1.0
  idna==3.20
)
SDISTS=(
  aiohttp==3.14.5
  multidict==7.2.1
  yarl==1.25.1
  frozenlist==1.8.0
  propcache==0.5.4
)

# 0. Idempotence : ne rien reconstruire si la cible est déjà là.
manquant=0
for n in "${NATIFS[@]}"; do
  [ -e "$WHEELS/$n-cp313-cp313-android_24_arm64_v8a.whl" ] || manquant=1
done
for spec in "${PIURS[@]}"; do
  [ -e "$WHEELS/${spec/==/-}-py3-none-any.whl" ] || manquant=1
done
if [ "$manquant" -eq 0 ]; then
  echo "[aiohttp] 9 wheels déjà présents dans wheels/ — rien à reconstruire"
  exit 0
fi

[ -x "$PYHOST" ] || { echo "ERREUR : buildPython $PYHOST absent"; exit 1; }
[ -d "$PYO3/include/python3.13" ] || { echo "ERREUR : prefix PyO3 absent (lancer scripts/build-wheels.sh)"; exit 1; }
[ -x "$WRAP/aarch64-linux-android24-clang" ] || { echo "ERREUR : wrapper NDK absent"; exit 1; }
mkdir -p "$BUILD/sdists" "$BUILD/src" "$BUILD/logs" "$STAGE" "$WHEELS" "$PROJ/.tmp"

# 1. Venv de build isolée, dans le projet. Deux versions de Cython sont
#    nécessaires : 3.1.4 pour frozenlist, 3.3.0 pour yarl et propcache
#    (contraintes requirements/cython.txt des sdists). aiohttp et multidict
#    embarquent leurs sources C pré-générées : pas de Cython pour eux.
VENV="$BUILD/venv"
[ -d "$VENV" ] || "$PYHOST" -m venv "$VENV"
"$VENV/bin/pip" install --quiet --no-cache-dir --upgrade pip setuptools wheel expandvars
cython() { "$VENV/bin/pip" install --quiet --no-cache-dir --force-reinstall "Cython==$1"; }

# 2. Téléchargement des sdists (jamais de binaire : on veut les sources C/pxd).
for spec in "${SDISTS[@]}"; do
  name="${spec%%==*}"
  if ! compgen -G "$BUILD/sdists/$name-*.tar.gz" >/dev/null; then
    echo "[aiohttp] sdist $spec…"
    "$VENV/bin/pip" download --quiet --no-deps --no-binary :all: --no-cache-dir \
      -d "$BUILD/sdists" "$spec"
  fi
  dir="$BUILD/src/$name"
  if [ ! -d "$dir" ]; then
    archive=$(ls "$BUILD/sdists/$name-"*.tar.gz | head -1)
    tar -xzf "$archive" -C "$BUILD/src"
  fi
done

# 3. Environnement de cross-compilation (clang hôte aarch64 + sysroot NDK API 24,
#    en-têtes et libpython3.13.so du prefix Chaquopy) — cf. journal D8.
export CC="$WRAP/aarch64-linux-android24-clang"
export CXX="$WRAP/aarch64-linux-android24-clang++"
export LDSHARED="$WRAP/aarch64-linux-android24-clang -shared"
export LDFLAGS="-L$PYO3/lib -lpython3.13 -L$WRAP/lib"
export CFLAGS="-fPIC -I$PYO3/include/python3.13"
export CPPFLAGS="-I$PYO3/include/python3.13"

build_native() {
  local name="$1" pkg="${1%-*}" src="$BUILD/src/${1%-*}"
  echo "[aiohttp] wheel $name…"
  "$VENV/bin/pip" wheel --quiet --no-deps --no-build-isolation \
    --wheel-dir "$STAGE" "$src" >"$BUILD/logs/$name.log" 2>&1 || {
      tail -30 "$BUILD/logs/$name.log"; return 1;
    }
}

cython 3.1.4
build_native frozenlist-1.8.0
cython 3.3.0
for n in aiohttp-3.14.5 multidict-7.2.1 yarl-1.25.1 propcache-0.5.4; do
  build_native "$n"
done

# 4. Normalisation des tags, des suffixes .so ET du RECORD pour Chaquopy.
#    setuptools produit `cpython-313-aarch64-linux-gnu.so` et
#    `cp313-cp313-linux_aarch64`. Renommer les .so sans régénérer le RECORD
#    fait ajouter par pip une ligne vide pour le nouveau nom : Chaquopy
#    échoue alors sur `int(size_str)` (CI #46076329015). Le script dédié
#    recalcule les empreintes et les tailles de chaque entrée du zip.
"$PYHOST" "$PROJ/scripts/normalize-aiohttp-wheel.py" "$STAGE" "$WHEELS"

# 5. Dépendances pures Python (mêmes versions que la résolution amont).
for spec in "${PIURS[@]}"; do
  pkg="${spec%%==*}"
  if [ ! -e "$WHEELS/${spec/==/-}-py3-none-any.whl" ]; then
    echo "[aiohttp] wheel pur $spec…"
    "$VENV/bin/pip" download --quiet --no-deps --only-binary :all: --no-cache-dir \
      -d "$WHEELS" "$spec"
  fi
done

# 6. Vérification : résolution hors ligne pour la cible Android, architecture
#    AArch64 des .so, absence de glibc (bionic uniquement).
echo "[aiohttp] vérification de la résolution hors ligne…"
"$VENV/bin/pip" install --dry-run --ignore-installed --only-binary :all: --no-index \
  --find-links "$WHEELS" --platform android_24_arm64_v8a --python-version 3.13 \
  --implementation cp --abi cp313 --target "$BUILD/resolve" aiohttp==3.14.5 \
  >"$BUILD/logs/resolve.log" 2>&1 || { tail -20 "$BUILD/logs/resolve.log"; exit 1; }
"$PYHOST" - "$WHEELS" <<'PY'
import pathlib, subprocess, sys, tempfile, zipfile
wheels = pathlib.Path(sys.argv[1])
for whl in sorted(wheels.glob("*.whl")):
    with zipfile.ZipFile(whl) as z:
        sos = [n for n in z.namelist() if n.endswith(".so")]
    if not sos:
        continue
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "x.so"
        p.write_bytes(zipfile.ZipFile(whl).read(sos[0]))
        elf = subprocess.run(["readelf", "-h", str(p)], capture_output=True, text=True).stdout
        dyn = subprocess.run(["readelf", "-d", str(p)], capture_output=True, text=True).stdout
        sym = subprocess.run(["strings", str(p)], capture_output=True, text=True).stdout
    assert "AArch64" in elf, f"{whl.name} : architecture non AArch64"
    assert "libpython3.13.so" in dyn, f"{whl.name} : libpython non liée"
    assert "GLIBC" not in sym, f"{whl.name} : dépendance glibc"
    print(f"[aiohttp] OK {whl.name} ({len(sos)} .so, AArch64, bionic)")
PY
echo "[aiohttp] terminé — $(ls "$WHEELS"/*.whl | wc -l) wheels au total"
