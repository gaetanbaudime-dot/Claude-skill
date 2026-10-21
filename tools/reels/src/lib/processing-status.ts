import type { NativePhase, UploadProgress } from "./opus-native";

export type ProcessingState = "processing" | "error" | "done";
export type ProcessingContext = { upload?: UploadProgress | null; processingElapsedSeconds?: number; online?: boolean };
export const PHASE_LABELS: Record<NativePhase, string> = {
  checking: "Vérification du rush",
  upload: "Envoi du rush",
  preparing: "Préparation de la vidéo",
  native: "Analyse et montage",
  variants: "Création des six variantes",
  exports: "Exports et finitions HD",
  cached: "Vérification des vidéos disponibles",
};
export const PROCESSING_STEPS = ["Envoi", "Montage", "Variantes", "Finitions"] as const;
const STEP: Record<NativePhase, number> = { checking: 0, upload: 0, preparing: 1, native: 1, variants: 2, exports: 3, cached: 3 };
const PHASE_WIDTH: Record<NativePhase, number> = { checking: 0, upload: 0, preparing: 25, native: 35, variants: 58, exports: 75, cached: 75 };
export function elapsedLabel(seconds: number) {
  const value = Math.max(0, Math.floor(Number.isFinite(seconds) ? seconds : 0));
  return value < 60 ? `${value} s` : `${Math.floor(value / 60)} min ${String(value % 60).padStart(2, "0")} s`;
}
export const elapsedSince = (startedAt: number, now: number) => Math.max(0, Math.floor((now - startedAt) / 1000));
export function processingStatus(stage: ProcessingState, phase: NativePhase, elapsedSeconds: number,
  resuming: boolean | null, readyCount: number, context: ProcessingContext = {}) {
  const elapsed = Math.max(0, Number.isFinite(elapsedSeconds) ? elapsedSeconds : 0);
  const processingElapsed = Math.max(0, context.processingElapsedSeconds ?? elapsed);
  const count = Number.isFinite(readyCount) ? Math.max(0, Math.min(6, Math.floor(readyCount))) : 0;
  const complete = stage === "done" && count === 6;
  const active = stage === "processing" && !complete;
  const upload = context.upload;
  const uploadPercent = phase === "upload" && upload && upload.total > 0
    ? Math.max(0, Math.min(100, Math.floor(upload.loaded / upload.total * 100))) : null;
  const transfer = phase === "upload" && upload && upload.total > 0
    ? `${(Math.min(upload.loaded, upload.total) / 1048576).toFixed(1)} / ${(upload.total / 1048576).toFixed(1)} Mo`
      + (upload.bytesPerSecond > 0 ? ` · ${(upload.bytesPerSecond / 1048576).toFixed(1)} Mo/s` : "") : null;
  let estimate: string;
  if (complete) estimate = "Les six vidéos sont disponibles, en qualité HD.";
  else if (stage === "error") estimate = "Traitement interrompu. Les vidéos déjà prêtes restent disponibles.";
  else if (stage === "done") estimate = "Les fichiers disponibles peuvent être enregistrés ; le lot reste incomplet.";
  else if (context.online === false) estimate = "Connexion interrompue. Garde cette page ouverte et retrouve du réseau pour reprendre le suivi.";
  else if (phase === "upload") {
    const remaining = upload && upload.bytesPerSecond > 0 ? Math.ceil(Math.max(0, upload.total - upload.loaded) / upload.bytesPerSecond) : null;
    estimate = uploadPercent === 100 ? "Rush envoyé · confirmation en cours…"
      : remaining !== null ? `Encore environ ${remaining < 60 ? `${Math.max(1, remaining)} s` : `${Math.ceil(remaining / 60)} min`} pour l’envoi, selon ta connexion.`
        : "Envoi sans compression du rush · la durée dépend de ta connexion.";
  } else if (resuming === null || phase === "checking") estimate = "Recherche d’un montage à reprendre…";
  else if (resuming || phase === "cached") estimate = "Reprise du montage existant · seules les étapes manquantes sont poursuivies.";
  else if (processingElapsed >= 300) estimate = "Plus long que prévu · le montage continue. Durée restante indéterminée.";
  else {
    const lower = Math.ceil(Math.max(0, 240 - processingElapsed) / 60);
    const upper = Math.ceil((300 - processingElapsed) / 60);
    estimate = lower > 0 ? `Encore environ ${lower}–${upper} min de montage, à titre indicatif.`
      : "Dernières étapes · encore environ 1 min, à titre indicatif ; cela peut prendre plus longtemps.";
  }
  const indeterminate = active && (phase === "checking" || phase === "cached" || (phase === "upload" && uploadPercent === null));
  const width = complete ? 100 : phase === "upload" ? (uploadPercent || 0) * 0.24
    : Math.min(97, Math.max(PHASE_WIDTH[phase], phase === "exports" || phase === "cached" ? 75 + count / 6 * 22 : 0));
  return { complete, active, count, estimate, indeterminate, width, transfer, uploadPercent, step: STEP[phase],
    title: complete ? "Tes 6 Reels sont prêts" : stage === "error" ? "Traitement interrompu" : stage === "done" ? "Montage incomplet" : PHASE_LABELS[phase],
    elapsed: elapsedLabel(elapsed),
    timingLabel: resuming ? "Depuis cette reprise" : "Temps écoulé",
    showReference: active && resuming === false,
    reference: phase === "upload" ? "Puis environ 4–5 min de montage, à titre indicatif." : null,
  };
}
