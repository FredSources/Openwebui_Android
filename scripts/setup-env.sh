#!/usr/bin/env bash
# ============================================================================
# setup-env.sh — Reconstruction complète de l'environnement de build
# ----------------------------------------------------------------------------
# Reproduit TOUT l'environnement à partir du dépôt git seul, dans le projet :
# Python 3.12 portable, venv 3.13, JDK 21, Android SDK, Gradle, NDK, Rust,
# qemu + sysroot amd64, Python Android (PyO3), sources vendor (Open WebUI +
# SearXNG), wheels natifs cross-buildés, sources patchées.
#
# Usage :
#   bash scripts/setup-env.sh            # environnement complet
#   bash scripts/setup-env.sh --build    # …puis build de l'APK
#   bash scripts/setup-env.sh --check    # audit de l'existant sans rien télécharger
#
# Règles : ISOLATION TOTALE (tout reste sous le projet, aucune installation
# globale, aucune écriture dans ~/.profil — rustup --no-modify-path).
# Prérequis machine : Linux aarch64, git, curl, unzip, python3.13, ~20 Go libres.
# Durée indicative : 20-40 min selon le réseau (téléchargements ~3 Go).
# ============================================================================
set -euo pipefail

PROJ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJ"
[ -f "$PROJ/AGENTS.md" ] || { echo "ERREUR : à lancer depuis le dépôt du projet"; exit 1; }

MODE="${1:-}"
VENDOR_COMMIT="a30b2d47492ab46ae82ce25ee62a31626565cf67"   # SearXNG figé (pré-curl_cffi)
PYTHON_MVN="3.13.8"                                          # Python Android (PyO3)
DEBIAN_POOL="https://deb.debian.org/debian/pool"

log()  { printf '\033[1;36m[env]\033[0m %s\n' "$*"; }
need() { command -v "$1" >/dev/null 2>&1 || { echo "ERREUR : '$1' manquant (prérequis machine)"; exit 1; }; }

# --- Ancrage d'isolation (jamais en dehors du projet) ---
export TMPDIR="$PROJ/.tmp"
export XDG_CACHE_HOME="$PROJ/.xdg-cache"
export CARGO_HOME="$PROJ/tools/cargo"
export RUSTUP_HOME="$PROJ/tools/rustup"
export GRADLE_USER_HOME="$PROJ/.gradle-cache"
export ANDROID_HOME="$PROJ/android-sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PIP_CACHE_DIR="$PROJ/.pip-cache"
mkdir -p "$TMPDIR" "$XDG_CACHE_HOME" downloads tools vendor wheels dist docs

if [ "$MODE" = "--check" ]; then
  log "=== Audit de l'environnement ==="
  for probe in \
    "tools/python312/bin/python3.12:Python 3.12 portable" \
    ".venv313/bin/python:venv Python 3.13" \
    "tools/jdk/bin/javac:JDK 21" \
    "android-sdk/platforms/android-34:SDK platform-34" \
    "android-sdk/build-tools/34.0.0/aapt2:build-tools 34" \
    "tools/gradle/gradle-8.10.2/bin/gradle:Gradle 8.10.2" \
    "tools/android-ndk/toolchains/llvm/prebuilt/linux-x86_64/sysroot:NDK (sysroot)" \
    "tools/cargo/bin/cargo:Rust (projet)" \
    "tools/qemu/qemu-x86_64-static:qemu x86_64" \
    "tools/pyo3/prefix/include/python3.13:Python Android (PyO3)" \
    "wheels/pydantic_core-2.46.4-cp313-cp313-android_24_arm64_v8a.whl:wheel pydantic_core" \
    "vendor/unpacked/open_webui:Open WebUI (pristine)" \
    "vendor/searxng/searx:SearXNG (figé)" \
    "src/open_webui:src/ patché"; do
    path="${probe%%:*}"; label="${probe#*:}"
    if [ -e "$PROJ/$path" ]; then echo "  [OK]      $label"; else echo "  [MANQUE]  $label  ($path)"; fi
  done
  exit 0
