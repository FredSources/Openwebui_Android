// P134 — mode vocal (« Voice mode » / appel) utilisable en STT local.
//
// Open WebUI refuse le mode vocal quand le moteur STT est « web » (dictée
// native) : son implémentation transcrit chaque énoncé par l'API serveur
// `/api/v1/audio/transcriptions`, qui ne traite pas les fichiers avec ce
// moteur. Ici on garde l'écran amont intact et on branche la transcription
// sur le SpeechRecognition natif (AndroidSpeech), déjà utilisé par la dictée.
//
// Contrat utilisé par les micro-patchs de `BeEbX_lw.js` (prepare_src) :
//   __realMic(constraints)        → VRAI micro (contourne le flux silencieux
//                                    que le shim de dictée substitue au
//                                    getUserMedia pour laisser le micro libre) ;
//   __callDictation.start(lang)   → ouvre la reconnaissance à chaque début
//                                    d'énoncé (détection de parole de l'appel) ;
//   __callDictation.hold()        → fige l'énoncé (le moteur natif renvoie son
//                                    résultat final) ;
//   __callDictation.text()        → Promise<{text}> : transcription locale ;
//   __callSilent()                → flux audio SILENCIEUX (P141) : le
//                                    MediaRecorder du mode vocal enregistre
//                                    dessus — sinon il monopolise le micro et
//                                    le SpeechRecognizer n'entend rien.
(function () {
  if (window.__callDictation) return;

  var rec = null;
  var active = false;
  var text = '';
  var partial = '';
  var safety = null;
  var lastActivityAt = 0;
  var lastError = '';
  var startedAt = 0;
  var readyAt = 0;
  var warmRec = null;

  function trace(msg) {
    try { console.warn('[call-dict] ' + msg); } catch (e) {}
  }

  // P142 — « la parole continue » : pendant l'énoncé, le micro réel est
  // libéré pour le SpeechRecognizer (le VAD WebAudio devient muet). C'est
  // l'activité du recognizer (résultats partiels/finaux, prêt du moteur)
  // qui entretient la détection. P143 : grâce portée à 2,5 s — un moteur
  // au démarrage froid (liaison du service, 1-2 s) ne doit pas être coupé
  // avant d'avoir pu entendre (« no-speech » injustifié).
  window.__callVadHit = function () {
    return active && (Date.now() - lastActivityAt < 2500);
  };

  function spawn(lang, attempt) {
    if (!active) return;
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR || attempt > 40) return;
    var r = new SR();
    r.continuous = true;
    r.interimResults = false;
    r.lang = lang || '';
    r.onresult = function (ev) {
      lastActivityAt = Date.now();
      for (var i = ev.resultIndex || 0; i < ev.results.length; i++) {
        var res = ev.results[i];
        var t = ((res[0] && res[0].transcript) || '').replace(/^\s+|\s+$/g, '');
        if (!t) continue;
        if (!res.isFinal) {
          // P141 : les résultats partiels servent de repli — si le résultat
          // final n'arrive jamais (moteur coupé après stop), on ne repart pas
          // les mains vides.
          partial = t;
          continue;
        }
        text = text ? text.replace(/\s+$/, '') + ' ' + t : t;
        partial = '';
      }
    };
    // le moteur s'arrête seul sur les silences : tant que l'énoncé est ouvert,
    // on relance — sinon un silence de 1 s couperait la phrase en deux.
    r.onend = function () {
      if (active) setTimeout(function () { spawn(lang, attempt + 1); }, 250);
    };
    // P143 — « start » = le moteur est prêt (onReadyForSpeech) : horodaté
    // pour mesurer la latence de démarrage, et pris pour de l'activité.
    r.onstart = function () {
      readyAt = Date.now();
      lastActivityAt = Date.now();
      trace('moteur prêt (' + (readyAt - startedAt) + ' ms)');
    };
    r.onerror = function (ev) {
      lastError = String((ev && (ev.error || ev.message)) || 'inconnue')
        + (ev && typeof ev.code === 'number' && ev.code >= 0 ? ' #' + ev.code : '');
      trace('erreur moteur : ' + lastError);
    };
    rec = r;
    try { r.start(); } catch (e) { /* onend relancera */ }
  }

  window.__callDictation = {
    start: function (lang) {
      if (active) return;
      // P143 — un préchauffage en cours ne doit jamais gêner la vraie
      // écoute (ni être annulé après coup par son minuteur).
      if (warmRec) {
        var w = warmRec;
        warmRec = null;
        try { w.abort(); } catch (e) {}
      }
      active = true;
      text = '';
      partial = '';
      lastError = '';
      startedAt = Date.now();
      readyAt = 0;
      lastActivityAt = Date.now();
      trace('écoute ouverte');
      spawn(String(lang || ''), 0);
      if (safety) clearTimeout(safety);
      // garde-fou : jamais de reconnaissance qui tourne en boucle (sinon elle
      // finirait par transcrire la voix de l'assistant).
      safety = setTimeout(function () { window.__callDictation.hold(); }, 30000);
    },

    hold: function () {
      active = false;
      if (safety) { clearTimeout(safety); safety = null; }
      var r = rec;
      rec = null;
      if (r) {
        r.onend = null; // pas de relance : l'énoncé est clos
        try { r.stop(); } catch (e) { try { r.abort(); } catch (e2) {} }
      }
    },

    // Arrête l'écoute puis rend la transcription (le moteur natif a besoin
    // d'un instant pour livrer son résultat final : on attend max 5 s).
    text: function () {
      this.hold();
      return new Promise(function (resolve) {
        var deadline = Date.now() + 5000;
        (function poll() {
          var t = text || partial;
          if (t || Date.now() >= deadline) {
            // P143 — diagnostic device : code d'erreur brut + latence de
            // démarrage du moteur (distingue « micro tenu » / « moteur
            // froid » / « moteur en échec »).
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
    },

    // P143 — préchauffage : lie le service de reconnaissance AVANT le
    // premier énoncé (démarrage froid ~1-2 s : sans ça, l'énoncé est écoulé
    // avant que le moteur n'écoute → « no-speech »). La session est annulée
    // aussitôt ; seul le lien de service compte.
    warm: function () {
      if (active || warmRec) return;
      var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) return;
      trace('préchauffage du moteur');
      var r = new SR();
      warmRec = r;
      r.onend = function () { if (warmRec === r) warmRec = null; };
      r.onerror = function () { /* le préchauffage échoue silencieusement */ };
      try { r.start(); } catch (e) { warmRec = null; }
      setTimeout(function () {
        if (warmRec !== r) return;
        warmRec = null;
        try { r.abort(); } catch (e) {}
      }, 400);
    }
  };

  // P141 — flux silencieux partagé : le MediaRecorder du mode vocal (qui ne
  // sert qu'à déclencher le traitement de fin d'énoncé) enregistre dessus en
  // STT local, le micro réel restant libre pour le SpeechRecognizer.
  window.__callSilent = function () {
    if (!window.__callSilentStream) {
      try {
        var AC = window.AudioContext || window.webkitAudioContext;
        window.__callSilentStream = new AC().createMediaStreamDestination().stream;
      } catch (e) {
        return null;
      }
    }
    return window.__callSilentStream;
  };

  // Micro réel pour l'appel : le shim de dictée remplace le getUserMedia par
  // un flux silencieux (sinon le MediaRecorder monopolise le micro et le
  // SpeechRecognizer natif n'entend rien) — or le mode vocal a besoin, lui,
  // d'une vraie source pour sa détection de parole.
  window.__realMic = function (constraints) {
    if (window.__origGUM) return window.__origGUM(constraints);
    return navigator.mediaDevices.getUserMedia(constraints);
  };
})();
