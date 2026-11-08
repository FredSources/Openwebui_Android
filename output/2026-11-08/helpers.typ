// ════════════════════════════════════════════════════════════════════════════
// helpers.typ — Helpers Typst unifiés (tout-en-un)
//
// Fusion de trois sources en un seul fichier :
//   1. Canonique veille-* (CTI / OSINT / médias / académique) — source de vérité
//      pour le rendu graphique cohérent des rapports (confiance, TLP, sources...).
//   2. helpers2.typ — composants pédagogiques « SDK pour agents IA »
//      (palette, _box générique, exercices numérotés, fiches SDK...).
//   3. helpers1.typ — compléments pédagogiques (math-box, intuition-box).
//
// Décisions de fusion (2026-08) :
//   - Pour les noms en conflit (ref-box, note-box, obj-box, exo-box, code-box),
//     les versions helper2 sont retenues, SAUF code-box et ref-box (versions
//     helper1 : code mono simple, et références titre + liste).
//   - Cohérence de style : toutes les boîtes pleine largeur (width: 100%),
//     même insets/radius et accent latéral, quel que soit le texte interne.
//   - 2026-09 : ajouts inspirés des rapports institutionnels de référence
//     (ANSSI « Panorama de la cybermenace 2025 » ; InterCERT France
//     « Incidentologie 2026 ») : concept-box, identity-box, sample-note,
//     yoy-badge, dist-bars.
//
// Usage dans un rapport :
//   #import "../typst/helpers.typ": *
// ════════════════════════════════════════════════════════════════════════════

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║  DESIGN SYSTEM PARTAGÉ — palette + encadré générique                       ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

#let c-primary = rgb("#1d4ed8")
#let c-accent = rgb("#0e7490")
#let c-ok = rgb("#15803d")
#let c-warn = rgb("#b45309")
#let c-danger = rgb("#b91c1c")
#let c-soft = rgb("#eef2ff")
#let c-soft2 = luma(246)
#let c-muted = luma(90)

// Encadré générique : pleine largeur, accent latéral gauche, texte normalisé.
// Les boîtes gardent la largeur de la ligne même si le texte interne est réduit.
#let _box(fill, accent, title, body) = block(
  width: 100%,
  fill: fill,
  stroke: (left: 3pt + accent),
  radius: (right: 4pt),
  inset: 10pt,
  {
    if title != none {
      text(fill: accent, weight: "bold", size: 9.5pt, title)
      parbreak()
    }
    set text(size: 9.5pt)
    body
  },
)

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║  PARTIE A — CANONIQUE VEILLE-* (CTI / OSINT / MÉDIAS / ACADÉMIQUE)         ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

// ── Badge de confiance — 4 niveaux FR unifiés ───────────────────────────────
//
// Niveaux : "Critique" | "Haute" | "Moyenne" | "Basse"
// Alias acceptés (rétro-compat) :
//   "Haut"    -> "Haute"
//   "Moyen"   -> "Moyenne"
//   "Faible"  -> "Basse"
//   "HIGH"    -> "Haute"
//   "MEDIUM"  -> "Moyenne"
//   "LOW"     -> "Basse"
#let confidence-badge(level) = {
  let canonical = (
    "Critique": "Critique",
    "Haute": "Haute",
    "Haut": "Haute",
    "Moyenne": "Moyenne",
    "Moyen": "Moyenne",
    "Basse": "Basse",
    "Faible": "Basse",
    "HIGH": "Haute",
    "MEDIUM": "Moyenne",
    "LOW": "Basse",
  )
  let norm = canonical.at(level, default: "Moyenne")
  let entry = (
    "Critique": red,
    "Haute": orange,
    "Moyenne": yellow.darken(30%),
    "Basse": green,
  )
  let col = entry.at(norm, default: gray)
  box(
    fill: col.lighten(70%),
    inset: (x: 4pt, y: 3pt),
    radius: 3pt,
    [#box(circle(fill: col, radius: 2.5pt))#h(0.3em)#text(
        size: 7pt,
        weight: "bold",
      )[#norm]],
  )
}

// ── Légende des niveaux de confiance — à insérer en début de rapport ─────────
#let confidence-legend() = _box(
  luma(248),
  luma(190),
  none,
  text(size: 8.5pt)[
    *Légende — Niveaux de confiance :* \
    #h(1em) #confidence-badge("Critique") Preuve critique (source officielle + recoupement 3+ sources) \
    #h(1em) #confidence-badge("Haute") Preuve forte (3+ sources indépendantes) \
    #h(1em) #confidence-badge("Moyenne") Preuve modérée (2 sources ou concordance partielle) \
    #h(1em) #confidence-badge("Basse") Preuve faible (source unique ou anecdotique)
  ],
)

