/** 24/10 (Gaëtan : « affiche la cadence sur les sept derniers jours, les vues sur les sept derniers jours, les followers et les
 *  clics » ; « dans les versements, un truc par rapport à l'objectif : j'ai rajouté un objectif de Reels et d'input »).
 *  Pur, sans accès réseau, testé par tests/activite.cjs.
 *
 *  Source des Reels : la colonne « Reels par jour (17 j) » de l'onglet « Comptes app », publiée par le bot
 *  (dashboard.reels_par_jour) : les Reels VUS par le bot, jour par jour à Paris. C'est un minimum, jamais un chiffre inventé.
 *
 *  Prime volume (annonce Discord du 21/10, période de paie de 15 jours) : en moyenne chaque jour, sur les 2 comptes de croissance,
 *    3 Reels par jour et par compte et au moins 200 clics payés → +10 $ ; 6 Reels et 400 clics → +20 $ ; 9 Reels et 600 clics → +30 $.
 *  Règle (Gaëtan, 24/10 : « la prime est la cadence moyenne sur chaque compte de croissance ») : CHAQUE compte de croissance doit
 *  tenir la moyenne. La cadence retenue est donc celle du moins actif de ses 2 comptes de croissance les plus actifs : 6 Reels
 *  par jour sur un compte et 0 sur l'autre, c'est 0, pas 3. La moyenne se fait sur les jours clos de la période. */
import { decaler } from "./dates";

export type Palier = { reels: number; clics: number; bonus: number; emoji: string };
export const PALIERS: Palier[] = [
  { reels: 3, clics: 200, bonus: 10, emoji: "👍" },
  { reels: 6, clics: 400, bonus: 20, emoji: "✅" },
  { reels: 9, clics: 600, bonus: 30, emoji: "🚀" },
];
export const COMPTES_CROISSANCE = 2;                                 // la prime se juge sur ses 2 comptes de croissance

