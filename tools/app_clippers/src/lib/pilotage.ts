/** Pilotage (12/10, Gaëtan : « une app pour tracker au quotidien les clics de toute la team : un onglet vertical, un horizontal, un
 *  subs »). Réservé à Gaëtan : un seul lien, `/p/<jeton>`, jeton = HMAC-SHA256(ADMIN_SECRET, "pilotage") en base64url, 24 caractères
 *  (aucune variable de plus sur Vercel ; changer ADMIN_SECRET change le lien).
 *
 *  Aucun appel GAML, Apify ni Metricool ici : le bot publie quatre onglets dans le tableur « App clippers · usage »
 *  (tools/bot_clippers/pilotage.py, à chaque passage du Dashboard, 15 minutes) et l'app les lit en un appel, avec 2 minutes de cache :
 *    « Pilotage comptes » : un compte Instagram par ligne, l'état du moment ;
 *    « Pilotage clics »   : jour × créatrice × axe × source × personne, visites payables (francophones, hors robots) ;
 *    « Pilotage subs »    : jour × créatrice, subs et CA OnlyFans et MYM (Data G&M) ;
 *    « Pilotage infos »   : heure de publication, fraîcheur des sources, taux USD → EUR. */
import { createHmac, timingSafeEqual } from "crypto";
import { jetonGoogle } from "./google";
import { tableur } from "./usage";
import { suiviIg } from "./igSource";
import { appliquerIg } from "./igSuivi";

export const ONGLETS = { comptes: "Pilotage comptes", clics: "Pilotage clics", subs: "Pilotage subs", infos: "Pilotage infos",
  boutons: "Pilotage boutons", identites: "Référentiel clippers" };

export function jetonPilotage(): string | null {
  const secret = process.env.ADMIN_SECRET;
  if (!secret) return null;
  return createHmac("sha256", secret).update("pilotage").digest("base64url").slice(0, 24);
}

export function jetonValide(jeton: string | undefined): boolean {
  const attendu = jetonPilotage();
  if (!attendu || !jeton || jeton.length !== attendu.length) return false;
  return timingSafeEqual(Buffer.from(jeton), Buffer.from(attendu));
}

export type Compte = {
  /** Numéro d'origine du parcours (1, 2 croissance ; 3 privé), jamais renuméroté après un ban. */
  numero?: number;
  roleCompte?: string;
  creatrice: string; axe: string; type: string; gerant: string; handle: string; etat: string;
  followers: number | null; d24: number | null; d7: number | null; courbe: (number | null)[];
  reelsAuj: number | null; reelsHier: number | null; reels7: number | null;
  vues7: number | null; vues7Avant: number | null;
  clicsAuj: number | null; clicsHier: number | null; clics7: number | null; clics7Avant: number | null;
  dernierReel: string; mesure: string;
  /** 13/10 : la dernière valeur relevée des vues de chaque Reel publié ces 7 jours (à côté des vues à 48 h, plus strictes). */
  vuesRecentes: number | null;
};
/** Une ligne de clics : un jour, une créatrice, un axe (Vertical / Horizontal), une source (Page principale, Bio Instagram, YouTube,
 *  Facebook, Clipper, Metricool, Libéré…), une personne ou une page ; `manquants` > 0 = des liens pas encore relevés ce jour-là. */
export type Clic = { jour: string; creatrice: string; axe: string; source: string; qui: string; visites: number; horsRobots: number; liens: number; manquants: number };
/** 13/10 : les clics sur les boutons OnlyFans et MYM des pages GAML, rangés comme les visites (relevés toutes les 3 h). */
export type Bouton = { jour: string; creatrice: string; axe: string; source: string; qui: string; of: number; mym: number; autre: number };
export type Sub = { jour: string; creatrice: string; subsOf: number; caOfUsd: number; subsMym: number; caMymEur: number; saisi: boolean };
export type Clipper360 = {
  uid: string; prenom: string; role: string; creatrice: string;
  tl: string; tlUid: string; manager: string; managerUid: string;
  app: boolean; comptes: { handle: string; etat: string; numero?: number }[];
  totalIg: number; gaml: string; gamlUuids: string; liens: number;
  visites7: number | null; qualiteVisites: string;
  reels7: number | null; anomalies: string;
};
export type Pilotage = { publie: string; fraicheur: string; taux: number; aujourdhui: string; comptes: Compte[]; clics: Clic[]; subs: Sub[]; boutons: Bouton[]; clippers: Clipper360[] };

