/** Les quatre tuiles Drive d'un clipper (08/10, Gaëtan) : **Carrousel · Reels · Stories · TOP 20 Reels**. Chaque tuile ouvre
 *  le DOSSIER RACINE de la section dans l'app Google Drive (le clipper descend lui-même dans le mois ou la semaine), et
 *  affiche l'état du dossier du moment : ✅ plein · ⏳ en cours de remplissage · ❌ dossier vide.
 *
 *  Racines (jamais créées ici : c'est le bot et le script Drive de l'agence qui créent les dossiers) :
 *  Reels     → la source Reels de sa créatrice (DRIVE_SOURCES), sinon le dossier Reels de CREATRICES_JSON ;
 *  Carrousel → la source « Carrousel » si elle existe, sinon le dossier « Carrousel » du dossier Instagram de la créatrice
 *              (le parent de « 🎬 Clippers »), sinon la source Photos ;
 *  Stories   → la source Stories, sinon le dossier « Stories » du dossier Instagram de la créatrice ;
 *  TOP 20    → 🎬 Clippers / <Prénom> / TOP 20 Reels (ses variantes uniques, déposées par le bot), sinon le TOP 20 de la créatrice.
 *
 *  Dossier « du moment » (celui dont on affiche l'état) : Reels = année → mois → semaine en cours ; Carrousel et Stories =
 *  année → mois en cours (ou la racine s'il n'y a pas de mois) ; TOP 20 = le dossier lui-même. Un mois ou une semaine
 *  absents font reculer au plus récent existant. L'état se lit en comptant les fichiers du dossier du moment (jamais les
 *  sous-dossiers ni les raccourcis) : 0 → ❌ vide ; sous le seuil → ⏳ en cours ; au seuil ou plus → ✅ plein. Seuils : Reels
 *  14 (deux par jour sur la semaine), Carrousel 10, Stories 10, TOP 20 20. Le tout est en cache 10 minutes par clipper. */
import { driveDossiers, driveFichiers, driveParents, type Dossier } from "./google";
import { aujourdhuiParis, MOIS } from "./dates";
import { creatriceDe, sourcesDe, type Creatrice } from "./config";
import { normaliser, type Clipper } from "./clippers";

export type TypeTuile = "carrousel" | "reels" | "stories" | "top";
export const TUILES: TypeTuile[] = ["carrousel", "reels", "stories", "top"];
export type Statut = "plein" | "en_cours" | "vide" | "inconnu";
export type Cible = {
  type: TypeTuile;
  id: string;                 // le dossier racine, celui que la tuile ouvre
  url: string;
  racine: string;             // libellé de la racine (« Reels de Chloé », « TOP 20 Reels »…)
  courant: string[];          // chemin du dossier du moment sous la racine (« Octobre », « Semaine 2 »)
  statut: Statut;
  fichiers: number;           // fichiers comptés dans le dossier du moment (100 au plus)
};
export const SEUILS: Record<TypeTuile, number> = { reels: 14, carrousel: 10, stories: 10, top: 20 };
export const LIBELLES_STATUT: Record<Statut, string> = { plein: "✅ plein", en_cours: "⏳ en cours de remplissage", vide: "❌ dossier vide", inconnu: "état inconnu" };

const cache = new Map<string, { expire: number; valeur: Cible }>();
const DIX_MINUTES = 10 * 60 * 1000;

const plat = (t: string) => normaliser(t);
const majuscule = (t: string) => t[0].toUpperCase() + t.slice(1);
const nomPropre = (t: string) => t.replace(/[✅❌⏳🔞📱📣📁🎬]/g, "").trim();

function trouverAnnee(dossiers: Dossier[], annee: number): Dossier | undefined {
  return dossiers.find((d) => new RegExp(`^\\s*${annee}\\b`).test(d.name));
}

/** Numéro du mois (1-12) lu dans un nom de dossier : « 10.Octobre », « 10. Octobre ✅ », « Octobre 2026 »… */
export function moisDuNom(nom: string): number | null {
  const n = nom.match(/^\s*(0?[1-9]|1[0-2])\s*[.\-_ ]/);
  if (n) return parseInt(n[1], 10);
  const i = MOIS.findIndex((m) => plat(nom).includes(plat(m)));
  return i >= 0 ? i + 1 : null;
}

