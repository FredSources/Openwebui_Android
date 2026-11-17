// P128 — shim speechSynthesis → AndroidTTS (moteur vocal natif Android).
// Injecté par MainActivity.onPageFinished. Quand la WebView ne fournit pas
// (ou mal) l'API Web Speech, ce shim prend la main et délègue la synthèse
// vocale au TextToSpeech du téléphone : 100 % local, souvent hors-ligne.
// Contrat : SpeechSynthesisUtterance(text) avec rate/voice/voiceURI et les
// événements onstart/onend/onerror/onpause/onresume ;
// speechSynthesis.speak/cancel/pause/resume/getVoices/speaking/pending/paused.
(function () {
  if (!window.AndroidTTS || window.__androidTtsPolyfilled) return;
  window.__androidTtsPolyfilled = true;

  var queue = [];
  var current = null;
  var speaking = false;
  var paused = false;
  var voicesCache = null;
  var uid = 0;

  function Utterance(text) {
    this.text = text == null ? '' : String(text);
    this.rate = 1;
    this.pitch = 1;
    this.volume = 1;
    this.voice = null;
    this.voiceURI = '';
    this.lang = '';
    this.onstart = this.onend = this.onerror = this.onpause = this.onresume = null;
    this.__id = 'u' + (++uid);
  }

  function ev(u, kind) {
    if (!u) return;
    try {
      var f = u['on' + kind];
      if (typeof f === 'function') f.call(u, { type: kind, target: u });
    } catch (e) { /* les erreurs d'écouteur ne doivent pas casser la file */ }
  }

  function pump() {
    if (speaking || paused || !queue.length) return;
    current = queue.shift();
    speaking = true;
    synth.speaking = true;
    synth.pending = queue.length > 0;
    try {
      var uri = '';
      if (current.voice && current.voice.voiceURI) uri = current.voice.voiceURI;
      else if (current.voiceURI) uri = current.voiceURI;
      window.AndroidTTS.speak(current.__id, current.text, current.rate || 1, uri);
    } catch (e) {
      speaking = false;
      synth.speaking = false;
      var u = current;
      current = null;
      ev(u, 'error');
      pump();
    }
  }

  // Rappel Java (AndroidTTS.fire → evaluateJavascript).
  window.__androidTtsEvent = function (id, kind) {
    if (!current || current.__id !== id) return;
    if (kind === 'start') {
      ev(current, 'start');
      return;
    }
    var u = current;
    current = null;
    speaking = false;
    synth.speaking = false;
    if (kind === 'error') {
      queue = [];
      synth.pending = false;
      ev(u, 'error');
      return;
    }
    ev(u, 'end');
    pump();
  };

  var synth = {
    speaking: false,
    pending: false,
    paused: false,
    getVoices: function () {
      // le navigateur interroge les voix en boucle jusqu'à en obtenir :
      // on ne met en cache que la première réponse non vide (le TextToSpeech
      // s'initialise de façon asynchrone).
      if (!voicesCache || !voicesCache.length) {
        try {
          voicesCache = JSON.parse(window.AndroidTTS.voicesJson() || '[]');
        } catch (e) {
          voicesCache = [];
        }
      }
      return voicesCache;
    },
    speak: function (u) {
      if (!u) return;
      queue.push(u);
      this.pending = true;
      pump();
    },
    cancel: function () {
      queue = [];
      this.pending = false;
      try { window.AndroidTTS.stop(); } catch (e) {}
      current = null;
      speaking = false;
      paused = false;
      this.speaking = false;
      this.paused = false;
    },
    pause: function () {
      if (speaking && current) {
        try { window.AndroidTTS.stop(); } catch (e) {}
        speaking = false;
        paused = true;
        this.speaking = false;
        this.paused = true;
        ev(current, 'pause');
      }
    },
    resume: function () {
      if (paused && current) {
        paused = false;
        this.paused = false;
        ev(current, 'resume');
        queue.unshift(current);
        current = null;
        pump();
      }
    },
  };

  // window.speechSynthesis est un attribut EN LECTURE SEULE dans Chromium :
  // une affectation simple échoue silencieusement et l'API native (muette ou
  // incomplète dans la WebView) resterait en place — d'où Object.defineProperty.
  try {
    Object.defineProperty(window, 'SpeechSynthesisUtterance',
      { value: Utterance, writable: true, configurable: true });
    Object.defineProperty(window, 'speechSynthesis',
      { value: synth, writable: true, configurable: true });
  } catch (e) {
    window.SpeechSynthesisUtterance = Utterance;
    window.speechSynthesis = synth;
  }
})();
