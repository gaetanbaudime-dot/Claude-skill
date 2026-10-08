/* Service worker minimal de l'app clippers G&M : il rend l'app « installable » d'un geste sur Android (Chrome, Samsung Internet)
   et affiche une page hors ligne lisible. Il ne met rien en cache : les chiffres viennent toujours du serveur. */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  if (e.request.mode !== "navigate") return;
  e.respondWith(fetch(e.request).catch(() => new Response(
    "<!doctype html><html lang=\"fr\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>G&amp;M</title>"
    + "<body style=\"margin:0;background:#070f1c;color:#cfd8e6;font-family:-apple-system,system-ui,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;text-align:center;padding:32px\">"
    + "<div><div style=\"font-size:28px;font-weight:700;color:#fff\">G&amp;M</div><p style=\"line-height:1.5;margin-top:12px\">Pas de connexion pour l'instant.<br>Réouvre l'app quand tu as du réseau.</p></div></body></html>",
    { headers: { "Content-Type": "text/html; charset=utf-8" } })));
});
