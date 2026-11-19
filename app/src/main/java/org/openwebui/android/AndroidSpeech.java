package org.openwebui.android;

import android.content.Context;
import android.content.Intent;
import android.media.AudioManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;

/**
 * Pont SpeechRecognition (API web) → SpeechRecognizer (moteur natif Android).
 *
 * Le mode STT « web » d'Open WebUI crée un objet
 * new (window.SpeechRecognition || window.webkitSpeechRecognition) et lit les
 * événements onresult/onend/onerror. Le shim JS (injecté par MainActivity)
 * délègue ici : la reconnaissance vocale se fait avec le moteur du téléphone
 * (souvent hors-ligne), sans faster-whisper ni service distant.
 *
 * « no-speech » : le SpeechRecognizer renvoie NO_MATCH/SPEECH_TIMEOUT quand il
 * n'entend rien (micro tenu par un autre captateur, latence de démarrage,
 * locuteur lent). On relance l'écoute silencieusement (MAX_RETRIES) avant de
 * conclure — la plupart des « no speech » disparus disparaissent ainsi.
 */
public class AndroidSpeech {

    private static final int MAX_RETRIES = 2;
    // P133 — ERROR_CLIENT : le service de reconnaissance s'est déconnecté ou
    // redémarre (très fréquent au tout premier appel, ou quand on relance
    // l'écoute trop vite après un arrêt). On retente après une courte pause
    // au lieu d'afficher « client » à l'utilisateur.
    private static final int MAX_CLIENT_RETRIES = 2;
    private static final long CLIENT_RETRY_DELAY_MS = 400;

    private final WebView webView;
    private final Handler main = new Handler(Looper.getMainLooper());
    private SpeechRecognizer recognizer;
    private String currentId = null;
    private String currentLang = "";
    private Intent currentIntent = null;
    private int retries = 0;
    private int clientRetries = 0;
    private boolean resultsSeen = false;
    private boolean stoppedByUser = false;
    // P145 — « tiling » : le service de reconnaissance joue un bip système
    // sur le canal STREAM_NOTIFICATION à chaque début/fin de session. On
    // masque ce canal pendant toute la session de dictée/appel et on le
    // restaure à l'arrêt (et à la fermeture, garde-fou).
    private boolean notifMuted = false;
    private Runnable unmuteTask = null;

    public AndroidSpeech(WebView webView) {
        this.webView = webView;
    }

    // ---- P145 — masquage du bip du recognizer (canal notification) --------

    private void muteNotif() {
        // une nouvelle session annule un dé-mute différé en attente
        // (l'écoute permanente ne doit jamais re-entendre le bip)
        if (unmuteTask != null) {
            main.removeCallbacks(unmuteTask);
            unmuteTask = null;
        }
        if (notifMuted) {
            return;
        }
        try {
            AudioManager am = (AudioManager) webView.getContext()
                    .getSystemService(Context.AUDIO_SERVICE);
            if (am != null && !am.isStreamMuted(AudioManager.STREAM_NOTIFICATION)) {
                am.adjustStreamVolume(AudioManager.STREAM_NOTIFICATION,
                        AudioManager.ADJUST_MUTE, 0);
                notifMuted = true;
            }
        } catch (Exception ignored) {
        }
    }

    /** Restaure le canal notification (seulement si c'est nous qui l'avons masqué). */
    public void unmuteNotifNow() {
        if (unmuteTask != null) {
            main.removeCallbacks(unmuteTask);
            unmuteTask = null;
        }
        if (!notifMuted) {
            return;
        }
        notifMuted = false;
        try {
            AudioManager am = (AudioManager) webView.getContext()
                    .getSystemService(Context.AUDIO_SERVICE);
            if (am != null) {
                am.adjustStreamVolume(AudioManager.STREAM_NOTIFICATION,
                        AudioManager.ADJUST_UNMUTE, 0);
            }
        } catch (Exception ignored) {
        }
    }

