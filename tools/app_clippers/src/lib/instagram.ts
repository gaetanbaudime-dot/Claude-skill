/** 13/10 (Gaëtan : « un petit bouton à la place du username : je clique sur le @ et ça m'ouvre directement son compte dans
 *  l'application Instagram, pour regarder les comptes des clippers sur mon téléphone »).
 *  iPhone : le lien `instagram://` ouvre l'app ; si elle n'est pas là (la page reste visible), le profil web prend le relais.
 *  Android : un lien `intent://` vers l'app Instagram, avec le profil web en repli. Ordinateur : le profil web, nouvel onglet. */
export function lienInstagram(handle: string): string {
  return `https://www.instagram.com/${encodeURIComponent(handle.replace(/^@/, ""))}/`;
}

export function ouvrirInstagram(handle: string): void {
  const h = handle.replace(/^@/, "").trim();
  if (!h) return;
  const web = lienInstagram(h);
  const ua = typeof navigator !== "undefined" ? navigator.userAgent : "";
  if (/iPhone|iPad|iPod/i.test(ua)) {
    const depart = Date.now();
    window.location.href = `instagram://user?username=${encodeURIComponent(h)}`;
    window.setTimeout(() => {
      if (document.visibilityState === "visible" && Date.now() - depart < 3000) window.location.href = web;
    }, 1200);
    return;
  }
  if (/Android/i.test(ua)) {
    window.location.href = `intent://www.instagram.com/_u/${encodeURIComponent(h)}/#Intent;package=com.instagram.android;scheme=https;S.browser_fallback_url=${encodeURIComponent(web)};end`;
    return;
  }
  window.open(web, "_blank", "noopener");
}
