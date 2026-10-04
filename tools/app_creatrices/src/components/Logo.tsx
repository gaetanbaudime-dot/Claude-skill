/* eslint-disable @next/next/no-img-element */
export default function Logo({ taille = 40 }: { taille?: number }) {
  return (
    <img src="/icones/icone-192.png" alt="G&M" width={taille} height={taille}
         style={{ width: taille, height: taille, borderRadius: taille * 0.24, boxShadow: "0 8px 24px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.08)" }} />
  );
}
