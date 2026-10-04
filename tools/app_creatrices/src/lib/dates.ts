/** Dates à l'heure de Paris, sans dépendance. Un jour = "AAAA-MM-JJ". */
export const MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
export const MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
export const JOURS_COURTS = ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."];

export function aujourdhuiParis(): string {
  const f = new Intl.DateTimeFormat("fr-CA", { timeZone: "Europe/Paris", year: "numeric", month: "2-digit", day: "2-digit" });
  return f.format(new Date());
}

export function decaler(jour: string, n: number): string {
  const d = new Date(jour + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export function serialVersJour(serial: number): string {
  const d = new Date(Date.UTC(1899, 11, 30) + Math.round(serial) * 86400000);
  return d.toISOString().slice(0, 10);
}

/** « 12 septembre », « 12 septembre 2026 », « 12/09/2026 », « 2026-09-12 » → "2026-09-12" (année courante par défaut, l'an passé si le mois est à venir). */
export function texteVersJour(t: string, aujourdhui: string): string | null {
  const s = t.trim().toLowerCase();
  let m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return `${m[1]}-${m[2]}-${m[3]}`;
  m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2,4})/);
  if (m) return `${m[3].length === 2 ? "20" + m[3] : m[3]}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}`;
  m = s.match(/^(\d{1,2})(?:er)?\s+([a-zéû]+)\.?(?:\s+(\d{4}))?$/);
  if (m) {
    const mois = MOIS.findIndex((x) => x.startsWith(m![2].slice(0, 4)));
    if (mois < 0) return null;
    let annee = m[3] ? parseInt(m[3], 10) : parseInt(aujourdhui.slice(0, 4), 10);
    const moisCourant = parseInt(aujourdhui.slice(5, 7), 10) - 1;
    if (!m[3] && mois > moisCourant + 1) annee -= 1;
    return `${annee}-${String(mois + 1).padStart(2, "0")}-${m[1].padStart(2, "0")}`;
  }
  return null;
}

export function libelleJour(jour: string, avecAnnee = false): string {
  const d = new Date(jour + "T12:00:00Z");
  return `${JOURS_COURTS[d.getUTCDay()]} ${d.getUTCDate()} ${MOIS_COURTS[d.getUTCMonth()]}${avecAnnee ? " " + d.getUTCFullYear() : ""}`;
}

export function finDuMois(annee: number, mois1: number): number {
  return new Date(Date.UTC(annee, mois1, 0)).getUTCDate();
}

export type Periode = { cle: string; libelle: string; debut: string; fin: string; avantDebut: string; avantFin: string };

/** Les cinq périodes de l'appli, calculées sur la veille (la saisie du jour arrive le lendemain). */
export function periodes(aujourdhui: string): Record<string, Periode> {
  const hier = decaler(aujourdhui, -1);
  const [a, m] = [parseInt(aujourdhui.slice(0, 4), 10), parseInt(aujourdhui.slice(5, 7), 10)];
  const debutMois = `${aujourdhui.slice(0, 7)}-01`;
  const [aPrec, mPrec] = m === 1 ? [a - 1, 12] : [a, m - 1];
  const debutPrec = `${aPrec}-${String(mPrec).padStart(2, "0")}-01`;
  const finPrec = `${aPrec}-${String(mPrec).padStart(2, "0")}-${String(finDuMois(aPrec, mPrec)).padStart(2, "0")}`;
  const [aPP, mPP] = mPrec === 1 ? [aPrec - 1, 12] : [aPrec, mPrec - 1];
  const debutPP = `${aPP}-${String(mPP).padStart(2, "0")}-01`;
  const finPP = `${aPP}-${String(mPP).padStart(2, "0")}-${String(finDuMois(aPP, mPP)).padStart(2, "0")}`;
  const joursMois = Math.max(1, Math.round((Date.parse(hier) - Date.parse(debutMois)) / 86400000) + 1);
  return {
    hier: { cle: "hier", libelle: "Hier", debut: hier, fin: hier, avantDebut: decaler(hier, -1), avantFin: decaler(hier, -1) },
    j7: { cle: "j7", libelle: "7 jours", debut: decaler(hier, -6), fin: hier, avantDebut: decaler(hier, -13), avantFin: decaler(hier, -7) },
    j30: { cle: "j30", libelle: "30 jours", debut: decaler(hier, -29), fin: hier, avantDebut: decaler(hier, -59), avantFin: decaler(hier, -30) },
    m: { cle: "m", libelle: MOIS[m - 1][0].toUpperCase() + MOIS[m - 1].slice(1), debut: debutMois, fin: hier < debutMois ? debutMois : hier,
         avantDebut: debutPrec, avantFin: decaler(debutPrec, Math.min(joursMois, finDuMois(aPrec, mPrec)) - 1) },
    m1: { cle: "m1", libelle: MOIS[mPrec - 1][0].toUpperCase() + MOIS[mPrec - 1].slice(1), debut: debutPrec, fin: finPrec, avantDebut: debutPP, avantFin: finPP },
  };
}
