# REFONTE.md — Architecture v2 : submodule + patchs en diff

Branche : `v2/submodule-patches`. Objectif : **le même livrable** que
`master` (0.0.79), mais construit depuis la **source d'origine** (`submodule
Open WebUI v0.13.4`) et une **liste de patchs en diff** versionné, au lieu du
wheel PyPI + `scripts/prepare_src.py` (remplacements par motifs minifiés).

## Architecture

```
vendor/open-webui/     SUBMODULE git (open-webui, tag v0.13.4) — source vierge
patches/backend/       33 patchs en diff (git format) → src/open_webui/
patches/frontend/      patchs en diff sur le SOURCE Svelte/TS → vendor/open-webui/src/
patches/complements/   fichiers ajoutés (shims tiktoken/re2, non issus d'Open WebUI)
scripts/apply_patches.sh   applique tout (idempotent) — reconstruit src/
.github/workflows/build-apk-submodule.yml   CI : submodule → apply → build frontend → APK
```

- **Aucun sous-module dans Open WebUI** (vérifié 2026-11-22 : pas de `.gitmodules`,
  aucun gitlink, 404 côté GitHub) : le submodule est unique, le CI peut
  travailler en `--recursive` sans risque de dépendance cachée.
- `apply_patches.sh` utilise `patch -p1` (pas `git apply`, qui résout les
  chemins depuis la racine du repo parent) et `--forward` pour l'idempotence.
- La cible `src/` est inchangée (`python.srcDirs = src`) : `build.gradle` et
  `smoke.sh` n'ont **pas** besoin de modification.

## Vérifications faites

| Contrôle | Résultat |
|---|---|
| Appliquer les 33 patchs backend sur le submodule vierge | **identique au `src/` de référence** (diff -rq vide) |
| Patch frontend `01-Audio.svelte.patch` | s'applique et donne bien l'option `android` + le `{#if}` de masquage |
| `apply_patches.sh` (complet : shims + SearXNG) | 33 appliqués / 1 déjà / 0 échec ; `src/` = paquet + searx + shims |
| Smoke 8090 | `/health`, `/`, signin → **200** ; config audio complète (`realtime.PROVIDER` = patch actif) ; SearXNG 8888 → 200 |

## Reste à faire (prochaine session)

1. **Porter les patchs front au source** : les anciens (P134/P141/P144 sur les
   chunks minifiés `BnHPywC-.js`, `DLUiU9_Q.js`) ont un équivalent **source lisible**
   (`CallPanel.svelte`, `CallOverlay.svelte`, `VoiceRecording.svelte`). Écrire les
   diffs correspondants dans `patches/frontend/` :
   - P149a (dropdown + masquage) → **déjà fait** (`patches/frontend/01-Audio.svelte.patch`),
      l'option `android` et le `{#if realtime.PROVIDER === 'android'}` remplacent
      l'approche par `display:none` du minifié ;
   - P149b (bifurcation `current`) → `CallPanel.svelte` (l. 28-29) ;
   - P141a/P144b (flux silencieux, les deux stores) + `_w` (transcription locale)
     → `CallOverlay.svelte` ;
   - P150 (pause dictée) → `VoiceRecording.svelte` (l. 305-340, `speechRecognition.start()`) ;
   - P134 (refus overlay) → `CallPanel.svelte` (l. 31-38) ;
   - les shims `call_polyfill.js` / `tts_polyfill.js` sont dans `app/src/main/assets/`
     (hors submodule, pas de diff à faire).
2. **Sortir les compléments du hors-git** : `vendor/searxng` est un vendor git séparé ;
      le garder ou le transformer en submodule dédié.
3. **Chaîne APK** : vérifier en CI que `npm run build` passe (il demande ~12 Go de RAM ;
      le runner GitHub en fournit 7 → à mesurer, sinon `--max-old-space-size` réduit
      ou runner plus gros).
4. Supprimer `scripts/prepare_src.py` (mode v1) quand tous les patchs sont portés.

## Commandes

```bash
git submodule update --init --recursive   # source vierge
bash scripts/apply_patches.sh             # reconstruit src/ (+ applique les patchs front au submodule)
bash scripts/apply_patches.sh --check      # vérifie sans écrire
bash scripts/smoke.sh                      # validation 8090 (ne pas utiliser 8080 !)
```