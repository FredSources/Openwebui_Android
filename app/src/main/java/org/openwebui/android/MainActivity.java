package org.openwebui.android;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.Manifest;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.TextView;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * MainActivity — héberge le serveur Open WebUI (Python/Chaquopy) et affiche
 * son interface dans une WebView pointant sur http://127.0.0.1:8080.
 */
public class MainActivity extends Activity {

    private static final String APP_URL = "http://127.0.0.1:8080";
    private static final int FILE_CHOOSER_REQUEST = 1001;
    private static final int PERMISSION_REQUEST_CODE = 1002;

    /**
     * Shim SpeechRecognition → moteur vocal natif Android (AndroidSpeech).
     * Injecté à chaque chargement de page : reproduit l'API web utilisée par le
     * mode STT « web » d'Open WebUI (onresult / onend / onerror).
     */
    private static final String SPEECH_POLYFILL =
            "(function(){" +
            "if(window.__androidSpeechPolyfill)return;" +
            "window.__androidSpeechPolyfill=true;" +
            "var seq=0,registry={};" +
            // Mode STT « web » : l'UI enregistre (MediaRecorder) ET lance la
            // reconnaissance en même temps. Le MediaRecorder monopolise le micro
            // et le SpeechRecognizer natif n'entend rien (« no-speech »). En mode
            // « web » le blob enregistré est de toute façon ignoré par l'UI : on
            // remplace donc le flux audio par un flux silencieux et le micro réel
            // reste libre pour le moteur vocal natif.
            "var sttWeb=true;" +
            "try{fetch('/api/v1/audio/config').then(function(r){return r.ok?r.json():null}).then(function(c){" +
            "  if(c&&c.stt&&typeof c.stt.engine==='string')sttWeb=(c.stt.engine==='web');" +
            "}).catch(function(){})}catch(e){}" +
            "if(navigator.mediaDevices&&navigator.mediaDevices.getUserMedia){" +
            "  var origGUM=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);" +
            "  navigator.mediaDevices.getUserMedia=async function(c){" +
            "    if(!sttWeb||!c||!c.audio)return origGUM(c);" +
            "    try{" +
            "      var AC=window.AudioContext||window.webkitAudioContext;" +
            "      var ctx=new AC();" +
            "      var stream=ctx.createMediaStreamDestination().stream;" +
            "      if(c.video){var vs=await origGUM({video:c.video});vs.getVideoTracks().forEach(function(t){stream.addTrack(t)})}" +
            "      return stream;" +
            "    }catch(e){return origGUM(c)}" +
            "  };" +
            "}" +
            "window.__androidSpeechEvent=function(id,type,payload){" +
            "  var inst=registry[id];if(!inst)return;" +
            "  if(type==='result'){" +
            "    var ev={resultIndex:0,results:[]};" +
            "    (payload.results||[]).forEach(function(r){" +
            "      var row=(r.alts||[]).map(function(a){return {transcript:a.transcript,confidence:a.confidence};});" +
            "      row.isFinal=!!r.isFinal;ev.results.push(row);" +
            "    });" +
            "    if(inst.onresult)try{inst.onresult(ev);}catch(e){}" +
            "  }else if(type==='error'){" +
            "    if(inst.onerror)try{inst.onerror({error:(payload&&payload.error)||'client'});}catch(e){}" +
            "  }else if(type==='start'){" +
            "    if(inst.onstart)try{inst.onstart();}catch(e){}" +
            "  }else if(type==='end'){" +
            "    delete registry[id];" +
            "    if(inst.onend)try{inst.onend();}catch(e){}" +
            "  }" +
            "};" +
            "function SpeechRecognition(){this.continuous=false;this.interimResults=false;" +
            "this.lang='';this.onresult=null;this.onend=null;this.onerror=null;this.onstart=null;}" +
            "SpeechRecognition.prototype.start=function(){" +
            "  var id='r'+(++seq);registry[id]=this;this._id=id;" +
            "  if(window.AndroidSpeech){AndroidSpeech.start(id,this.lang||'');}" +
            "  else{delete registry[id];if(this.onerror)this.onerror({error:'not-allowed'});if(this.onend)this.onend();}" +
            "};" +
            "SpeechRecognition.prototype.stop=function(){if(window.AndroidSpeech)AndroidSpeech.stop();else if(this.onend)this.onend();};" +
            "SpeechRecognition.prototype.abort=function(){if(window.AndroidSpeech)AndroidSpeech.cancel();else if(this.onend)this.onend();};" +
            "window.SpeechRecognition=SpeechRecognition;" +
            "window.webkitSpeechRecognition=SpeechRecognition;" +
            "})();";
    private static final long RETRY_DELAY_MS = 1000;
    private static final int MAX_RETRIES = 900; // ~15 min : le 1er lancement extrait les ressources