// ── likelihood-badge — probabilité d'un ÉVÉNEMENT (Yardstick / ICD 203) ─────
//
// CONFUSION À ÉVITER (règle ICD 203) :
//   • confidence-badge = solidité de la PREUVE (4 niveaux FR),
//   • likelihood-badge = probabilité d'un ÉVÉNEMENT (7 bandes en %).
// Les deux ne JAMAIS apparaître dans la même phrase, ni sur la même ligne.
// Échelle 7 niveaux FR (Probability Yardstick) ; « possible » seul = interdit.
//
// Entrées acceptées (insensible à la casse) :
//   "Presque certain" | "Très probable" | "Probable" | "Chance égale"
//   | "Improbable" | "Très improbable" | "Lointain"
//   alias EN : "Almost certain" | "Very likely" | "Likely" | "Roughly even chance"
//              | "Unlikely" | "Very unlikely" | "Remote chance"
//   alias %  : "95-99" | "80-95" | "60-80" | "40-60" | "20-40" | "5-20" | "<5"
#let likelihood-badge(level) = {
  let bands = (
    "presque certain": (
      term: "Presque certain",
      band: "> 95 %",
      col: c-primary,
    ),
    "très probable": (term: "Très probable", band: "80–95 %", col: c-accent),
    "probable": (term: "Probable", band: "60–80 %", col: rgb("#0891b2")),
    "chance égale": (term: "Chance égale", band: "40–60 %", col: luma(140)),
    "improbable": (term: "Improbable", band: "20–40 %", col: c-warn),
    "très improbable": (
      term: "Très improbable",
      band: "5–20 %",
      col: c-warn.lighten(30%),
    ),
    "lointain": (term: "Lointain", band: "< 5 %", col: c-muted),
  )
  let aliases = (
    "almost certain": "presque certain",
    "quasi certain": "presque certain",
    "very likely": "très probable",
    "très probable": "très probable",
    "likely": "probable",
    "probable": "probable",
    "roughly even chance": "chance égale",
    "chance égale": "chance égale",
    "unlikely": "improbable",
    "improbable": "improbable",
    "very unlikely": "très improbable",
    "très improbable": "très improbable",
    "remote chance": "lointain",
    "lointain": "lointain",
    "quasi impossible": "lointain",
    "95-99": "presque certain",
    "80-95": "très probable",
    "60-80": "probable",
    "40-60": "chance égale",
    "20-40": "improbable",
    "5-20": "très improbable",
    "<5": "lointain",
  )
  let q = lower(str(level)).trim(" ")
  let key = if bands.keys().contains(q) {
    q
  } else {
    aliases.at(q, default: "chance égale")
  }
  let e = bands.at(key, default: bands.at("chance égale"))
  // Marqueur carré (la confiance utilise un cercle) : lisibilité en niveaux de gris.
  box(
    fill: e.col.lighten(78%),
    stroke: 0.6pt + e.col,
    inset: (x: 4pt, y: 3pt),
    radius: 3pt,
    [#box(width: 6pt, height: 6pt, fill: e.col, radius: 1.5pt)#h(0.3em)
      #text(size: 7pt, weight: "bold", fill: e.col)[#e.band]#h(0.35em)
      #text(size: 7pt, weight: "bold")[#e.term]],
  )
}

// ── Légende des probabilités — à insérer en début de rapport ─────────────────
#let likelihood-legend() = _box(
  luma(248),
  luma(190),
  none,
  text(size: 8.5pt)[
    *Légende — Probabilité d'un événement (Yardstick / ICD 203) :* \
    #h(1em) #likelihood-badge("Presque certain") > 95 % — quasi-certitude \
    #h(1em) #likelihood-badge("Très probable") 80–95 % — forte certitude, surprise peu probable \
    #h(1em) #likelihood-badge("Probable") 60–80 % — plus probable que l'inverse \
    #h(1em) #likelihood-badge("Chance égale") 40–60 % — autant de chances que non \
    #h(1em) #likelihood-badge("Improbable") 20–40 % — plus de chances que non \
    #h(1em) #likelihood-badge("Très improbable") 5–20 % — surprise, ne pas s'y attendre \
    #h(1em) #likelihood-badge("Lointain") < 5 % — potentiel théorique uniquement \
    #h(1em) *Règle ICD 203* : cette échelle ne se confond pas avec `confidence-badge`
    (solidité de la preuve) — les deux ne partagent jamais une phrase.
  ],
)

