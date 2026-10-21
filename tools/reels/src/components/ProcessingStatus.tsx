import { PROCESSING_STEPS, processingStatus, type ProcessingContext, type ProcessingState } from "../lib/processing-status";
import type { NativePhase } from "../lib/opus-native";
import styles from "../reels.module.css";

type Props = ProcessingContext & { stage: ProcessingState; phase: NativePhase; elapsedSeconds: number; resuming: boolean | null; readyCount: number };
export default function ProcessingStatus(props: Props) {
  const view = processingStatus(props.stage, props.phase, props.elapsedSeconds, props.resuming, props.readyCount, props);
  return <section className={styles.progress} aria-label="Suivi du montage">
    <div className={styles.progressHeading}><strong>{view.title}</strong><span className={styles.count}>{view.count}/6 prêts</span></div>
    <ol className={styles.steps} aria-label="Étapes du montage">{PROCESSING_STEPS.map((label, index) => <li key={label} data-state={view.complete || index < view.step ? "done" : index === view.step ? "current" : "waiting"} aria-current={view.active && index === view.step ? "step" : undefined}><span aria-hidden="true">{view.complete || index < view.step ? "✓" : index + 1}</span>{label}</li>)}</ol>
    <div role="progressbar" aria-label={view.complete ? "Vidéos disponibles" : "Avancement des étapes"}
      aria-valuetext={view.estimate} {...(view.complete ? { "aria-valuenow": 100, "aria-valuemin": 0, "aria-valuemax": 100 } : {})} className={styles.track}>
      <div className={view.active && view.indeterminate ? styles.indeterminate : styles.fill}
        style={{ width: view.indeterminate ? "100%" : `${view.width}%`, opacity: props.stage === "error" ? 0.3 : 1 }} />
    </div>
    {view.transfer && <div className={styles.uploadProgress}><strong>{view.uploadPercent}% envoyé</strong><span>{view.transfer}</span></div>}
    <p role="status" aria-live="polite" className={styles.estimate}>{view.estimate}</p>
    {view.reference && <p className={styles.hint}>{view.reference}</p>}
    <div className={styles.elapsed}><span>{view.timingLabel}</span><span aria-live="off">{view.elapsed}</span></div>
    {view.active && <p className={styles.hint}>Tu peux changer d’onglet dans l’app. Garde cette page ouverte.</p>}
  </section>;
}
