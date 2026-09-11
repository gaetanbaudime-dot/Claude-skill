/**
 * ════════════════════════════════════════════════════════════════
 * G&M AGENCY — AUTO-STATUS DRIVE  (VERSION v5 — tout le Marketing)
 * ════════════════════════════════════════════════════════════════
 *
 * NOUVEAUTÉS v5 (par rapport à la v4 du 20 juin, bug fix Lila) :
 *   ★ TOUT LE DOSSIER MARKETING de chaque créatrice est parcouru :
 *     Instagram, Facebook, TikTok, YouTube, Stories… et tous les
 *     dossiers de contenu (Reels, Carrousel, Story, Photos…), quel
 *     que soit leur nom. Plus de liste NOMS_INSTAGRAM / NOMS_CONTENU.
 *   ★ MOIS SANS ANNÉE : un dossier qui contient directement
 *     « 1. Janvier … 12. Décembre » (ex. Instagram/Carrousel) est
 *     traité comme l'année en cours — la v4 l'ignorait (pas de
 *     « 2026 » dans le nom), d'où les Carrousels jamais marqués.
 *   ★ MOIS MANQUANTS CRÉÉS : dans l'année en cours (explicite ou
 *     implicite), les 12 mois existent toujours (« 1. Janvier » …).
 *     Rien n'est créé dans les archives des années passées.
 *   ★ FICHIERS EN VRAC RANGÉS : un fichier posé à la racine d'un
 *     dossier de contenu ou d'un dossier année part dans le mois de
 *     sa date de création — seulement si son année correspond,
 *     sinon il reste où il est et le journal le signale.
 *   ★ BILAN DISCORD facultatif (propriété DISCORD_WEBHOOK_URL).
 *
 * CONSERVÉ de la v4 : emoji EN FIN de nom (« 1. Janvier ✅ »),
 * pas d'emoji sur un mois futur vide, verrou, checkpoint par
 * créatrice + trigger de continuation, dry-run, scan complet,
 * skip des ✅ passés, fichiers système ignorés, trigger 6 h.
 *
 * MISE À JOUR : dans le projet Apps Script existant (« G&M Auto-Status
 * Drive »), remplace TOUT le code par ce fichier, Enregistrer, puis
 * lance `lancerEnDryRun` (simulation) → `lancerManuellement`. Le
 * trigger _lancerAuto déjà installé continue de marcher tel quel.
 * ════════════════════════════════════════════════════════════════
 */


// ──────────────────────────────────────────────
// CONFIG
// ──────────────────────────────────────────────

// Une ligne par créatrice : le dossier MARKETING (pas Instagram) — id = fin de l'URL du dossier.
var CREATRICES = [
  { nom: "Jade",      id: "" },
  { nom: "Amandine",  id: "" },
  { nom: "Naomie",    id: "" },
  { nom: "Mad",       id: "" },
  { nom: "Sophie",    id: "" },
  { nom: "Chloé",     id: "" },
  { nom: "Capucine",  id: "" },
  { nom: "Lila",      id: "" },
  { nom: "Lily",      id: "" }
];

var MOIS_NOMS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Aout",
                 "Septembre", "Octobre", "Novembre", "Décembre"];

var FICHIERS_IGNORES = [".DS_Store", "Thumbs.db", "desktop.ini"];
// Dossiers jamais parcourus (majuscules/minuscules et emojis ignorés).
var DOSSIERS_EXCLUS = ["corbeille", "trash", "old", "ne pas toucher"];

var PROFONDEUR_MAX = 8;
var PAUSE_RENAME_MS = 50;
var MAX_EXEC_MS = 270000;
var CONTINUATION_DELAY_S = 90;
var HANDLER_AUTO = "_lancerAuto";
var HEURE_TRIGGER = 6;
var SKIP_DONE_PAST_DEFAULT = true;
var CREER_MOIS_MANQUANTS = true;
var RANGER_FICHIERS_EN_VRAC = true;

var LAST_RUN_KEY             = "GM_AUTOSTATUS_LAST_RUN";
var DRY_RUN_KEY              = "GM_AUTOSTATUS_DRY_RUN";
var FULL_SCAN_KEY            = "GM_AUTOSTATUS_FULL_SCAN";
var CHECKPOINT_KEY           = "GM_CHECKPOINT_CREATOR";
var LAST_DAILY_RESET_KEY     = "GM_LAST_DAILY_RESET";
var CONTINUATION_TRIGGER_KEY = "GM_CONTINUATION_TRIGGER_ID";
var WEBHOOK_KEY              = "DISCORD_WEBHOOK_URL";