export type CompteActivite = {
  handle: string; etat: string; role?: string;
  followers: number | null; reels7: number | null; vues7: number | null;
  /** Reels publiés par jour ; undefined si le bot ne publie pas encore la colonne. */
  jours?: Record<string, number>;
  /** 31/10 : vues à ce jour des Reels publiés chaque jour (suivi RapidAPI) ; undefined sans suivi. */
  vuesJours?: Record<string, number>;
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

/** `parCompte` : les Reels du jour, compte de croissance par compte de croissance (dans l'ordre de `Semaine.croissance`). */
export type JourActivite = { jour: string; reels: number | null; clics: number | null; parCompte?: number[] };
/** Un compte de croissance et sa cadence : `rang` = son n° parmi ses comptes de croissance (« Compte 1 », « Compte 2 »), le même
 *  dans Comptes et dans Versements. */
export type CadenceSemaine = { handle: string; rang: number; reels: number | null; moyenne: number | null };
export type Semaine = {
  jours: JourActivite[];
  /** 31/10 (Gaëtan : « 3,3 Reels par jour de moyenne sur les deux comptes ») : Reels et cadence de ses comptes de croissance,
   *  le compte privé à part (il porte le lien, il ne compte pas dans la prime). */
  reels: number | null; cadence: number | null; vues: number | null; followers: number | null; clics: number | null;
  parJour: boolean;               // la colonne jour par jour est publiée : le graphique peut s'afficher
  croissance: CadenceSemaine[];   // 31/10 : « moyenne par jour sur le compte 1, moyenne par jour sur le compte 2 »
};

/** 31/10 : ses comptes de croissance, dans l'ordre de l'app (comptesAffiches : actifs d'abord) ; ni le privé, ni un compte à créer.
 *  Leur position fait « Compte 1 », « Compte 2 »… partout dans l'app. */
export function comptesCroissance<T extends CompteActivite>(comptes: T[]): T[] {
  return comptes.filter((c) => !estPrive(c.role) && !plat(c.etat).includes("creer"));
}

/** Un compte dont les Reels sont connus sur la fenêtre qui commence `depuis` : « Reels 7 j » relevé (0 compris, le bot ne le
 *  remplit que pour un compte relu dans les 36 h), ou au moins un Reel vu depuis `depuis`. Sinon ses Reels sont inconnus.
 *  24/10 (après déploiement : 0 Reel affiché pour un clipper à 1 129 clics ; son seul compte « lu » avait des Reels du 12 et du
 *  13/10, puis plus rien, et ses deux autres comptes ne sont pas lus du tout). */
export const reelsMesures = (c: CompteActivite, depuis: string) =>
  c.reels7 !== null || Object.keys(c.jours || {}).some((j) => j >= depuis);

/** Les 7 derniers jours clos du clipper (comptes déjà triés par comptesAffiches) : Reels et cadence de ses comptes de croissance,
 *  vues et followers de tous ses comptes, clics payés. */
export function semaine(comptes: CompteActivite[], aujourdhui: string, clicsParJour: Record<string, number> | null): Semaine {
  const jours = joursClos(aujourdhui, 7);
  const croissance = comptesCroissance(comptes);
  const lus = croissance.some((c) => reelsMesures(c, jours[0]));
  // 24/10 : un compte du LOG DASHBOARD absent de la fiche du bot n'a pas de détail jour par jour ; ses Reels comptent quand même,
  // par « Reels 7 j » (sans graphique) plutôt que d'être oubliés
  const parJour = lus && croissance.some((c) => c.jours !== undefined)
    && croissance.filter((c) => reelsMesures(c, jours[0])).every((c) => c.jours !== undefined);
  const detail: JourActivite[] = jours.map((j) => {
    const parCompte = croissance.map((c) => (c.jours || {})[j] || 0);
    return {
      jour: j,
      reels: parJour ? parCompte.reduce((s, n) => s + n, 0) : null,
      clics: clicsParJour ? clicsParJour[j] || 0 : null,
      ...(parJour ? { parCompte } : {}),
    };
  });
  const reels = !lus ? null : parJour ? detail.reduce((s, d) => s + (d.reels || 0), 0) : somme(croissance.map((c) => c.reels7));
  return {
    jours: detail,
    reels,
    cadence: reels === null ? null : Math.round((reels / 7) * 10) / 10,
    vues: somme(comptes.map((c) => c.vues7)),
    followers: somme(comptes.map((c) => c.followers)),
    clics: clicsParJour ? detail.reduce((s, d) => s + (d.clics || 0), 0) : null,
    parJour,
    croissance: croissance.map((c, i) => {
      const r = !reelsMesures(c, jours[0]) ? null
        : c.jours !== undefined ? jours.reduce((s, j) => s + ((c.jours || {})[j] || 0), 0) : c.reels7;
      return { handle: c.handle, rang: i + 1, reels: r, moyenne: r === null ? null : Math.round((r / 7) * 10) / 10 };
    }),
  };
}

/** 31/10 (Gaëtan : « un graphique pour mettre en corrélation… les Reels publiés sur les deux comptes de croissance mènent vraiment
 *  aux vues et aux clics ») : 14 jours clos, jour par jour, les Reels de chaque compte de croissance, les vues à ce jour des Reels
 *  publiés ce jour-là, et les clics payés du jour. Avec ce qu'un Reel rapporte en moyenne et le meilleur jour. null si aucun Reel
 *  n'est suivi jour par jour. */
export type JourCorrelation = { jour: string; reels: number[]; vues: number | null; clics: number | null };
export type Correlation = {
  jours: JourCorrelation[];
  croissance: { handle: string; rang: number }[];
  reels: number; vues: number | null; clics: number | null;
  vuesParReel: number | null; clicsParReel: number | null;
  meilleur: { jour: string; reels: number; vues: number | null; clics: number | null } | null;
};

export function correlation(comptes: CompteActivite[], aujourdhui: string, clicsParJour: Record<string, number> | null, n = 14): Correlation | null {
  const croissance = comptesCroissance(comptes).filter((c) => c.jours !== undefined);
  const jours = joursClos(aujourdhui, n);
  if (!croissance.some((c) => reelsMesures(c, jours[0]))) return null;
  const avecVues = croissance.some((c) => c.vuesJours !== undefined);
  const detail: JourCorrelation[] = jours.map((j) => ({
    jour: j,
    reels: croissance.map((c) => (c.jours || {})[j] || 0),
    vues: avecVues ? croissance.reduce((s, c) => s + ((c.vuesJours || {})[j] || 0), 0) : null,
    clics: clicsParJour ? clicsParJour[j] || 0 : null,
  }));
  const reels = detail.reduce((s, d) => s + d.reels.reduce((t, x) => t + x, 0), 0);
  const vues = avecVues ? detail.reduce((s, d) => s + (d.vues || 0), 0) : null;
  const clics = clicsParJour ? detail.reduce((s, d) => s + (d.clics || 0), 0) : null;
  const total = (d: JourCorrelation) => d.reels.reduce((t, x) => t + x, 0);
  const cle = (d: JourCorrelation) => (clics !== null ? d.clics || 0 : d.vues || 0);
  const top = [...detail].sort((a, b) => cle(b) - cle(a) || total(b) - total(a))[0];
  return {
    jours: detail,
    croissance: croissance.map((c, i) => ({ handle: c.handle, rang: i + 1 })),
    reels, vues, clics,
    vuesParReel: reels && vues !== null ? Math.round(vues / reels) : null,
    clicsParReel: reels && clics !== null ? Math.round((clics / reels) * 10) / 10 : null,
    meilleur: top && cle(top) > 0 ? { jour: top.jour, reels: total(top), vues: top.vues, clics: top.clics } : null,
  };
}

/** `suspendu` : compte en « appel à faire », que le suivi ne relit plus ; il ne publie rien, il compte pour 0 (« comptes en règle »). */
export type CadenceCompte = { handle: string; rang: number; reels: number; moyenne: number | null; lu: boolean; suspendu?: boolean; introuvable?: boolean };
export type ReelsPrime = {
  debut: string; fin: string;
  joursEcoules: number;           // jours clos de la période (aujourd'hui exclu)
  totalJours: number;             // 31/10 : jours de la période (15 ou 16)
  joursRestants: number;          // 31/10 : jours encore ouverts, aujourd'hui compris (0 : période finie)
  reels: number;                  // Reels publiés sur ses comptes de croissance pendant ces jours
  /** Cadence retenue : Reels par jour du moins actif de ses 2 comptes de croissance les plus actifs. null si on ne peut pas
   *  conclure : période commencée aujourd'hui, ou un des 2 comptes pas lu par le bot. */
  moyenne: number | null;
  parCompte: CadenceCompte[];     // ses comptes de croissance, les plus actifs d'abord, les non lus à la fin
  comptes: number;                // comptes de croissance trouvés
  manque: "" | "deuxieme_compte" | "deuxieme_non_lu";
  mesure: boolean;                // false : colonne pas publiée, ou aucun compte de croissance lu par le bot
};

/** Les Reels de la période de paie, compte de croissance par compte de croissance (le compte privé ne compte pas). */
export function reelsPrime(comptes: CompteActivite[], debut: string, fin: string, aujourdhui: string): ReelsPrime {
  const croissance = comptesCroissance(comptes);                       // 31/10 : un compte à créer n'est pas un 2e compte
  const hier = decaler(aujourdhui, -1);
  const dernier = hier < fin ? hier : fin;
  const jours: string[] = [];
  for (let j = debut; j <= dernier; j = decaler(j, 1)) jours.push(j);
  const parCompte: CadenceCompte[] = croissance.map((c, i) => {
    const reels = jours.reduce((t, j) => t + ((c.jours || {})[j] || 0), 0);
    // 28/10 : un compte introuvable sur Instagram (banni, supprimé, renommé) ne publie plus : 0, comme un compte en appel
    const introuvable = plat(c.etat) === "introuvable";
    const suspendu = !reelsMesures(c, debut) && (plat(c.etat).includes("appel") || introuvable);
    const lu = suspendu || reelsMesures(c, debut);
    return { handle: c.handle, rang: i + 1, reels, lu, suspendu, ...(introuvable ? { introuvable } : {}),
      moyenne: lu && jours.length ? Math.round((reels / jours.length) * 10) / 10 : null };
  }).sort((a, b) => Number(b.lu) - Number(a.lu) || (b.moyenne ?? 0) - (a.moyenne ?? 0));
  const lus = parCompte.filter((c) => c.lu);
  const deux = parCompte.slice(0, COMPTES_CROISSANCE);
  let moyenne: number | null = null, manque: ReelsPrime["manque"] = "";
  if (croissance.length < COMPTES_CROISSANCE) {
    manque = "deuxieme_compte";
    moyenne = jours.length && lus.length ? 0 : null;                     // la prime demande 2 comptes : sans le 2e, 0
  } else if (deux.some((c) => !c.lu)) {
    manque = "deuxieme_non_lu";
  } else if (jours.length) {
    moyenne = Math.min(...deux.map((c) => c.moyenne ?? 0));
  }
  let totalJours = 0;
  for (let j = debut; j <= fin; j = decaler(j, 1)) totalJours++;
  return {
    debut, fin, joursEcoules: jours.length, totalJours, joursRestants: Math.max(0, totalJours - jours.length - (aujourdhui > fin ? 1 : 0)),
    reels: parCompte.reduce((t, c) => t + c.reels, 0),
    moyenne, parCompte, comptes: croissance.length, manque,
    mesure: comptes.some((c) => c.jours !== undefined) && lus.some((c) => !c.suspendu),   // un compte suspendu n'est pas « lu »
  };
}

/** 31/10 (Gaëtan : « l'objectif pour atteindre, augmenter la cadence sur le compte 1 ou le compte 2 ») : les Reels par jour à
 *  publier sur un compte, d'aujourd'hui à la fin de la période, pour finir la période à `cible` de moyenne. 0 : déjà acquis,
 *  même sans rien publier de plus. null : période finie. Arrondi au dixième supérieur. Pur. */
export function rythmeNecessaire(reels: number, totalJours: number, joursRestants: number, cible: number): number | null {
  if (joursRestants <= 0) return null;
  const manque = cible * totalJours - reels;
  return manque <= 0 ? 0 : Math.ceil(Math.round((manque / joursRestants) * 1000) / 100) / 10;
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
