/** Les quatre tuiles Drive d'un clipper (08/10, Gaëtan) : **Carrousel · TOP 20 Reels · Story · Reels**. Chaque tuile ouvre le
 *  DOSSIER RACINE de la section dans l'app Google Drive, « on ne s'embête pas, le clipper fouille dedans » : pas de descente
 *  dans le mois ou la semaine, pas d'état.
 *
 *  Racines (jamais créées ici : c'est le bot et le script Drive de l'agence qui créent les dossiers) : les sous-dossiers du
 *  dossier Instagram de sa créatrice (le parent de « 🎬 Clippers ») nommés Carrousel, Reels, Story ; en secours, les sources
 *  DRIVE_SOURCES (Reels, Photos, Stories) puis les dossiers de CREATRICES_JSON. TOP 20 Reels = le sous-dossier « TOP 20 Reels »
 *  de son dossier personnel dans « 🎬 Clippers » (ses variantes uniques, déposées par le bot), sinon le « TOP 20 Reels » de la
 *  créatrice (dans son dossier Reels), sinon son dossier personnel. Le tout est en cache 10 minutes par clipper. */
import { driveDossiers, driveParents, type Dossier } from "./google";
import { creatriceDe, sourcesDe } from "./config";
import { normaliser, type Clipper } from "./clippers";

export type TypeTuile = "carrousel" | "top" | "story" | "reels";
export const TUILES: TypeTuile[] = ["carrousel", "top", "story", "reels"];
export type Cible = { type: TypeTuile; id: string; url: string; racine: string };

const cache = new Map<string, { expire: number; valeur: Cible }>();
const DIX_MINUTES = 10 * 60 * 1000;
const plat = (t: string) => normaliser(t);
const nomPropre = (t: string) => t.replace(/[✅❌⏳🔞📱📣📁🎬]/g, "").trim();

/** Le dossier personnel du clipper dans « 🎬 Clippers » de sa créatrice (créé par le bot à l'onboarding), ou null. */
async function dossierClipper(clipper: Clipper): Promise<Dossier | null> {
  const s = sourcesDe(clipper.creatrice);
  if (!s) return null;
  const dossiers = await driveDossiers(s.parent);
  return dossiers.find((d) => plat(d.name) === clipper.cle) || dossiers.find((d) => plat(d.name).split(/\s+/)[0] === clipper.cle) || null;
}

/** Les sous-dossiers du dossier Instagram de la créatrice (au-dessus de « 🎬 Clippers ») : Carrousel, Reels, Story… */
async function sousDossiersInstagram(clipper: Clipper): Promise<Dossier[]> {
  const s = sourcesDe(clipper.creatrice);
  if (!s) return [];
  const parents = await driveParents(s.parent);
  if (!parents.length) return [];
  return driveDossiers(parents[0]);
}

/** Une racine par nom : d'abord le sous-dossier Instagram dont le nom contient un des mots (et aucun des mots exclus),
 *  sinon la source DRIVE_SOURCES dont `sous` correspond. */
async function racineParNom(clipper: Clipper, mots: string[], exclus: string[] = []): Promise<Dossier | null> {
  const convient = (nom: string) => mots.some((m) => plat(nom).includes(m)) && !exclus.some((x) => plat(nom).includes(x));
  const dossier = (await sousDossiersInstagram(clipper).catch(() => [] as Dossier[])).find((d) => convient(d.name));
  if (dossier) return dossier;
  const source = sourcesDe(clipper.creatrice)?.sources.find((x) => convient(x.sous || ""));
  return source ? { id: source.id, name: source.sous || "" } : null;
}

/** Le « TOP 20 Reels » de la créatrice : Instagram / 📁 Reels / TOP 20 Reels. */
async function top20Creatrice(clipper: Clipper): Promise<Dossier | null> {
  const reels = (await sousDossiersInstagram(clipper)).find((d) => plat(d.name).includes("reels"));
  if (!reels) return null;
  return (await driveDossiers(reels.id)).find((d) => plat(d.name).includes("top")) || null;
}

export async function cibleClipper(clipper: Clipper, type: TypeTuile): Promise<Cible> {
  const cle = `${clipper.cle}:${type}`;
  const enCache = cache.get(cle);
  if (enCache && enCache.expire > Date.now()) return enCache.valeur;
  const c = creatriceDe(clipper.creatrice);
  const prenomCrea = clipper.creatrice.split(/\s+/)[0] || clipper.creatrice;
  let id = "", racine = "";

  if (type === "reels") {
    const d = await racineParNom(clipper, ["reels"], ["top"]);
    id = d?.id || c?.reels || c?.racine || "";
    racine = d ? nomPropre(d.name) : "Reels";
  } else if (type === "carrousel") {
    const d = (await racineParNom(clipper, ["carrousel", "carousel"])) || (await racineParNom(clipper, ["photos"]));
    id = d?.id || c?.photos || "";
    racine = d ? nomPropre(d.name) : "Carrousel";
  } else if (type === "story") {
    const d = await racineParNom(clipper, ["story", "stories"]);
    id = d?.id || "";
    racine = d ? nomPropre(d.name) : "Story";
  } else {
    const mien = await dossierClipper(clipper);
    const top = mien ? (await driveDossiers(mien.id)).find((d) => plat(d.name).includes("top") || plat(d.name).includes("unique")) : null;
    if (top) { id = top.id; racine = nomPropre(top.name); }
    else {
      const topC = await top20Creatrice(clipper).catch(() => null);
      if (topC) { id = topC.id; racine = `TOP 20 de ${prenomCrea}`; }
      else if (mien) { id = mien.id; racine = "Mon dossier"; }
    }
  }
  if (!id) throw new Error(`pas de dossier ${type} pour ${prenomCrea}`);
  const valeur: Cible = { type, id, url: `https://drive.google.com/drive/folders/${id}`, racine };
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