// ──────────────────────────────────────────────
// ▶ POINTS D'ENTRÉE
// ──────────────────────────────────────────────

function lancerManuellement() {
  var props = PropertiesService.getScriptProperties();
  props.deleteProperty(DRY_RUN_KEY);
  props.deleteProperty(FULL_SCAN_KEY);
  props.deleteProperty(CHECKPOINT_KEY);
  _runWithLock("Lancement manuel (rapide, skip ✅)");
}

function lancerScanComplet() {
  var props = PropertiesService.getScriptProperties();
  props.deleteProperty(DRY_RUN_KEY);
  props.setProperty(FULL_SCAN_KEY, "1");
  props.deleteProperty(CHECKPOINT_KEY);
  _runWithLock("SCAN COMPLET — re-vérifie tout, ignore les ✅ existants");
  props.deleteProperty(FULL_SCAN_KEY);
}

function lancerEnDryRun() {
  var props = PropertiesService.getScriptProperties();
  props.setProperty(DRY_RUN_KEY, "1");
  props.deleteProperty(FULL_SCAN_KEY);
  props.deleteProperty(CHECKPOINT_KEY);
  _runWithLock("Lancement DRY-RUN (aucun renommage, aucune création, aucun déplacement)");
  props.deleteProperty(DRY_RUN_KEY);
}

function _lancerAuto() {
  var props = PropertiesService.getScriptProperties();
  props.deleteProperty(DRY_RUN_KEY);
  _supprimerTriggerContinuation(props);

  var today = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd");
  var lastReset = props.getProperty(LAST_DAILY_RESET_KEY);
  if (lastReset !== today) {
    props.setProperty(LAST_DAILY_RESET_KEY, today);
    props.deleteProperty(CHECKPOINT_KEY);
    Logger.log("🔄 Nouveau jour — checkpoint effacé, on repart de la première créatrice");
  }

  _runWithLock("Lancement auto");
}


// ──────────────────────────────────────────────
// ⏰ TRIGGERS
// ──────────────────────────────────────────────

function setupTrigger6h() {
  var supprimes = removeTrigger6h();
  ScriptApp.newTrigger(HANDLER_AUTO)
    .timeBased()
    .everyDays(1)
    .atHour(HEURE_TRIGGER)
    .create();
  Logger.log("✅ Trigger créé — " + HANDLER_AUTO + "() à " + HEURE_TRIGGER + "h chaque matin"
             + (supprimes > 0 ? "  (" + supprimes + " ancien(s) remplacé(s))" : ""));
}

function removeTrigger6h() {
  var n = 0;
  ScriptApp.getProjectTriggers().forEach(function(t) {
    if (t.getHandlerFunction() === HANDLER_AUTO) {
      ScriptApp.deleteTrigger(t);
      n++;
    }
  });
  if (n > 0) Logger.log("🗑️  " + n + " trigger(s) " + HANDLER_AUTO + " supprimé(s)");
  return n;
}

function listerTriggers() {
  var triggers = ScriptApp.getProjectTriggers();
  if (!triggers.length) { Logger.log("ℹ️ Aucun trigger configuré"); return; }
  triggers.forEach(function(t) {
    Logger.log("• " + t.getHandlerFunction()
               + "  type="   + t.getEventType()
               + "  source=" + t.getTriggerSource());
  });
}

function _creerTriggerContinuation(props) {
  _supprimerTriggerContinuation(props);
  var trigger = ScriptApp.newTrigger(HANDLER_AUTO)
    .timeBased()
    .after(CONTINUATION_DELAY_S * 1000)
    .create();
  props.setProperty(CONTINUATION_TRIGGER_KEY, trigger.getUniqueId());
  Logger.log("⏭️ Trigger de continuation créé — relance dans " + CONTINUATION_DELAY_S + "s");
}

function _supprimerTriggerContinuation(props) {
  var id = props.getProperty(CONTINUATION_TRIGGER_KEY);
  if (!id) return;
  ScriptApp.getProjectTriggers().forEach(function(t) {
    if (t.getUniqueId() === id) {
      ScriptApp.deleteTrigger(t);
    }
  });
  props.deleteProperty(CONTINUATION_TRIGGER_KEY);
}


