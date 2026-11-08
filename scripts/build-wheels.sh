#!/usr/bin/env bash
# build-wheels.sh — cross-build Rust → Android (arm64-v8a) des wheels manquants :
#   pydantic-core (requis par pydantic v2) et jiter (requis par openai).
# Tout est installé DANS le projet (rustup, NDK, python cible) : isolation D5.
#   PYO3_CROSS_LIB_DIR pointe sur le Python Android précompilé (artefact Maven
#   com.chaquo.python:python) — technique documentée par pax0r (chaquo/chaquopy#1017).
set -euo pipefail
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJ"
export TMPDIR="$PROJ/.tmp"
export RUSTUP_HOME="$PROJ/tools/rustup"
export CARGO_HOME="$PROJ/tools/cargo"

PYVER=3.13.8                       # artefact Maven com.chaquo.python:python
NDK="$PROJ/tools/android-ndk"
NDK_CC="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin"
API=24
TARGET=aarch64-linux-android

mkdir -p downloads wheels tools

# 1. Python Android précompilé (pour PyO3) — le tarball extrait directement prefix/
PYO3_ROOT="$PROJ/tools/pyo3/prefix"
if [ ! -d "$PYO3_ROOT/include/python3.13" ]; then
  echo "[wheels] téléchargement du Python Android $PYVER…"
  mkdir -p "$PROJ/tools/pyo3"
  curl -sL -o "$PROJ/downloads/python-$PYVER-$TARGET.tar.gz" \
    "https://repo1.maven.org/maven2/com/chaquo/python/python/$PYVER/python-$PYVER-$TARGET.tar.gz"
  tar -xzf "$PROJ/downloads/python-$PYVER-$TARGET.tar.gz" -C "$PROJ/tools/pyo3"
  [ -d "$PYO3_ROOT/include/python3.13" ] || { echo "ERREUR: layout inattendu du tarball"; find "$PROJ/tools/pyo3" -maxdepth 3 | head; exit 1; }
fi
echo "[wheels] PYO3_CROSS_LIB_DIR=$PYO3_ROOT"

# 2. NDK Android
if [ ! -d "$NDK" ]; then
  echo "[wheels] installation du NDK…"
  [ -f "$PROJ/downloads/ndk.zip" ] || { echo "ERREUR: downloads/ndk.zip absent"; exit 1; }
  unzip -q "$PROJ/downloads/ndk.zip" -d "$PROJ/tools"
  mv "$PROJ/tools/android-ndk-r27c" "$NDK"
fi

# 3. Rust (dans le projet) — --no-modify-path : rustup-init ne doit JAMAIS
# toucher ~/.profile / ~/.bashrc (règle d'isolation D5)
if [ ! -x "$CARGO_HOME/bin/cargo" ]; then
  echo "[wheels] installation de Rust…"
  curl -sL https://sh.rustup.rs | sh -s -- -y --profile minimal \
    --no-modify-path \
    --default-toolchain stable --target $TARGET
fi
export PATH="$CARGO_HOME/bin:$PATH"

# 4. maturin + sdists
"$PROJ/.venv313/bin/pip" install --quiet maturin 2>&1 | tail -1
for spec in "pydantic_core==2.46.4" "jiter==0.10.0" "uuid-utils==0.12.0" "orjson==3.11.9" "rpds-py" "primp==1.2.3"; do
  name="${spec%%==*}"; name="${name//-/_}"
  # sdist déjà présent : pas de re-téléchargement (primp vient via curl direct)
  ls "$PROJ/downloads/sdists/${name}"-*.tar.gz >/dev/null 2>&1 && continue
  "$PROJ/.venv313/bin/pip" download --quiet --no-deps --no-binary :all: \
    --no-cache-dir -d "$PROJ/downloads/sdists" "$spec"
done

