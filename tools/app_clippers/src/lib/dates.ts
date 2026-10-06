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

export function finDuMois(annee: number, mois1: number): number {
  return new Date(Date.UTC(annee, mois1, 0)).getUTCDate();
}

/** « lun. 6 oct. » (avec l'année si demandé). */
export function libelleJour(jour: string, avecAnnee = false): string {
  const d = new Date(jour + "T12:00:00Z");
  return `${JOURS_COURTS[d.getUTCDay()]} ${d.getUTCDate()} ${MOIS_COURTS[d.getUTCMonth()]}${avecAnnee ? " " + d.getUTCFullYear() : ""}`;
}

/** « 20 octobre » : la date d'un versement, en toutes lettres. */
export function libelleLong(jour: string): string {
  const d = new Date(jour + "T12:00:00Z");
  return `${d.getUTCDate()}${d.getUTCDate() === 1 ? "er" : ""} ${MOIS[d.getUTCMonth()]}`;
}

/** « 1 → 15 oct. » ou « 16 sept. → 5 oct. » si les mois diffèrent. */
export function libellePlage(debut: string, fin: string): string {
  const a = new Date(debut + "T12:00:00Z"), b = new Date(fin + "T12:00:00Z");
  if (a.getUTCMonth() === b.getUTCMonth()) return `${a.getUTCDate()} → ${b.getUTCDate()} ${MOIS_COURTS[b.getUTCMonth()]}`;
  return `${a.getUTCDate()} ${MOIS_COURTS[a.getUTCMonth()]} → ${b.getUTCDate()} ${MOIS_COURTS[b.getUTCMonth()]}`;
}
