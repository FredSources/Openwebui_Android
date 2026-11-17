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
//   __callDictation.text()        → Promise<{text}> : transcription locale.
(function () {
  if (window.__callDictation) return;

  var rec = null;
  var active = false;
  var text = '';
  var safety = null;

  function spawn(lang, attempt) {
    if (!active) return;
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR || attempt > 40) return;
    var r = new SR();
    r.continuous = true;
    r.interimResults = false;
    r.lang = lang || '';
    r.onresult = function (ev) {
      for (var i = ev.resultIndex || 0; i < ev.results.length; i++) {
        var res = ev.results[i];
        if (!res.isFinal) continue;
        var t = ((res[0] && res[0].transcript) || '').replace(/^\s+|\s+$/g, '');
        if (!t) continue;
        text = text ? text.replace(/\s+$/, '') + ' ' + t : t;
      }
    };
    // le moteur s'arrête seul sur les silences : tant que l'énoncé est ouvert,
    // on relance — sinon un silence de 1 s couperait la phrase en deux.
    r.onend = function () {
      if (active) setTimeout(function () { spawn(lang, attempt + 1); }, 250);
    };
    r.onerror = function () { /* la relance se fait via onend */ };
    rec = r;
    try { r.start(); } catch (e) { /* onend relancera */ }
  }

  window.__callDictation = {
    start: function (lang) {
      if (active) return;
      active = true;
      text = '';
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
    // d'un instant pour livrer son résultat final : on attend max 3 s).
    text: function () {
      this.hold();
      return new Promise(function (resolve) {
        var deadline = Date.now() + 3000;
        (function poll() {
          if (text || Date.now() >= deadline) {
            resolve({ text: text });
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

  // Micro réel pour l'appel : le shim de dictée remplace le getUserMedia par
  // un flux silencieux (sinon le MediaRecorder monopolise le micro et le
  // SpeechRecognizer natif n'entend rien) — or le mode vocal a besoin, lui,
  // d'une vraie source pour sa détection de parole.
  window.__realMic = function (constraints) {
    if (window.__origGUM) return window.__origGUM(constraints);
    return navigator.mediaDevices.getUserMedia(constraints);
  };
})();