// ── grade-badge — certitude GRADE d'un corps de preuves ───────────────────────
//
// GRADE mesure la *certitude d'un corps de preuves* (grade de la conclusion d'une
// revue), pas la confiance dans un constat unique (confidence-badge), ni la
// probabilité d'un événement (likelihood-badge) : trois échelles, trois usages.
// Niveaux GRADE : Élevé / Modéré / Faible / Très faible (high / moderate / low / very low).
//
// Entrées acceptées (insensible à la casse) : "Élevé" | "Modéré" | "Faible" |
// "Très faible" + alias EN "High" | "Moderate" | "Low" | "Very low".
#let grade-badge(level) = {
  let grades = (
    "élevé": (
      term: "Élevé",
      col: c-ok,
      note: "la vraie valeur se situe très près de l'estimation",
    ),
    "modéré": (
      term: "Modéré",
      col: c-accent,
      note: "la vraie valeur pourrait être sensiblement différente",
    ),
    "faible": (
      term: "Faible",
      col: c-warn,
      note: "la vraie valeur est probablement très différente",
    ),
    "très faible": (
      term: "Très faible",
      col: c-danger,
      note: "l'estimation est très incertaine",
    ),
  )
  let aliases = (
    "high": "élevé",
    "moderate": "modéré",
    "low": "faible",
    "very low": "très faible",
    "tres faible": "très faible",
    "very low ": "très faible",
  )
  let q = lower(str(level)).trim(" ")
  let key = if grades.keys().contains(q) {
    q
  } else {
    aliases.at(q, default: "modéré")
  }
  let e = grades.at(key, default: grades.at("modéré"))
  // Marqueur losange — cercle = confiance, carré = probabilité, losange = GRADE.
  box(
    fill: e.col.lighten(78%),
    stroke: 0.6pt + e.col,
    inset: (x: 4pt, y: 3pt),
    radius: 3pt,
    [
      #polygon(
        (0pt, 3pt),
        (3pt, 0pt),
        (6pt, 3pt),
        (3pt, 6pt),
        fill: e.col,
        stroke: none,
      )
      #h(0.3em)
      #text(size: 7pt, weight: "bold", fill: e.col)[GRADE #e.term]
    ],
  )
}

// ── Légende GRADE — à insérer dès qu'une synthèse d'études est produite ───────
#let grade-legend() = _box(
  luma(248),
  luma(190),
  none,
  text(size: 8.5pt)[
    *Légende — Certitude des preuves (GRADE) :* \
    #h(1em) #grade-badge("Élevé") la vraie valeur est très proche de l'estimation — des recherches
    futures ne la modifieront probablement pas \
    #h(1em) #grade-badge("Modéré") la vraie valeur pourrait différer de l'estimation \
    #h(1em) #grade-badge("Faible") la vraie valeur est probablement très différente \
    #h(1em) #grade-badge("Très faible") l'estimation est très incertaine \
    #h(1em) *Abaissée si* : biais, incohérence, indirectivité, imprécision, biais de
    publication — *rehaussée si* : effet massif, relation dose-réponse, confusion
    plausible qui réduirait l'effet. Règle : `grade-badge` ne partage jamais une phrase
    avec `confidence-badge` ni `likelihood-badge`.
  ],
)