// ──────────────────────────────────────────────
// VERROU
// ──────────────────────────────────────────────

function _runWithLock(libelle) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(10 * 1000)) {
    Logger.log("⚠️ Une autre exécution est déjà en cours — abandon");
    return;
  }
  try {
    Logger.log("▶ " + libelle + " — " + new Date().toLocaleString("fr-FR"));
    _main();
    PropertiesService.getScriptProperties().setProperty(LAST_RUN_KEY, new Date().toISOString());
  } catch (e) {
    Logger.log("⛔ Erreur globale : " + (e && e.message ? e.message : e));
  } finally {
    lock.releaseLock();
  }
}


// ──────────────────────────────────────────────
// MAIN
// ──────────────────────────────────────────────

function _main() {
  var startTime = Date.now();
  var date      = _getDate();
  var dryRun    = _isDryRun();
  var props     = PropertiesService.getScriptProperties();

  var startIndex = parseInt(props.getProperty(CHECKPOINT_KEY) || "0", 10);
  if (isNaN(startIndex) || startIndex < 0 || startIndex >= CREATRICES.length) startIndex = 0;

  Logger.log("Date pivot — Année=" + date.annee + "  Mois=" + date.mois + "  Semaine=" + date.semaine
             + (dryRun ? "  MODE=DRY-RUN" : "")
             + (startIndex > 0 ? "  [Reprise depuis " + CREATRICES[startIndex].nom + "]" : ""));

  var stats = { scanned: 0, renamed: 0, created: 0, moved: 0, unmoved: 0, errors: 0, ignored: 0, skipped: 0,
                readonly: [], details: [] };

  for (var i = startIndex; i < CREATRICES.length; i++) {

    var elapsed = Date.now() - startTime;
    if (elapsed > MAX_EXEC_MS) {
      props.setProperty(CHECKPOINT_KEY, i.toString());
      _creerTriggerContinuation(props);
      Logger.log("⏸️ Limite de temps approchée (" + Math.round(elapsed/1000) + "s)"
                 + " — checkpoint sauvegardé à " + CREATRICES[i].nom
                 + ", continuation dans " + CONTINUATION_DELAY_S + "s");
      _logStats(stats, dryRun);
      return;
    }

    var c = CREATRICES[i];
    if (!c.id) { Logger.log("\n━━ " + c.nom + " ━━ (pas d'identifiant : ligne ignorée)"); continue; }
    Logger.log("\n━━ " + c.nom + " ━━");
    try {
      _traiterCreatrice(c, date, stats, dryRun);
    } catch (e) {
      Logger.log("⚠️ Erreur " + c.nom + " : " + (e && e.message ? e.message : e));
      stats.errors++;
    }
  }

  props.deleteProperty(CHECKPOINT_KEY);

  Logger.log("\n✅ Terminé — " + new Date().toLocaleTimeString("fr-FR")
             + "  (" + Math.round((Date.now() - startTime) / 1000) + "s)");
  _logStats(stats, dryRun);
  _envoyerBilanDiscord(stats, dryRun, date);
}

function _logStats(stats, dryRun) {
  Logger.log("   📊 Dossiers scannés     : " + stats.scanned);
  Logger.log("   ✏️  Renommages          : " + stats.renamed + (dryRun ? "  (simulés)" : ""));
  Logger.log("   ➕ Mois créés           : " + stats.created + (dryRun ? "  (simulés)" : ""));
  Logger.log("   🗂️  Fichiers rangés     : " + stats.moved + (dryRun ? "  (simulés)" : "")
             + (stats.unmoved ? "   (" + stats.unmoved + " laissé(s) : année différente)" : ""));
  Logger.log("   ⏭️  Dossiers ignorés    : " + stats.ignored + "  (hors pattern)");
  Logger.log("   ⚡ Sous-arbres skippés  : " + stats.skipped + "  (déjà ✅)");
  Logger.log("   🔒 Lecture seule        : " + stats.readonly.length + (stats.readonly.length ? "  → " + stats.readonly.slice(0, 6).join(" · ") : ""));
  Logger.log("   ⚠️  Erreurs locales     : " + stats.errors);
}