/** Le dossier du mois demandé ; sinon le mois le plus récent déjà créé (jamais un mois futur). */
function trouverMois(dossiers: Dossier[], mois1: number): { d: Dossier; mois: number } | undefined {
  const candidats = dossiers.map((d) => ({ d, mois: moisDuNom(d.name) })).filter((x): x is { d: Dossier; mois: number } => x.mois !== null);
  const exact = candidats.find((x) => x.mois === mois1);
  if (exact) return exact;
  const passes = candidats.filter((x) => x.mois < mois1).sort((a, b) => b.mois - a.mois);
  return passes[0] || candidats.sort((a, b) => b.mois - a.mois)[0];
}

function numeroDeSemaine(nom: string): number | null {
  const m = plat(nom).match(/^\s*semaine\s*(\d+)\b/);
  return m ? parseInt(m[1], 10) : null;
}

/** La semaine demandée ; sinon la dernière semaine déjà créée avant elle. */
function trouverSemaine(dossiers: Dossier[], n: number): { d: Dossier; semaine: number } | undefined {
  const candidats = dossiers.map((d) => ({ d, semaine: numeroDeSemaine(d.name) })).filter((x): x is { d: Dossier; semaine: number } => x.semaine !== null);
  return candidats.find((x) => x.semaine === n) || candidats.filter((x) => x.semaine < n).sort((a, b) => b.semaine - a.semaine)[0] || candidats.sort((a, b) => b.semaine - a.semaine)[0];
}

export function numeroSemaine(jourDuMois: number): number {
  return Math.min(4, Math.floor((jourDuMois - 1) / 7) + 1);
}

/** Descend de la racine vers le dossier du moment : année → mois (→ semaine pour les Reels). Renvoie l'id du dossier
 *  atteint et le chemin lisible ; sans dossier d'année ni de mois, le dossier du moment est la racine elle-même. */
async function dossierDuMoment(racine: string, avecSemaine: boolean): Promise<{ id: string; chemin: string[] }> {
  const aujourdhui = aujourdhuiParis();
  const annee = parseInt(aujourdhui.slice(0, 4), 10), mois = parseInt(aujourdhui.slice(5, 7), 10), jour = parseInt(aujourdhui.slice(8, 10), 10);
  let id = racine;
  const chemin: string[] = [];
  const enfants = await driveDossiers(id);
  const an = trouverAnnee(enfants, annee);
  const niveauMois = an ? await driveDossiers(an.id) : enfants;
  if (an) { id = an.id; }
  const m = trouverMois(niveauMois, mois);
  if (!m) return { id, chemin };                                        // ni année ni mois : la racine est le dossier du moment
  id = m.d.id; chemin.push(majuscule(MOIS[m.mois - 1]));
  if (avecSemaine) {
    const s = trouverSemaine(await driveDossiers(id), numeroSemaine(jour));
    if (s) { id = s.d.id; chemin.push(`Semaine ${s.semaine}`); }
  }
  return { id, chemin };
}

/** Le dossier personnel du clipper dans « 🎬 Clippers » de sa créatrice (créé par le bot à l'onboarding), ou null. */
async function dossierClipper(clipper: Clipper): Promise<Dossier | null> {
  const s = sourcesDe(clipper.creatrice);
  if (!s) return null;
  const dossiers = await driveDossiers(s.parent);
  return dossiers.find((d) => plat(d.name) === clipper.cle) || dossiers.find((d) => plat(d.name).split(/\s+/)[0] === clipper.cle) || null;
}

/** Le dossier Instagram de la créatrice (au-dessus de « 🎬 Clippers ») et ses sous-dossiers : Reels, Carrousel, Stories… */
async function sousDossiersInstagram(clipper: Clipper): Promise<Dossier[]> {
  const s = sourcesDe(clipper.creatrice);
  if (!s) return [];
  const parents = await driveParents(s.parent);
  if (!parents.length) return [];
  return driveDossiers(parents[0]);
}

/** Le « TOP 20 Reels » de la créatrice : Instagram / 📁 Reels / TOP 20 Reels. */
async function top20Creatrice(clipper: Clipper): Promise<Dossier | null> {
  const reels = (await sousDossiersInstagram(clipper)).find((d) => plat(d.name).includes("reels"));
  if (!reels) return null;
  return (await driveDossiers(reels.id)).find((d) => plat(d.name).includes("top")) || null;
}