    /**
     * P145 — restauration différée : le bip de FIN du recognizer est joué par
     * le service après stopListening() ; dé-muter trop tôt le laisserait
     * passer. Si une nouvelle session démarre avant le délai, le dé-mute est
     * annulé (l'écoute permanente reste muette sans flicker).
     */
    private void scheduleUnmute() {
        if (!notifMuted) {
            return;
        }
        if (unmuteTask != null) {
            main.removeCallbacks(unmuteTask);
        }
        unmuteTask = () -> {
            unmuteTask = null;
            unmuteNotifNow();
        };
        main.postDelayed(unmuteTask, 800);
    }

    // ---- Appels JS (AndroidSpeech.xxx) : arrivent sur un thread binder ----

    @JavascriptInterface
    public void start(final String id, final String lang) {
        main.post(() -> {
            // P145 — masqué AVANT startListening() : le bip de début de
            // session du service est joué sur le canal notification.
            muteNotif();
            currentId = id;
            currentLang = lang != null ? lang : "";
            retries = 0;
            clientRetries = 0;
            resultsSeen = false;
            stoppedByUser = false;
            startListening();
        });
    }

    @JavascriptInterface
    public void stop() {
        main.post(() -> {
            stoppedByUser = true;
            if (recognizer != null) {
                try {
                    recognizer.stopListening();
                } catch (Exception ignored) {
                }
            }
            // P145 — le bip de FIN est joué par le service après
            // stopListening() : restauration différée (800 ms).
            scheduleUnmute();
        });
    }

    @JavascriptInterface
    public void cancel() {
        main.post(() -> {
            stoppedByUser = true;
            String id = currentId;
            destroyRecognizer();
            scheduleUnmute();
            if (id != null) {
                fire(id, "end", new JSONObject());
            }
        });
    }

    // ---- Thread principal : SpeechRecognizer l'exige ----

    private void startListening() {
        String id = currentId;
        if (id == null) {
            return;
        }
        if (recognizer == null) {
            if (!SpeechRecognizer.isRecognitionAvailable(webView.getContext())) {
                fire(id, "error", obj("error", "service-not-allowed"));
                fire(id, "end", new JSONObject());
                currentId = null;
                return;
            }
            recognizer = SpeechRecognizer.createSpeechRecognizer(webView.getContext());
            recognizer.setRecognitionListener(new RecognitionListener() {
                @Override
                public void onResults(Bundle results) {
                    resultsSeen = true;
                    fireResults(currentId, results, true);
                    destroyRecognizer();
                    fire(id, "end", new JSONObject());
                }

                @Override
                public void onPartialResults(Bundle results) {
                    resultsSeen = true;
                    fireResults(currentId, results, false);
                }

                @Override
                public void onError(int error) {
                    // « no speech » : relance silencieuse avant de conclure
                    boolean transientNoSpeech =
                            (error == SpeechRecognizer.ERROR_NO_MATCH
                                    || error == SpeechRecognizer.ERROR_SPEECH_TIMEOUT)
                                    && !resultsSeen && !stoppedByUser && retries < MAX_RETRIES;
                    // P133 : service déconnecté / relance trop rapide → on
                    // retente après une courte pause (MAX_CLIENT_RETRIES fois).
                    boolean transientClient =
                            error == SpeechRecognizer.ERROR_CLIENT
                                    && !resultsSeen && !stoppedByUser
                                    && clientRetries < MAX_CLIENT_RETRIES;
                    if (transientNoSpeech || transientClient) {
                        if (transientClient) {
                            clientRetries++;
                        } else {
                            retries++;
                        }
                        try {
                            recognizer.destroy();
                        } catch (Exception ignored) {
                        }
                        recognizer = null;
                        if (transientClient) {
                            // une pause est indispensable : relancer
                            // immédiatement provoque un nouveau ERROR_CLIENT
                            main.postDelayed(AndroidSpeech.this::startListening,
                                    CLIENT_RETRY_DELAY_MS);
                        } else {
                            startListening();
                        }
                        return;
                    }
                    fire(id, "error", err(mapError(error), error));
                    destroyRecognizer();
                    fire(id, "end", new JSONObject());
                }

                @Override public void onReadyForSpeech(Bundle params) { fire(id, "start", new JSONObject()); }
                @Override public void onBeginningOfSpeech() { }
                @Override public void onRmsChanged(float rmsdB) { }
                @Override public void onBufferReceived(byte[] buffer) { }
                @Override public void onEndOfSpeech() { }
                @Override public void onEvent(int eventType, Bundle params) { }
            });
        }

        if (currentIntent == null) {
            currentIntent = buildIntent(currentLang);
        }
        try {
            recognizer.startListening(currentIntent);
        } catch (Exception e) {
            fire(id, "error", err("client", -1));
            destroyRecognizer();
            fire(id, "end", new JSONObject());
        }
    }

