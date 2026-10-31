/** Les clippers viennent en direct de GAML : chaque lien dont la note est « Clipping Prénom » (même règle que
 *  `_prenom_note` dans paie_clics.py), regroupé par prénom normalisé (un clipper peut avoir plusieurs liens, chez
 *  plusieurs créatrices : on additionne ; sa créatrice = le `name` du lien le plus récent, premier mot).
 *  Zéro configuration : le jeton d'un clipper est dérivé de son prénom avec le secret de l'app, donc un nouveau
 *  clipper est dans l'app dès que son lien GAML existe. Un jeton inconnu ne révèle rien (404). */
import { createHmac } from "crypto";
import { liensGaml, type LienGaml } from "./gaml";

/** Prénoms jamais traités comme clippers (CLICS_EXCLURE du bot), sans accent ni majuscule. */
const EXCLURE = new Set(["gaetan", "jonas", "x", "y"]);                // 13/10 : Rianah au clic pour son clipping, elle a son app

export type Clipper = {
  prenom: string;                                                  // tel qu'écrit dans la note GAML du lien le plus récent
  cle: string;                                                     // prénom normalisé (minuscules, sans accents)
  jeton: string;
  creatrice: string;                                               // premier mot du `name` du lien le plus récent
  liens: { id: string; url: string; creeLe: string; enabled: boolean }[];
};

