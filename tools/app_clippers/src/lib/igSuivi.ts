/** 24/10 (Gaëtan : « si le bot ne lit aucun compte du clipper, c'est nous le problème… on ne traque pas ses followers sur ses
 *  comptes Instagram ») : l'app prend ses chiffres Instagram au suivi RapidAPI, celui qui marche.
 *
 *  Le suivi RapidAPI (tools/bot_clippers/instagram_rapidapi.py, lancé 3 fois par jour par GitHub Actions) relit chaque compte du
 *  LOG DASHBOARD par son ID Instagram et publie deux onglets du tableur d'usage :
 *    « IG · Comptes » : une ligne par compte (statut public / privé / introuvable, followers, publications, Reels et vues 7 j…) ;
 *    « IG · Reels »   : chaque Reel des 60 derniers jours (@, date de publication, vues).
 *  Jusqu'ici l'app lisait l'ancien relevé du bot (Apify, onglets « Comptes app » et « Pilotage comptes »), qui ne voit pas les
 *  comptes « restreints » : le 24/10, le compte de croissance de Caroline (1 669 followers, 20 Reels et 223 683 vues en 7 jours
 *  selon RapidAPI) s'affichait vide. Pur, testé par tests/ig-suivi.cjs. */

export type IgCompte = {
  handle: string; statut: string;                    // « public », « privé » ou « introuvable »
  followers: number | null; publications: number | null;
  reels7: number | null; reels30: number | null; vues7: number | null;
  dernierReel: string;                               // ISO, vide si aucun
  reluLe: string;                                    // ISO du dernier relevé du profil
};
export type IgSuivi = { comptes: Map<string, IgCompte>; jours: Map<string, Record<string, number>> };

const plat = (t?: string) => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
export const cleIg = (h?: string) => plat(h).replace(/^@+/, "");
const nb = (x: string | undefined): number | null => {
  const t = String(x ?? "").replace(/\s/g, "").replace(",", ".");
  if (t === "") return null;
  const v = Number(t);
  return Number.isFinite(v) ? v : null;
};

const PARIS = new Intl.DateTimeFormat("fr-CA", { timeZone: "Europe/Paris", year: "numeric", month: "2-digit", day: "2-digit" });
/** Le jour à Paris « AAAA-MM-JJ » d'un horodatage ISO ; "" si illisible. */
export function jourParis(iso: string): string {
  const t = Date.parse(iso || "");
  return Number.isFinite(t) ? PARIS.format(new Date(t)) : "";
}

/** « IG · Comptes »!A2:W : Créatrice, Gérant, Type, @, ID, Statut, Followers, Δ 24 h, Δ 7 j, Publications, Reels 24 h, Reels 7 j,
 *  Reels 15 j, Reels 30 j, Reels 60 j, Vues 7 j, Vues 15 j, Vues 30 j, Vues 60 j, Dernier Reel, Profil relu le, Reels relus le,
 *  Renommé en. Un compte renommé se trouve sous ses deux @. */
export function lireIgComptes(lignes: string[][]): Map<string, IgCompte> {
  const out = new Map<string, IgCompte>();
  for (const l of lignes) {
    const h = cleIg(l[3]);
    if (!h) continue;
    const c: IgCompte = {
      handle: h, statut: plat(l[5]), followers: nb(l[6]), publications: nb(l[9]),
      reels7: nb(l[11]), reels30: nb(l[13]), vues7: nb(l[15]), dernierReel: l[19] || "", reluLe: l[20] || "",
    };
    out.set(h, c);
    const nouveau = cleIg(l[22]);
    if (nouveau && !out.has(nouveau)) out.set(nouveau, { ...c, handle: nouveau });
  }
  return out;
}

/** « IG · Reels »!D2:H (@, Code, Lien, Publié le, Vues) → par @, {jour à Paris : Reels publiés}, depuis `depuis` inclus. */
export function lireIgJours(lignes: string[][], depuis: string): Map<string, Record<string, number>> {
  const out = new Map<string, Record<string, number>>();
  const vus = new Set<string>();
  for (const l of lignes) {
    const h = cleIg(l[0]), j = jourParis(l[3] || "");
    if (!h || !j || j < depuis) continue;
    const code = `${h}|${l[1] || l[2] || l[3]}`;                     // un Reel compte une fois
    if (vus.has(code)) continue;
    vus.add(code);
    const m = out.get(h) || {};
    m[j] = (m[j] || 0) + 1;
    out.set(h, m);
  }
  return out;
}

/** Un compte qui publie des Reels publics est un compte de croissance, quel que soit son n° dans la fiche du bot (le 24/10, le
 *  compte « callistachloe.prv » de Caroline, n° 3 donc marqué privé, publiait 7 Reels par semaine). Privé sur Instagram : privé.
 *  Sinon, la fiche du bot décide (un compte privé « ouvert » sans Reel, comme celui de Romaric, reste le compte du lien). */
export function roleIg(roleFiche: string | undefined, ig?: IgCompte): string {
  if (!ig || ig.statut === "introuvable") return roleFiche || "";
  if (ig.statut === "prive") return "privé";
  if ((ig.reels30 ?? 0) > 0 || (ig.reels7 ?? 0) > 0) return "croissance";
  return roleFiche || "";
}

/** « aujourd'hui », « hier », « il y a 3 j » ou « aucun » : le format du bot, lu par alerteMesure. */
export function dernierReelRelatif(iso: string, aujourdhui: string): string {
  const j = jourParis(iso);
  if (!j) return "aucun";
  const n = Math.round((Date.parse(aujourdhui + "T12:00:00Z") - Date.parse(j + "T12:00:00Z")) / 86400000);
  return n <= 0 ? "aujourd'hui" : n === 1 ? "hier" : `il y a ${n} j`;
}

type Base = { handle: string; followers: number | null; reels7: number | null; vues7: number | null; role?: string; jours?: Record<string, number>; mesure?: string; dernierReel?: string };

/** Les chiffres RapidAPI remplacent ceux de l'ancien relevé pour un compte que RapidAPI connaît ; sinon rien ne change. */
export function appliquerIg<T extends Base>(c: T, ig: IgSuivi | null, aujourdhui: string): T {
  const x = ig?.comptes.get(cleIg(c.handle));
  if (!ig || !x) return c;
  if (x.statut === "introuvable") return { ...c, mesure: "introuvable (RapidAPI)" };
  const prive = x.statut === "prive";
  return {
    ...c,
    followers: x.followers ?? c.followers,
    reels7: prive ? c.reels7 : x.reels7,
    vues7: prive ? c.vues7 : x.vues7,
    jours: prive ? c.jours : (ig.jours.get(cleIg(c.handle)) || ig.jours.get(x.handle) || {}),
    role: roleIg(c.role, x),
    mesure: prive ? "privé (RapidAPI)" : "lu (RapidAPI)",
    dernierReel: prive ? (c.dernierReel || "") : dernierReelRelatif(x.dernierReel, aujourdhui),
  };
}