# 5. Environnement de cross-compilation
# NB : le NDK officiel ne fournit que des binaires x86_64 ; on utilise les
# wrappers tools/ndk-cc/ (clang hôte aarch64 + sysroot du NDK) — cf. journal D8.
export ANDROID_NDK_HOME="$NDK"
export PYO3_CROSS_PYTHON_VERSION=3.13
export PYO3_CROSS_LIB_DIR="$PYO3_ROOT"
export CARGO_BUILD_TARGET=$TARGET
WRAP="$PROJ/tools/ndk-cc"
export CC_${TARGET//-/_}="$WRAP/aarch64-linux-android24-clang"
export CXX_${TARGET//-/_}="$WRAP/aarch64-linux-android24-clang++"
export AR_${TARGET//-/_}="/data/data/com.termux/files/usr/bin/llvm-ar"
export CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER="$WRAP/aarch64-linux-android24-clang"
export CARGO_TARGET_AARCH64_LINUX_ANDROID_AR="/data/data/com.termux/files/usr/bin/llvm-ar"
# libpython3.13 (prefix PyO3) + libunwind.a (copié dans tools/ndk-cc/lib, le NDK
# officiel ne l'expédie pas pour ce target)
export RUSTFLAGS="-L native=$PYO3_ROOT/lib -L native=$WRAP/lib"
# Les wheels ABI3 (uuid_utils, typst) ne lient PAS libpython : PyO3 considère que
# les symboles Py* seront résolus à l'exécution — vrai sur desktop, FAUX sur
# Android (dlopen échoue). On force la liaison via le config PyO3 officiel :
# suppress_build_script_link_lines=false → pyo3 émet -lpython3.13 au link.
mkdir -p "$PROJ/tools/pyo3"
PYO3_CONF="$PROJ/tools/pyo3/pyo3-config.txt"
cat > "$PYO3_CONF" <<EOF
implementation=CPython
version=3.13
shared=true
abi3=true
lib_name=python3.13
lib_dir=$PYO3_ROOT/lib
executable=
pointer_width=64
build_flags=
suppress_build_script_link_lines=false
EOF
export PYO3_CONFIG_FILE="$PYO3_CONF"
export CARGO_TARGET_AARCH64_LINUX_ANDROID_RUSTFLAGS="\
$RUSTFLAGS -C link-args=-L$PYO3_ROOT/lib -C link-args=-lpython3.13"

# 6. Build des wheels
build_one() {
  local src_tar name dir
  # sauter si le wheel existe déjà
  if ls "$PROJ/wheels/${1//-/_}"-*.whl >/dev/null 2>&1; then
    echo "[wheels] $1 déjà construit — sauté"
    return 0
  fi
  src_tar=$(ls "$PROJ/downloads/sdists"/$1-*.tar.gz | head -1)
  name=$(basename "$src_tar" .tar.gz)
  dir="$PROJ/.tmp/build-$name"
  rm -rf "$dir"; mkdir -p "$dir"
  tar -xzf "$src_tar" -C "$dir"
  echo "[wheels] build de $name…"
  (cd "$dir/$name" && "$PROJ/.venv313/bin/python" -m maturin build --release \
     --target $TARGET --out "$PROJ/wheels")
}

build_one 'pydantic_core'
build_one 'jiter'
build_one 'uuid_utils'
build_one 'orjson'
build_one 'rpds_py'
build_one 'typst'
build_one 'pycrdt'
# maturin nomme le .so « aarch64-android-android » — l'import Android attend
# le SOABI « aarch64-linux-android » (cf. le renommage msgspec)
"$PROJ/.venv313/bin/python" "$PROJ/scripts/fix-pycrdt-suffix.py" "$PROJ/wheels"

# msgspec : extension C (setuptools, pas maturin) — build via clang wrapper
build_msgspec() {
  if ls "$PROJ/wheels"/msgspec-*.whl >/dev/null 2>&1; then
    echo "[wheels] msgspec déjà construit — sauté"
    return 0
  fi
  local src_tar name dir
  src_tar=$(ls "$PROJ/downloads/sdists"/msgspec-*.tar.gz | head -1)
  name=$(basename "$src_tar" .tar.gz)
  dir="$PROJ/.tmp/build-$name"
  rm -rf "$dir"; mkdir -p "$dir"
  tar -xzf "$src_tar" -C "$dir"
  echo "[wheels] build de $name (extension C setuptools)…"
  (cd "$dir/$name" && \
    CC="$WRAP/aarch64-linux-android24-clang" \
    CXX="$WRAP/aarch64-linux-android24-clang++" \
    LDSHARED="$WRAP/aarch64-linux-android24-clang -shared" \
    LDFLAGS="-L$PYO3_ROOT/lib -lpython3.13 -L$WRAP/lib" \
    CFLAGS="-fPIC" \
    "$PROJ/.venv313/bin/python" setup.py -q build_ext \
      --include-dirs="$PYO3_ROOT/include/python3.13" && \
    # suffixe d'import Android : -gnu.so → -android.so (sinon le module n'est pas trouvé)
    find build/lib.* -name '*-gnu.so' -exec bash -c 'mv "$1" "${1%-gnu.so}-android.so"' _ {} \; && \
    "$PROJ/.venv313/bin/python" setup.py -q bdist_wheel --dist-dir "$PROJ/wheels")
  # setuptools_scm sans git produit une version 0.0.0 : on la corrige
  local ver="${name#msgspec-}"
  for w in "$PROJ/wheels"/msgspec-0.0.0-*.whl; do
    [ -e "$w" ] || continue
    "$PROJ/.venv313/bin/python" "$PROJ/scripts/fix-wheel-version.py" "$w" "$ver"
  done
}
build_msgspec

# 7. Normalisation des tags de wheel (maturin → format attendu par Chaquopy)
"$PROJ/.venv313/bin/python" - <<'EOF'
import pathlib, re, zipfile, shutil, tempfile

wheels = pathlib.Path("wheels")
for whl in wheels.glob("*.whl"):
    name = whl.name
    if "android_24_arm64_v8a" in name:
        continue
    new_name = re.sub(r"android_\d+_(aarch64|arm64_v8a)", "android_24_arm64_v8a", name)
    new_name = re.sub(r"-linux_(aarch64|arm64)", "-android_24_arm64_v8a", new_name)
    if new_name == name:
        print(f"[wheels] tag conservé : {name}")
        continue
    tmp = whl.with_suffix(".whl.tmp")
    with zipfile.ZipFile(whl) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.endswith("WHEEL"):
                text = data.decode()
                text = re.sub(r"(Tag: .*)android_\d+_(aarch64|arm64_v8a)", r"\1android_24_arm64_v8a", text)
                text = re.sub(r"(Tag: .*)-linux_(aarch64|arm64)", r"\1-android_24_arm64_v8a", text)
                data = text.encode()
            zout.writestr(item, data)
    shutil.move(tmp, wheels / new_name)
    whl.unlink()
    print(f"[wheels] {name} → {new_name}")
EOF

echo "[wheels] terminé :"
ls -la "$PROJ/wheels"
