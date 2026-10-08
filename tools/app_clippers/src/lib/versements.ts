/** Les versements d'un clipper : visites francophones jour par jour (sur 14 jours, ou la période de paie en cours si elle
 *  est plus longue), total et montant de la période en cours, prochaine date de versement, aujourd'hui, hier, et les
 *  périodes précédentes déjà versées. Les appels GAML sont lancés par ordre d'importance (aujourd'hui, hier, puis les
 *  jours plus anciens, puis l'historique) ; si la limite est atteinte en route, on rend ce qu'on a avec `partiel`. */
import { aujourdhuiParis, decaler, libelleLong, libellePlage } from "./dates";
import { ErreurGaml, visitesJour, visitesPeriodePassee } from "./gaml";
import { ANCIENS_AVANT, BASCULE_CLIC, CLICS_DEPUIS, montant, PAIE_FIXE, periodeEnCours, periodePrecedente, TAUX_CLIC, type PeriodePaie } from "./paie";
import { normaliser, type Clipper } from "./clippers";
import { regimeDe } from "./regimes";

export type Jour = { jour: string; visites: number; complet: boolean };
export type Bloc = { debut: string; fin: string; paie: string; libelle: string; libellePaie: string; visites: number; montant: number; complet: boolean };
export type Versements = {
  prenom: string; creatrice: string; taux: number;
  fixe: boolean;                  // 08/10 : au fixe (Caroline, Lilian, Josué, Yves, Rianah…), les montants ne sont que pour info
  depuis: string;                 // premier jour compté dans la période en cours (le 08/10 pour un ancien passé au clic)
  liens: { url: string; creeLe: string }[];
  periode: Bloc;
  aujourdhui: Jour; hier: Jour;
  serie: Jour[];
  precedents: (Bloc & { versee: boolean })[];
  partiel: boolean;
  majA: string;
};

async function enParallele<T>(taches: (() => Promise<T>)[], n: number): Promise<T[]> {
  const res: T[] = new Array(taches.length);
  let i = 0;
  await Promise.all(Array.from({ length: Math.min(n, taches.length) }, async () => {
    while (i < taches.length) { const k = i++; res[k] = await taches[k](); }
  }));
  return res;
}

function bloc(p: PeriodePaie, visites: number, complet: boolean): Bloc {
  return { ...p, libelle: libellePlage(p.debut, p.fin), libellePaie: libelleLong(p.paie), visites, montant: montant(visites), complet };
}

export async function versements(c: Clipper): Promise<Versements> {
  const aujourdhui = aujourdhuiParis();
  const p = periodeEnCours(aujourdhui);
  const debutSerie = decaler(aujourdhui, -13) < p.debut ? decaler(aujourdhui, -13) : p.debut;
  const jours: string[] = [];
  for (let j = aujourdhui; j >= debutSerie; j = decaler(j, -1)) jours.push(j);         // du plus récent au plus ancien : l'ordre des appels
  const liens = c.liens.filter((l) => l.id);
  const etat = { limite: false };
  const lire = async (lienId: string, creeLe: string, debut: string, fin: string, unJour: boolean): Promise<number | null> => {
    if (creeLe && creeLe > fin) return 0;                                   // lien créé après : aucune visite possible, aucun appel
    if (etat.limite) return null;
    try { return unJour ? await visitesJour(lienId, debut, aujourdhui) : await visitesPeriodePassee(lienId, debut, fin); }
    catch (e) { if ((e as ErreurGaml).limite) etat.limite = true; return null; }
  };
  const premierLien = liens.map((l) => l.creeLe).filter(Boolean).sort()[0] || aujourdhui;
  // 08/10 (revue) : le régime publié par le bot fait foi (onglet « Régime paie ») ; la règle locale n'est qu'un repli
  const r = await regimeDe(c.cle);
  const fixe = r ? r.regime === "fixe" : PAIE_FIXE.has(normaliser(c.prenom).split(" ")[0] || "");
  const plancher = r ? r.clicDepuis : (!fixe && premierLien < ANCIENS_AVANT ? BASCULE_CLIC : "");   // un ancien : au clic depuis le 08/10
  const plancherLien = (id: string) => r?.liens.get(id) || "";        // un lien repris : compté à partir de la reprise
  const max = (a: string, b: string) => (a > b ? a : b);
  const depuis = plancher > p.debut ? plancher : p.debut;
  const precedentsP: PeriodePaie[] = [];
  let q = periodePrecedente(p);
  for (let i = 0; i < 2 && q.fin >= CLICS_DEPUIS; i++) {
    if (q.fin >= premierLien && q.fin >= plancher) precedentsP.push(q);  // pas d'historique avant son premier lien ni avant son passage au clic
    q = periodePrecedente(q);
  }

  const taches: (() => Promise<number | null>)[] = [];
  const index: { jour?: string; periode?: number; lien: number }[] = [];
  for (const j of jours) liens.forEach((l, k) => { taches.push(() => lire(l.id, l.creeLe, j, j, true)); index.push({ jour: j, lien: k }); });
  precedentsP.forEach((pp, n) => liens.forEach((l, k) => {
    const debutL = max(max(pp.debut, plancher), plancherLien(l.id));
    taches.push(() => (debutL > pp.fin ? Promise.resolve(0) : lire(l.id, l.creeLe, debutL, pp.fin, false)));
    index.push({ periode: n, lien: k });
  }));
  const resultats = await enParallele(taches, 4);

  const parJour = new Map<string, { visites: number; complet: boolean }>();
  for (const j of jours) parJour.set(j, { visites: 0, complet: liens.length > 0 });
  const parPeriode = precedentsP.map(() => ({ visites: 0, complet: liens.length > 0 }));
  resultats.forEach((v, i) => {
    const x = index[i];
    if (x.jour !== undefined && x.jour < plancherLien(liens[x.lien].id)) return;   // avant la reprise : les visites de l'ancien
    const cible = x.jour !== undefined ? parJour.get(x.jour)! : parPeriode[x.periode!];
    if (v === null) cible.complet = false; else cible.visites += v;
  });
  const serie: Jour[] = [...jours].reverse().map((j) => ({ jour: j, ...parJour.get(j)! }));
  const dansPeriode = serie.filter((j) => j.jour >= depuis && j.jour <= p.fin);
  const visitesPeriode = dansPeriode.reduce((s, j) => s + j.visites, 0);
  const hier = decaler(aujourdhui, -1);
  return {
    prenom: c.prenom, creatrice: c.creatrice, taux: TAUX_CLIC, fixe, depuis,
    liens: liens.filter((l) => l.enabled).map((l) => ({ url: l.url, creeLe: l.creeLe })),
    periode: bloc(p, visitesPeriode, dansPeriode.every((j) => j.complet)),
    aujourdhui: serie.find((j) => j.jour === aujourdhui) || { jour: aujourdhui, visites: 0, complet: false },
    hier: serie.find((j) => j.jour === hier) || { jour: hier, visites: 0, complet: false },
    serie,
    precedents: precedentsP.map((pp, n) => ({ ...bloc(pp, parPeriode[n].visites, parPeriode[n].complet), versee: pp.paie < aujourdhui })),
    partiel: etat.limite || serie.some((j) => !j.complet) || parPeriode.some((x) => !x.complet),
    majA: new Date().toISOString(),
  };
}
