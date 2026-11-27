#!/usr/bin/env bash
# apply_patches.sh — reconstruction de src/ (backend patché) depuis le SUBMODULE
# open-webui (source vierge v0.13.5) + la liste de patchs en diff (patches/).
#
# Remplace l'ancien mode (wheel PyPI + scripts/prepare_src.py en replace_once)
# par : source d'origine (submodule) + diffs lisibles et versionnés.
# R164 : le CHANGELOG amont est COPIÉ (plus de patch de 7 170 lignes à
# régénérer à chaque montée de version) ; cf. bloc « complements ».
#
# Usage : scripts/apply_patches.sh [--check]   (--check = vérifie sans écrire)
set -euo pipefail
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$PROJ/AGENTS.md" ] || { echo "refus de tourner hors racine projet"; exit 1; }
export GIT_CONFIG_GLOBAL=/dev/null   # pas de dépendance à la config git du système

SUB="$PROJ/vendor/open-webui"
PATCHES="$PROJ/patches"
BACKEND_SRC="$SUB/backend/open_webui"
FRONTEND_SRC="$SUB/src"
CIBLE="$PROJ/src/open_webui"   # paquet Python attendu par Chaquopy (python.srcDirs = src)

CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1

command -v git >/dev/null || { echo "git requis"; exit 1; }
if [ ! -d "$SUB/.git" ] && [ ! -f "$SUB/.git" ]; then
  echo "submodule absent : git submodule update --init --recursive"
  exit 1
fi

n_app=0; n_deja=0; n_ech=0

# `patch` (et non `git apply`, qui résout les chemins depuis la racine du repo
# parent) : cwd = dossier cible, chemins `a/… b/…` → strip1.
# NB : `patch` retourne 1 quand le patch est déjà appliqué (« Reversed ») —
# avec `set -o pipefail` un `patch | grep` renverrait 1 même si grep matche,
# d'où la sortie capturée sans pipeline.
appliquer() {  # $1 = fichier .patch (absolu) ; $2 = répertoire cible
  local p="$1" cwd="$2" out
  out=$( (cd "$cwd" && patch -p1 --forward --dry-run < "$p") 2>&1; true )
  if (cd "$cwd" && patch -p1 --forward --dry-run < "$p" >/dev/null 2>&1); then
    if [ "$CHECK" = "1" ]; then
      echo "  appliquerait : ${p##*/}"
      return 0
    fi
    (cd "$cwd" && patch -p1 --forward < "$p" >/dev/null 2>&1)
    echo "  appliqué : ${p##*/}"
    n_app=$((n_app+1))
  elif echo "$out" | grep -qi "reversed (or previously applied)\|previously applied\|already exists"; then
    echo "  déjà appliqué : ${p##*/}"
    n_deja=$((n_deja+1))
  else
    echo "  ÉCHEC : ${p##*/}"
    echo "$out" | head -2 | sed 's/^/      /'
    n_ech=$((n_ech+1))
  fi
}

echo "=== patchs backend (src/*.patch) ==="
if [ "$CHECK" = "0" ]; then
  rm -rf "$CIBLE"
  mkdir -p "$(dirname "$CIBLE")"
  cp -a "$BACKEND_SRC" "$CIBLE"
  find "$CIBLE" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null
  find "$CIBLE" -name "*.pyc" -delete 2>/dev/null
fi
for p in "$PATCHES"/backend/*.patch; do
  [ -f "$p" ] || continue
  appliquer "$p" "$CIBLE"
done

echo "=== patchs frontend (source Svelte/TS, dans le submodule) ==="
for p in "$PATCHES"/frontend/*.patch; do
  [ -f "$p" ] || continue
  appliquer "$p" "$FRONTEND_SRC"
done

echo "=== complements (non issus d'Open WebUI) ==="
if [ "$CHECK" = "0" ]; then
  # R164 — CHANGELOG amont : copie du fichier du submodule au lieu d'un patch
  # « nouveau fichier » de 7 170 lignes à régénérer à chaque montée. L'UI le
  # lit via pkgutil.get_data('open_webui', 'CHANGELOG.md') (env.py) et
  # check_apk.py exige la section ## [0.13.5] dans l'APK.
  cp "$SUB/CHANGELOG.md" "$CIBLE/CHANGELOG.md"
  echo "  copié : vendor/open-webui/CHANGELOG.md -> src/open_webui/CHANGELOG.md"
  # SearXNG embarqué (vendor séparé, commit figé) — AVANT les compléments :
  # le rm -rf ci-dessous écraserait sinon src/searx/version_frozen.py
  if [ -d "$PROJ/vendor/searxng/searx" ]; then
    rm -rf "$PROJ/src/searx"
    cp -a "$PROJ/vendor/searxng/searx" "$PROJ/src/searx"
    echo "  copié : vendor/searxng/searx -> src/searx"
  else
    echo "  ATTENTION : vendor/searxng/searx absent (SearXNG ne démarrera pas)"
  fi
  # shims (tiktoken natif absent, google-re2 absent) + searx/version_frozen.py
  # (piege git SearXNG) — fichiers versionnés, chemins relatifs preserves
  ( cd "$PATCHES/complements" && find . -type f | sort ) | while read -r f; do
    f="${f#./}"
    [ -n "$f" ] || continue
    mkdir -p "$PROJ/src/$(dirname "$f")"
    cp -a "$PATCHES/complements/$f" "$PROJ/src/$f"
    echo "  copié : $f"
  done
fi

echo "=== patchs searx (sources SearXNG embarquées, dans src/searx) ==="
for p in "$PATCHES"/searx/*.patch; do
  [ -f "$p" ] || continue
  appliquer "$p" "$PROJ/src/searx"
done

echo "=== bilan : $n_app appliqué(s), $n_deja déjà, $n_ech échec(s) ==="
[ "$n_ech" -gt 0 ] && exit 1
exit 0