    private static Intent buildIntent(String lang) {
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3);
        if (lang != null && !lang.isEmpty()) {
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, lang);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, lang);
        }
        // P133 — sans langue explicite, on ne force rien : le service utilise
        // la langue de l'appareil. Forcer `Locale.toString()` (« fr_FR »)
        // provoquait des ERROR_CLIENT / ERROR_LANGUAGE_* sur certains
        // moteurs de reconnaissance, qui exposent un tag BCP-47 (« fr-FR »).
        return intent;
    }

    private void fireResults(String id, Bundle bundle, boolean isFinal) {
        if (bundle == null || id == null) {
            return;
        }
        ArrayList<String> texts = bundle.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        if (texts == null || texts.isEmpty()) {
            return;
        }
        float[] confidences = bundle.getFloatArray(SpeechRecognizer.CONFIDENCE_SCORES);
        try {
            JSONArray alts = new JSONArray();
            for (int i = 0; i < texts.size(); i++) {
                JSONObject alt = new JSONObject();
                alt.put("transcript", texts.get(i));
                alt.put("confidence", confidences != null && i < confidences.length ? confidences[i] : 0.0);
                alts.put(alt);
            }
            JSONObject result = new JSONObject();
            result.put("isFinal", isFinal);
            result.put("alts", alts);
            JSONArray results = new JSONArray();
            results.put(result);
            fire(id, "result", obj("results", results));
        } catch (Exception ignored) {
        }
    }

    private void destroyRecognizer() {
        if (recognizer != null) {
            try {
                recognizer.destroy();
            } catch (Exception ignored) {
            }
            recognizer = null;
        }
        currentId = null;
        currentIntent = null;
    }

    private static JSONObject obj(String key, Object value) {
        JSONObject o = new JSONObject();
        try {
            o.put(key, value);
        } catch (Exception ignored) {
        }
        return o;
    }

    private static String mapError(int error) {
        switch (error) {
            case SpeechRecognizer.ERROR_AUDIO:
                return "audio-capture";
            case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS:
                return "not-allowed";
            case SpeechRecognizer.ERROR_NO_MATCH:
            case SpeechRecognizer.ERROR_SPEECH_TIMEOUT:
                return "no-speech";
            case SpeechRecognizer.ERROR_NETWORK:
            case SpeechRecognizer.ERROR_NETWORK_TIMEOUT:
            case SpeechRecognizer.ERROR_SERVER:
                return "network";
            case SpeechRecognizer.ERROR_RECOGNIZER_BUSY:
                return "busy";
            // P133 — codes explicités (sinon tout retombait sur « client ») :
            // trop de demandes empilées, service serveur coupé, langue non
            // prise en charge / indisponible sur l'appareil.
            case SpeechRecognizer.ERROR_TOO_MANY_REQUESTS:
                return "busy";
            case SpeechRecognizer.ERROR_SERVER_DISCONNECTED:
                return "network";
            case SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED:
            case SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE:
                return "language";
            default:
                return "client";
        }
    }

    /** P133 — charge utile d'erreur : code métier + code Android brut. */
    private static JSONObject err(String mapped, int code) {
        JSONObject o = new JSONObject();
        try {
            o.put("error", mapped);
            o.put("code", code);
        } catch (Exception ignored) {
        }
        return o;
    }

    /** Envoie un événement au shim JS (window.__androidSpeechEvent). */
    private void fire(String id, String type, JSONObject payload) {
        main.post(() -> webView.evaluateJavascript(
                "window.__androidSpeechEvent && window.__androidSpeechEvent("
                        + JSONObject.quote(id) + "," + JSONObject.quote(type) + ","
                        + payload.toString() + ");",
                null));
    }
}