export function normaliser(t: string): string {
  return (t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

export function prenomNote(note: string): string {
  const m = /^\s*clipping\s+(.+)$/i.exec(note || "");
  return m ? m[1].trim() : "";
}

/** HMAC-SHA256(CLIPPERS_SECRET, prénom normalisé), base64url, 24 caractères. */
export function jetonDe(cle: string): string {
  const secret = process.env.CLIPPERS_SECRET;
  if (!secret) throw new Error("CLIPPERS_SECRET absent");
  return createHmac("sha256", secret).update(cle).digest("base64url").slice(0, 24);
}

function premierMot(t: string): string {
  return (t || "").trim().split(/\s+/)[0] || "";
}

export function regrouper(liens: LienGaml[]): Clipper[] {
  const parCle = new Map<string, { liens: LienGaml[] }>();
  for (const l of liens) {
    const prenom = prenomNote(l.note);
    const cle = normaliser(prenom);
    // 09/10 : « Clipping libre (ex-Eddy) » = lien d'un clipper parti, en attente du suivant (le bot le renomme) : à personne
    if (!prenom || prenom.length < 3 || EXCLURE.has(cle) || cle.split(/\s+/)[0] === "libre") continue;
    // 28/10 (audit) : « Clipping Rianah (ex-Ckycia, lien recyclé, sans tracking à elle) » ouvrait une 15e app au nom de la note :
    // un lien recyclé n'est l'app de personne
    if (/\(\s*ex-/.test(cle)) continue;
    const g = parCle.get(cle) || { liens: [] };
    g.liens.push(l);
    parCle.set(cle, g);
  }
  const out: Clipper[] = [];
  parCle.forEach((g, cle) => {
    const tries = [...g.liens].sort((a, b) => (b.createdAt > a.createdAt ? 1 : b.createdAt < a.createdAt ? -1 : 0));
    const recent = tries[0];
    out.push({
      prenom: prenomNote(recent.note), cle, jeton: jetonDe(cle), creatrice: premierMot(recent.name),
      liens: tries.map((l) => ({ id: l.id, url: l.url, creeLe: l.createdAt.slice(0, 10), enabled: l.enabled })),
    });
  });
  return out.sort((a, b) => a.cle.localeCompare(b.cle));
}

/** 27/10 (Gaëtan : « envoie son application clippeur à Esperance ») : depuis le 24/10, le bot note les nouveaux liens
 *  « Clipping UID:<id Discord> » (process_liens, aucune recherche par prénom). L'app affichait alors « UID:1560… » au lieu du prénom,
 *  et aucun compte : les comptes se cherchent par prénom dans la colonne Gérant du LOG DASHBOARD. La clé reste « uid:<id> » : c'est
 *  elle qui fait le jeton (le lien de l'app ne change pas) et qui relie l'app aux onglets du bot (« Comptes app », « Régime paie »,
 *  « Équipes », « Adresses USDC »). Seul le prénom vient de l'onglet « Comptes app » du bot (clé → prénom). Pur, testé par
 *  tests/clippers-uid.cjs. */
export const estCleUid = (cle: string) => /^uid:\s*\d{6,}$/.test(cle);

export function nommer(liste: Clipper[], noms: Map<string, string> | null): Clipper[] {
  if (!noms) return liste;
  return liste.map((c) => {
    const p = estCleUid(c.cle) ? (noms.get(c.cle) || "").trim() : "";
    return p ? { ...c, prenom: p } : c;
  });
}

/** 31/10 (Mathieu : « donner à Pierre et Amour le lien de l'application ») : Pierre avait deux apps, /14 noté « Clipping Pierre »
 *  (`!lien` du 28/10) et /1 noté « Clipping UID:<id> » (processus), chacune avec la moitié de ses chiffres, et le bot ne trouvait
 *  plus la sienne (deux lignes « Liens app »). Le bot publie dans « Régime paie » UNE clé par clipper avec tous ses liens : un groupe
 *  dont la clé n'y est pas et dont tous les liens sont rattachés par le bot à UNE autre clé présente rejoint ce clipper (son prénom,
 *  sa clé, son jeton). `anciennes` : jeton de la clé fusionnée → clé d'arrivée, l'ancien lien de l'app mène toujours au clipper.
 *  Onglet illisible (null) : rien ne bouge. Pur, testé par tests/clippers-fusion.cjs. */
export function fusionner(liste: Clipper[], cles: Map<string, Set<string>> | null): { liste: Clipper[]; anciennes: Map<string, string> } {
  const anciennes = new Map<string, string>();
  if (!cles || !cles.size) return { liste, anciennes };
  const presentes = new Set(liste.map((c) => c.cle));
  const vers = new Map<string, string>();
  for (const c of liste) {
    if (cles.has(c.cle) || !c.liens.length) continue;
    const cibles = [...cles.entries()]
      .filter(([k, ids]) => k !== c.cle && presentes.has(k) && c.liens.every((l) => ids.has(l.id)))
      .map(([k]) => k);
    if (cibles.length === 1) vers.set(c.cle, cibles[0]);
  }
  if (!vers.size) return { liste, anciennes };
  const parCle = new Map(liste.map((c) => [c.cle, { ...c, liens: [...c.liens] }] as [string, Clipper]));
  vers.forEach((k, source) => {
    const s = parCle.get(source)!;
    const t = parCle.get(k)!;
    t.liens = [...t.liens, ...s.liens].sort((a, b) => (b.creeLe > a.creeLe ? 1 : b.creeLe < a.creeLe ? -1 : 0));
    anciennes.set(s.jeton, k);
    parCle.delete(source);
  });
  return { liste: [...parCle.values()].sort((a, b) => a.cle.localeCompare(b.cle)), anciennes };
}

async function etat(): Promise<{ liste: Clipper[]; anciennes: Map<string, string> }> {
  let liste = regrouper(await liensGaml());
  if (liste.some((c) => estCleUid(c.cle))) {
    // import dynamique : comptesApp → usage → config → clippers ferait une boucle d'imports
    const noms = await import("./comptesApp").then((m) => m.prenomsDesCles()).catch(() => null);
    liste = nommer(liste, noms);                                   // onglet illisible : « UID:… » comme avant, rien ne casse
  }
  const cles = await import("./regimes").then((m) => m.liensParCle()).catch(() => null);
  return fusionner(liste, cles);
}

export async function clippers(): Promise<Clipper[]> {
  return (await etat()).liste;
}

/** 13/10 (le lien de Yves ne marchait plus) : le jeton vient de la note GAML ; renommer « Clipping Yves Redirect YTB » en
 *  « Clipping Yves » change le lien. Ancienne clé → clé actuelle : l'ancien lien déjà envoyé mène toujours au clipper. */
const ANCIENNES_CLES: Record<string, string> = { "yves redirect ytb": "yves" };

export async function clipperParJeton(jeton: string | undefined): Promise<Clipper | null> {
  if (!jeton || !/^[A-Za-z0-9_-]{24}$/.test(jeton)) return null;
  const { liste, anciennes } = await etat();
  const direct = liste.find((c) => c.jeton === jeton);
  if (direct) return direct;
  const fusionne = anciennes.get(jeton);                           // 31/10 : l'app d'une clé fusionnée (Pierre, /14)
  if (fusionne) return liste.find((c) => c.cle === fusionne) || null;
  for (const [ancienne, actuelle] of Object.entries(ANCIENNES_CLES)) {
    if (jetonDe(ancienne) === jeton) return liste.find((c) => c.cle === actuelle) || null;
  }
  return null;
}
