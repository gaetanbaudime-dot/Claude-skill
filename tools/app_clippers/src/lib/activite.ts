/** 24/10 (Gaëtan : « affiche la cadence sur les sept derniers jours, les vues sur les sept derniers jours, les followers et les
 *  clics » ; « dans les versements, un truc par rapport à l'objectif : j'ai rajouté un objectif de Reels et d'input »).
 *  Pur, sans accès réseau, testé par tests/activite.cjs.
 *
 *  Source des Reels : la colonne « Reels par jour (17 j) » de l'onglet « Comptes app », publiée par le bot
 *  (dashboard.reels_par_jour) : les Reels VUS par le bot, jour par jour à Paris. C'est un minimum, jamais un chiffre inventé.
 *
 *  Prime volume (annonce Discord du 21/10, période de paie de 15 jours) : en moyenne chaque jour, sur les 2 comptes de croissance,
 *    3 Reels par jour et par compte et au moins 200 clics payés → +10 $ ; 6 Reels et 400 clics → +20 $ ; 9 Reels et 600 clics → +30 $.
 *  Lecture retenue : « 3 Reels par jour et par compte », soit 6 Reels par jour sur les deux comptes (Gaëtan, 21/10 : « +10 $ si
 *  3 Reels/jour/compte sur les comptes 1 et 2 en moyenne sur 15 jours »). La moyenne se fait sur les jours clos de la période. */
import { decaler } from "./dates";

export type Palier = { reels: number; clics: number; bonus: number; emoji: string };
export const PALIERS: Palier[] = [
  { reels: 3, clics: 200, bonus: 10, emoji: "👍" },
  { reels: 6, clics: 400, bonus: 20, emoji: "✅" },
  { reels: 9, clics: 600, bonus: 30, emoji: "🚀" },
];
export const COMPTES_CROISSANCE = 2;

export type CompteActivite = {
  handle: string; etat: string; role?: string;
  followers: number | null; reels7: number | null; vues7: number | null;
  /** Reels publiés par jour ; undefined si le bot ne publie pas encore la colonne. */
  jours?: Record<string, number>;
};

/** « 2026-10-20:3 2026-10-22:2 » → { "2026-10-20": 3, "2026-10-22": 2 }. Ce qui est illisible est ignoré. */
export function lireJours(txt: string): Record<string, number> {
  const out: Record<string, number> = {};
  for (const morceau of String(txt || "").split(/\s+/)) {
    const m = /^(\d{4}-\d{2}-\d{2}):(\d+)$/.exec(morceau);
    if (m) out[m[1]] = (out[m[1]] || 0) + parseInt(m[2], 10);
  }
  return out;
}

const plat = (t?: string) => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
export const estPrive = (role?: string) => plat(role) === "prive";

const somme = (valeurs: (number | null | undefined)[]): number | null => {
  const connues = valeurs.filter((v): v is number => typeof v === "number" && Number.isFinite(v));
  return connues.length ? connues.reduce((s, v) => s + v, 0) : null;
};

/** Les `n` jours clos qui finissent hier, du plus ancien au plus récent. */
export function joursClos(aujourdhui: string, n = 7): string[] {
  return Array.from({ length: n }, (_, i) => decaler(aujourdhui, i - n));
}

export type JourActivite = { jour: string; reels: number | null; clics: number | null };
export type Semaine = {
  jours: JourActivite[];
  reels: number | null; cadence: number | null; vues: number | null; followers: number | null; clics: number | null;
  parJour: boolean;               // la colonne jour par jour est publiée : le graphique peut s'afficher
};

/** Un compte dont les Reels sont connus sur la fenêtre qui commence `depuis` : « Reels 7 j » relevé (0 compris, le bot ne le
 *  remplit que pour un compte relu dans les 36 h), ou au moins un Reel vu depuis `depuis`. Sinon ses Reels sont inconnus.
 *  24/10 (après déploiement : 0 Reel affiché pour un clipper à 1 129 clics ; son seul compte « lu » avait des Reels du 12 et du
 *  13/10, puis plus rien, et ses deux autres comptes ne sont pas lus du tout). */
