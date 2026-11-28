"""Validation P171/P172/P173 : SDK 28, SAF, service 8889 au boot.

Usage : .venv313/bin/python3 scripts/test_p171.py

Trois problèmes observés sur l'appareil après P169 :
- `errno=13, mode=0o700, X_OK=True, racine=interne` — le bit exécutable est
  bon, mais `execve()` est interdit par la politique W^X d'Android 10+ quand
  l'APK cible SDK 29+. Termux reste volontairement en targetSdk 28 ;
- le storage doit apparaître dans le navigateur de fichiers comme pour Termux,
  qui expose son $HOME via un DocumentsProvider SAF (pas un dossier public) ;
- au boot, Open WebUI précharge `/openapi.json` sur 127.0.0.1:8889 avant que
  le service Open Terminal ne soit lancé (`Initialized 0 tool server(s)`).
"""
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
print('=== P171/P172/P173 — SDK 28, SAF et service 8889 au boot ===')

gradle = (PROJ / 'app/build.gradle').read_text(encoding='utf-8')
assert 'targetSdk 28' in gradle, \
    'l APK cible encore SDK 29+ : execve(proot) reste interdit (W^X)'
assert 'targetSdk 34' not in gradle
assert 'Termux reste volontairement en 28' in gradle
assert "disable 'ExpiredTargetSdkVersion'" in gradle, \
    'lint bloque la release GitHub alors que targetSdk 28 est volontaire'
print('OK  targetSdk 28 (aligné Termux), exclusion de 34 et lint désamorcé')

java_dir = PROJ / 'app/src/main/java/org/openwebui/android'
java = (java_dir / 'MainActivity.java').read_text(encoding='utf-8')
assert 'android.system.Os.chmod(binaire.getAbsolutePath(), 0700)' in java, \
    'le chmod Termux P169 a régressé'
assert 'return MiniDebianStorage.get(this);' in java, \
    'MainActivity n utilise pas le storage unique'
assert 'getExternalStorageDirectory' not in java, \
    'retour au dossier public legacy : il faut un DocumentsProvider SAF'
assert 'minidebian-storage.path' not in java, \
    'le marqueur de chemin P171 doit être supprimé'

util = (java_dir / 'MiniDebianStorage.java').read_text(encoding='utf-8')
assert 'context.getExternalFilesDir(null)' in util
assert 'new File(new File(home, "minidebian"), "storage")' in util
provider = (java_dir / 'MiniDebianDocumentsProvider.java').read_text(encoding='utf-8')
assert 'extends DocumentsProvider' in provider
assert 'MiniDebianStorage.get(getContext())' in provider
assert 'Root.FLAG_SUPPORTS_CREATE' in provider
assert 'isInside(file, base)' in provider, \
    'le fournisseur doit refuser les doc ids hors du storage'
print('OK  Java : utilitaire SAF + provider + chmod 0700 conservé')

source = (PROJ / 'app/src/main/python/android_main.py').read_text(encoding='utf-8')
assert 'storage = home / "minidebian" / "storage"' in source, \
    'le Python n utilise pas le même chemin que le provider SAF'
assert 'minidebian-storage.path' not in source
assert 'os.environ["OPENWEBUI_ANDROID_STORAGE"] = str(storage)' in source
assert 'os.environ["OPENWEBUI_ANDROID_MACHINE_ENABLED"] = "0"' in source, \
    'la machine locale doit rester désactivée jusqu à l ouverture du port'
assert 'def _activer_machine_locale' in source
assert source.count('_activer_machine_locale()') >= 2, \
    'la réactivation doit couvrir démarrage et service déjà actif'
assert '_warm_up_then_open_terminal' not in source, \
    'le service 8889 est encore démarré après Open WebUI'

position_start = source.index('data_dir = _prepare_env(files_dir, exec_dir)')
position_ot = source.index('_start_open_terminal()', position_start)
position_app = source.index('from open_webui.main import app', position_ot)
assert position_start < position_ot < position_app, \
    'Open Terminal doit être à l écoute avant l import de open_webui.main'
print('OK  Python : chemin SAF partagé et 8889 ouvert avant open_webui.main')

manifest = (PROJ / 'app/src/main/AndroidManifest.xml').read_text(encoding='utf-8')
assert '.MiniDebianDocumentsProvider' in manifest
assert 'org.openwebui.android.minidebian.documents' in manifest
assert 'android.content.action.DOCUMENTS_PROVIDER' in manifest
assert 'android.permission.MANAGE_DOCUMENTS' in manifest
assert 'android:name="android.permission.WRITE_EXTERNAL_STORAGE"' in manifest, \
    'permission conservée pour les téléchargements WebView (DownloadManager)'
print('OK  Manifest : fournisseur SAF enregistré et permission conservée')

journal = (PROJ / 'journal.md').read_text(encoding='utf-8')
for marqueur in ('P171', 'P172', 'P173'):
    assert marqueur in journal, f'décision {marqueur} non journalisée'

print('Tous les cas P171/P172/P173 sont valides.')
