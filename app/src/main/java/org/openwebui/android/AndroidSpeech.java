package org.openwebui.android;

import android.content.Intent;
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
import java.util.Locale;

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

    private final WebView webView;
    private final Handler main = new Handler(Looper.getMainLooper());
    private SpeechRecognizer recognizer;
    private String currentId = null;
    private String currentLang = "";
    private Intent currentIntent = null;
    private int retries = 0;
    private boolean resultsSeen = false;
    private boolean stoppedByUser = false;

    public AndroidSpeech(WebView webView) {
        this.webView = webView;
    }

    // ---- Appels JS (AndroidSpeech.xxx) : arrivent sur un thread binder ----

    @JavascriptInterface
    public void start(final String id, final String lang) {
        main.post(() -> {
            currentId = id;
            currentLang = lang != null ? lang : "";
            retries = 0;
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
        });
    }

    @JavascriptInterface
    public void cancel() {
        main.post(() -> {
            stoppedByUser = true;
            String id = currentId;
            destroyRecognizer();
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
                    if (transientNoSpeech) {
                        retries++;
                        try {
                            recognizer.destroy();
                        } catch (Exception ignored) {
                        }
                        recognizer = null;
                        startListening();
                        return;
                    }
                    fire(id, "error", obj("error", mapError(error)));
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
            fire(id, "error", obj("error", "client"));
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
        } else {
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toString());
        }
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
            default:
                return "client";
        }
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
