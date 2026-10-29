/** Calculs du pilotage, côté téléphone (les tables arrivent brutes du tableur, quelques milliers de lignes au plus). */
import type { Bouton, Clic, Pilotage, Sub } from "@/lib/pilotage";

export type Periode = "auj" | "hier" | "j7" | "j30";
export const PERIODES: { cle: Periode; libelle: string }[] = [
  { cle: "auj", libelle: "Auj." }, { cle: "hier", libelle: "Hier" }, { cle: "j7", libelle: "7 j" }, { cle: "j30", libelle: "30 j" },
];
export type Fenetre = { debut: string; fin: string; avantDebut: string; avantFin: string; compare: boolean; libelleAvant: string };

export function decaler(jour: string, n: number): string {
  const d = new Date(jour + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** La période et celle d'avant, de même longueur. « Auj. » n'est pas comparé : la journée n'est pas finie. */
export function fenetre(aujourdhui: string, p: Periode): Fenetre {
  const h = decaler(aujourdhui, -1);
  if (p === "auj") return { debut: aujourdhui, fin: aujourdhui, avantDebut: h, avantFin: h, compare: false, libelleAvant: "" };
  if (p === "hier") return { debut: h, fin: h, avantDebut: decaler(h, -1), avantFin: decaler(h, -1), compare: true, libelleAvant: "avant-hier" };
  const n = p === "j7" ? 7 : 30;
  return { debut: decaler(aujourdhui, -n), fin: h, avantDebut: decaler(aujourdhui, -2 * n), avantFin: decaler(aujourdhui, -n - 1), compare: true, libelleAvant: `${n} j d'avant` };
}

export type Somme = { visites: number; manquants: number };
export function somme(clics: Clic[], debut: string, fin: string, filtre: (c: Clic) => boolean = () => true): Somme {
  let visites = 0, manquants = 0;
  for (const c of clics) if (c.jour >= debut && c.jour <= fin && filtre(c)) { visites += c.visites; manquants += c.manquants; }
  return { visites, manquants };
}

/** Variation en % (arrondie), null si rien à comparer. */
export function variation(cur: number, avant: number): number | null {
  if (!avant) return null;
  return Math.round(((cur - avant) / avant) * 100);
}

/** 29/10 (app de Clarisse : « ▲ 34500 % » pour Ricardo, passé de 1 à 346 clics) : au-delà de +900 %, le multiple se lit mieux
 *  (« × 346 ») ; en dessous, le pourcentage. Sans signe : la flèche du badge le porte. */
export function texteDelta(v: number): string {
  if (v >= 900) return `× ${new Intl.NumberFormat("fr-FR").format(Math.round(v / 100 + 1))}`;
  return `${Math.abs(v)} %`;
}

/** Les jours de `debut` à `fin` inclus. */
export function jours(debut: string, fin: string): string[] {
  const out: string[] = [];
  for (let j = debut; j <= fin; j = decaler(j, 1)) out.push(j);
  return out;
}

/** Série par jour, une clé par groupe (`cle(c)`), pour un graphique empilé. */
export function serieParJour<T>(lignes: T[], jour: (x: T) => string, cle: (x: T) => string, valeur: (x: T) => number, debut: string, fin: string) {
  const js = jours(debut, fin);
  const index = new Map(js.map((j, i) => [j, i]));
  const groupes = new Set<string>();
  const data: Record<string, number | string>[] = js.map((j) => ({ jour: j }));
  for (const x of lignes) {
    const i = index.get(jour(x));
    if (i === undefined) continue;
    const k = cle(x);
    groupes.add(k);
    data[i][k] = ((data[i][k] as number) || 0) + valeur(x);
  }
  return { data, groupes: [...groupes] };
}

export const normaliser = (t: string) => (t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

const COULEURS: Record<string, string> = {
  chloe: "#f06292", sarah: "#64b5f6", sophie: "#ba68c8", jade: "#81c784", maddie: "#ffb74d", clara: "#4dd0e1", amanda: "#e57373", lila: "#a1887f",
};
const AUTRES = ["#90caf9", "#ce93d8", "#80cbc4", "#ffcc80", "#ef9a9a", "#b0bec5"];
export function couleur(creatrice: string, i = 0): string {
  return COULEURS[normaliser(creatrice).split(/\s+/)[0]] || AUTRES[i % AUTRES.length];
}

export function creatrices(p: Pilotage): string[] {
  const vues = new Map<string, number>();
  const ajoute = (c: string, v: number) => {
    if (!c || c === "?") return;
    const deja = [...vues.keys()].find((k) => meme(k, c));            // « Maddy » et « Maddie » : une seule créatrice
    vues.set(deja || c, (vues.get(deja || c) || 0) + v);
  };
  p.clics.forEach((c) => ajoute(c.creatrice, c.visites));
  p.subs.forEach((s) => ajoute(s.creatrice, s.subsOf + s.subsMym));
  p.comptes.forEach((c) => ajoute(c.creatrice, 0));
  return [...vues.entries()].sort((a, b) => b[1] - a[1]).map(([c]) => c);
}

/** Même créatrice malgré les accents ou la casse (« Chloé » du classeur, « Chloe » d'un lien) ; 13/10 : Maddy = Maddie. */
const ALIAS: Record<string, string> = { maddy: "maddie" };
const prenomCr = (t: string) => { const p = normaliser(t).split(/\s+/)[0]; return ALIAS[p] || p; };
export const meme = (a: string, b: string) => prenomCr(a) === prenomCr(b);
/** 13/10 (Gaëtan : « uniquement les comptes qui sont verts ») : GOOD (un WARMUP d'avant le 12/10 compte comme GOOD). */
export const estGood = (etat: string) => ["good", "warmup"].includes(normaliser(etat));

export type SubsSomme = { subs: number; subsOf: number; subsMym: number; caEur: number; nonSaisis: number };
export function sommeSubs(subs: Sub[], debut: string, fin: string, taux: number, filtre: (s: Sub) => boolean = () => true): SubsSomme {
  const o: SubsSomme = { subs: 0, subsOf: 0, subsMym: 0, caEur: 0, nonSaisis: 0 };
  for (const s of subs) {
    if (s.jour < debut || s.jour > fin || !filtre(s)) continue;
    o.subsOf += s.subsOf; o.subsMym += s.subsMym; o.subs += s.subsOf + s.subsMym;
    o.caEur += s.caOfUsd * taux + s.caMymEur;
    if (!s.saisi) o.nonSaisis += 1;
  }
  return o;
}

export const fmt = (n: number) => new Intl.NumberFormat("fr-FR").format(Math.round(n));
export const fmtEur = (n: number) => `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(n)} €`;
export const fmtUsd = (n: number) => `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(n)} $`;
export const compact = (v: number) => (Math.abs(v) >= 1000 ? `${(v / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} k` : `${Math.round(v)}`);
export const jourCourt = (j: string) => { const d = new Date(j + "T12:00:00Z"); return `${d.getUTCDate()}/${String(d.getUTCMonth() + 1).padStart(2, "0")}`; };

/** 13/10 : clics sur les boutons OF et MYM d'une période, et les visites hors robots (tous pays) des mêmes liens : le taux de clic
 *  d'une page = boutons / visites. `releve` faux tant que le bot n'a encore rien relevé (jamais un faux 0). */
export type SommeBoutons = { of: number; mym: number; total: number; visitesTous: number; taux: number | null; releve: boolean };
export function sommeBoutons(d: Pilotage, debut: string, fin: string, filtre: (x: { creatrice: string; axe: string; source: string; qui: string }) => boolean = () => true): SommeBoutons {
  let of = 0, mym = 0, autre = 0, visitesTous = 0, releve = false;
  const cles = new Set<string>();
  for (const b of d.boutons || []) {
    if (b.jour < debut || b.jour > fin || !filtre(b)) continue;
    of += b.of; mym += b.mym; autre += b.autre; releve = true;
    cles.add(`${b.jour}|${b.creatrice}|${b.axe}|${b.source}|${b.qui}`);
  }
  for (const c of d.clics as Clic[]) if (cles.has(`${c.jour}|${c.creatrice}|${c.axe}|${c.source}|${c.qui}`)) visitesTous += c.horsRobots;
  const total = of + mym + autre;
  return { of, mym, total, visitesTous, taux: releve && visitesTous ? (of + mym) / visitesTous * 100 : null, releve };
}
export const pct = (x: number | null) => (x === null ? "–" : `${x.toFixed(1).replace(".", ",")} %`);
export type { Bouton };
