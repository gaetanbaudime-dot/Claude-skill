/** Les créatrices : un jeton secret par créatrice, posé dans la variable d'environnement CREATRICES_JSON (jamais dans le dépôt).
 *  Forme : { "<jeton>": { "prenom": "Chloé", "onglet": "Chloé", "racine": "<id Drive>", "reels": "<id>", "photos": "<id>", "feed": "<id>|null", "scripts": "<id>|null" } } */
export type Creatrice = {
  jeton: string;
  prenom: string;
  onglet: string;
  racine: string;
  reels?: string | null;
  photos?: string | null;
  feed?: string | null;
  scripts?: string | null;
};

let cache: Record<string, Creatrice> | null = null;

export function creatrices(): Record<string, Creatrice> {
  if (cache) return cache;
  const brut = process.env.CREATRICES_JSON || "{}";
  const data = JSON.parse(brut) as Record<string, Omit<Creatrice, "jeton">>;
  cache = Object.fromEntries(Object.entries(data).map(([jeton, c]) => [jeton, { ...c, jeton }]));
  return cache;
}

export function creatriceParJeton(jeton: string | undefined): Creatrice | null {
  if (!jeton || !/^[A-Za-z0-9_-]{12,64}$/.test(jeton)) return null;
  return creatrices()[jeton] || null;
}
