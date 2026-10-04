/** Le taux dollar → euro du jour (Frankfurter, données BCE), en cache 12 h ; repli 0,88 si l'API ne répond pas. */
let cache: { taux: number; date: string; expire: number } | null = null;
const REPLI = 0.88;

export async function tauxUsdEur(): Promise<{ taux: number; date: string; source: string }> {
  if (cache && cache.expire > Date.now()) return { taux: cache.taux, date: cache.date, source: "BCE" };
  try {
    const r = await fetch("https://api.frankfurter.app/latest?from=USD&to=EUR", { next: { revalidate: 43200 } });
    if (r.ok) {
      const d = (await r.json()) as { rates?: { EUR?: number }; date?: string };
      if (d.rates?.EUR) {
        cache = { taux: d.rates.EUR, date: d.date || "", expire: Date.now() + 12 * 3600 * 1000 };
        return { taux: cache.taux, date: cache.date, source: "BCE" };
      }
    }
  } catch { /* repli */ }
  return { taux: cache?.taux ?? REPLI, date: cache?.date ?? "", source: cache ? "BCE" : "repli" };
}
