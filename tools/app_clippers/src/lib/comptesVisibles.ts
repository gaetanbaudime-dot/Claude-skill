/** 24/10 (Gaëtan : « on ne voit pas les comptes Instagram que le clipper gère… remets sur l'application des clippers les comptes
 *  Instagram que le clipper gère ») : les comptes affichés en haut de l'onglet Comptes. Pur, sans import, testé seul.
 *
 *  - Tous les comptes du clipper au classeur, quel que soit leur n° de parcours : un compte refait porte le n° 4, 5 ou 6
 *    (Esperance : son seul compte actif est son n° 5). Avant, la route ne gardait que les n° 1 à 3.
 *  - Sans les BAN : un compte banni n'appartient à personne (règles gelées).
 *  - Sans les @ absents du classeur (ETAT vide dans « Comptes app ») : c'est un ancien @ remplacé, son lien Instagram est mort.
 *  - Un même @ une seule fois. Les actifs d'abord, puis ceux qui demandent une action, puis ceux à créer ; l'ordre du parcours
 *    ensuite. */

export type Ton = "vert" | "orange" | "gris";
export type EtatAffiche = { libelle: string; ton: Ton; rang: number; masque: boolean; enLigne: boolean };

const plat = (t: string) => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, " ").trim();

export function etatAffiche(etat: string): EtatAffiche {
  const e = plat(etat);
  if (!e) return { libelle: "", ton: "gris", rang: 9, masque: true, enLigne: false };
  if (e === "ban" || e.startsWith("banni")) return { libelle: "Banni", ton: "gris", rang: 9, masque: true, enLigne: false };
  if (["good", "warmup", "prive"].includes(e)) return { libelle: "Actif", ton: "vert", rang: 0, masque: false, enLigne: true };
  if (e.includes("appel")) return { libelle: "Appel à faire", ton: "orange", rang: 2, masque: false, enLigne: true };
  if (e === "introuvable") return { libelle: "Introuvable", ton: "orange", rang: 2, masque: false, enLigne: true };
  if (e.includes("creer")) return { libelle: "À créer", ton: "gris", rang: 3, masque: false, enLigne: false };
  return { libelle: "À vérifier", ton: "orange", rang: 2, masque: false, enLigne: true };
}

/** 28/10 (audit des apps, Gaëtan : « que le clipper voie bien ») : l'état affiché tient compte du suivi Instagram (RapidAPI).
 *  - « Faire appel » au LOG DASHBOARD, mais le suivi lit le compte en public avec des Reels sur 7 jours : il est actif (Yves, le
 *    28/10 : 16 Reels en 7 jours sur un compte marqué « Faire appel », l'app lui disait de faire appel).
 *  - Actif au LOG, mais introuvable au dernier relevé : « Introuvable », plus « Actif » (Clarisse, le 28/10 : « Actif » à côté de
 *    « introuvable sur Instagram » et 0 follower).
 *  Le LOG reste la source pour qui gère quoi ; seul le badge change. */
export function etatEffectif(etat: string, mesure?: string, reels7?: number | null): string {
  const e = plat(etat), m = plat(mesure || "");
  if (!e || e === "ban" || e.startsWith("banni") || e.includes("creer")) return etat;
  if (e.includes("appel") && m.startsWith("lu") && (reels7 ?? 0) > 0) return "GOOD";
  if (m.includes("introuvable") && ["good", "warmup", "prive"].includes(e)) return "INTROUVABLE";
  return etat;
}

const prive = (role?: string) => plat(role || "") === "prive";

/** Les comptes de croissance actifs d'abord, puis le compte privé, puis ceux qui demandent une action, puis ceux à créer. */
export function comptesAffiches<T extends { n: number; handle: string; etat: string; role?: string }>(comptes: T[]): T[] {
  const vus = new Set<string>();
  const rang = (c: T) => etatAffiche(c.etat).rang + (etatAffiche(c.etat).rang === 0 && prive(c.role) ? 1 : 0);
  return comptes
    .filter((c) => {
      const h = plat(c.handle).replace(/^@+/, "");
      if (!h || etatAffiche(c.etat).masque || vus.has(h)) return false;
      vus.add(h);
      return true;
    })
    .sort((a, b) => rang(a) - rang(b) || a.n - b.n);
}
