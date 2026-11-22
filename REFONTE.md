# REFONTE.md — Architecture v2 : submodule + patchs en diff

Branche : `v2/submodule-patches`. Objectif : **le même livrable** que
`master` (0.0.79), mais construit depuis la **source d'origine** (`submodule
Open WebUI v0.13.4`) et une **liste de patchs en diff** versionné, au lieu du
wheel PyPI + `scripts/prepare_src.py` (remplacements par motifs minifiés).

## Architecture

```
vendor/open-webui/     SUBMODULE git (open-webui, tag v0.13.4) — source vierge
vendor/searxng/        SUBMODULE git (searxng, SHA a30b2d4749) — source vierge
patches/backend/       33 patchs en diff (git format) → src/open_webui/
patches/frontend/      patchs en diff sur le SOURCE Svelte/TS → vendor/open-webui/src/
patches/complements/   fichiers ajoutés (shims tiktoken/re2, searx/version_frozen.py)
patches/searx/         patchs en diff sur les sources SearXNG → src/searx/
scripts/apply_patches.sh   applique tout (idempotent) — reconstruit src/
.github/workflows/build-apk-submodule.yml   CI : submodule → apply → build frontend → APK
```

- **Aucun sous-module dans Open WebUI** (vérifié 2026-11-22 : pas de `.gitmodules`,
  aucun gitlink, 404 côté GitHub) : le submodule est unique, le CI peut
  travailler en `--recursive` sans risque de dépendance cachée.
- `apply_patches.sh` utilise `patch -p1` (pas `git apply`, qui résout les
  chemins depuis la racine du repo parent) et `--forward` pour l'idempotence.
  Ordre : backend → frontend (dans le submodule) → copie `vendor/searxng/searx`
  → compléments (copie récursive, chemins relatifs) → patchs `searx/`.
- La cible `src/` est inchangée (`python.srcDirs = src`) : `build.gradle` et
  `smoke.sh` n'ont **pas** besoin de modification.

## Vérifications faites

| Contrôle | Résultat |
|---|---|
| Appliquer les 33 patchs backend sur le submodule vierge | **identique au `src/` de référence** (diff -rq vide) |
| Patch frontend `01-Audio.svelte.patch` | s'applique et donne bien l'option `android` + le `{#if}` de masquage |
| `apply_patches.sh` (complet : shims + SearXNG + patchs searx) | **34 appliqués / 2 déjà / 0 échec** ; `src/` = paquet + searx + shims |
| **Convergence v1/v2** | `diff -r` v1 (prepare_src) vs v2 (apply_patches) : **ZÉRO écart** hors `__pycache__` |
| Smoke 8090 | `/health`, `/`, signin → **200** ; config audio complète (`realtime.PROVIDER` = patch actif) ; SearXNG 8888 → 200 |

## Correctifs CI découverts par les runs (v0.0.80_beta)

| Run | Échec | Correctif |
|---|---|---|
| 45012666158 | `fallocate: Text file busy` (swap déjà actif sur `/swapfile`) | swap créé seulement si `SwapTotal < 8 Go` (fichier `/swapfile-openwebui`) |
| 45012886148 | `npm ci` : postinstall `onnxruntime-node` télécharge les binaires CUDA (404 GitHub) | `ONNXRUNTIME_NODE_INSTALL_CUDA=skip` (variable lue par `install.js`) |
| 45013208945 | `check_apk.py` : 3 familles — wheels pyodide absentes, `/fm` absent, `version_frozen.py` absent | P47 : copie `wheels-extra/*.whl` → `src-assets/frontend/pyodide/` ; P26b : `patches/frontend/02-app.html.patch` ; P24b : `patches/searx/01-version.py.patch` |

`build-apk.yml` (v1) est neutralisé sur cette branche (`workflow_dispatch` uniquement)
pour éviter un double build et un conflit de release sur le même tag ; intact sur `master`.

## Reste à faire (prochaine session)

1. **Porter les patchs front au source** : les anciens (P134/P141/P144 sur les
   chunks minifiés `BnHPywC-.js`, `DLUiU9_Q.js`) ont un équivalent **source lisible**
   (`CallPanel.svelte`, `CallOverlay.svelte`, `VoiceRecording.svelte`). Écrire les
   diffs correspondants dans `patches/frontend/` :
   - P149a (dropdown + masquage) → **déjà fait** (`patches/frontend/01-Audio.svelte.patch`),
     l'option `android` et le `{#if realtime.PROVIDER === 'android'}` remplacent
     l'approche par `display:none` du minifié ;
   - P26b (FAB /fm + shim Notification + capture Blob) → **déjà fait**
     (`patches/frontend/02-app.html.patch`, généré depuis la chaîne v1 elle-même) ;
   - P149b (bifurcation `current`) → `CallPanel.svelte` (l. 28-29) ;
   - P141a/P144b (flux silencieux, les deux stores) + `_w` (transcription locale)
     → `CallOverlay.svelte` ;
   - P150 (pause dictée) → `VoiceRecording.svelte` (l. 305-340, `speechRecognition.start()`) ;
   - P134 (refus overlay) → `CallPanel.svelte` (l. 31-38) ;
   - les shims `call_polyfill.js` / `tts_polyfill.js` sont dans `app/src/main/assets/`
     (hors submodule, pas de diff à faire).
2. **P24b documenté** : `patches/searx/01-version.py.patch` (le fichier
   `searx/version.py` appelle `git` au démarrage — absent d'Android : l'OSError
   remonte au lieu de tuer le thread SearXNG).
3. **Chaîne APK** : validée en CI (swap 8 Go + skip CUDA nécessaires, voir tableau).
4. Supprimer `scripts/prepare_src.py` (mode v1) quand tous les patchs sont portés.
5. Nettoyer le doublon P150 dans `app/src/main/assets/call_polyfill.js` (3 blocs
   identiques sur la branche, 2 sur master — sans effet runtime, mais à réduire
   à 1 ; hors de la course au build 0.0.80_beta).

## Commandes

```bash
git submodule update --init --recursive   # source vierge
bash scripts/apply_patches.sh             # reconstruit src/ (+ applique les patchs front au submodule)
bash scripts/apply_patches.sh --check      # vérifie sans écrire
bash scripts/smoke.sh                      # validation 8090 (ne pas utiliser 8080 !)
```
