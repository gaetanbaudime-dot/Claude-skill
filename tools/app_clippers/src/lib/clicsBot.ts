/** 28/10 (audit des apps, Gaëtan : « que je sois capable de voir… ses clics assez précisément ») : le repli des versements quand GAML
 *  refuse des appels. L'agence entière a 60 requêtes GAML par minute, le bot en consomme aussi : quand plusieurs clippers ouvrent
 *  leur app en même temps, des jours restaient « non relevés » et la période s'affichait trop basse (le 28/10 au matin : 0 $ pour
 *  Yves au lieu de 75,20 $, 7,20 $ pour Mathieu au lieu de 15,45 $).
 *  Le bot relève les mêmes visites (francophones, robots exclus, heure de Paris) lien par lien et publie chaque jour, par clipper,
 *  l'onglet « Pilotage clics » du tableur d'usage : Jour, Créatrice, Axe, Source, Qui, Visites payables, Visites hors robots,
 *  Liens, Liens non relevés. Un jour que GAML n'a pas rendu est pris là, s'il y est complet. C'est aussi la base de la paie du bot. */
import { lirePlage, tableur } from "./usage";

export type JourBot = { visites: number; complet: boolean };
const plat = (t?: string) => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, " ").trim();

/** Pur : les visites payables du clipper `prenom` par jour (toutes créatrices), depuis `depuis` inclus. Un jour dont un lien n'est
 *  pas relevé (colonne I > 0) ou un chiffre illisible est incomplet. */
export function visitesBot(lignes: string[][], prenom: string, depuis: string): Map<string, JourBot> {
  const cible = plat(prenom);
  const out = new Map<string, JourBot>();
  if (!cible) return out;
  for (const l of lignes) {
    const jour = String(l[0] || "").slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(jour) || jour < depuis || plat(l[3]) !== "clipper" || plat(l[4]) !== cible) continue;
    const x = out.get(jour) || { visites: 0, complet: true };
    const v = parseInt(String(l[5] ?? "").replace(/\s/g, ""), 10);
    if (Number.isFinite(v)) x.visites += v; else x.complet = false;
    if ((parseInt(String(l[8] ?? "0"), 10) || 0) > 0) x.complet = false;
    out.set(jour, x);
  }
  return out;
}

/** Pur : remplit les jours incomplets de `parJour` avec les jours complets du bot. Renvoie le nombre de jours repris. */
export function completer(parJour: Map<string, JourBot>, bot: Map<string, JourBot>): number {
  let n = 0;
  parJour.forEach((j, jour) => {
    const b = bot.get(jour);
    if (j.complet || !b || !b.complet) return;
    parJour.set(jour, { visites: b.visites, complet: true });
    n++;
  });
  return n;
}

/** Pur : les visites d'une période passée [debut, fin] d'après le bot, ou null s'il manque un jour (ou un jour incomplet). */
export function periodeBot(bot: Map<string, JourBot>, debut: string, fin: string, jours: string[]): number | null {
  let total = 0;
  for (const j of jours) {
    if (j < debut || j > fin) continue;
    const b = bot.get(j);
    if (!b || !b.complet) return null;
    total += b.visites;
  }
  return total;
}

let cache: { t: number; lignes: string[][] } | null = null;
/** L'onglet « Pilotage clics » (cache 10 minutes par instance). Lu seulement quand GAML a laissé des jours non relevés. */
export async function lignesClicsBot(): Promise<string[][]> {
  if (cache && Date.now() - cache.t < 10 * 60 * 1000) return cache.lignes;
  const lignes = await lirePlage(await tableur(), "'Pilotage clics'!A2:I");
  cache = { t: Date.now(), lignes };
  return lignes;
}