    private WebView webView;
    private TextView loadingText;
    private TextView progressLabel;
    private TextView errorText;
    private View loadingPanel;
    private android.widget.ProgressBar progressBar;
    private ValueCallback<Uri[]> filePathCallback;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        dataHome = resolveDataHome();
        loadingText = findViewById(R.id.loading_text);
        progressBar = findViewById(R.id.progress_bar);
        progressLabel = findViewById(R.id.progress_label);
        errorText = findViewById(R.id.error_text);
        loadingPanel = findViewById(R.id.loading_panel);
        webView = findViewById(R.id.webview);
        setupWebView();

        // Service avant-plan : garde le serveur vivant quand l'app passe en arrière-plan
        startForegroundService(new Intent(this, ServerService.class));

        // Purge du cache WebView quand la version de l'APK change : l'UI (JS)
        // a changé et la WebView servirait sinon les anciens chunks depuis son
        // cache HTTP (l'utilisateur verrait des listes/menus périmés).
        try {
            SharedPreferences prefs = getSharedPreferences("openwebui_state", MODE_PRIVATE);
            PackageManager pm = getPackageManager();
            long current = Build.VERSION.SDK_INT >= Build.VERSION_CODES.P
                    ? pm.getPackageInfo(getPackageName(), 0).getLongVersionCode()
                    : pm.getPackageInfo(getPackageName(), 0).versionCode;
            long last = prefs.getLong("last_version_code", -1);
            if (last != current) {
                webView.clearCache(true);
                prefs.edit().putLong("last_version_code", current).apply();
            }
        } catch (Exception ignored) {
        }

