"use client";
import { useRef } from "react";
import type { ReelsJob } from "./use-reels-job";
import ProcessingStatus from "./components/ProcessingStatus";
import Downloads from "./components/Downloads";
import styles from "./reels.module.css";

export default function ReelsPanel({ job, active }: { job: ReelsJob; active: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const running = job.stage === "processing", ready = job.stage === "ready";
  const pick = () => { if (input.current) { input.current.value = ""; input.current.click(); } };
  const seconds = Math.floor(job.duration || 0);
  return <section hidden={!active} aria-label="Créer des Reels" className={styles.panel}>
    <input ref={input} type="file" accept="video/mp4,video/quicktime,.mp4,.mov" className={styles.hiddenInput} aria-label="Choisir un rush vidéo" onChange={event => job.choose(event.target.files?.[0])} />
    <div className={styles.heading}><h2>Créer 6 Reels</h2><span>HD · 9:16</span></div>
    {!job.file && <div className={styles.upload}>
      <p className={styles.intro}>Un rush, six variantes sous-titrées.</p>
      <button type="button" className={styles.primary} onClick={pick}><svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M12 16V4m-5 5 5-5 5 5M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4" /></svg>Choisir une vidéo</button>
      <p className={styles.limits}>MP4 ou MOV · 250 Mo · 3 min max</p>
      <p className={styles.hint}>Rush brut, sans texte ni sous-titres incrustés.</p>
    </div>}
    {job.file && ready && <div className={styles.selection}>
      <div className={styles.selectedRow}>
        <video key={job.preview} src={job.preview || undefined} muted playsInline preload="metadata" className={styles.thumbnail}
          onLoadedMetadata={event => job.metadata(event.currentTarget.duration)} onError={() => job.metadata(NaN)} aria-label="Aperçu du rush choisi" />
        <div className={styles.fileInfo}><strong title={job.file.name}>{job.file.name}</strong><span>{(job.file.size / 1048576).toFixed(1)} Mo · {job.duration === null ? "Lecture de la durée…" : `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`}</span></div>
        <button type="button" className={styles.change} onClick={pick}>Changer</button>
      </div>
      <button type="button" className={styles.primary} disabled={job.duration === null || job.duration > 180 || !!job.error} onClick={() => void job.run()}>Créer mes 6 Reels</button>
      <p className={styles.hint}>Six styles natifs · format vertical HD. Un seul import.</p>
    </div>}
    {job.file && !ready && <>
      <p className={styles.currentFile} title={job.file.name}>{job.file.name}</p>
      <ProcessingStatus stage={job.stage === "done" ? "done" : running ? "processing" : "error"} phase={job.phase} elapsedSeconds={job.elapsed} resuming={job.resuming} readyCount={job.variants.length} />
      {running && <button type="button" className={styles.stop} onClick={job.stop}>Arrêter le suivi</button>}
    </>}
    {job.error && <div role="alert" className={styles.error}><p>{job.error}</p>
      {job.file && job.stage === "error" && <button type="button" className={styles.secondary} onClick={() => void job.run()}>Reprendre ce montage</button>}
    </div>}
    {!!job.variants.length && <Downloads variants={job.variants} />}
    {job.file && !running && !ready && <button type="button" className={styles.newVideo} onClick={job.reset}>Choisir une nouvelle vidéo</button>}
  </section>;
}