function _envoyerBilanDiscord(stats, dryRun, date) {
  var url = PropertiesService.getScriptProperties().getProperty(WEBHOOK_KEY);
  if (!url || dryRun) return;
  var texte = "📁 **Drive créatrices — " + Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "dd/MM HH:mm") + "**"
    + "\n✏️ " + stats.renamed + " renommage(s) · ➕ " + stats.created + " mois créé(s) · 🗂️ " + stats.moved + " fichier(s) rangé(s)"
    + (stats.unmoved ? " · " + stats.unmoved + " laissé(s) (année différente)" : "")
    + (stats.readonly.length ? "\n🔒 Lecture seule (non modifiables) : " + stats.readonly.slice(0, 8).join(" · ") : "")
    + (stats.errors ? "\n⚠️ " + stats.errors + " erreur(s) — voir le journal d'exécution" : "")
    + (stats.details.length ? "\n" + stats.details.slice(0, 12).join("\n") : "");
  try {
    UrlFetchApp.fetch(url, { method: "post", contentType: "application/json",
                             payload: JSON.stringify({ content: texte.slice(0, 1900) }), muteHttpExceptions: true });
  } catch (e) {
    Logger.log("⚠️ Discord injoignable : " + e);
  }
}


// ──────────────────────────────────────────────
// NIVEAU 0 : CRÉATRICE → tout le dossier Marketing
// ──────────────────────────────────────────────

function _traiterCreatrice(c, date, stats, dryRun) {
  var marketing;
  try {
    marketing = DriveApp.getFolderById(c.id);
  } catch (e) {
    Logger.log("  ❌ Marketing introuvable (ID invalide ou permissions manquantes)");
    stats.errors++;
    return;
  }
  Logger.log("  📂 Marketing : " + marketing.getName());
  var avant = { renamed: stats.renamed, created: stats.created, moved: stats.moved };
  _traiterDossier(marketing, null, date, stats, dryRun, 0, c.nom);
  var d = (stats.renamed - avant.renamed) + (stats.created - avant.created) + (stats.moved - avant.moved);
  if (d > 0) stats.details.push("· " + c.nom + " : " + (stats.renamed - avant.renamed) + " renommé(s), "
                                + (stats.created - avant.created) + " créé(s), " + (stats.moved - avant.moved) + " rangé(s)");
}


// ──────────────────────────────────────────────
// PARCOURS GÉNÉRIQUE
//   Un dossier peut contenir : des ANNÉES (« 2026 », « Archives 2025 »),
//   des MOIS (« 1. Janvier »), ou d'autres dossiers (Instagram, Reels…)
//   dans lesquels on descend. Retourne true si un fichier existe
//   quelque part dessous (pour marquer le parent).
// ──────────────────────────────────────────────

function _traiterDossier(dossier, anneeContexte, date, stats, dryRun, profondeur, chemin) {
  if (profondeur > PROFONDEUR_MAX) return _aContenuRecursif(dossier);
  var enfants = _listerEnfants(dossier);
  var annees = [], mois = [], autres = [];
  for (var i = 0; i < enfants.length; i++) {
    var f = enfants[i];
    var nom = _nettoyer(f.getName());
    if (_estExclu(nom)) { stats.ignored++; continue; }
    if (_numMois(nom) > 0) mois.push(f);
    else if (_extraireAnnee(nom) !== null) annees.push(f);
    else autres.push(f);
  }
  var aContenu = false;

  // A. Années explicites → chacune est traitée comme un conteneur de mois.
  for (var a = 0; a < annees.length; a++) {
    if (_traiterAnnee(annees[a], date, stats, dryRun, profondeur, chemin)) aContenu = true;
  }

  // B. Mois posés directement ici (ex. Instagram/Carrousel/1. Janvier) : année implicite.
  if (mois.length) {
    var annee = (anneeContexte !== null) ? anneeContexte : date.annee;
    if (_traiterConteneurDeMois(dossier, mois, annee, date, stats, dryRun, chemin)) aContenu = true;
  }

  // C. Autres dossiers (Instagram, Facebook, Reels, Carrousel, Story…) : on descend.
  for (var o = 0; o < autres.length; o++) {
    var sous = autres[o];
    var nomS = _nettoyer(sous.getName());
    stats.scanned++;
    if (_traiterDossier(sous, anneeContexte, date, stats, dryRun, profondeur + 1, chemin + "/" + nomS)) aContenu = true;
  }

  if (!aContenu && _aFichiersDirects(dossier)) aContenu = true;
  return aContenu;
}

