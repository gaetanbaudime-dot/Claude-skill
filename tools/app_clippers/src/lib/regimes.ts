/** Le régime de paie de chaque clipper, tel que le bot le décide (08/10, revue : l'app devinait « fixe » et « ancien » autrement que
 *  le bot, et affichait des montants que le bot ne paierait pas). Le bot écrit l'onglet « Régime paie » du tableur « App clippers ·
 *  usage » (`paie_clics.publier_regimes`, à chaque relecture horaire des liens, seulement s'il a changé) : une ligne par clé de
 *  clipper — régime (clic ou fixe), premier jour payé au clic, et le premier jour compté de chaque lien (un lien repris d'un sortant
 *  ne compte pour le nouveau qu'à partir de la reprise). Lu ici avec 10 minutes de cache ; onglet absent ou illisible → null, et
 *  l'app retombe sur sa règle de repli (paie.ts). */
import { lirePlage, tableur } from "./usage";

export const ONGLET_REGIMES = "Régime paie";
export type Regime = { regime: "clic" | "fixe"; clicDepuis: string; liens: Map<string, string> };

let cache: { t: number; m: Map<string, Regime> } | null = null;

async function regimes(): Promise<Map<string, Regime>> {
  if (cache && Date.now() - cache.t < 10 * 60 * 1000) return cache.m;
  const lignes = await lirePlage(await tableur(), `${ONGLET_REGIMES}!A2:D`);
  const m = new Map<string, Regime>();
  for (const l of lignes) {
    const cle = (l[0] || "").trim();
    if (!cle) continue;
    const liens = new Map<string, string>(
      (l[3] || "").split(";").filter(Boolean).map((x) => {
        const [id, jour] = x.split(":");
        return [id || "", (jour || "").slice(0, 10)] as [string, string];
      }).filter(([id]) => id),
    );
    m.set(cle, { regime: (l[1] || "").trim() === "fixe" ? "fixe" : "clic", clicDepuis: (l[2] || "").slice(0, 10), liens });
  }
  cache = { t: Date.now(), m };
  return m;
}

/** Le régime publié par le bot pour cette clé, ou null (pas encore publié, tableur indisponible). */
export async function regimeDe(cle: string): Promise<Regime | null> {
  try {
    return (await regimes()).get(cle) || null;
  } catch {
    return null;
  }
}