// ── meta-glossary — glossaire canonique de la synthèse d'études ───────────────
//
// À appeler dans l'annexe d'une revue ou d'une synthèse d'études : le vocabulaire
// de la méta-analyse est la première source de surinterprétation.
#let meta-glossary() = _box(
  c-soft,
  c-primary,
  "Glossaire — méta-analyse et synthèse d'études",
  text(size: 8.5pt)[
    #table(
      columns: (1.5fr, 4.5fr),
      inset: 5pt,
      stroke: 0.5pt + luma(200),
      [*Terme*], [*Définition courte*],
      [*Méta-analyse*],
      [Combinaison statistique des résultats de plusieurs études sur une
        même question ; elle exige une hétérogénéité maîtrisée],

      [*Synthèse sans méta-analyse (SWiM)*],
      [Rapport narratif structuré des résultats
        quand la combinaison statistique est impossible ou trompeuse],

      [*$I^2$ (I-carré)*],
      [Part de la variabilité due à l'hétérogénéité réelle et non au
        hasard : < 30 % faible, 30–60 % modérée, > 60 % forte],

      [*$tau^2$ (tau-carré)*],
      [Variance entre études, utilisée dans les modèles à effets
        aléatoires],

      [*OR / RR / HR*],
      [Odds ratio (≥ 1 = plus de chances), risque relatif (≥ 1 = plus de
        risque), ratio de hasards (≥ 1 = plus de risque instantané) ; 1 = effet nul],

      [*IC 95 %*],
      [Intervalle de confiance à 95 % — un IC qui coupe la valeur nulle (1 pour
        OR/RR/HR, 0 pour la différence) traduit un résultat non significatif],

      [*Effet globalement pondéré (EGM)*],
      [Estimation combinée pondérée par la précision de
        chaque étude (inverse de la variance)],

      [*Test de Q (Cochran)*],
      [Test d'hétérogénéité — p < 0,10 suggère une hétérogénéité
        significative entre études],

      [*Courbe de forêt (forest plot)*],
      [Affichage par étude de l'effet et de son IC,
        puis de l'estimation combinée (losange)],

      [*Courbe d'entonnoir (funnel plot)*],
      [Asymétrie = possible biais de publication ou
        hétérogénéité liée à la taille des études],

      [*Biais de publication*],
      [Tendance à publier les résultats positifs ; GRADE l'abaissé
        quand l'asymétrie est plausible],

      [*ROB (risk of bias)*],
      [Évaluation du biais par domaine (randomisation, aveuglement,
        données manquantes, mesure sélective)],

      [*GRADE*],
      [Évaluation de la *certitude* de l'ensemble des preuves :
        `grade-badge()` — Élevé / Modéré / Faible / Très faible],

      [*PRISMA 2020 / PRISMA-ScR*],
      [Checklists de signalement d'une revue systématique /
        d'une revue de scoping — leur non-respect doit être déclaré, jamais dissimulé],

      [*$kappa$ de Cohen*],
      [Accord entre deux criblages indépendants ; 0-0,20 pauvre,
        0,21-0,40 faible, 0,41-0,60 modéré, 0,61-0,80 substantiel, > 0,81 quasi parfait],

      [*Saturation (Wohlin)*],
      [Arrêt de la collecte après 2 itérations consécutives sans
        nouvelle inclusion],
    )
    *Règle d'usage* : un terme du glossaire n'est jamais utilisé au sens courant ; une
    conclusion de méta-analyse porte obligatoirement `grade-badge()` et, dans une autre
    phrase, `confidence-badge()` si le constat lui-même est gradé.
  ],
)

// ── abstract-box — encadré de résumé, pleine largeur ─────────────────────────
//
// SANS label intégré : chaque section ajoute son propre *Contexte :* / *Problème :* / *Résumé :*
// Ne JAMAIS imbriquer un abstract-box dans un autre. Pas de doublon par source.
#let abstract-box(body) = _box(
  luma(246),
  luma(190),
  none,
  {
    set text(size: 9pt)
    set par(leading: 0.65em, first-line-indent: 0pt)
    body
  },
)

// ── inline-cite — citation inline avec lien cliquable ────────────────────────
// Chaque inline-cite DOIT avoir un paramètre url: (règle absolue).
#let inline-cite(src, date, url: none) = {
  let display = if url != none { link(url)[#src] } else { src }
  text(size: 9pt, fill: gray, style: "italic")[#display, #date]
}

// ── source-link — référence courte dans le texte (sans date) ────────────────
#let source-link(name, url) = link(url, text(
  style: "italic",
  fill: blue,
)[[#name]])

// ── source-entry — entrée de source structurée (API canonique) ───────────────
//
// source accepte :
//   - une chaîne simple : "Source"
//   - un tableau de paires (nom, url) : (("Src1", "https://..."), ("Src2", "https://..."))
// NE PAS grouper plusieurs sources dans une chaîne " / " — chaque source a son lien.
#let source-entry(title, source, date, excerpt: none) = {
  v(0.2cm)
  block(text(weight: "bold", size: 9.5pt)[#title])
  let src-links = if type(source) == str {
    text(size: 9pt, fill: gray)[#source, #date]
  } else {
    let links = source.map(item => link(item.at(1))[#item.at(0)])
    text(size: 9pt, fill: gray)[#links.join(" / "), #date]
  }
  block(src-links)
  if excerpt != none {
    block(text(size: 9pt, style: "italic")[#excerpt])
  }
  v(0.3cm)
}

// ── press-entry — wrapper de compatibilité pour les rapports CTI ─────────────
//
// Préserve l'API (title, source_string, date, url:) utilisée par veille-cti.
// En interne, appelle source-entry avec un tableau de paires.
#let press-entry(title, source, date, url: none, excerpt: none) = {
  let src = if url != none { ((source, url),) } else { source }
  source-entry(title, src, date, excerpt: excerpt)
}

// ── source-box — entrée de source simple (référence bibliographique) ────────
// Alias de compat pour les agents qui vérifient source-box.
#let source-box(name, date, url) = {
  line(length: 100%)
  grid(
    columns: (1fr, 0.35fr, 2fr),
    inset: 6pt,
    [*#name*],
    [#text(size: 8pt)[#date]],
    [#link(url)[#text(size: 8pt, fill: blue)[#url]]],
  )
}

// ── TLP / PAP badges (CTI) ───────────────────────────────────────────────────
#let tlp-badge(tlp) = {
  let colors = (
    "RED": (fill: red.lighten(70%), text: red),
    "AMBER": (fill: orange.lighten(70%), text: orange),
    "AMBER+STRICT": (fill: orange.lighten(50%), text: orange.darken(30%)),
    "GREEN": (fill: green.lighten(70%), text: green),
    "CLEAR": (fill: luma(240), text: luma(200)),
  )
  let parts = tlp.split("/")
  let badges = parts.map(part => {
    let c = colors.at(part, default: (fill: luma(230), text: luma(60)))
    box(fill: c.fill, inset: (x: 3pt, y: 1.5pt), radius: 3pt, text(
      size: 6.5pt,
      weight: "bold",
      fill: c.text,
    )[TLP:#part])
  })
  badges.join([ ])
}

#let pap-badge(level) = {
  // PAP:CLEAR = libellé canonique (aligné TLP 2.0, adopté par l'ANSSI) ;
  // PAP:WHITE = alias legacy accepté (spec OASIS STIX 2.1), rendu identique.
  let lvl = if level == "WHITE" { "CLEAR" } else { level }
  let colors = (
    "RED": red.darken(20%),
    "AMBER": orange,
    "GREEN": green,
    "CLEAR": luma(60),
  )
  let bg-colors = (
    "RED": red.lighten(70%),
    "AMBER": orange.lighten(70%),
    "GREEN": green.lighten(70%),
    "CLEAR": luma(240),
  )
  box(
    fill: bg-colors.at(lvl, default: gray.lighten(70%)),
    inset: (x: 3pt, y: 1.5pt),
    radius: 3pt,
    text(size: 6.5pt, weight: "bold", fill: colors.at(
      lvl,
      default: gray,
    ))[PAP:#lvl],
  )
}

// ── tlp-legend / pap-legend — légendes des protocoles TLP et PAP ─────────────
// À insérer dans les sections OSINT/CTI de chaque rapport (voir AGENTS.md).
#let tlp-legend(..args) = _box(
  luma(248),
  luma(190),
  none,
  {
    let pos = args.pos()
    let body = if pos.len() > 0 { pos.at(0) } else { none }
    if body != none {
      body
      v(4pt)
    }
    text(size: 8.5pt)[
      *Légende TLP (Traffic Light Protocol, géré par le FIRST) :* \
      #h(1em) #tlp-badge("RED") Diffusion restreinte aux destinataires uniques et stricts. Pas de rediffusion. \
      #h(1em) #tlp-badge("AMBER+STRICT") Limité strictement à votre propre organisation. \
      #h(1em) #tlp-badge("AMBER") Partage restreint à l'organisation et ses clients de confiance. \
      #h(1em) #tlp-badge("GREEN") Partage libre au sein de la communauté identifiée. \
      #h(1em) #tlp-badge("CLEAR") Diffusion publique et libre.
    ]
  },
)

#let pap-legend(..args) = _box(
  luma(248),
  luma(190),
  none,
  {
    let pos = args.pos()
    let body = if pos.len() > 0 { pos.at(0) } else { none }
    if body != none {
      body
      v(4pt)
    }
    text(size: 8.5pt)[
      *Légende PAP (Permitted Actions Protocol) :* \
      #h(1em) #pap-badge("CLEAR") Usage libre, dans le respect des règles applicables (anciennement PAP:WHITE). \
      #h(1em) #pap-badge("GREEN") Sensibilisation et remédiation autorisées, sans diffusion hors canaux prévus. \
      #h(1em) #pap-badge("AMBER") Attribution et partage prudents ; pas de publication sans accord. \
      #h(1em) #pap-badge("RED") Aucune action hors besoin de connaissance strict (protection des victimes uniquement).
    ]
  },
)

// ── apt-tag / region-tag — tags colorés (CTI) ───────────────────────────────
#let apt-tag(body, url: none) = {
  let display = if url != none { link(url)[#body] } else { body }
  box(fill: red.lighten(60%), inset: (x: 4pt, y: 2pt), radius: 3pt, text(
    size: 7pt,
    weight: "bold",
    fill: red.darken(30%),
  )[#display])
}

#let region-tag(body, color: blue) = {
  box(fill: color.lighten(70%), inset: (x: 4pt, y: 2pt), radius: 3pt, text(
    size: 7pt,
    weight: "bold",
    fill: color.darken(30%),
  )[#body])
}

// ── event — entrée de timeline (date, description, source, confiance) ───────
#let event(date, description, source, confidence) = {
  block(
    width: 100%,
    inset: (x: 0pt, y: 3pt),
    stroke: (bottom: 0.3pt + luma(220)),
    grid(
      columns: (auto, 1fr, auto),
      inset: 2pt,
      [ #text(size: 7pt, weight: "bold", fill: luma(80))[#date] ],
      [ #text(size: 8pt)[#description] ],
      [ #confidence-badge(confidence) ],
    ),
  )
}

// ── ioc-box — encadré pour code IOC (YARA / SIGMA / KQL) ────────────────────
#let ioc-box(body) = _box(
  luma(248),
  luma(190),
  none,
  {
    set text(size: 8.5pt, font: "DejaVu Sans Mono")
    body
  },
)

// ── meta-box — encadré esthétique pour profils de menace ────────────────────
#let meta-box(body) = _box(
  luma(250),
  luma(190),
  none,
  {
    set text(size: 9pt)
    body
  },
)

// ── concept-box — encadré pédagogique thématique (style ANSSI) ──────────────
// Explanation latérale indépendante du fil analytique (ex. « Les enjeux de
// l'endiguement d'un incident », « Les fuites de données »). Construit sur
// _box() : même design system que key-box / def-box (accent latéral, titre).
// Place près du texte qu'elle éclaire. Un seul concept-box par concept.
#let concept-box(title, body) = _box(
  c-soft,
  c-accent,
  title,
  {
    set text(size: 9pt)
    set par(leading: 0.65em)
    body
  },
)

// ── identity-box — fiche d'identité MOA (style ANSSI) ───────────────────────
// Cartouche structuré pour un acteur : ancienneté, sponsor présumé, sources
// d'attribution, victimologie. Champ = paire (label, valeur).
// Conforme aux conventions existantes : mêmes couleurs que def-box
// (luma 250 + accent c-accent), grille (1fr, 3fr) + labels gras à gauche
// comme les profils meta-box, texte 9pt.
// Usage : #identity-box("Callisto", ("Actif depuis", "2015"), ("Sponsor réputé", "FSB"), ("Attribution", "différentes sources"))
#let identity-box(name, ..fields) = {
  let rows = ()
  for f in fields.pos() {
    rows.push(text(size: 9pt, weight: "bold")[#f.at(0)])
    rows.push(text(size: 9pt)[#f.at(1)])
  }
  _box(
    luma(250),
    c-accent,
    [Fiche d'identité — #name],
    grid(
      columns: (1fr, 3fr),
      row-gutter: 5pt,
      ..rows,
    ),
  )
}

// ── subtext — texte secondaire gris ─────────────────────────────────────────
#let subtext(body) = text(size: 8pt, fill: luma(100))[#body]

// ── bar — barre proportionnelle (volumes ransomware) ────────────────────────
#let bar(max: 338, val: 0, color: red) = {
  let pct = calc.max(val / max, 0.02)
  block(width: pct * 100%, height: 10pt, fill: color.lighten(30%), radius: 2pt)
}

// ── trend-bar — barre de variation (croissance / baisse) ────────────────────
#let trend-bar(val, ref, label, color: blue) = {
  let pct = if ref > 0 { calc.round(val / ref * 100) } else { 0 }
  let dir = if pct > 100 { "+" + str(pct - 100) + "%" } else if pct < 100 {
    "-" + str(100 - pct) + "%"
  } else { "Stable" }
  block(
    width: calc.max(pct / 2, 2) * 1%,
    height: 8pt,
    fill: if pct > 100 { green.lighten(30%) } else if pct < 100 {
      red.lighten(30%)
    } else { luma(200) },
    radius: 2pt,
  )
  text(size: 7pt)[#dir (#label)]
}

// ── sample-note — taille d'échantillon sous chaque figure chiffrée ─────────
// Norme incidentologie (InterCERT) : toute statistique affiche son périmètre.
// Usage : après chaque #figure(table(...)) ou graphique de données.
#let sample-note(body) = (
  v(2pt)
    + text(
      size: 7.5pt,
      style: "italic",
      fill: c-muted,
    )[Taille de l'échantillon : #body]
)

// ── yoy-badge — badge compact de variation annuelle (YoY) ──────────────────
// Sémantique CTI par défaut : hausse = rouge (menace en croissance).
// invert: true pour les métriques où la hausse est favorable (détections...).
// Usage : #yoy-badge(+18) — #yoy-badge(-37) — #yoy-badge(0) — #yoy-badge(+40, invert: true)
#let yoy-badge(pct, invert: false) = {
  let up-col = if invert { green } else { red }
  let down-col = if invert { red } else { green }
  let (arrow, col) = if pct > 0 { ("▲", up-col) } else if pct < 0 {
    ("▼", down-col)
  } else { ("►", luma(120)) }
  let label = if pct > 0 { arrow + " +" + str(pct) + "% YoY" } else if pct < 0 {
    arrow + " " + str(pct) + "% YoY"
  } else { "Stable" }
  box(
    fill: col.lighten(75%),
    inset: (x: 4pt, y: 2pt),
    radius: 3pt,
    text(size: 7.5pt, weight: "bold", fill: col.darken(20%))[#label],
  )
}

// ── dist-bars — distribution horizontale en barres (répartitions %) ────────
// Pour les répartitions sectorielles, victimes, souches, sentiments...
// items = tableau de (label, valeur) ou (label, valeur, couleur).
// Usage : #dist-bars((("Éducation", 34), ("Ministères", 24), ("Santé", 10)))
#let dist-bars(items, max: none) = {
  let vmax = if max != none { max } else {
    items.map(i => i.at(1)).fold(0, (a, b) => calc.max(a, b))
  }
  let palette = (
    c-danger,
    c-warn,
    yellow.darken(20%),
    c-ok,
    c-primary,
    c-accent,
    purple,
  )
  let cells = ()
  for (i, item) in items.enumerate() {
    let col = if item.len() > 2 { item.at(2) } else {
      palette.at(calc.rem(i, palette.len()))
    }
    cells.push(text(size: 0.85em)[#item.at(0)])
    cells.push(pad(top: 3pt, bottom: 3pt, rect(
      width: calc.max(item.at(1) / vmax * 100, 1) * 1%,
      height: 8pt,
      fill: col.lighten(30%),
      radius: 3pt,
    )))
    cells.push(text(size: 0.8em, fill: c-muted)[#item.at(1)])
  }
  grid(
    columns: (12em, 1fr, auto),
    column-gutter: 10pt,
    row-gutter: 6pt,
    align: (right, left, right),
    ..cells,
  )
}

// ── key-figure — chiffre clé mis en valeur ─────────────────────────────────
#let key-figure(label, body) = _box(
  luma(240),
  navy,
  none,
  [#text(weight: "bold", fill: navy)[#label] : #body],
)

// ── alert-box — bloc d'alerte rouge ─────────────────────────────────────────
#let alert-box(body) = _box(rgb("#fef2f2"), red, none, body)

// ── grading-synth — cadre de grading pour ligne de jugement ────────────────
// Usage : #grading-synth("Affirmation", confiance: "Haute", sources: (("Nom", "https://..."),), note: "commentaire")
// Rétro-compatible : sources: ("src1", "src2") affiche du texte brut
#let grading-synth(claim, confiance: "Moyenne", sources: (), note: none) = {
  v(0.15cm)
  _box(luma(250), luma(190), none, {
    confidence-badge(confiance)
    h(4pt)
    claim
    if sources.len() > 0 [
      #v(3pt)
      #text(size: 8pt, fill: gray)[Sources : ]
      #text(size: 8pt, fill: gray)[
        #(
          sources
            .enumerate()
            .map(((i, src)) => {
              if type(src) == array and src.len() == 2 {
                let name = src.at(0)
                let url = src.at(1)
                link(url)[#name]
              } else {
                [#src]
              }
            })
            .join([, ])
        )
      ]
    ]
    if note != none [
      #v(3pt)
      #text(size: 8pt, style: "italic")[Note : #note]
    ]
  })
  v(0.15cm)
}

// ── small-table — réduit la fonte selon le nb de colonnes ───────────────────
//   4 cols → -10%, 5→-12%, 6→-14%, 9→-20%  ... n→ -(6+2n)%
//   Usage : #small-table(4, columns: (auto, auto, auto, auto), ... [cellules])
//   Premier argument = nombre de colonnes (explicite).
//   Les `set text` dans une fonction s'appliquent au rendu de cette fonction.
#let small-table(n, ..args) = {
  let sz = 0.98 - 0.02 * n
  set text(size: sz * 1em)
  table(..args)
}

// ╔═══════════════════════════════════════════════════════════════════════════╗
// ║  PARTIE B — COMPOSANTS PÉDAGOGIQUES (formation SDK pour agents IA)        ║
// ╚═══════════════════════════════════════════════════════════════════════════╝

// Objectifs pédagogiques — ouverture de module
#let obj-box(body) = _box(c-soft, c-primary, [Objectifs du module], body)

// Note informative
#let note-box(body) = _box(c-soft2, c-accent, none, body)

// Astuce / bonne pratique
#let tip-box(body) = _box(rgb("#f0fdf4"), c-ok, [Bonne pratique], body)

// Avertissement
#let warn-box(body) = _box(rgb("#fffbeb"), c-warn, [Attention], body)

// Piège fréquent
#let pitfall-box(body) = _box(rgb("#fef2f2"), c-danger, [Piège fréquent], body)

// Idée clé à retenir
#let key-box(body) = _box(c-soft, c-primary, [★ À retenir], body)

// Définition
#let def-box(term, body) = _box(luma(250), c-accent, none, {
  text(weight: "bold")[#term]
  h(6pt)
  text(fill: c-muted)[— définition]
  v(3pt)
  body
})

// Bloc de code (version helper1) — texte mono sur fond clair, pleine largeur
#let code-box(text-content) = block(
  width: 100%,
  fill: rgb("#f5f5f0"),
  stroke: (left: 3pt + luma(160)),
  radius: (right: 4pt),
  inset: 10pt,
  text(size: 9pt, font: "DejaVu Sans Mono")[#text-content],
)

// Exercice numéroté
#let exo-counter = counter("exo")
#let exo-box(title: none, body) = {
  exo-counter.step()
  let n = context exo-counter.get().first()
  _box(rgb("#f8fafc"), c-primary, none, {
    text(
      fill: c-primary,
      weight: "bold",
    )[Exercice #n.#if title != none [ — #title]]
    v(4pt)
    body
  })
}

// Barre de score proportionnelle (comparaison qualitative)
#let score-bar(label, val, max: 100, color: c-primary) = {
  let pct = calc.min(calc.max(val / max * 100, 0), 100)
  grid(
    columns: (11em, 1fr, auto),
    column-gutter: 10pt,
    row-gutter: 6pt,
    align(right, text(size: 0.85em)[#label]),
    pad(top: 3pt, bottom: 3pt, align(
      left,
      rect(width: pct * 1%, height: 8pt, fill: color, radius: 3pt),
    )),
    text(size: 0.8em, fill: c-muted)[#val],
  )
}

// Entrée de référence (source de vérité pour les liens)
#let ref-item(name, url, desc) = {
  block(inset: (bottom: 6pt))[
    - #link(url)[#name] : #desc
  ]
}

// Encadré de références (version helper1) — titre + liste, pleine largeur
#let ref-box(title, items) = block(
  width: 100%,
  fill: rgb("#f0f4f8"),
  stroke: (left: 3pt + rgb("#1a3c5e")),
  radius: (right: 4pt),
  inset: 10pt,
  [
    #text(weight: "bold", fill: rgb("#1a3c5e"))[📚 #title]
    #v(0.3em)
    #for item in items [
      - #item \
    ]
  ],
)

// Étiquette de niveau (débutant, intermédiaire...)
#let level-tag(niv) = box(
  radius: 999pt,
  fill: c-soft,
  stroke: 0.5pt + c-primary,
  inset: (x: 8pt, y: 3pt),
  text(size: 0.8em, fill: c-primary, weight: "semibold")[Niveau : #niv],
)

// Encadré résumé fin de module
#let recap-box(body) = _box(rgb("#f0fdf4"), c-ok, [Résumé du module], body)

// ----- Compléments de helper1, adaptés à la palette -----

// Bloc mathématiques / formules
#let math-box(title, steps) = _box(
  rgb("#e8f1f8"),
  c-primary,
  [#box(circle(fill: c-primary, radius: 2.5pt))#h(0.3em)#title],
  [
    #for s in steps [
      - #s \
    ]
  ],
)

// Encadré « Intuition d'abord » (approche pédagogique progressive)
#let intuition-box(body) = _box(
  rgb("#eaf6f1"),
  c-ok,
  [🤔 Intuition d'abord],
  body,
)
