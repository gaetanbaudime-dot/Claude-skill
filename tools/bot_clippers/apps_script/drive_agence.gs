/**
 * Drive de l'agence pour le bot clippers (machine horizontale v2, 23/09/2026).
 *
 * Pourquoi ce script : un compte de service Google n'a AUCUN espace de stockage (Google le refuse
 * depuis 2025 : « Service Accounts do not have storage quota »). Il peut lire et créer des dossiers,
 * mais pas copier une photo ni déposer un Reel. Ce script tourne sous le compte Google de l'agence
 * (celui qui le déploie), avec son espace : c'est lui qui copie les photos et Reels d'une créatrice
 * dans le dossier personnel d'un clipper, partage ce dossier en lecture, et reçoit les Reels spoofés.
 *
 * Déploiement (une fois, 2 minutes, connecté avec le compte de l'agence) :
 *   1. script.google.com → Nouveau projet → coller ce fichier → remplacer SECRET par une phrase longue.
 *   2. Déployer → Nouveau déploiement → type « Application Web » → Exécuter en tant que : Moi →
 *      Accès : Tout le monde → Déployer → autoriser (Paramètres avancés → Accéder au projet).
 *   3. Copier l'URL « /exec » et la poser dans Railway : DRIVE_AGENCE_URL, avec DRIVE_AGENCE_SECRET.
 *
 * Toutes les requêtes sont des POST JSON : {"secret": "...", "action": "...", ...}.
 * Réponse : {"ok": true, ...} ou {"ok": false, "erreur": "..."}.
 */

var SECRET = "CHANGE-MOI-phrase-longue-et-secrete";
var BUDGET_MS = 4.5 * 60 * 1000;          // Apps Script coupe à 6 min : on rend la main avant, le bot rappelle

function doGet() {
  return _json({ ok: true, compte: Session.getEffectiveUser().getEmail(), message: "POST attendu" });
}

function doPost(e) {
  var debut = Date.now();
  try {
    var corps = JSON.parse((e && e.postData && e.postData.contents) || "{}");
    if (!corps.secret || corps.secret !== SECRET) return _json({ ok: false, erreur: "secret invalide" });
    switch (corps.action) {
      case "ping":
        return _json({ ok: true, compte: Session.getEffectiveUser().getEmail() });
      case "copier":
        return _json(copier(corps, debut));
      case "partager":
        return _json(partager(corps));
      case "televerser":
        return _json(televerser(corps));
      case "lister":
        return _json(lister(corps));
      case "supprimer":
        return _json(supprimer(corps));
      default:
        return _json({ ok: false, erreur: "action inconnue : " + corps.action });
    }
  } catch (err) {
    return _json({ ok: false, erreur: String(err && err.message ? err.message : err) });
  }
}

/** Copie `source` (dossier) dans `parent`/`nom`, sous-dossiers compris. Idempotent : un fichier déjà
 *  présent (même nom) est sauté. `types` : ["image", "video"] pour ne copier que ces familles.
 *  Rend la main avant la limite de temps avec reste=true ; le bot rappelle jusqu'à reste=false. */
function copier(c, debut) {
  var source = DriveApp.getFolderById(c.source);
  var parent = DriveApp.getFolderById(c.parent);
  var cible = _dossierOuCree(parent, c.nom);
  var etat = { ok: true, id: cible.getId(), url: cible.getUrl(), copies: 0, sautes: 0, reste: false,
               max: Number(c.max || 0), sous: c.sous ? String(c.sous) : "" };
  var dest = etat.sous ? _dossierOuCree(cible, etat.sous) : cible;     // ex. sous = "Photos" ou "Reels"
  _copierDans(source, dest, c.types || null, etat, debut);
  return etat;
}

function _copierDans(source, cible, types, etat, debut) {
  var existants = {};
  var it = cible.getFiles();
  while (it.hasNext()) existants[it.next().getName()] = true;
  var fichiers = source.getFiles();
  while (fichiers.hasNext()) {
    if (Date.now() - debut > BUDGET_MS) { etat.reste = true; return; }
    var f = fichiers.next();
    if (types && !_typeOk(f.getMimeType(), types)) continue;
    if (etat.max && etat.copies + etat.sautes >= etat.max) return;   // assez de fichiers pour ce clipper
    if (existants[f.getName()]) { etat.sautes++; continue; }
    f.makeCopy(f.getName(), cible);
    etat.copies++;
  }
  var dossiers = source.getFolders();
  while (dossiers.hasNext()) {
    if (Date.now() - debut > BUDGET_MS) { etat.reste = true; return; }
    var d = dossiers.next();
    _copierDans(d, _dossierOuCree(cible, d.getName()), types, etat, debut);
    if (etat.reste) return;
  }
}

function _typeOk(mime, types) {
  for (var i = 0; i < types.length; i++) {
    if (types[i] === "image" && mime.indexOf("image/") === 0) return true;
    if (types[i] === "video" && mime.indexOf("video/") === 0) return true;
    if (types[i] === "tout") return true;
  }
  return false;
}

function _dossierOuCree(parent, nom) {
  var it = parent.getFoldersByName(nom);
  return it.hasNext() ? it.next() : parent.createFolder(nom);
}

/** Partage un dossier ou un fichier à une adresse : role "reader" (défaut) ou "writer". */
function partager(c) {
  var cible = _parId(c.id);
  if (c.role === "writer") cible.addEditor(c.email); else cible.addViewer(c.email);
  return { ok: true, id: c.id, url: cible.getUrl() };
}

/** Dépose un fichier envoyé en base64 (Reel spoofé, fiche) dans `parent`. Remplace un homonyme. */
function televerser(c) {
  var parent = DriveApp.getFolderById(c.parent);
  var it = parent.getFilesByName(c.nom);
  while (it.hasNext()) it.next().setTrashed(true);
  var blob = Utilities.newBlob(Utilities.base64Decode(c.base64), c.mime || "application/octet-stream", c.nom);
  var f = parent.createFile(blob);
  return { ok: true, id: f.getId(), url: f.getUrl(), taille: f.getSize() };
}

function lister(c) {
  var dossier = DriveApp.getFolderById(c.id);
  var out = [];
  var it = dossier.getFiles();
  while (it.hasNext()) { var f = it.next(); out.push({ id: f.getId(), nom: f.getName(), mime: f.getMimeType(), taille: f.getSize() }); }
  var dd = dossier.getFolders();
  while (dd.hasNext()) { var d = dd.next(); out.push({ id: d.getId(), nom: d.getName(), mime: "dossier" }); }
  return { ok: true, id: c.id, elements: out };
}

function supprimer(c) {
  _parId(c.id).setTrashed(true);
  return { ok: true, id: c.id };
}

function _parId(id) {
  try { return DriveApp.getFolderById(id); } catch (e) { return DriveApp.getFileById(id); }
}

function _json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
