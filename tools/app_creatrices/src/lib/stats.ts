/** Les statistiques d'une créatrice depuis son onglet du classeur Data G&M :
 *  colonnes A Date · B nouveaux abonnés OnlyFans · C CA OnlyFans ($) · E nouveaux abonnés MYM · F CA MYM (€).
 *  Tout est rendu en euros nets (le CA saisi est le net de la plateforme ; les dollars sont convertis au taux du jour). */
import { sheetsLire } from "./google";
import { aujourdhuiParis, periodes, serialVersJour, texteVersJour, libelleJour, decaler, type Periode } from "./dates";
import { tauxUsdEur } from "./taux";
import type { Creatrice } from "./config";

export type Jour = { jour: string; of: number; mym: number; subsOf: number; subsMym: number; saisi: boolean; ofSaisi: boolean; mymSaisi: boolean };
export type Totaux = { total: number; of: number; mym: number; subs: number; subsOf: number; subsMym: number; jours: number };

const cacheOnglet = new Map<string, { expire: number; jours: Map<string, Jour> }>();

function nombre(v: unknown): number {
  if (typeof v === "number") return v;
  if (typeof v === "string") {
    const n = parseFloat(v.replace(/[^\d,.-]/g, "").replace(/\s/g, "").replace(",", "."));
    return isNaN(n) ? 0 : n;
  }
  return 0;
}

async function lireOnglet(c: Creatrice): Promise<Map<string, Jour>> {
  const cle = c.onglet;
  const enCache = cacheOnglet.get(cle);
  if (enCache && enCache.expire > Date.now()) return enCache.jours;
  const id = process.env.DATA_GM_ID;
  if (!id) throw new Error("DATA_GM_ID absent");
  const lignes = await sheetsLire(id, `'${c.onglet}'!A3:F`);
  const { taux } = await tauxUsdEur();
  const aujourdhui = aujourdhuiParis();
  const jours = new Map<string, Jour>();
  for (const l of lignes) {
    const brutDate = l[0];
    const jour = typeof brutDate === "number" ? serialVersJour(brutDate) : typeof brutDate === "string" && brutDate.trim() ? texteVersJour(brutDate, aujourdhui) : null;
    if (!jour) continue;
    const rempli = (v: unknown) => v !== undefined && v !== null && v !== "";
    const ofSaisi = rempli(l[1]) || rempli(l[2]), mymSaisi = rempli(l[4]) || rempli(l[5]);
    jours.set(jour, {
      jour, saisi: ofSaisi || mymSaisi, ofSaisi, mymSaisi,
      subsOf: Math.round(nombre(l[1])), of: Math.round(nombre(l[2]) * taux * 100) / 100,
      subsMym: Math.round(nombre(l[4])), mym: Math.round(nombre(l[5]) * 100) / 100,
    });
  }
  cacheOnglet.set(cle, { expire: Date.now() + 5 * 60 * 1000, jours });
  return jours;
}

function totaux(jours: Map<string, Jour>, debut: string, fin: string): Totaux {
  const t: Totaux = { total: 0, of: 0, mym: 0, subs: 0, subsOf: 0, subsMym: 0, jours: 0 };
  for (let j = debut; j <= fin; j = decaler(j, 1)) {
    const x = jours.get(j);
    if (!x || !x.saisi) continue;
    t.of += x.of; t.mym += x.mym; t.subsOf += x.subsOf; t.subsMym += x.subsMym; t.jours += 1;
  }
  t.total = Math.round((t.of + t.mym) * 100) / 100; t.of = Math.round(t.of * 100) / 100; t.mym = Math.round(t.mym * 100) / 100;
  t.subs = t.subsOf + t.subsMym;
  return t;
}

export type Stats = {
  periode: Periode & { libelleDates: string };
  totaux: Totaux;
  precedent: Totaux;
  serie: Jour[];
  dernierJourSaisi: string | null; enAttente: { of: string[]; mym: string[] };
  taux: { valeur: number; date: string; source: string };
  periodes: { cle: string; libelle: string }[];
};

export async function stats(c: Creatrice, cle: string): Promise<Stats> {
  const aujourdhui = aujourdhuiParis();
  const toutes = periodes(aujourdhui);
  const p = toutes[cle] || toutes.hier;
  const jours = await lireOnglet(c);
  const { taux, date, source } = await tauxUsdEur();
  const serie: Jour[] = [];
  for (let j = p.debut; j <= p.fin; j = decaler(j, 1)) serie.push(jours.get(j) || { jour: j, of: 0, mym: 0, subsOf: 0, subsMym: 0, saisi: false, ofSaisi: false, mymSaisi: false });
  const saisis = [...jours.values()].filter((x) => x.saisi && x.jour <= aujourdhui).map((x) => x.jour).sort();
  return {
    periode: { ...p, libelleDates: p.debut === p.fin ? libelleJour(p.debut, true) : `${libelleJour(p.debut)} → ${libelleJour(p.fin, true)}` },
    totaux: totaux(jours, p.debut, p.fin),
    precedent: totaux(jours, p.avantDebut, p.avantFin),
    serie,
    dernierJourSaisi: saisis.length ? saisis[saisis.length - 1] : null,
    enAttente: {                                                       // jours de la période saisis d'un côté seulement (l'autre arrive plus tard dans la journée)
      of: serie.filter((x) => x.mymSaisi && !x.ofSaisi).map((x) => x.jour),
      mym: serie.filter((x) => x.ofSaisi && !x.mymSaisi).map((x) => x.jour),
    },
    taux: { valeur: taux, date, source },
    periodes: Object.values(toutes).map((x) => ({ cle: x.cle, libelle: x.libelle })),
  };
}