fi

need git; need curl; need unzip; need python3
PYV="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
[ "$PYV" = "3.13" ] || log "ATTENTION : python3 = $PYV (3.13 attendu pour le venv)"

# ============================================================================
log "1/10 — Python 3.12 portable (buildPython + récupération du wheel Open WebUI)"
if [ ! -x tools/python312/bin/python3.12 ]; then
  if [ -d /opt/uv-python/cpython-3.12.16-linux-aarch64-gnu ]; then
    mkdir -p tools/python312
    cp -a /opt/uv-python/cpython-3.12.16-linux-aarch64-gnu/. tools/python312/
  else
    log "  téléchargement python-build-standalone 3.12…"
    URL=$(curl -sL https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest \
      | python3 -c "import json,sys; r=json.load(sys.stdin); print(next(a['browser_download_url'] for a in r['assets'] if 'aarch64-unknown-linux-gnu' in a['name'] and 'install_only' in a['name'] and '3.12' in a['name']))")
    curl -sL -o downloads/python312.tar.gz "$URL"
    mkdir -p tools/python312
    tar -xzf downloads/python312.tar.gz -C tools/python312 --strip-components=1
  fi
fi
tools/python312/bin/python3.12 --version

# ============================================================================
log "2/10 — venv Python 3.13 (buildPython Chaquopy) + dépendances"
if [ ! -x .venv313/bin/python ]; then
  python3 -m venv .venv313
fi
.venv313/bin/pip install --quiet --upgrade pip
.venv313/bin/pip install --quiet wheel setuptools maturin
.venv313/bin/pip install --quiet -r requirements-min.txt

# ============================================================================
log "3/10 — JDK 21 portable (Temurin)"
if [ ! -x tools/jdk/bin/javac ]; then
  curl -sL -o downloads/jdk21.tar.gz \
    "https://api.adoptium.net/v3/binary/latest/21/ga/linux/aarch64/jdk/hotspot/normal/eclipse"
  mkdir -p tools/jdk
  tar -xzf downloads/jdk21.tar.gz -C tools/jdk --strip-components=1
fi
export JAVA_HOME="$PROJ/tools/jdk"; export PATH="$JAVA_HOME/bin:$PATH"
javac -version

# ============================================================================
log "4/10 — Android SDK (cmdline-tools, platform-34, build-tools 34)"
if [ ! -x android-sdk/cmdline-tools/latest/bin/sdkmanager ]; then
  [ -f downloads/cmdline-tools.zip ] || curl -sL -o downloads/cmdline-tools.zip \
    "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
  mkdir -p android-sdk/cmdline-tools
  unzip -q downloads/cmdline-tools.zip -d android-sdk/cmdline-tools
  mv android-sdk/cmdline-tools/cmdline-tools android-sdk/cmdline-tools/latest
fi
if [ ! -d android-sdk/platforms/android-34 ]; then
  yes | android-sdk/cmdline-tools/latest/bin/sdkmanager --licenses >/dev/null 2>&1 || true
  android-sdk/cmdline-tools/latest/bin/sdkmanager "platform-tools" \
    "platforms;android-34" "build-tools;34.0.0" >/dev/null
fi

# ============================================================================
log "5/10 — Gradle 8.10.2"
if [ ! -x tools/gradle/gradle-8.10.2/bin/gradle ]; then
  [ -f downloads/gradle.zip ] || curl -sL -o downloads/gradle.zip \
    "https://services.gradle.org/distributions/gradle-8.10.2-bin.zip"
  mkdir -p tools/gradle
  unzip -q downloads/gradle.zip -d tools/gradle
fi

# ============================================================================
log "6/10 — NDK r27c (sysroot pour le cross-build Rust)"
if [ ! -d tools/android-ndk ]; then
  [ -f downloads/ndk.zip ] || curl -sL -o downloads/ndk.zip \
    "https://dl.google.com/android/repository/android-ndk-r27c-linux.zip"
  unzip -q downloads/ndk.zip -d tools
  mv tools/android-ndk-r27c tools/android-ndk
