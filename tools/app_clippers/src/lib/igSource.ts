/** 24/10 : lecture des onglets du suivi RapidAPI (« IG · Comptes », « IG · Reels ») en un appel, cache 5 minutes (le suivi tourne
 *  3 fois par jour). Côté serveur seulement : les chiffres de tous les comptes ne partent jamais tels quels vers un téléphone.
 *  Onglets absents ou Google en panne : null, et l'app garde l'ancien relevé (lib/igSuivi). */
import { jetonGoogle } from "./google";
import { tableur } from "./usage";
import { lireIgComptes, lireIgJours, type IgSuivi } from "./igSuivi";
import { decaler } from "./dates";

const JOURS = 17;                                                     // une période de paie (16 j au plus) + aujourd'hui
let cache: { t: number; valeur: IgSuivi } | null = null;
let enCours: Promise<IgSuivi | null> | null = null;

async function lire(aujourdhui: string): Promise<IgSuivi | null> {
  const id = await tableur();
  const jeton = await jetonGoogle();
  const plages = ["'IG · Comptes'!A2:W", "'IG · Reels'!D2:H"];
  const r = await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${id}/values:batchGet?${plages.map((p) => `ranges=${encodeURIComponent(p)}`).join("&")}`,
    { headers: { Authorization: `Bearer ${jeton}` }, cache: "no-store" });
  if (!r.ok) return null;
  const d = (await r.json()) as { valueRanges?: { values?: string[][] }[] };
  const [vc, vr] = (d.valueRanges || []).map((x) => x.values || []);
  if (!vc?.length) return null;
  return { comptes: lireIgComptes(vc), jours: lireIgJours(vr || [], decaler(aujourdhui, -(JOURS - 1))) };
}

export async function suiviIg(aujourdhui: string): Promise<IgSuivi | null> {
  if (cache && Date.now() - cache.t < 5 * 60 * 1000) return cache.valeur;
  if (!enCours) {
    enCours = lire(aujourdhui).then((v) => { if (v) cache = { t: Date.now(), valeur: v }; return v ?? cache?.valeur ?? null; })
      .catch(() => cache?.valeur ?? null).finally(() => { enCours = null; });
  }
  return enCours;
}