function _traiterAnnee(dossierAnnee, date, stats, dryRun, profondeur, chemin) {
  var nomBrut = dossierAnnee.getName();
  var nom     = _nettoyer(nomBrut);
  var annee   = _extraireAnnee(nom);
  var estActive = annee === date.annee;
  var estPasse  = annee <  date.annee;
  stats.scanned++;

  if (_shouldSkipDone() && estPasse && _aEmoji(nomBrut, "✅")) {
    stats.skipped++;
    return true;
  }
  var aContenu = _traiterDossier(dossierAnnee, annee, date, stats, dryRun, profondeur + 1, chemin + "/" + nom);

  var emoji = null;
  if      (aContenu)  emoji = "✅";
  else if (estActive) emoji = "⏳";
  else if (estPasse)  emoji = "❌";
  _renommerSafe(dossierAnnee, nom, emoji, stats, dryRun, chemin);
  return aContenu;
}


// ──────────────────────────────────────────────
// CONTENEUR DE MOIS (année explicite ou implicite)
// ──────────────────────────────────────────────

function _traiterConteneurDeMois(dossier, moisTrouves, annee, date, stats, dryRun, chemin) {
  var estAnneeActive = annee === date.annee;
  var estAnneePasse  = annee <  date.annee;
  var estAnneeFuture = annee >  date.annee;
  var parMois = {};
  for (var i = 0; i < moisTrouves.length; i++) {
    var n = _numMois(_nettoyer(moisTrouves[i].getName()));
    if (!parMois[n]) parMois[n] = moisTrouves[i];
  }

  // 1. Les 12 mois existent (année en cours seulement — jamais dans les archives).
  if (CREER_MOIS_MANQUANTS && estAnneeActive) {
    for (var m = 1; m <= 12; m++) {
      if (parMois[m]) continue;
      var nomMois = m + ". " + MOIS_NOMS[m - 1];
      if (dryRun) {
        Logger.log("    🧪 [DRY-RUN]  créer " + chemin + "/" + nomMois);
        stats.created++;
        continue;
      }
      try {
        parMois[m] = dossier.createFolder(nomMois);
        stats.created++;
        Logger.log("    ➕ " + chemin + "/" + nomMois);
      } catch (e) {
        _lectureSeule(stats, chemin + " (création de " + nomMois + ")");
        break;
      }
    }
  }

  // 2. Les fichiers en vrac à ce niveau vont dans le mois de leur date de création (même année).
  if (RANGER_FICHIERS_EN_VRAC) {
    var fichiers = _listerFichiers(dossier);
    for (var k = 0; k < fichiers.length; k++) {
      var f = fichiers[k];
      var dc = f.getDateCreated();
      var anneeF = parseInt(Utilities.formatDate(dc, Session.getScriptTimeZone(), "yyyy"), 10);
      var moisF  = parseInt(Utilities.formatDate(dc, Session.getScriptTimeZone(), "M"), 10);
      if (anneeF !== annee || !parMois[moisF]) {
        stats.unmoved++;
        Logger.log("    ↔️ laissé en place (année " + anneeF + " ≠ " + annee + " ou mois absent) : " + chemin + "/" + f.getName());
        continue;
      }
      if (dryRun) {
        Logger.log("    🧪 [DRY-RUN]  ranger " + f.getName() + " → " + _nettoyer(parMois[moisF].getName()));
        stats.moved++;
        continue;
      }
      try {
        f.moveTo(parMois[moisF]);
        stats.moved++;
        Logger.log("    🗂️ " + f.getName() + " → " + _nettoyer(parMois[moisF].getName()));
      } catch (e) {
        stats.errors++;
        Logger.log("    ⛔ Déplacement refusé pour " + f.getName() + " : " + (e && e.message ? e.message : e));
      }
    }
  }

  // 3. Chaque mois : semaines → tenues, puis son statut.
  var conteneurAContenu = false;
  for (var mm = 1; mm <= 12; mm++) {
    var sub = parMois[mm];
    if (!sub) continue;
    try {
      var nomBrut = sub.getName();
      var nom     = _nettoyer(nomBrut);
      var enCours, passe, future;
      if (estAnneePasse)       { enCours = false;            passe = true;            future = false; }
      else if (estAnneeFuture) { enCours = false;            passe = false;           future = true;  }
      else                     { enCours = mm === date.mois; passe = mm < date.mois;  future = mm > date.mois; }

      if (_shouldSkipDone() && passe && _aEmoji(nomBrut, "✅")) {
        conteneurAContenu = true;
        stats.skipped++;
        continue;
      }
      stats.scanned++;

      var aContenu = _traiterSemaines(sub, enCours, passe, future, date, stats, dryRun);
      if (!aContenu) aContenu = _aFichiersDirects(sub);
      if (aContenu) conteneurAContenu = true;

      var emoji = null;
      if      (aContenu) emoji = "✅";
      else if (enCours)  emoji = "⏳";
      else if (passe)    emoji = "❌";
      _renommerSafe(sub, nom, emoji, stats, dryRun, chemin);
    } catch (e) {
      Logger.log("      ⚠️ Erreur mois " + sub.getName() + " : " + (e && e.message ? e.message : e));
      stats.errors++;
    }
  }
  return conteneurAContenu;
}


