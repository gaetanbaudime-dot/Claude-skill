import type { NativePhase } from "./opus-native";

export type ProcessingState = "processing" | "error" | "done";
export const PHASE_LABELS: Record<NativePhase, string> = {
  checking: "Vérification du montage",
  upload: "Envoi du rush",
  preparing: "Préparation de la vidéo",
  native: "Analyse et montage",
  variants: "Création des six variantes",
  exports: "Exports et finitions",
  cached: "Vérification des vidéos disponibles",
};
export function elapsedLabel(seconds: number) {
  const value = Math.max(0, Math.floor(Number.isFinite(seconds) ? seconds : 0));
  return value < 60 ? `${value} s` : `${Math.floor(value / 60)} min ${String(value % 60).padStart(2, "0")} s`;
}
export const elapsedSince = (startedAt: number, now: number) => Math.max(0, Math.floor((now - startedAt) / 1000));
export function processingStatus(stage: ProcessingState, phase: NativePhase, elapsedSeconds: number,
  resuming: boolean | null, readyCount: number) {
  const elapsed = Math.max(0, Number.isFinite(elapsedSeconds) ? elapsedSeconds : 0);
  const count = Math.max(0, Math.min(6, Math.floor(readyCount)));
  const complete = stage === "done" && count === 6;
  let estimate: string;
  let indeterminate = true;
  let width = 0;
  if (complete) { estimate = "Les six vidéos sont disponibles."; indeterminate = false; width = 100; }
  else if (stage === "error") estimate = "Traitement interrompu. Les vidéos déjà prêtes restent disponibles.";
  else if (stage === "done") estimate = "Certaines vidéos ne sont pas encore confirmées. Les fichiers disponibles peuvent être téléchargés.";
  else if (resuming === null) estimate = "Recherche d’un montage à reprendre…";
  else if (resuming || phase === "cached") estimate = "Reprise en cours · durée restante variable selon les étapes à terminer.";
  else if (elapsed >= 300) estimate = "Plus long que prévu · le traitement est toujours en cours. Durée restante indéterminée.";
  else {
    const lower = Math.ceil(Math.max(0, 240 - elapsed) / 60);
    const upper = Math.ceil((300 - elapsed) / 60);
    estimate = lower > 0 ? `Encore environ ${lower}–${upper} min, à titre indicatif.`
      : "Encore environ 1 min, à titre indicatif ; cela peut prendre plus longtemps.";
    indeterminate = false;
    width = elapsed / 300 * 100;
  }
  return { complete, count, estimate, indeterminate, width,
    title: complete ? "Montage terminé" : stage === "error" ? "Traitement interrompu" : stage === "done" ? "Montage incomplet" : PHASE_LABELS[phase],
    elapsed: elapsedLabel(elapsed),
    timingLabel: resuming ? "Écoulé depuis cette reprise" : "Temps écoulé",
    showReference: stage === "processing" && resuming === false,
    active: stage === "processing" && !complete,
  };
}
