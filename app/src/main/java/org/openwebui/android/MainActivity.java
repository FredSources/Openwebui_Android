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
    private static final int MAX_RETRIES = 120; // ~2 min (1er lancement : extraction assets)

    private WebView webView;
    private TextView loadingText;
    private ValueCallback<Uri[]> filePathCallback;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        loadingText = findViewById(R.id.loading_text);
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
            Python py = Python.getInstance();
            py.getModule("android_main").callAttr("start_server", 8080);
        } catch (Exception e) {
            mainHandler.post(() -> loadingText.setText("Erreur Python : " + e.getMessage()));
            return;
        }
        mainHandler.post(() -> loadWhenReady(0));
    }

    private void loadWhenReady(int attempt) {
        if (attempt > MAX_RETRIES) {
            loadingText.setText("Le serveur ne démarre pas. Redémarrez l'application.");
            return;
        }
        executor.execute(() -> {
            boolean up = isServerUp();
            mainHandler.post(() -> {
                if (up) {
                    webView.loadUrl(APP_URL);
                } else {
                    loadingText.setText(getString(R.string.loading));
                    mainHandler.postDelayed(() -> loadWhenReady(attempt + 1), RETRY_DELAY_MS);
                }
            });
        });
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
            mainHandler.post(() -> loadWhenReady(0));
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
                loadingText.setVisibility(View.GONE);
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
