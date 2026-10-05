/** Côté téléphone : envoie un événement d'usage au serveur sans jamais bloquer l'interface (sendBeacon, sinon fetch en arrière-plan). */
export type Mode = "app" | "navigateur";

export function modeApp(): Mode {
  try {
    const standalone = window.matchMedia("(display-mode: standalone)").matches || (navigator as Navigator & { standalone?: boolean }).standalone === true;
    return standalone ? "app" : "navigateur";
  } catch {
    return "navigateur";
  }
}

export function signaler(jeton: string, evenement: string, mode?: Mode): void {
  try {
    const url = `/api/c/${jeton}/ev`;
    const corps = JSON.stringify({ e: evenement, m: mode || modeApp() });
    if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
      if (navigator.sendBeacon(url, new Blob([corps], { type: "application/json" }))) return;
    }
    fetch(url, { method: "POST", body: corps, headers: { "Content-Type": "application/json" }, keepalive: true }).catch(() => undefined);
  } catch {
    /* jamais d'erreur visible */
  }
}
