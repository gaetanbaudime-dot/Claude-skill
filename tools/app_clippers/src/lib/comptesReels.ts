/** 24/10 (Gaëtan : « j'en ai marre qu'on n'ait pas un visuel entre la réalité et ce qu'on affiche… je mets tout le temps à jour le
 *  sheet, log dashboard, pars de là ») : les comptes qu'un clipper gère VRAIMENT. Pur, sans import réseau, testé par
 *  tests/comptes-reels.cjs.
 *
 *  Deux sources :
 *  - la fiche du bot (onglet « Comptes app ») : le parcours du clipper, avec un n° par compte livré, le seul qui permet de corriger
 *    un @ (`!pseudo`) ; elle garde aussi les anciens @ et peut porter une faute de frappe (« sophie.enroutelatroupe » au lieu de
 *    « sophie.enroutelatroupee », 158 000 vues en 7 jours invisibles le 24/10) ;
 *  - le LOG DASHBOARD de Gaëtan, recopié par le bot dans « Pilotage comptes » : la colonne Gérant dit qui gère quel @ aujourd'hui.
 *
 *  Règle : le LOG DASHBOARD gagne.
 *  - Un @ de clipping (Type « Clipper ») dont le Gérant est le clipper s'affiche, même absent de sa fiche (n° 100+, non modifiable
 *    depuis l'app).
 *  - Un @ de sa fiche que le LOG DASHBOARD donne à quelqu'un d'autre (ou à personne : compte libéré) ne s'affiche plus chez lui.
 *  - Un @ de sa fiche absent du LOG DASHBOARD garde son état (vide : ancien @, masqué par comptesAffiches).
 *  Sans LOG DASHBOARD lisible, la fiche seule (comportement d'avant). */
import type { CompteApp } from "./comptesApp";

export type CompteClasseur = {
  handle: string; etat: string; gerant: string; type: string; creatrice: string;
  followers: number | null; reels7: number | null; vues7: number | null; vuesRecentes: number | null;
  mesure: string; dernierReel: string; roleCompte?: string;
};
export type CompteReel = CompteApp & { modifiable: boolean; mesure: string; dernierReel: string; source: "fiche" | "classeur" };

const plat = (t?: string) => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
const cle = (h?: string) => plat(h).replace(/^@+/, "");

/** « Rianah Clipping Chloé » est géré par Rianah ; « Gaetan » par Gaëtan ; « Julien » n'est pas géré par « Jules ». */
export function gerePar(gerant: string, prenom: string): boolean {
  const g = plat(gerant), p = plat(prenom);
  return Boolean(p) && (g === p || g.startsWith(p + " ") || g.startsWith(p + "("));
}

export function comptesReels(prenom: string, fiche: CompteApp[], classeur: CompteClasseur[] | null): CompteReel[] {
  const depuisFiche = (c: CompteApp, x?: CompteClasseur): CompteReel => ({
    ...c, modifiable: c.n >= 1 && c.n <= 20, mesure: x?.mesure || "", dernierReel: x?.dernierReel || "", source: "fiche",
  });
  if (!classeur) return fiche.map((c) => depuisFiche(c));
  const parHandle = new Map<string, CompteClasseur>();
  for (const x of classeur) if (cle(x.handle) && !parHandle.has(cle(x.handle))) parHandle.set(cle(x.handle), x);
  const out: CompteReel[] = [];
  const vus = new Set<string>();
  for (const c of fiche) {
    const x = parHandle.get(cle(c.handle));
    if (x && !gerePar(x.gerant, prenom)) continue;                     // le LOG DASHBOARD le donne à un autre, ou à personne
    vus.add(cle(c.handle));
    out.push(depuisFiche(c, x));
  }
  let n = 100;
  for (const x of classeur) {
    const h = cle(x.handle);
    // ajout seulement pour une ligne de clipping : Rianah gère aussi des comptes Metricool, payés au fixe, hors de son app de clippeuse
    if (!h || vus.has(h) || plat(x.type) !== "clipper" || !gerePar(x.gerant, prenom)) continue;
    vus.add(h);
    out.push({
      n: n++, handle: x.handle.replace(/^@+/, ""), etat: x.etat, creatrice: x.creatrice, followers: x.followers,
      reels7: x.reels7, vues7: x.vuesRecentes ?? x.vues7, role: x.roleCompte || (plat(x.mesure).startsWith("prive") ? "privé" : ""),
      modifiable: false, mesure: x.mesure, dernierReel: x.dernierReel, source: "classeur",
    });
  }
  return out;
}

/** Ce que le dernier relevé du bot dit d'un compte en ligne, quand ce qu'on affiche risque de ne pas être la réalité. null : rien
 *  à signaler. `grave` : le compte n'est peut-être plus là (banni, renommé, faute de frappe). */
export function alerteMesure(c: { etat: string; mesure?: string; dernierReel?: string; role?: string }): { texte: string; grave: boolean } | null {
  const e = plat(c.etat), m = plat(c.mesure), d = plat(c.dernierReel);
  if (!e || e === "ban" || e.includes("creer")) return null;
  if (m.includes("introuvable")) return { texte: "introuvable sur Instagram au dernier relevé : vérifier le @", grave: true };
  if (m.startsWith("restreint")) return { texte: "Instagram limite la lecture de ce compte : chiffres partiels", grave: false };
  const abonnes = /followers non lus depuis le (\d{1,2}\/\d{1,2})/.exec(m);
  if (abonnes) return { texte: `abonnés non relus depuis le ${abonnes[1]}`, grave: false };
  if (m.includes("reels non lus")) return { texte: "Reels pas encore lus par le bot", grave: false };
  if (plat(c.role) === "prive" || m.startsWith("prive")) return null;
  if (d === "aucun") return { texte: "aucun Reel vu par le bot", grave: false };
  const jours = /il y a (\d+) j/.exec(d);
  if (jours && Number(jours[1]) >= 3) return { texte: `dernier Reel vu il y a ${jours[1]} jours`, grave: false };
  return null;
}