// ──────────────────────────────────────────────
// NIVEAU SEMAINES (inchangé v4)
// ──────────────────────────────────────────────

function _traiterSemaines(dossierMois, moisEnCours, moisPasse, moisFuture, date, stats, dryRun) {
  var moisAContenu = false;

  var iter = dossierMois.getFolders();
  while (iter.hasNext()) {
    var sub = iter.next();
    try {
      var nom = _nettoyer(sub.getName());
      var num = _numSemaine(nom);

      if (num === 0) {
        if (_aContenuRecursif(sub)) moisAContenu = true;
        stats.ignored++;
        continue;
      }
      stats.scanned++;

      var enCours, passe, future;
      if (moisPasse) {
        enCours = false; passe = true;  future = false;
      } else if (moisFuture) {
        enCours = false; passe = false; future = true;
      } else if (moisEnCours) {
        enCours = num === date.semaine;
        passe   = num <  date.semaine;
        future  = num >  date.semaine;
      } else {
        enCours = false; passe = true;  future = false;
      }

      var aContenu = _traiterTenues(sub, enCours, passe, future, stats, dryRun);
      if (!aContenu) aContenu = _aFichiersDirects(sub);

      if (aContenu) moisAContenu = true;

      var emoji = null;
      if      (aContenu) emoji = "✅";
      else if (enCours)  emoji = "⏳";
      else if (passe)    emoji = "❌";

      _renommerSafe(sub, nom, emoji, stats, dryRun, "");
    } catch (e) {
      Logger.log("        ⚠️ Erreur semaine " + sub.getName() + " : " + (e && e.message ? e.message : e));
      stats.errors++;
    }
  }

  return moisAContenu;
}


// ──────────────────────────────────────────────
// NIVEAU TENUES (inchangé v4)
// ──────────────────────────────────────────────

function _traiterTenues(dossierSemaine, semaineEnCours, semainePasse, semaineFuture, stats, dryRun) {
  var semaineAContenu = false;

  var iter = dossierSemaine.getFolders();
  while (iter.hasNext()) {
    var sub = iter.next();
    try {
      var nom = _nettoyer(sub.getName());
      var num = _numTenue(nom);

      if (num === 0) {
        if (_aContenuRecursif(sub)) semaineAContenu = true;
        stats.ignored++;
        continue;
      }
      stats.scanned++;

      var aContenu = _aContenuRecursif(sub);
      if (aContenu) semaineAContenu = true;

      var emoji = null;
      if      (aContenu)       emoji = "✅";
      else if (semaineEnCours) emoji = "⏳";
      else if (semainePasse)   emoji = "❌";

      _renommerSafe(sub, nom, emoji, stats, dryRun, "");
    } catch (e) {
      Logger.log("          ⚠️ Erreur tenue " + sub.getName() + " : " + (e && e.message ? e.message : e));
      stats.errors++;
    }
  }

  return semaineAContenu;
}


// ──────────────────────────────────────────────
// SCAN DE CONTENU
// ──────────────────────────────────────────────

function _aContenuRecursif(dossier) {
  if (_aFichiersDirects(dossier)) return true;
  var iter = dossier.getFolders();
  while (iter.hasNext()) {
    if (_aContenuRecursif(iter.next())) return true;
  }
  return false;
}

function _aFichiersDirects(dossier) {
  var iter = dossier.getFiles();
  while (iter.hasNext()) {
    var f = iter.next();
    if (FICHIERS_IGNORES.indexOf(f.getName()) === -1) return true;
  }
  return false;
}

