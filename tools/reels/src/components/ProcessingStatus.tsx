import { processingStatus, type ProcessingState } from "../lib/processing-status";
import type { NativePhase } from "../lib/opus-native";
import styles from "../reels.module.css";

type Props = { stage: ProcessingState; phase: NativePhase; elapsedSeconds: number; resuming: boolean | null; readyCount: number };
export default function ProcessingStatus(props: Props) {
  const view = processingStatus(props.stage, props.phase, props.elapsedSeconds, props.resuming, props.readyCount);
  return <section className={styles.progress} aria-label="Suivi du montage">
    <div className={styles.progressHeading}><strong>{view.title}</strong><span className={styles.count}>{view.count}/6 prêts</span></div>
    <div role="progressbar" aria-label={view.complete ? "Vidéos disponibles" : "Repère de temps indicatif"}
      aria-valuetext={view.estimate} {...(view.complete ? { "aria-valuenow": 100, "aria-valuemin": 0, "aria-valuemax": 100 } : {})} className={styles.track}>
      <div className={view.active && view.indeterminate ? styles.indeterminate : styles.fill}
        style={{ width: view.indeterminate ? "100%" : `${view.width}%`, opacity: props.stage === "error" ? 0.3 : 1 }} />
    </div>
    <p role="status" aria-live="polite" className={styles.estimate}>{view.estimate}</p>
    <div className={styles.elapsed}><span>{view.timingLabel}</span><span aria-live="off">{view.elapsed}</span></div>
    {view.active && <p className={styles.hint}>Tu peux changer d’onglet dans l’app. Garde cette page ouverte.</p>}
  </section>;
}