fi

# ============================================================================
log "7/10 — Rust (dans le projet ; --no-modify-path : jamais de ~/.profile)"
if [ ! -x tools/cargo/bin/cargo ]; then
  curl -sL https://sh.rustup.rs | sh -s -- -y --profile minimal --no-modify-path \
    --default-toolchain stable --target aarch64-linux-android
fi
export PATH="$CARGO_HOME/bin:$PATH"
cargo --version

# ============================================================================
log "8/10 — Python Android (PyO3) + wrappers de compilation + qemu"
if [ ! -d tools/pyo3/prefix/include/python3.13 ]; then
  mkdir -p tools/pyo3
  curl -sL -o downloads/python-android.tar.gz \
    "https://repo1.maven.org/maven2/com/chaquo/python/python/$PYTHON_MVN/python-$PYTHON_MVN-aarch64-linux-android.tar.gz"
  tar -xzf downloads/python-android.tar.gz -C tools/pyo3
fi
# wrappers clang (tools/ndk-cc) et libunwind.a : VERSIONNÉS dans le dépôt ✔
chmod +x tools/ndk-cc/* tools/wrappers/* 2>/dev/null || true
if [ ! -x tools/qemu/qemu-x86_64-static ]; then
  log "  qemu-user-static (Debian 12) + sysroot amd64…"
  curl -sL -o downloads/qemu-user-static.deb \
    "$DEBIAN_POOL/main/q/qemu/qemu-user-static_7.2+dfsg-7+deb12u18+b3_arm64.deb"
  mkdir -p .tmp/qemu-extract tools/qemu
  dpkg-deb -x downloads/qemu-user-static.deb .tmp/qemu-extract
  cp .tmp/qemu-extract/usr/bin/qemu-x86_64-static tools/qemu/
  chmod +x tools/qemu/qemu-x86_64-static
  for deb in \
    "main/g/glibc/libc6_2.41-12+deb13u4_amd64.deb" \
    "main/g/gcc-14/libgcc-s1_14.2.0-19_amd64.deb"; do
    curl -sL -o "downloads/$(basename "$deb")" "$DEBIAN_POOL/$deb"
    dpkg-deb -x "downloads/$(basename "$deb")" tools/qemu/sysroot-x86_64
  done
  ln -sfn usr/lib64 tools/qemu/sysroot-x86_64/lib64
  ln -sfn usr/lib   tools/qemu/sysroot-x86_64/lib
fi

# ============================================================================
log "9/10 — Sources vendor : Open WebUI (wheel pristine) + SearXNG (commit figé)"
if [ ! -d vendor/unpacked/open_webui ]; then
  tools/python312/bin/python3.12 -m pip download open-webui --no-deps --no-cache-dir -d vendor/wheel
  mkdir -p vendor/unpacked
  (cd vendor/unpacked && unzip -q -o ../wheel/open_webui-*.whl)
fi
if [ ! -d vendor/searxng/searx ]; then
  git clone --quiet --depth 1 https://github.com/searxng/searxng vendor/searxng || true
  (cd vendor/searxng && git fetch --quiet --depth 1 origin "$VENDOR_COMMIT" \
     && git checkout --quiet "$VENDOR_COMMIT")
fi
echo "  Open WebUI : $(ls vendor/wheel/ | head -1)"
echo "  SearXNG    : $(cd vendor/searxng && git log -1 --format='%h %ad' --date=short)"

# ============================================================================
log "10/10 — Wheels natifs cross-buildés (Rust → Android)"
bash scripts/build-wheels.sh

# ============================================================================
log "Sources patchées (patchs P1-P11)"
.venv313/bin/python scripts/prepare_src.py >/dev/null && echo "  src/ régénéré ✔"

log "=== Environnement prêt ==="
bash scripts/setup-env.sh --check

if [ "$MODE" = "--build" ]; then
  log "Build de l'APK…"
  bash scripts/build.sh
fi
