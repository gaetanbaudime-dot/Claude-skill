/** Accès à l'API GetAllMyLinks (GAML), en lecture seule, avec le budget d'appels en tête :
 *  l'agence entière dispose de 60 requêtes par minute (le bot Discord en consomme aussi).
 *  - la liste des liens est mise en cache 10 minutes ;
 *  - les jours passés sont immuables : relevés une fois, gardés 7 jours ;
 *  - seul le jour en cours est relu, au plus toutes les 5 minutes ;
 *  - un 429 (ou une limite annoncée par les en-têtes) n'est jamais une erreur pour le clipper :
 *    il remonte `ErreurGaml.limite` et l'app affiche « chiffres en cours de mise à jour ». */
import { unstable_cache } from "next/cache";
import { PAYS_PAYES } from "./paie";

const API = "https://getallmylinks.com/api/v1";
const FUSEAU = "Europe/Paris";

export class ErreurGaml extends Error {
  limite: boolean;
  constructor(message: string, limite = false) { super(message); this.limite = limite; }
}

/** Dernière limite annoncée par GAML (par instance de fonction) : on n'appelle pas quand on sait que c'est plein. */
const limite = { restant: 60, reset: 0 };

async function requete<T>(chemin: string, params?: Record<string, string>): Promise<T> {
  const cle = process.env.GAML_API_KEY;
  if (!cle) throw new ErreurGaml("GAML_API_KEY absent");
  if (limite.restant <= 1 && limite.reset * 1000 > Date.now()) throw new ErreurGaml("limite GAML atteinte", true);
  const url = `${API}${chemin}${params ? "?" + new URLSearchParams(params).toString() : ""}`;
  for (let essai = 0; essai < 2; essai++) {
    const r = await fetch(url, {
      headers: { "X-Api-Key": cle, Accept: "application/json", "User-Agent": "Mozilla/5.0 (app-clippers G&M)" },
      cache: "no-store",
    });
    const restant = parseInt(r.headers.get("x-ratelimit-remaining") || "", 10), reset = parseFloat(r.headers.get("x-ratelimit-reset") || "");
    if (!isNaN(restant)) limite.restant = restant;
    if (!isNaN(reset)) limite.reset = reset;
    if (r.status === 429) throw new ErreurGaml("GAML 429", true);
    if (r.status >= 500 && essai === 0) { await new Promise((ok) => setTimeout(ok, 1500)); continue; }
    if (!r.ok) throw new ErreurGaml(`GAML ${r.status} sur ${chemin}`);
    return (await r.json()) as T;
  }
  throw new ErreurGaml(`GAML injoignable sur ${chemin}`);
}

/** GAML renvoie tantôt une liste, tantôt un objet { member | data } (API Platform). */
function liste<T>(d: unknown): T[] {
  if (Array.isArray(d)) return d as T[];
  const o = (d || {}) as { member?: T[]; data?: T[]; items?: T[] };
  return o.member || o.data || o.items || [];
}

export type LienGaml = { id: string; url: string; name: string; note: string; createdAt: string; enabled: boolean };

let derniereListe: LienGaml[] | null = null;                       // repli si GAML tombe : la dernière liste connue de l'instance

const liensEnCache = unstable_cache(async (): Promise<LienGaml[]> => {
  const d = await requete<unknown>("/links");
  return liste<Record<string, unknown>>(d).map((l) => ({
    id: String(l.id || ""), url: String(l.url || ""), name: String(l.name || ""), note: String(l.note || ""),
    createdAt: String(l.createdAt || ""), enabled: l.enabled !== false,
  })).filter((l) => l.id);
}, ["gaml-liens"], { revalidate: 600 });

/** Tous les liens du compte GAML (cache 10 minutes). */
export async function liensGaml(): Promise<LienGaml[]> {
  try {
    const l = await liensEnCache();
    derniereListe = l;
    return l;
  } catch (e) {
    if (derniereListe) return derniereListe;
    throw e;
  }
}

/** Visites hors robots venant des pays payés, pour un lien entre deux jours inclus (un seul appel). */
async function francophones(linkId: string, debut: string, fin: string): Promise<number> {
  const d = await requete<unknown>("/analytics/countries", { link_id: linkId, range: "custom", date_from: debut, date_to: fin, timezone: FUSEAU });
  return liste<{ country?: string; count?: number | string }>(d)
    .filter((x) => PAYS_PAYES.has(String(x.country || "")))
    .reduce((s, x) => s + (parseInt(String(x.count ?? 0), 10) || 0), 0);
}

const jourPasse = unstable_cache((linkId: string, jour: string) => francophones(linkId, jour, jour), ["gaml-jour-passe"], { revalidate: 7 * 86400 });
const jourCourant = unstable_cache((linkId: string, jour: string) => francophones(linkId, jour, jour), ["gaml-jour-courant"], { revalidate: 300 });
const periodePassee = unstable_cache((linkId: string, debut: string, fin: string) => francophones(linkId, debut, fin), ["gaml-periode-passee"], { revalidate: 7 * 86400 });

/** Visites francophones d'un jour : cache long si le jour est passé, 5 minutes s'il est en cours. */
export function visitesJour(linkId: string, jour: string, aujourdhui: string): Promise<number> {
  return jour < aujourdhui ? jourPasse(linkId, jour) : jourCourant(linkId, jour);
}

/** Visites francophones d'une période entièrement passée (un appel, cache long). */
export function visitesPeriodePassee(linkId: string, debut: string, fin: string): Promise<number> {
  return periodePassee(linkId, debut, fin);
}