const nb = (x: string | undefined): number | null => {
  const t = String(x ?? "").replace(/\s/g, "").replace(",", ".");
  if (t === "") return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
};
const n0 = (x: string | undefined): number => nb(x) ?? 0;

let cache: { t: number; valeur: Pilotage } | null = null;
let enCours: Promise<Pilotage> | null = null;

async function lire(): Promise<Pilotage> {
  const id = await tableur();
  const jeton = await jetonGoogle();
  const plages = [`'${ONGLETS.comptes}'!A2:V`, `'${ONGLETS.clics}'!A2:I`, `'${ONGLETS.subs}'!A2:G`, `'${ONGLETS.infos}'!A1:B10`, `'${ONGLETS.boutons}'!A2:H`, `'${ONGLETS.identites}'!A2:W`, "'Comptes app'!A2:M"];
  const url = (ps: string[]) => `https://sheets.googleapis.com/v4/spreadsheets/${id}/values:batchGet?${ps.map((p) => `ranges=${encodeURIComponent(p)}`).join("&")}`;
  let r = await fetch(url(plages), { headers: { Authorization: `Bearer ${jeton}` }, cache: "no-store" });
  // 13/10 : l'onglet des boutons n'existe qu'après la première publication du bot ; sans lui, le reste se lit quand même
  if (r.status === 400) r = await fetch(url(plages.slice(0, 6)), { headers: { Authorization: `Bearer ${jeton}` }, cache: "no-store" });
  if (r.status === 400) r = await fetch(url(plages.slice(0, 5)), { headers: { Authorization: `Bearer ${jeton}` }, cache: "no-store" });
  if (r.status === 400) r = await fetch(url(plages.slice(0, 4)), { headers: { Authorization: `Bearer ${jeton}` }, cache: "no-store" });
  if (!r.ok) throw new Error(`Sheets ${r.status}`);
  const d = (await r.json()) as { valueRanges?: { values?: string[][] }[] };
  const [vc, vk, vs, vi, vb, vref, vapp] = (d.valueRanges || []).map((x) => x.values || []);
  // Seul le numéro sort de cette table : ses clés d'app restent côté serveur.
  const numeros = new Map((vapp || []).filter(l => l[4]).map(l => [l[4].replace(/^@/, "").toLowerCase(), n0(l[3])]));
  const roles = new Map((vapp || []).filter(l => l[4]).map(l => [l[4].replace(/^@/, "").toLowerCase(), l[12] || ""]));
  const infos = Object.fromEntries((vi || []).map((l) => [l[0], l[1]]));
  const comptes: Compte[] = (vc || []).filter((l) => l[4]).map((l) => ({
    creatrice: l[0] || "?", axe: l[1] || "", type: l[2] || "", gerant: l[3] || "", handle: l[4] || "", etat: l[5] || "", numero: numeros.get(l[4].replace(/^@/, "").toLowerCase()), roleCompte: roles.get(l[4].replace(/^@/, "").toLowerCase()),
    followers: nb(l[6]), d24: nb(l[7]), d7: nb(l[8]), courbe: String(l[9] || "").split(";").map((x) => nb(x)),
    reelsAuj: nb(l[10]), reelsHier: nb(l[11]), reels7: nb(l[12]), vues7: nb(l[13]), vues7Avant: nb(l[14]),
    clicsAuj: nb(l[15]), clicsHier: nb(l[16]), clics7: nb(l[17]), clics7Avant: nb(l[18]), dernierReel: l[19] || "", mesure: l[20] || "", vuesRecentes: nb(l[21]),
  }));
  const clics: Clic[] = (vk || []).filter((l) => /^\d{4}-\d{2}-\d{2}$/.test(l[0] || "")).map((l) => ({
    jour: l[0], creatrice: l[1] || "?", axe: l[2] || "", source: l[3] || "", qui: l[4] || "",
    visites: n0(l[5]), horsRobots: n0(l[6]), liens: n0(l[7]), manquants: n0(l[8]),
  }));
  const subs: Sub[] = (vs || []).filter((l) => /^\d{4}-\d{2}-\d{2}$/.test(l[0] || "")).map((l) => ({
    jour: l[0], creatrice: l[1] || "?", subsOf: n0(l[2]), caOfUsd: n0(l[3]), subsMym: n0(l[4]), caMymEur: n0(l[5]), saisi: l[6] === "oui",
  }));
  const boutons: Bouton[] = (vb || []).filter((l) => /^\d{4}-\d{2}-\d{2}$/.test(l[0] || "")).map((l) => ({
    jour: l[0], creatrice: l[1] || "?", axe: l[2] || "", source: l[3] || "", qui: l[4] || "", of: n0(l[5]), mym: n0(l[6]), autre: n0(l[7]),
  }));
  const clippers: Clipper360[] = (vref || []).filter((l) => l[0]).map((l) => ({
    uid: l[0], prenom: l[1] || "", role: l[2] || "", creatrice: l[3] || "",
    tl: l[4] || "", tlUid: l[5] || "", manager: l[6] || "", managerUid: l[7] || "",
    app: l[8] === "OUI", comptes: [[l[9], l[10]], [l[11], l[12]], [l[13], l[14]]]
      .map((pair, i) => ({ handle: pair[0] || "", etat: pair[1] || "", numero: numeros.get((pair[0] || "").replace(/^@/, "").toLowerCase()) ?? i + 1 })).filter(c => Boolean(c.handle)),
    totalIg: n0(l[15]), gaml: l[16] || "", gamlUuids: l[17] || "", liens: n0(l[18]),
    visites7: nb(l[19]), qualiteVisites: l[20] || "", reels7: nb(l[21]), anomalies: l[22] || "",
  }));
  const aujourdhui = new Intl.DateTimeFormat("fr-CA", { timeZone: "Europe/Paris", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  // 24/10 : followers, Reels et vues viennent du suivi RapidAPI quand il connaît le compte (lib/igSuivi) ; l'ancien relevé du bot
  // ne voit pas les comptes « restreints » (Caroline, Yves…). Sans suivi lisible, rien ne change.
  const ig = await suiviIg(aujourdhui).catch(() => null);
  const comptesIg = ig ? comptes.map((c) => {
    const x = appliquerIg({ handle: c.handle, followers: c.followers, reels7: c.reels7, vues7: c.vuesRecentes ?? c.vues7, role: c.roleCompte,
      mesure: c.mesure, dernierReel: c.dernierReel }, ig, aujourdhui);
    return { ...c, followers: x.followers, reels7: x.reels7, vues7: x.vues7, vuesRecentes: x.vues7, roleCompte: x.role || c.roleCompte,
      mesure: x.mesure || c.mesure, dernierReel: x.dernierReel ?? c.dernierReel };
  }) : comptes;
  return { publie: infos["Publié"] || "", fraicheur: infos["Fraîcheur"] || "", taux: nb(infos["Taux USD→EUR"]) ?? 0.92, aujourdhui, comptes: comptesIg, clics, subs, boutons, clippers };
}

/** Les quatre onglets, lus en un appel (cache 2 minutes : le bot publie au plus toutes les 15). */
export async function pilotage(): Promise<Pilotage> {
  if (cache && Date.now() - cache.t < 2 * 60 * 1000) return cache.valeur;
  if (!enCours) {
    enCours = lire().then((v) => { cache = { t: Date.now(), valeur: v }; return v; }).finally(() => { enCours = null; });
  }
  try {
    return await enCours;
  } catch (e) {
    if (cache) return cache.valeur;                                    // Google en panne : la dernière version connue
    throw e;
  }
}
