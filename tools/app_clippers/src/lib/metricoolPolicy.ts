export const SEUIL_METRICOOL = 500;
const HEURE = 3_600_000;

export function recent(iso: string | undefined, heures: number, now = Date.now()): boolean {
  const t = Date.parse(iso || "");
  return Number.isFinite(t) && t <= now && now - t <= heures * HEURE;
}

export function eligible(c: { followers: number | null; followersVerifiesLe?: string }, now = Date.now()): boolean {
  return c.followers !== null && Number.isInteger(c.followers) && c.followers >= SEUIL_METRICOOL && recent(c.followersVerifiesLe, 48, now);
}

// Le lien est copié par l'agence depuis Connections > Share > Create link.
// Aucun lien d'inscription ou de création de marque n'est fabriqué par l'app.
export function lienMetricool(brut: string): string | null {
  try {
    const u = new URL(brut);
    if (u.protocol !== "https:" || !["app.metricool.com", "mtr.cool"].includes(u.hostname) || u.port || u.username || u.password) return null;
    if (u.pathname === "/" && !u.search) return null;
    return u.href;
  } catch { return null; }
}

export type ValidationAgence = {
  marque: string; proprietaireMarque: string; accesAgence: string;
  nombreMarques: string; capaciteVerifieeLe: string; lien: string; creeLe: string; expireLe?: string;
};
export function connexionAutorisee(v: ValidationAgence, now = Date.now()): string | null {
  if (v.expireLe && (!Number.isFinite(Date.parse(v.expireLe)) || Date.parse(v.expireLe) <= now)) return null;
  const n = Number(v.nombreMarques);
  if (!v.marque.trim() || v.proprietaireMarque !== "oui" || v.accesAgence !== "oui" ||
      !/^\d+$/.test(v.nombreMarques) || !Number.isInteger(n) || n < 1 || n > 25 ||
      !recent(v.capaciteVerifieeLe, 24, now) || !recent(v.creeLe, 71, now)) return null;
  return lienMetricool(v.lien);
}
