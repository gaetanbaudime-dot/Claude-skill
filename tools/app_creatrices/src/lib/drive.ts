/** Le bon dossier Drive du moment, en suivant la structure existante (jamais créée ici : c'est le script Drive de l'agence qui crée les dossiers) :
 *  Reels   → <Reels> / 2026 ✅ / 10.Octobre / Semaine N      (semaine 1 = jours 1 à 7, 2 = 8 à 14, 3 = 15 à 21, 4 = 22 à 31)
 *  Photos  → <Photos> / 2026 ✅ / 10. Octobre
 *  Feed    → <Feed - Stories> / « Feed MYM Octobre 2026 » si ce dossier existe, sinon la racine du feed
 *  Scripts → <Script> / « Octobre » ou « 10 » si un dossier du mois existe, sinon la racine
 *  Un mois ou une semaine pas encore créés font reculer au plus récent existant ; un niveau absent s'arrête au dernier dossier trouvé : le bouton ouvre toujours quelque chose d'utile. */
import { driveDossiers, type Dossier } from "./google";
import { aujourdhuiParis, MOIS } from "./dates";
import type { Creatrice } from "./config";

export type TypeDossier = "reels" | "photos" | "feed" | "scripts";
export const TYPES: TypeDossier[] = ["reels", "photos", "feed", "scripts"];
const cache = new Map<string, { expire: number; valeur: Cible }>();

export type Cible = { type: TypeDossier; id: string; url: string; chemin: string[]; complet: boolean };

function plat(t: string): string {
  return t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

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

/** Le dossier du mois demandé ; sinon le mois le plus récent déjà créé (jamais un mois futur), pour que le bouton ouvre toujours un dossier utile. */
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

export async function cible(c: Creatrice, type: TypeDossier): Promise<Cible> {
  const cle = `${c.jeton}:${type}`;
  const enCache = cache.get(cle);
  if (enCache && enCache.expire > Date.now()) return enCache.valeur;
  const aujourdhui = aujourdhuiParis();
  const annee = parseInt(aujourdhui.slice(0, 4), 10), mois = parseInt(aujourdhui.slice(5, 7), 10), jour = parseInt(aujourdhui.slice(8, 10), 10);
  const nomMois = MOIS[mois - 1][0].toUpperCase() + MOIS[mois - 1].slice(1);
  let id = (type === "reels" ? c.reels : type === "photos" ? c.photos : type === "feed" ? c.feed : c.scripts) || c.racine;
  const chemin: string[] = [];
  let complet = true;
  const majuscule = (t: string) => t[0].toUpperCase() + t.slice(1);
  const nomPropre = (t: string) => t.replace(/[✅❌⏳🔞📱📣]/g, "").trim();
  /** Descend d'un niveau : `chercher` renvoie le dossier retenu et son libellé ; `exact` dit si c'est bien celui du jour (sinon le chemin reste utile mais « incomplet »). */
  const descendre = async (chercher: (ds: Dossier[]) => { d: Dossier; libelle: string; exact: boolean } | undefined, deja?: Dossier[]) => {
    if (!complet) return;
    const r = chercher(deja || (await driveDossiers(id)));
    if (r) { id = r.d.id; chemin.push(r.libelle); if (!r.exact) complet = false; } else complet = false;
  };
  const niveauMois = (ds: Dossier[]) => { const r = trouverMois(ds, mois); return r && { d: r.d, libelle: majuscule(MOIS[r.mois - 1]), exact: r.mois === mois }; };
  if (type === "reels" || type === "photos") {
    const racine = await driveDossiers(id);
    const an = trouverAnnee(racine, annee);
    if (an) { id = an.id; chemin.push(String(annee)); await descendre(niveauMois); }
    else await descendre(niveauMois, racine);                          // pas de dossier d'année : les mois sont directement à la racine
    if (type === "reels") await descendre((ds) => { const r = trouverSemaine(ds, numeroSemaine(jour)); return r && { d: r.d, libelle: `Semaine ${r.semaine}`, exact: r.semaine === numeroSemaine(jour) }; });
  } else if (type === "feed" && c.feed) {
    await descendre((ds) => {
      const d = ds.find((x) => plat(x.name).includes(plat(nomMois)) && x.name.includes(String(annee))) || ds.find((x) => plat(x.name).includes(plat(nomMois)));
      if (d) return { d, libelle: `${nomMois} ${annee}`, exact: true };
      const r = trouverMois(ds, mois);                                 // sinon le feed le plus récent, sous son vrai nom
      return r && { d: r.d, libelle: nomPropre(r.d.name), exact: false };
    });
  } else if (type === "scripts" && c.scripts) {
    await descendre((ds) => {
      const r = trouverMois(ds, mois);
      if (r) return { d: r.d, libelle: r.mois === mois ? nomMois : nomPropre(r.d.name), exact: r.mois === mois };
      const d = trouverAnnee(ds, annee);
      return d && { d, libelle: String(annee), exact: true };
    });
  } else {
    complet = false;                                                   // pas de dossier MYM connu : la racine de la créatrice
  }
  const valeur: Cible = { type, id, url: `https://drive.google.com/drive/folders/${id}`, chemin, complet };
  cache.set(cle, { expire: Date.now() + 10 * 60 * 1000, valeur });
  return valeur;
}
