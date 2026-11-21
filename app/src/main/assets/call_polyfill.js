// P134/P141/P142/P143/P144 — mode vocal (« Voice mode » / appel) en STT local.
//
// Open WebUI refuse le mode vocal quand le moteur STT est « web » (dictée
// native) : son implémentation transcrit chaque énoncé par l'API serveur
// `/api/v1/audio/transcriptions`, qui ne traite pas les fichiers avec ce
// moteur. Ici on garde l'écran amont intact et on branche la transcription
// sur le SpeechRecognition natif (AndroidSpeech), déjà utilisé par la dictée.
//
// P144 — écoute PERMANENTE : le recognizer tourne pendant tout l'appel
// (démarré à l'ouverture, relancé après chaque fin de session native).
// Découper les énoncés au démarrage du recognizer tronquait le début des
// phrases (latence de démarrage ~300-500 ms) ; en écoutant avant la parole,
// l'hypothèse partielle en cours contient la phrase dès son premier mot.
//
// Contrat utilisé par les micro-patchs de `BeEbX_lw.js` (prepare_src) :
//   __callDictation.warm(lang)  → démarre l'écoute permanente (à l'ouverture
//                                  de l'appel) ; alias de start() ;
//   __callDictation.start(lang) → ouvre un énoncé : si l'écoute tourne déjà,
//                                  marqueur de début (garde la phrase en
//                                  cours, efface l'historique) ;
//   __callDictation.hold()      → fige l'énoncé (le moteur livre son final) ;
//   __callDictation.text()      → Promise<{text,error}> : transcription ;
//   __callDictation.stop()      → arrête l'écoute (fermeture de l'appel) ;
//   __callVadHit()              → « la parole continue » (activité du
//                                  recognizer < 500 ms) — pilote le VAD amont ;
//   __callSpeechGate(muted)     → appelé à chaque image par le chunk : pendant
//                                  la lecture TTS, vide les tampons (jamais la
//                                  voix de l'assistant dans la transcription) ;
//   __callSilent()              → flux audio SILENCIEUX : la détection de
//                                  parole et le MediaRecorder s'y branchent —
//                                  le micro réel reste AU SEUL recognizer
//                                  (toute capture web concurrente le rend
//                                  sourd).
(function () {
  if (window.__callDictation) return;

  var rec = null;
  var listening = false;   // l'écoute permanente tourne
  var utterance = false;   // un énoncé est ouvert (garde-fou 30 s)
  var segs = [];           // segments FINAUX depuis le marqueur
  var cur = '';            // hypothèse en cours (partielle ou dernier final)
  var lastWasFinal = false;
  var safety = null;
  var lastActivityAt = 0;
  var lastError = '';
  var startedAt = 0;
  var readyAt = 0;
  var spawnAttempts = 0;
  // P146 — fin de grâce post-lecture TTS : les résultats TARDIFS du
  // recognizer (voix de l'assistant encore en cours de finalisation après
  // l'extinction) n'ouvrent jamais d'énoncé et n'entretiennent pas la
  // détection de parole. Armée à chaque image « muette », court 2,5 s.
  var graceUntil = 0;
  var pausedForDictation = false;
  var lastLang = '';

  function trace(msg) {
    try { console.warn('[call-dict] ' + msg); } catch (e) {}
  }

  function contenu() {
    var t = segs.slice();
    if (cur) t.push(cur);
    return t.join(' ');
  }

  // P142/P144/P146 — « la parole continue » : activité récente du recognizer
  // (partiel ou final reçu). Pilote le VAD amont : la détection de parole
  // WebAudio ne tient plus le micro (le recognizer doit entendre).
  // P146 : pendant la grâce post-TTS, jamais d'activité — sinon un résultat
  // tardif rouvrirait un énoncé sur la voix de l'assistant.
  window.__callVadHit = function () {
    if (Date.now() < graceUntil) return false;
    return listening && (Date.now() - lastActivityAt < 500);
  };

  // P144/P146 — pendant la lecture TTS, le chunk vide les tampons à chaque
  // image : la voix de l'assistant n'entre JAMAIS dans la transcription, et
  // aucune activité résiduelle ne déclenche un faux énoncé après la lecture.
  // P146 : le recognizer peut livrer ses résultats TARDIF (émis pendant la
  // lecture, arrivés après l'extinction) — on arme alors une fenêtre de grâce
  // de 2,5 s pendant laquelle l'activité est ignorée (résultats, VAD,
  // marqueur) : la voix de l'assistant n'entretient plus la conversation.
  window.__callSpeechGate = function (muted) {
    if (muted) {
      segs = [];
      cur = '';
      lastWasFinal = false;
      lastActivityAt = 0;
      graceUntil = Date.now() + 2500;
    }
  };

  function spawn(lang) {
    if (!listening) return;
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR || ++spawnAttempts > 40) return;
    var r = new SR();
    r.continuous = true;
    r.interimResults = false;
    r.lang = lang || '';
    r.onresult = function (ev) {
      // P146 — résultat TARDIF pendant la grâce post-TTS : la voix de
      // l'assistant ne doit ni alimenter les tampons ni entretenir le VAD.
      if (Date.now() < graceUntil) {
        trace('résultat ignoré (grâce post-TTS)');
        return;
      }
      lastActivityAt = Date.now();
      for (var i = ev.resultIndex || 0; i < ev.results.length; i++) {
        var res = ev.results[i];
        var t = ((res[0] && res[0].transcript) || '').replace(/^\s+|\s+$/g, '');
        if (!t) continue;
        if (!res.isFinal) {
          cur = t;             // hypothèse en cours = la phrase entière
          lastWasFinal = false;
          continue;
        }
        segs.push(t);          // segment finalisé
        cur = '';
        lastWasFinal = true;
      }
    };
    r.onstart = function () {
      // le moteur est prêt (onReadyForSpeech) : horodaté (mesure de latence),
      // et une session qui démarre = la chaîne est saine (compteur remis).
      spawnAttempts = 0;
      readyAt = Date.now();
      // P146 — une session qui (re)démarre pendant la grâce n'entretient
      // pas le VAD (sinon elle rouvrirait un énoncé sur le silence).
      if (Date.now() >= graceUntil) lastActivityAt = Date.now();
      trace('moteur prêt (' + (readyAt - startedAt) + ' ms)');
    };
    // le moteur s'arrête seul sur les silences : tant que l'écoute est
    // demandée, on relance aussitôt (l'écoute permanente ne doit jamais
    // laisser de trou entre deux sessions).
    r.onend = function () {
      if (listening) setTimeout(function () { spawn(lang); }, 150);
    };
    r.onerror = function (ev) {
      lastError = String((ev && (ev.error || ev.message)) || 'inconnue')
        + (ev && typeof ev.code === 'number' && ev.code >= 0 ? ' #' + ev.code : '');
      trace('erreur moteur : ' + lastError);
    };
    rec = r;
    try { r.start(); } catch (e) { /* onend relancera */ }
  }

  // P144/P146 — marqueur de début d'énoncé : garde UNIQUEMENT ce qui vient
  // d'arriver (la phrase en cours — sa « tête » est dans l'hypothèse
  // partielle), efface l'historique (ambiance, énoncés précédents).
  function mark() {
    // P146 — pendant la grâce post-TTS, aucun énoncé ne s'ouvre : un
    // déclencheur résiduel ne doit pas repartir sur la voix de l'assistant.
    if (Date.now() < graceUntil) {
      trace('énoncé refusé (grâce post-TTS)');
      return;
    }
    // le déclenchement a lieu dans la foulée du résultat (une image de la
    // boucle VAD) : seules les données de moins de 100 ms sont « la phrase
    // en cours » ; tout le reste est de l'ambiance à effacer.
    var recent = Date.now() - lastActivityAt <= 100;
    if (!recent) {
      segs = [];
      cur = '';
      lastWasFinal = false;
    } else if (lastWasFinal) {
      segs = segs.slice(-1);
      cur = '';
    } else {
      segs = [];               // cur conservé : l'hypothèse en cours
    }
    lastError = '';
    startedAt = Date.now();
    readyAt = 0;
    lastActivityAt = Date.now();
    utterance = true;
    if (safety) clearTimeout(safety);
    // garde-fou : jamais d'énoncé qui tourne indéfiniment (sinon il finirait
    // par transcrire la voix de l'assistant).
    safety = setTimeout(function () { window.__callDictation.hold(); }, 30000);
    trace('énoncé ouvert');
  }

  window.__callDictation = {
    start: function (lang) {
      lastLang = lang || lastLang;
      if (listening) {
        mark();
        return;
      }
      listening = true;
      spawnAttempts = 0;
      mark();
      trace('écoute ouverte');
      spawn(String(lang || ''));
    },

    // P143/P144 — alias de start() : appelé dès l'ouverture de l'appel, il
    // lance l'écoute PERMANENTE (le service de reconnaissance est lié avant
    // la première parole : plus jamais de démarrage froid).
    warm: function (lang) {
      this.start(lang);
    },

    mark: mark,

    hold: function () {
      utterance = false;
      if (safety) { clearTimeout(safety); safety = null; }
      // P144 : l'écoute permanente continue (le prochain énoncé n'aura
      // aucune latence de démarrage) ; on ne remet que la fenêtre d'activité.
      lastActivityAt = 0;
    },

    stop: function () {
      pausedForDictation = false;  // fermeture d'appel : plus de reprise
      listening = false;
      utterance = false;
      graceUntil = 0;   // P146 : une réouverture d'appel n'hérite pas de la grâce
      if (safety) { clearTimeout(safety); safety = null; }
      var r = rec;
      rec = null;
      if (r) {
        r.onend = null;
        try { r.stop(); } catch (e) { try { r.abort(); } catch (e2) {} }
      }
    },

    // P150 — la dictée démarre SON recognizer : le service Android
    // n'en accepte qu'un à la fois (erreurs `network`, démarrages à
    // 5-22 s en plein appel). On libère l'écoute de l'appel le temps de
    // la dictée, puis on la reprend — seulement si elle tournait.
    pauseForDictation: function () {
      this.pausedForDictation = listening;
      if (listening) {
        this.stop();
        trace('écoute mise en pause (dictée)');
      }
    },

    resumeAfterDictation: function () {
      if (this.pausedForDictation) {
        this.pausedForDictation = false;
        this.start(lastLang);
        trace('écoute reprise (fin dictée)');
      }
    },

    // Fige l'énoncé puis rend la transcription (le moteur natif a besoin
    // d'un instant pour livrer son résultat final : on attend max 5 s).
    text: function () {
      this.hold();
      var self = this;
      return new Promise(function (resolve) {
        var deadline = Date.now() + 5000;
        (function poll() {
          var t = contenu();
          if (t || Date.now() >= deadline) {
            // P143 — diagnostic device : code d'erreur brut + latence de
            // démarrage (distingue « micro tenu » / « moteur froid » /
            // « moteur en échec »).
            var info = t ? '' : (lastError || 'aucun résultat')
              + (readyAt ? ' (prêt à ' + (readyAt - startedAt) + ' ms)'
                         : ' (jamais prêt)');
            trace('transcription : ' + (t ? t.length + ' car.' : 'vide — ' + info));
            resolve({ text: t, error: info });
            return;
          }
          setTimeout(poll, 100);
        })();
      });
    },

    isLocal: function () {
      return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
    }
  };

  // P141/P144 — flux silencieux partagé : la détection de parole (analyseur
  // WebAudio) et le MediaRecorder du mode vocal s'y branchent en STT local.
  // Le micro réel reste AU SEUL SpeechRecognizer : toute capture web
  // concurrente le rend sourd (conflit documenté par le shim de dictée).
  window.__callSilent = function () {
    var s = window.__callSilentStream;
    if (s && (!s.getAudioTracks || s.getAudioTracks().some(function (t) {
      return t.readyState === 'live';
    }))) {
      return s;
    }
    try {
      var AC = window.AudioContext || window.webkitAudioContext;
      window.__callSilentStream = new AC().createMediaStreamDestination().stream;
    } catch (e) {
      return null;
    }
    return window.__callSilentStream;
  };

  // Micro réel pour le mode vocal (STT serveur : le blob enregistré doit être
  // réel) : le shim de dictée remplace le getUserMedia par un flux silencieux
  // — accès direct au getUserMedia d'origine, contournant ce substitut.
  window.__realMic = function (constraints) {
    if (window.__origGUM) return window.__origGUM(constraints);
    return navigator.mediaDevices.getUserMedia(constraints);
  };
})();