function _listerEnfants(dossier) {
  var out = [];
  var iter = dossier.getFolders();
  while (iter.hasNext()) out.push(iter.next());
  return out;
}

function _listerFichiers(dossier) {
  var out = [];
  var iter = dossier.getFiles();
  while (iter.hasNext()) {
    var f = iter.next();
    if (FICHIERS_IGNORES.indexOf(f.getName()) === -1) out.push(f);
  }
  return out;
}


// ──────────────────────────────────────────────
// RENOMMAGE
// ──────────────────────────────────────────────

function _renommerSafe(dossier, nomPropre, emoji, stats, dryRun, chemin) {
  var nouveauNom = emoji ? nomPropre + " " + emoji : nomPropre;
  var nomActuel  = dossier.getName();
  if (nomActuel === nouveauNom) return;

  if (dryRun) {
    Logger.log("    🧪 [DRY-RUN]  " + nomActuel + "  →  " + nouveauNom);
    stats.renamed++;
    return;
  }

  try {
    dossier.setName(nouveauNom);
    stats.renamed++;
    Logger.log("    ✏️ " + nouveauNom);
    if (PAUSE_RENAME_MS > 0) Utilities.sleep(PAUSE_RENAME_MS);
  } catch (e) {
    _lectureSeule(stats, (chemin ? chemin + "/" : "") + nomActuel);
  }
}

function _lectureSeule(stats, libelle) {
  if (stats.readonly.indexOf(libelle) === -1) stats.readonly.push(libelle);
  stats.errors++;
  Logger.log("    🔒 Lecture seule : " + libelle);
}


// ──────────────────────────────────────────────
// NORMALISATION DE NOMS
// ──────────────────────────────────────────────

function _nettoyer(nom) {
  var n = nom || "";
  n = n.replace(/^[\s❌✅⏳]+/, "");
  n = n.replace(/[\s❌✅⏳]+$/, "");
  n = n.replace(/^\([^)]*\)\s*/, "");
  return n.replace(/\s+/g, " ").trim();
}

function _normaliser(nom) {
  return _nettoyer(nom).toLowerCase();
}

function _estExclu(nomPropre) {
  var n = nomPropre.toLowerCase().replace(/[^a-zà-ÿ0-9 ]/g, "").trim();
  for (var i = 0; i < DOSSIERS_EXCLUS.length; i++) {
    if (n === DOSSIERS_EXCLUS[i]) return true;
  }
  return false;
}


// ──────────────────────────────────────────────
// EXTRACTION D'INDICES
// ──────────────────────────────────────────────

function _extraireAnnee(nom) {
  var m = nom.match(/\b(20\d{2})\b/);
  return m ? parseInt(m[1], 10) : null;
}

function _numMois(nom) {
  var m = nom.match(/^(\d{1,2})\s*[.\-–]\s*/);
  if (!m) return 0;
  var n = parseInt(m[1], 10);
  return (n >= 1 && n <= 12) ? n : 0;
}

function _numSemaine(nom) {
  var m = nom.match(/^semaine\s+(\d+)/i);
  return m ? parseInt(m[1], 10) : 0;
}

function _numTenue(nom) {
  var m = nom.match(/^tenue\s+(\d+)/i);
  return m ? parseInt(m[1], 10) : 0;
}


// ──────────────────────────────────────────────
// DATE PIVOT
// ──────────────────────────────────────────────

function _getDate() {
  var now  = new Date();
  var jour = now.getDate();
  var sem  = jour <= 7 ? 1 : jour <= 14 ? 2 : jour <= 21 ? 3 : 4;
  return { annee: now.getFullYear(), mois: now.getMonth() + 1, semaine: sem };
}


// ──────────────────────────────────────────────
// FLAGS RUNTIME
// ──────────────────────────────────────────────

function _isDryRun() {
  return PropertiesService.getScriptProperties().getProperty(DRY_RUN_KEY) === "1";
}

function _shouldSkipDone() {
  if (PropertiesService.getScriptProperties().getProperty(FULL_SCAN_KEY) === "1") return false;
  return SKIP_DONE_PAST_DEFAULT;
}

function _aEmoji(nomBrut, emoji) {
  if (!nomBrut) return false;
  var s = nomBrut.replace(/\s+$/, "");
  return s.length > 0 && s.charAt(s.length - 1) === emoji;
}
