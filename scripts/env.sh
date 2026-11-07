#!/usr/bin/env bash
# scripts/env.sh — ancrage ISOLATION (D5) : tout le projet vit sous $PROJ.
# Usage : source scripts/env.sh  (ou `bash scripts/xxx.sh` qui le source).
set -euo failglob 2>/dev/null || set -eu

# --- Racine du projet (le script refuse de tourner ailleurs) ---
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ ! -f "$PROJ/AGENTS.md" ]; then
  echo "ERREUR: racine projet introuvable ($PROJ) — refus de continuer." >&2
  return 1 2>/dev/null || exit 1
fi
export PROJ

# --- Aucun chemin hors projet ---
export ANDROID_HOME="$PROJ/android-sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export GRADLE_USER_HOME="$PROJ/.gradle-cache"
export UV_PYTHON_INSTALL_DIR="$PROJ/tools/python312"
export UV_CACHE_DIR="$PROJ/.uv-cache"
export npm_config_cache="$PROJ/.npm-cache"
export TMPDIR="$PROJ/.tmp"
export XDG_CACHE_HOME="$PROJ/.xdg-cache"
export PYTHONDONTWRITEBYTECODE=1
# Rust : TOUJOURS dans le projet (jamais ~/.cargo ni ~/.rustup — isolation D5)
export CARGO_HOME="$PROJ/tools/cargo"
export RUSTUP_HOME="$PROJ/tools/rustup"
# JDK portable du projet (le JDK système est un JRE sans javac) ; sur CI,
# un JDK système complet (setup-java) est utilisé si tools/jdk est absent
if [ -d "$PROJ/tools/jdk" ]; then
  export JAVA_HOME="$PROJ/tools/jdk"
  export PATH="$JAVA_HOME/bin:$PATH"
fi

mkdir -p "$ANDROID_HOME" "$GRADLE_USER_HOME" "$UV_PYTHON_INSTALL_DIR" \
         "$UV_CACHE_DIR" "$npm_config_cache" "$TMPDIR" "$XDG_CACHE_HOME" \
         "$PROJ/dist" "$PROJ/tools" "$PROJ/vendor" "$PROJ/scripts"

# --- Python outils du projet ---
VENV="$PROJ/.venv"
if [ ! -d "$VENV" ]; then
  /opt/opencode-venv/bin/python3 -m venv "$VENV" >/dev/null 2>&1 || true
fi
[ -x "$VENV/bin/python" ] && export PYTHON="$VENV/bin/python" || export PYTHON=/opt/opencode-venv/bin/python3

# --- buildPython 3.12 (Chaquopy) ---
BUILD_PYTHON="$PROJ/tools/python312/bin/python3.12"
export BUILD_PYTHON

log() { printf '\033[1;34m[env]\033[0m %s\n' "$*"; }
log "PROJ=$PROJ"
log "ANDROID_HOME=$ANDROID_HOME"
log "GRADLE_USER_HOME=$GRADLE_USER_HOME"
log "PYTHON=$PYTHON"
log "BUILD_PYTHON=$BUILD_PYTHON$([ -x "$BUILD_PYTHON" ] && echo ' (OK)' || echo ' (pas encore installé)')"