/** Une racine par nom : la source DRIVE_SOURCES dont `sous` correspond, sinon le sous-dossier Instagram dont le nom contient un des mots. */
async function racineParNom(clipper: Clipper, mots: string[]): Promise<string | null> {
  const s = sourcesDe(clipper.creatrice);
  const source = s?.sources.find((x) => mots.some((m) => plat(x.sous || "").includes(m)));
  if (source) return source.id;
  const dossier = (await sousDossiersInstagram(clipper).catch(() => [] as Dossier[])).find((d) => mots.some((m) => plat(d.name).includes(m)));
  return dossier ? dossier.id : null;
}

/** Les fichiers du dossier du moment ; s'il n'en a aucun mais des sous-dossiers (semaines, tenues…), on compte dans les
 *  quatre plus récents : un mois rangé en semaines n'est pas « vide » parce que ses fichiers sont un niveau plus bas. */
async function compterFichiers(id: string): Promise<number> {
  const direct = (await driveFichiers(id, 100).catch(() => [])).length;
  if (direct > 0) return direct;
  const sous = (await driveDossiers(id).catch(() => [] as Dossier[])).sort((a, b) => b.name.localeCompare(a.name, "fr")).slice(0, 4);
  let total = 0;
  for (const d of sous) total += (await driveFichiers(d.id, 100).catch(() => [])).length;
  return total;
}

function statutDe(type: TypeTuile, nb: number): Statut {
  if (nb <= 0) return "vide";
  return nb >= SEUILS[type] ? "plein" : "en_cours";
}

export async function cibleClipper(clipper: Clipper, type: TypeTuile): Promise<Cible> {
  const cle = `${clipper.cle}:${type}`;
  const enCache = cache.get(cle);
  if (enCache && enCache.expire > Date.now()) return enCache.valeur;
  const c: Creatrice | null = creatriceDe(clipper.creatrice);
  const s = sourcesDe(clipper.creatrice);
  const prenomCrea = clipper.creatrice.split(/\s+/)[0] || clipper.creatrice;
  let id = "", racine = "", courant: string[] = [], moment = "";

  if (type === "reels") {
    id = (await racineParNom(clipper, ["reels"])) || c?.reels || c?.racine || "";
    if (!id) throw new Error(`pas de dossier Reels pour ${prenomCrea}`);
    racine = `Reels de ${prenomCrea}`;
    const m = await dossierDuMoment(id, true); moment = m.id; courant = m.chemin;
  } else if (type === "carrousel") {
    id = (await racineParNom(clipper, ["carrousel", "carousel"])) || (await racineParNom(clipper, ["photos"])) || c?.photos || "";
    if (!id) throw new Error(`pas de dossier Carrousel pour ${prenomCrea}`);
    racine = `Carrousel de ${prenomCrea}`;
    const m = await dossierDuMoment(id, false); moment = m.id; courant = m.chemin;
  } else if (type === "stories") {
    id = (await racineParNom(clipper, ["stories", "story"])) || "";
    if (!id) {
      const mien = await dossierClipper(clipper);
      if (!mien) throw new Error(`pas de dossier Stories pour ${prenomCrea}`);
      id = mien.id; racine = "Mon dossier";
    } else racine = `Stories de ${prenomCrea}`;
    const m = await dossierDuMoment(id, false); moment = m.id; courant = m.chemin;
  } else {
    const mien = await dossierClipper(clipper);
    const top = mien ? (await driveDossiers(mien.id)).find((d) => plat(d.name).includes("top") || plat(d.name).includes("unique")) : null;
    if (top) { id = top.id; racine = nomPropre(top.name); }
    else {
      const topC = await top20Creatrice(clipper).catch(() => null);
      if (topC) { id = topC.id; racine = `TOP 20 de ${prenomCrea}`; }
      else if (mien) { id = mien.id; racine = "Mon dossier"; }
      else throw new Error("pas de dossier TOP 20");
    }
    moment = id;
  }
  const fichiers = await compterFichiers(moment);
  const valeur: Cible = { type, id, url: `https://drive.google.com/drive/folders/${id}`, racine, courant, statut: statutDe(type, fichiers), fichiers };
  cache.set(cle, { expire: Date.now() + DIX_MINUTES, valeur });
  return valeur;
}

/** Le repli de dernier recours d'une tuile : le dossier personnel du clipper (lisible par le lien), sinon le Drive. */
export async function urlDeSecours(clipper: Clipper): Promise<string> {
  try {
    const mien = await dossierClipper(clipper);
    if (mien) return `https://drive.google.com/drive/folders/${mien.id}`;
  } catch { /* on tombe sur le Drive */ }
  return "https://drive.google.com/";
}