        // Permissions système (micro/caméra/notification) : la WebView exige que
        // l'app les détienne AVANT de pouvoir accorder les accès web (getUserMedia)
        requestAppPermissions();

        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }
        executor.execute(this::startPythonServer);
    }

    private void startPythonServer() {
        try {
            writeStatus(3, "Préparation de l'interface…");
            prepareFrontend();
            writeStatus(45, "Démarrage du serveur Open WebUI…");
            Python py = Python.getInstance();
            py.getModule("android_main").callAttr("start_server", 8080, dataHome.getAbsolutePath());
        } catch (Exception e) {
            writeStatus(100, "Erreur : " + e);
            mainHandler.post(() -> showError("Erreur Python : " + e.getMessage()));
            return;
        }
        mainHandler.post(() -> loadWhenReady(0));
    }

    /** Affiche une erreur bloquante sur l'écran de démarrage. */
    private void showError(String message) {
        errorText.setText(message);
        errorText.setVisibility(View.VISIBLE);
    }

    /**
     * Écrit l'étape courante au format « PCT|message » (fichier lu par
     * MainActivity et par android_main.py — diagnostic intégré).
     */
    private void writeStatus(int percent, String message) {
        try {
            java.io.File f = new java.io.File(dataHome, "data/startup-status.txt");
            f.getParentFile().mkdirs();
            java.io.FileWriter w = new java.io.FileWriter(f);
            w.write(percent + "|" + message);
            w.close();
        } catch (Exception ignored) {
        }
        mainHandler.post(() -> {
            progressBar.setProgress(percent);
            loadingText.setText(message);
            progressLabel.setText(percent + " %");
        });
    }

    /**
     * Extrait les assets du frontend (src-assets → assets/) dans filesDir/frontend,
     * une fois par versionCode. Le frontend est trop volumineux pour rester dans
     * les assets Python (extrait à l'import, pendant le démarrage du serveur).
     */
    private void prepareFrontend() {
        java.io.File target = new java.io.File(dataHome, "frontend");
        java.io.File marker = new java.io.File(dataHome, "frontend.version");
        long current;
        try {
            android.content.pm.PackageManager pm = getPackageManager();
            current = android.os.Build.VERSION.SDK_INT >= 28
                    ? pm.getPackageInfo(getPackageName(), 0).getLongVersionCode()
                    : pm.getPackageInfo(getPackageName(), 0).versionCode;
        } catch (Exception e) {
            current = -1;
        }
        try {
            if (target.isDirectory() && marker.exists()) {
                java.io.BufferedReader r = new java.io.BufferedReader(new java.io.FileReader(marker));
                String v = r.readLine();
                r.close();
                if (v != null && v.equals(String.valueOf(current))) {
                    return; // déjà extrait pour cette version
                }
            }
            deleteRecursive(target);
            final int total = Math.max(1, countAssets("frontend"));
            final int[] done = {0};
            copyAssetFolder(getAssets(), "frontend", target, done, total);
            java.io.FileWriter w = new java.io.FileWriter(marker);
            w.write(String.valueOf(current));
            w.close();
        } catch (Exception e) {
            writeStatus(100, "Erreur d'extraction de l'interface : " + e);
        }
    }

    /** Nombre de fichiers d'un dossier d'assets (pour la barre de progression). */
    private int countAssets(String path) throws java.io.IOException {
        String[] list = getAssets().list(path);
        if (list == null || list.length == 0) {
            return 1;
        }
        int n = 0;
        for (String child : list) {
            n += countAssets(path + "/" + child);
        }
        return n;
    }

    private void copyAssetFolder(android.content.res.AssetManager am, String path,
                                 java.io.File out, int[] done, int total)
            throws java.io.IOException {
        String[] list = am.list(path);
        if (list == null || list.length == 0) {
            java.io.InputStream in = am.open(path);
            out.getParentFile().mkdirs();
            java.io.OutputStream os = new java.io.FileOutputStream(out);
            byte[] buf = new byte[65536];
            int n;
            while ((n = in.read(buf)) > 0) {
                os.write(buf, 0, n);
            }
            os.close();
            in.close();
            done[0]++;
            if (done[0] % 100 == 0 || done[0] == total) {
                int pct = 3 + (int) (37.0 * done[0] / total);
                writeStatus(pct, "Extraction de l'interface… (" + done[0] + "/" + total + " fichiers)");
            }
            return;
        }
        out.mkdirs();
        for (String child : list) {
            copyAssetFolder(am, path + "/" + child, new java.io.File(out, child), done, total);
        }
    }

    private void deleteRecursive(java.io.File f) {
        if (f.isDirectory()) {
            for (java.io.File c : f.listFiles()) {
                deleteRecursive(c);
            }
        }
        f.delete();
    }

    private void loadWhenReady(int attempt) {
        if (attempt > MAX_RETRIES) {
            showError("Le serveur ne démarre pas après " + (MAX_RETRIES) + " s. Redémarrez l'application.");
            return;
        }
        executor.execute(() -> {
            boolean up = isServerUp();
            mainHandler.post(() -> {
                if (up) {
                    progressBar.setProgress(100);
                    progressLabel.setText("100 %");
                    webView.loadUrl(APP_URL);
                } else {
                    updateProgressFromStatus(attempt);
                    mainHandler.postDelayed(() -> loadWhenReady(attempt + 1), RETRY_DELAY_MS);
                }
            });
        });
    }

    /**
     * Lit data/startup-status.txt (format « PCT|message », écrit par MainActivity
     * et par android_main.py) et met à jour la barre, le commentaire et la zone
     * d'erreur. Le PCT vient du serveur (étapes Python) ou, à défaut, d'une
     * progression assistée par le temps pendant l'import.
     */
    private void updateProgressFromStatus(int attempt) {
        int pct = -1;
        String msg = null;
        try {
            java.io.File f = new java.io.File(dataHome, "data/startup-status.txt");
            java.io.BufferedReader r = new java.io.BufferedReader(new java.io.FileReader(f));
            String line = r.readLine();
            r.close();
            if (line != null && !line.isEmpty()) {
                int sep = line.indexOf('|');
                if (sep > 0) {
                    try {
                        pct = Integer.parseInt(line.substring(0, sep).trim());
                    } catch (NumberFormatException ignored) {
                    }
                    msg = line.substring(sep + 1);
                } else {
                    msg = line;
                }
            }
        } catch (Exception ignored) {
        }
        if (msg == null || msg.isEmpty()) {
            msg = getString(R.string.loading);
        }
        boolean failed = msg.startsWith("Erreur");
        int shown = pct >= 0 ? pct : Math.min(45 + attempt / 2, 92);
        progressBar.setProgress(shown);
        loadingText.setText(failed ? getString(R.string.loading) : msg);
        progressLabel.setText(shown + " % · " + attempt + " s");
        if (failed) {
            showError(msg);
        }
    }

    private boolean isServerUp() {
        try {
            java.net.HttpURLConnection c = (java.net.HttpURLConnection)
                    new java.net.URL(APP_URL + "/health").openConnection();
            c.setConnectTimeout(700);
            c.setReadTimeout(700);
            boolean ok = c.getResponseCode() == 200;
            c.disconnect();
            return ok;
        } catch (Exception e) {
            return false;
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    /** Demande les permissions dangereuses non encore accordées (prompt système). */
    /** P35 — canal de notification Android (obligatoire depuis API 26). */
    private void ensureNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            android.app.NotificationChannel ch = new android.app.NotificationChannel(
                    "openwebui", "Open WebUI", android.app.NotificationManager.IMPORTANCE_DEFAULT);
            ch.setDescription("Réponses et événements Open WebUI");
            android.app.NotificationManager nm = getSystemService(android.app.NotificationManager.class);
            if (nm != null) {
                nm.createNotificationChannel(ch);
            }
        }
    }

    private void requestAppPermissions() {
        List<String> needed = new ArrayList<>();
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            needed.add(Manifest.permission.RECORD_AUDIO);
        }
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            needed.add(Manifest.permission.CAMERA);
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            needed.add(Manifest.permission.POST_NOTIFICATIONS);
            getSharedPreferences("owui", MODE_PRIVATE).edit().putBoolean("notif_asked", true).apply();
        }
        if (!needed.isEmpty()) {
            requestPermissions(needed.toArray(new String[0]), PERMISSION_REQUEST_CODE);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        // relance le chargement au cas où il attendait quelque chose
        if (requestCode == PERMISSION_REQUEST_CODE) {
            // P35 : résoudre la promesse Notification.requestPermission() côté JS
            boolean accorde = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU;
            for (int i = 0; i < permissions.length; i++) {
                if (Manifest.permission.POST_NOTIFICATIONS.equals(permissions[i])) {
                    accorde = grantResults[i] == PackageManager.PERMISSION_GRANTED;
                }
            }
            final String res = accorde ? "granted" : "denied";
            mainHandler.post(() -> {
                if (webView != null) {
                    webView.evaluateJavascript(
                            "window.__notifPermResolve && window.__notifPermResolve('" + res + "')", null);
                }
                loadWhenReady(0);
            });
        }
    }

    /** Répertoire de données : de préférence l'espace EXTERNE de l'app
     *  (/sdcard/Android/data/org.openwebui.android/files) — visible dans les
     *  gestionnaires de fichiers, donc consultable et effaçable par l'utilisateur. */
    private java.io.File dataHome;

    private java.io.File resolveDataHome() {
        java.io.File ext = null;
        try {
            ext = getExternalFilesDir(null);
        } catch (Exception ignored) {
        }
        java.io.File home = (ext != null) ? ext : getFilesDir();
        // Purge au démarrage des ANCIENS fichiers (mémoire interne, jamais plus
        // utilisée) : efface les restes de versions antérieures, y compris la
        // configuration restaurée par la sauvegarde Android (demande utilisateur :
        // « effacer les données invisibles »). Ne touche qu'aux entrées de l'app —
        // jamais au runtime Chaquopy (files/chaquopy).
        try {
            deleteRecursive(new java.io.File(getFilesDir(), "data"));
            deleteRecursive(new java.io.File(getFilesDir(), "frontend"));
            deleteRecursive(new java.io.File(getFilesDir(), "frontend.version"));
        } catch (Exception ignored) {
        }
        return home;
    }


    private static void copyRecursive(java.io.File src, java.io.File dst) throws java.io.IOException {
        if (src.isDirectory()) {
            dst.mkdirs();
            String[] kids = src.list();
            if (kids != null) {
                for (String k : kids) {
                    copyRecursive(new java.io.File(src, k), new java.io.File(dst, k));
                }
            }
            return;
        }
        dst.getParentFile().mkdirs();
        try (java.io.InputStream in = new java.io.FileInputStream(src);
             java.io.OutputStream out = new java.io.FileOutputStream(dst)) {
            byte[] buf = new byte[65536];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        }
    }

    private void setupWebView() {
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);            // requis par l'UI SvelteKit
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        webView.setKeepScreenOn(true);

        // Téléchargements : la WebView n'en gère aucun par défaut — DownloadManager
        // + session cookie pour les URL authentifiées (/api/v1/files/…/content).
        // Les URL « blob: » (exports JS de l'interface) sont récupérées par le
        // bridge JavaScript puis écrites dans Téléchargements.
        webView.setDownloadListener((url, agent, disposition, mime, length) -> {
            try {
                String name = android.webkit.URLUtil.guessFileName(url, disposition, mime);
                if (url != null && url.startsWith("blob:")) {
                    String safeName = name.replace("'", "\\'");
                    webView.evaluateJavascript(
                        "(async()=>{try{"
                                + "var b=window.__dlBlob;var fr=new FileReader();"
                                + "fr.onload=()=>AndroidDownload.save(fr.result.split(',')[1],'" + safeName + "');"
                                + "if(b){fr.readAsDataURL(b);return;}"
                                + "const r=await fetch('" + url.replace("'", "") + "');"
                                + "fr.readAsDataURL(await r.blob());"
                                + "}catch(e){AndroidDownload.save('', 'ERREUR:'+e);}})()",
                        null);
                    android.widget.Toast.makeText(this, "Préparation : " + name,
                            android.widget.Toast.LENGTH_SHORT).show();
                    return;
                }
                android.app.DownloadManager dm =
                        (android.app.DownloadManager) getSystemService(DOWNLOAD_SERVICE);
                android.net.Uri uri = android.net.Uri.parse(url);
                android.app.DownloadManager.Request req =
                        new android.app.DownloadManager.Request(uri);
                String cookie = android.webkit.CookieManager.getInstance().getCookie(url);
                if (cookie != null) req.addRequestHeader("Cookie", cookie);
                if (mime != null) req.setMimeType(mime);
                req.setTitle(name);
                req.setNotificationVisibility(
                        android.app.DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                try {
                    req.setDestinationInExternalPublicDir(
                            android.os.Environment.DIRECTORY_DOWNLOADS, name);
                } catch (Exception ignored) {
                }
                dm.enqueue(req);
                android.widget.Toast.makeText(this, "Téléchargement : " + name,
                        android.widget.Toast.LENGTH_LONG).show();
            } catch (Exception e) {
                android.widget.Toast.makeText(this, "Téléchargement impossible : " + e,
                        android.widget.Toast.LENGTH_LONG).show();
            }
        });

        // Bridge de réception des blob: → écriture dans Téléchargements
        webView.addJavascriptInterface(new Object() {
            @android.webkit.JavascriptInterface
            public void save(String base64, String name) {
                try {
                    if (base64 == null || base64.isEmpty() || name.startsWith("ERREUR")) {
                        android.widget.Toast.makeText(getApplicationContext(),
                                "Échec du téléchargement : " + name,
                                android.widget.Toast.LENGTH_LONG).show();
                        return;
                    }
                    byte[] bytes = android.util.Base64.decode(base64, android.util.Base64.DEFAULT);
                    java.io.File dir = android.os.Environment.getExternalStoragePublicDirectory(
                            android.os.Environment.DIRECTORY_DOWNLOADS);
                    dir.mkdirs();
                    java.io.File out = new java.io.File(dir, name);
                    try (java.io.FileOutputStream fos = new java.io.FileOutputStream(out)) {
                        fos.write(bytes);
                    }
                    android.widget.Toast.makeText(getApplicationContext(),
                            "Enregistré : " + name + " (" + bytes.length + " o)",
                            android.widget.Toast.LENGTH_LONG).show();
                } catch (Exception e) {
                    android.widget.Toast.makeText(getApplicationContext(),
                            "Sauvegarde impossible : " + e,
                            android.widget.Toast.LENGTH_LONG).show();
                }
            }
        }, "AndroidDownload");

        // P35 — pont Notifications : l'API web Notification n'existe pas dans
        // une WebView Android ; ce pont la shim vers les notifications natives.
        ensureNotificationChannel();
        webView.addJavascriptInterface(new Object() {
            @android.webkit.JavascriptInterface
            public String permissionState() {
                if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
                    return "granted";
                }
                if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                        == PackageManager.PERMISSION_GRANTED) {
                    return "granted";
                }
                boolean demande = getSharedPreferences("owui", MODE_PRIVATE)
                        .getBoolean("notif_asked", false);
                if (demande && !shouldShowRequestPermissionRationale(Manifest.permission.POST_NOTIFICATIONS)) {
                    return "denied";  // refus définitif → réglage système requis
                }
                return "default";     // pas encore demandé : on peut demander
            }

            @android.webkit.JavascriptInterface
            public void requestPermission() {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                        && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                                != PackageManager.PERMISSION_GRANTED) {
                    getSharedPreferences("owui", MODE_PRIVATE).edit().putBoolean("notif_asked", true).apply();
                    requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},
                            PERMISSION_REQUEST_CODE);
                }
            }

            @android.webkit.JavascriptInterface
            public void show(String title, String body) {
                try {
                    ensureNotificationChannel();
                    android.app.NotificationManager nm =
                            getSystemService(android.app.NotificationManager.class);
                    Intent intent = new Intent(getApplicationContext(), MainActivity.class);
                    intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
                    android.app.PendingIntent pi = android.app.PendingIntent.getActivity(
                            getApplicationContext(),
                            (int) (System.currentTimeMillis() & 0x7FFFFFFF), intent,
                            android.app.PendingIntent.FLAG_IMMUTABLE);
                    android.app.Notification.Builder b =
                            (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                                    ? new android.app.Notification.Builder(
                                            getApplicationContext(), "openwebui")
                                    : new android.app.Notification.Builder(getApplicationContext()))
                            .setSmallIcon(R.drawable.ic_notification)
                            .setContentTitle(title != null && !title.isEmpty() ? title : "Open WebUI")
                            .setContentText(body != null ? body : "")
                            .setStyle(new android.app.Notification.BigTextStyle()
                                    .bigText(body != null ? body : ""))
                            .setAutoCancel(true)
                            .setContentIntent(pi);
                    nm.notify((int) (System.nanoTime() & 0x7FFFFFFF), b.build());
                } catch (Exception e) {
                    mainHandler.post(() -> android.widget.Toast.makeText(
                            getApplicationContext(), "Notification impossible : " + e,
                            android.widget.Toast.LENGTH_SHORT).show());
                }
            }
        }, "AndroidNotify");

        // P89 — pont système : pilotage des services (utilisable même serveur
        // arrêté) et redémarrage complet de l'app — les variables
        // d'environnement sont réappliquées à chaque démarrage.
        webView.addJavascriptInterface(new Object() {
            @android.webkit.JavascriptInterface
            public String serverAction(final String name, final String action) {
                try {
                    Python.getInstance().getModule("android_main")
                            .callAttr("service_control", name, action);
                    return "ok";
                } catch (Exception e) {
                    return "erreur : " + e;
                }
            }

            @android.webkit.JavascriptInterface
            public void restartApp() {
                try {
                    Intent intent = new Intent(getApplicationContext(), MainActivity.class);
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
                    android.app.PendingIntent pi = android.app.PendingIntent.getActivity(
                            getApplicationContext(), 1001, intent,
                            android.app.PendingIntent.FLAG_IMMUTABLE
                                    | android.app.PendingIntent.FLAG_CANCEL_CURRENT);
                    android.app.AlarmManager am =
                            (android.app.AlarmManager) getSystemService(ALARM_SERVICE);
                    am.set(android.app.AlarmManager.RTC, System.currentTimeMillis() + 500, pi);
                } catch (Exception ignored) {
                }
                android.os.Process.killProcess(android.os.Process.myPid());
            }
        }, "AndroidSystem");

        // moteur vocal natif (dictée STT mode « web »)
        webView.addJavascriptInterface(new AndroidSpeech(webView), "AndroidSpeech");

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri uri = r.getUrl();
                // rester dans l'app pour le serveur local ; ouvrir le navigateur sinon
                if (uri.getHost() != null
                        && (uri.getHost().equals("127.0.0.1") || uri.getHost().equals("localhost"))) {
                    return false;
                }
                startActivity(new Intent(Intent.ACTION_VIEW, uri));
                return true;
            }

            @Override
            public void onPageFinished(WebView v, String url) {
                v.evaluateJavascript(SPEECH_POLYFILL, null);
                loadingPanel.setVisibility(View.GONE);
                webView.setVisibility(View.VISIBLE);
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            // micro / caméra (dictée, vision) : on n'accorde QUE les ressources de
            // capture prévues, et seulement si l'app détient la permission système
            // correspondante (recommandation Android). Sinon : prompt système puis
            // refus de cette requête — l'utilisateur réessaie et ça passe.
            @Override
            public void onPermissionRequest(PermissionRequest request) {
                mainHandler.post(() -> {
                    List<String> granted = new ArrayList<>();
                    List<String> needed = new ArrayList<>();
                    for (String r : request.getResources()) {
                        if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(r)) {
                            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)
                                    == PackageManager.PERMISSION_GRANTED) {
                                granted.add(r);
                            } else {
                                needed.add(Manifest.permission.RECORD_AUDIO);
                            }
                        } else if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(r)) {
                            if (checkSelfPermission(Manifest.permission.CAMERA)
                                    == PackageManager.PERMISSION_GRANTED) {
                                granted.add(r);
                            } else {
                                needed.add(Manifest.permission.CAMERA);
                            }
                        }
                    }
                    if (!needed.isEmpty()) {
                        requestPermissions(needed.toArray(new String[0]), PERMISSION_REQUEST_CODE);
                    }
                    if (granted.isEmpty()) {
                        request.deny();
                    } else {
                        request.grant(granted.toArray(new String[0]));
                    }
                });
            }

            @Override
            public void onPermissionRequestCanceled(PermissionRequest request) {
                // rien à libérer : les flux sont gérés par la page web
            }

            // upload de fichiers depuis le téléphone
            @Override
            public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> callback,
                                             FileChooserParams params) {
                if (filePathCallback != null) {
                    filePathCallback.onReceiveValue(null);
                }
                filePathCallback = callback;
                Intent intent = params != null && params.createIntent() != null
                        ? params.createIntent()
                        : new Intent(Intent.ACTION_GET_CONTENT).setType("*/*");
                try {
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                } catch (Exception e) {
                    startActivityForResult(
                            new Intent(Intent.ACTION_GET_CONTENT).setType("*/*")
                                    .addCategory(Intent.CATEGORY_OPENABLE),
                            FILE_CHOOSER_REQUEST);
                }
                return true;
            }
        });
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == FILE_CHOOSER_REQUEST && filePathCallback != null) {
            Uri[] results = null;
            if (resultCode == RESULT_OK && data != null) {
                Uri uri = data.getData();
                if (uri != null) {
                    results = new Uri[]{uri};
                } else if (data.getClipData() != null) {
                    int n = data.getClipData().getItemCount();
                    results = new Uri[n];
                    for (int i = 0; i < n; i++) {
                        results[i] = data.getClipData().getItemAt(i).getUri();
                    }
                }
            }
            filePathCallback.onReceiveValue(results);
            filePathCallback = null;
        } else {
            super.onActivityResult(requestCode, resultCode, data);
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.destroy();
        }
        super.onDestroy();
    }
}
