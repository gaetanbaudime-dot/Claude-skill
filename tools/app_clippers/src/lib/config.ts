/** Les dossiers Drive des créatrices, posés dans deux variables d'environnement (jamais dans le dépôt) :
 *  - CREATRICES_JSON : le même contenu que l'app créatrices, { "<jeton>": { "prenom", "racine", "reels", "photos", … } } ;
 *    ici on l'indexe par prénom normalisé et on ignore les jetons des créatrices (l'app clippers ne s'en sert pas) ;
 *  - DRIVE_SOURCES : le même JSON que le bot Discord, { "Chloé": { "parent": "<id de 🎬 Clippers>", "sources": [{ "id", "sous": "Reels|Photos|Stories" }] } },
 *    `parent` est le dossier qui contient le dossier personnel de chaque clipper (créé par le bot à l'onboarding). */
import { normaliser } from "./clippers";

export type Creatrice = { prenom: string; racine: string; reels?: string | null; photos?: string | null };
export type SourceDrive = { id: string; sous?: string; types?: string[] };
export type SourcesCreatrice = { parent: string; sources: SourceDrive[] };

let cacheCreatrices: Record<string, Creatrice> | null = null;
let cacheSources: Record<string, SourcesCreatrice> | null = null;

export function creatrices(): Record<string, Creatrice> {
  if (cacheCreatrices) return cacheCreatrices;
  const data = JSON.parse(process.env.CREATRICES_JSON || "{}") as Record<string, Creatrice>;
  cacheCreatrices = {};
  for (const c of Object.values(data)) if (c && c.prenom) cacheCreatrices[normaliser(c.prenom)] = { prenom: c.prenom, racine: c.racine, reels: c.reels, photos: c.photos };
  return cacheCreatrices;
}

export function sourcesDrive(): Record<string, SourcesCreatrice> {
  if (cacheSources) return cacheSources;
  const data = JSON.parse(process.env.DRIVE_SOURCES || "{}") as Record<string, { parent?: string; sources?: (SourceDrive | string)[] }>;
  cacheSources = {};
  for (const [nom, cfg] of Object.entries(data)) {
    if (!cfg || !cfg.parent) continue;
    cacheSources[normaliser(nom.split(/\s+/)[0])] = { parent: cfg.parent, sources: (cfg.sources || []).map((s) => (typeof s === "string" ? { id: s } : s)).filter((s) => s.id) };
  }
  return cacheSources;
}

/** La créatrice d'un clipper (premier mot du `name` du lien GAML), sans casse ni accent. */
export function creatriceDe(nom: string): Creatrice | null {
  return creatrices()[normaliser((nom || "").split(/\s+/)[0])] || null;
}

export function sourcesDe(nom: string): SourcesCreatrice | null {
  return sourcesDrive()[normaliser((nom || "").split(/\s+/)[0])] || null;
}
