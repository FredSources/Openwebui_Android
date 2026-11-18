package org.openwebui.android;

import android.os.Handler;
import android.os.Looper;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Set;

/**
 * Pont speechSynthesis (API web) → TextToSpeech (moteur vocal natif Android).
 *
 * P128 — la lecture à voix haute d'Open WebUI utilise `speechSynthesis` quand
 * aucun moteur TTS serveur n'est configuré. Or la WebView ne fournit pas
 * toujours cette API (voix absentes, `getVoices()` vide) : le shim JS
 * (`app/src/main/assets/tts_polyfill.js`, injecté par MainActivity) remplace
 * `window.speechSynthesis` et délègue ici. La parole est produite par le
 * synthétiseur du téléphone : 100 % local, souvent hors-ligne, aucune clé API.
 *
 * Contrat JS (window.AndroidTTS) :
 *   speak(id, text, rate, voiceURI) — synthétise et diffuse ; événements
 *     `window.__androidTtsEvent(id, "start"|"end"|"error")` émis vers le shim ;
 *   stop()        — arrête la diffusion en cours ;
 *   voicesJson()  — liste des voix du système, JSON
 *     [{voiceURI, name, lang, localService}] («[] » tant que non initialisé).
 *     P135 : cet appel lance aussi l'initialisation du synthétiseur — sans
 *     elle, la boucle d'attente des voix de l'amont ne se termine jamais.
 */
public class AndroidTTS {

    private final WebView webView;
    private final Handler main = new Handler(Looper.getMainLooper());
    private volatile TextToSpeech tts;
    private volatile boolean ready = false;
    /** Initialisation terminée (réussie OU échouée) — distinct de `ready`. */
    private volatile boolean initDone = false;
    private boolean warned = false;
    /** Demandes reçues pendant l'initialisation asynchrone du synthétiseur. */
    private final java.util.List<Runnable> pending = new java.util.ArrayList<>();

    public AndroidTTS(WebView webView) {
        this.webView = webView;
    }

    /**
     * Crée le TextToSpeech au premier appel (initialisation asynchrone).
     *
     * P135 — tant que l'initialisation n'est pas terminée, la demande est
     * MISE EN FILE au lieu d'être exécutée dans un état non prêt : sinon un
     * `speak()` lancé pendant le démarrage lève une erreur alors que le
     * synthétiseur devient disponible 200 ms plus tard.
     */
    private void ensureTts(final Runnable onReady) {
        main.post(() -> {
            if (tts != null && initDone) {
                onReady.run();
                return;
            }
            pending.add(onReady);
            if (tts != null) {
                return; // initialisation en cours : le rappel du constructeur purgera la file
            }
            tts = new TextToSpeech(webView.getContext().getApplicationContext(), status -> {
                ready = (status == TextToSpeech.SUCCESS);
                if (!ready && !warned) {
                    // Diagnostic (P133) : sans moteur TTS installé, la WebView
                    // reste muette sans explication — on dit pourquoi.
                    warned = true;
                    main.post(() -> android.widget.Toast.makeText(
                            webView.getContext(),
                            "Synthèse vocale indisponible : aucun moteur TTS installé "
                                    + "sur l'appareil (Réglages → Langue et saisie → "
                                    + "synthèse vocale).",
                            android.widget.Toast.LENGTH_LONG).show());
                }
                if (ready) {
                    tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                        @Override
                        public void onStart(String id) {
                            fire(id, "start");
                        }

                        @Override
                        public void onDone(String id) {
                            fire(id, "end");
                        }

                        @Deprecated
                        @Override
                        public void onError(String id) {
                            fire(id, "error");
                        }

                        @Override
                        public void onError(String id, int errorCode) {
                            fire(id, "error");
                        }
                    });
                }
                // P135 — l'initialisation est terminée (succès ou échec) :
                // on exécute tout ce qui attendait, puis les appels suivants
                // passeront directement.
                initDone = true;
                java.util.List<Runnable> file = new java.util.ArrayList<>(pending);
                pending.clear();
                for (Runnable r : file) {
                    r.run();
                }
            });
        });
    }

    @JavascriptInterface
    public void speak(final String id, final String text, final double rate, final String voiceURI) {
        ensureTts(() -> {
            if (!ready || tts == null) {
                fire(id, "error");
                return;
            }
            try {
                tts.setSpeechRate((float) (rate > 0 ? rate : 1.0));
                if (voiceURI != null && !voiceURI.isEmpty()) {
                    Set<Voice> voices = tts.getVoices();
                    if (voices != null) {
                        for (Voice v : voices) {
                            if (voiceURI.equals(v.getName())) {
                                tts.setVoice(v);
                                break;
                            }
                        }
                    }
                }
                tts.speak(text == null ? "" : text, TextToSpeech.QUEUE_FLUSH, null, id);
            } catch (Exception e) {
                fire(id, "error");
            }
        });
    }

    @JavascriptInterface
    public void stop() {
        main.post(() -> {
            if (tts != null) {
                try {
                    tts.stop();
                } catch (Exception ignored) {
                }
            }
        });
    }

    @JavascriptInterface
    public String voicesJson() {
        // P135 — INITIALISATION PARESSEUSE. Sans cette ligne, `tts` reste null
        // tant que speak() n'a pas été appelé, or speak() n'est appelé qu'APRÈS
        // que getVoices() n'est plus vide (la lecture à voix haute, y compris
        // celle des réponses de l'appel vocal, attend les voix en boucle à
        // 100 ms) : verrou silencieux, aucune voix jamais, aucun son jamais.
        ensureTts(() -> { });
        try {
            if (tts == null || !ready) {
                return "[]";
            }
            JSONArray arr = new JSONArray();
            Set<Voice> voices = tts.getVoices();
            if (voices != null) {
                for (Voice v : voices) {
                    JSONObject o = new JSONObject();
                    o.put("voiceURI", v.getName());
                    o.put("name", v.getName());
                    o.put("lang", v.getLocale() != null ? v.getLocale().toLanguageTag() : "");
                    o.put("localService", true);
                    arr.put(o);
                }
            }
            if (arr.length() == 0) {
                // Moteur prêt mais liste encore vide (chargement asynchrone de
                // certains synthétiseurs) : une voix par défaut suffit à
                // débloquer la boucle d'attente — elle ne retiendra `voiceURI`
                // que si elle la reconnaît.
                JSONObject o = new JSONObject();
                o.put("voiceURI", "default");
                o.put("name", "default");
                o.put("lang", java.util.Locale.getDefault().toLanguageTag());
                o.put("localService", true);
                arr.put(o);
            }
            return arr.toString();
        } catch (Exception e) {
            return "[]";
        }
    }

    /** Envoie un événement au shim JS (window.__androidTtsEvent). */
    private void fire(final String id, final String type) {
        main.post(() -> webView.evaluateJavascript(
                "window.__androidTtsEvent && window.__androidTtsEvent("
                        + JSONObject.quote(id) + "," + JSONObject.quote(type) + ");",
                null));
    }
}