export const reelsMesures = (c: CompteActivite, depuis: string) =>
  c.reels7 !== null || Object.keys(c.jours || {}).some((j) => j >= depuis);

/** Les 7 derniers jours clos du clipper, sur tous les comptes qu'il gère (déjà triés par comptesAffiches). */
export function semaine(comptes: CompteActivite[], aujourdhui: string, clicsParJour: Record<string, number> | null): Semaine {
  const jours = joursClos(aujourdhui, 7);
  const lus = comptes.some((c) => reelsMesures(c, jours[0]));
  const parJour = lus && comptes.some((c) => c.jours !== undefined);
  const detail: JourActivite[] = jours.map((j) => ({
    jour: j,
    reels: parJour ? comptes.reduce((s, c) => s + ((c.jours || {})[j] || 0), 0) : null,
    clics: clicsParJour ? clicsParJour[j] || 0 : null,
  }));
  const reels = !lus ? null : parJour ? detail.reduce((s, d) => s + (d.reels || 0), 0) : somme(comptes.map((c) => c.reels7));
  return {
    jours: detail,
    reels,
    cadence: reels === null ? null : Math.round((reels / 7) * 10) / 10,
    vues: somme(comptes.map((c) => c.vues7)),
    followers: somme(comptes.map((c) => c.followers)),
    clics: clicsParJour ? detail.reduce((s, d) => s + (d.clics || 0), 0) : null,
    parJour,
  };
}

export type ReelsPrime = {
  debut: string; fin: string;
  joursEcoules: number;           // jours clos de la période (aujourd'hui exclu)
  reels: number;                  // Reels publiés sur ses comptes de croissance pendant ces jours
  moyenne: number | null;         // Reels par jour et par compte de croissance ; null avant le premier jour clos
  comptes: number;                // comptes de croissance trouvés
  mesure: boolean;                // false : colonne pas publiée, ou aucun compte de croissance lu par le bot
};

/** Les Reels de la période de paie sur ses comptes de croissance (le compte privé ne compte pas). */
export function reelsPrime(comptes: CompteActivite[], debut: string, fin: string, aujourdhui: string): ReelsPrime {
  const croissance = comptes.filter((c) => !estPrive(c.role));
  const hier = decaler(aujourdhui, -1);
  const dernier = hier < fin ? hier : fin;
  const jours: string[] = [];
  for (let j = debut; j <= dernier; j = decaler(j, 1)) jours.push(j);
  const reels = croissance.reduce((s, c) => s + jours.reduce((t, j) => t + ((c.jours || {})[j] || 0), 0), 0);
  return {
    debut, fin, joursEcoules: jours.length, reels,
    moyenne: jours.length ? Math.round((reels / jours.length / COMPTES_CROISSANCE) * 10) / 10 : null,
    comptes: croissance.length,
    mesure: comptes.some((c) => c.jours !== undefined) && croissance.some((c) => reelsMesures(c, debut)),
  };
}

export type EtatPalier = Palier & { okReels: boolean; okClics: boolean; atteint: boolean; manqueReels: number; manqueClics: number };

/** Chaque palier avec ce qui manque ; `atteint` = le plus haut palier tenu à ce jour (null sinon). */
export function evaluerPrime(moyenne: number | null, clics: number | null): { paliers: EtatPalier[]; atteint: EtatPalier | null } {
  const m = moyenne ?? 0, k = clics ?? 0;
  const paliers = PALIERS.map((p) => {
    const okReels = moyenne !== null && m >= p.reels, okClics = clics !== null && k >= p.clics;
    return { ...p, okReels, okClics, atteint: okReels && okClics,
      manqueReels: Math.max(0, Math.round((p.reels - m) * 10) / 10), manqueClics: Math.max(0, p.clics - k) };
  });
  const atteint = [...paliers].reverse().find((p) => p.atteint) || null;
  return { paliers, atteint };
}
