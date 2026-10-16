"use client";
import { useEffect, useRef, useState } from "react";
import type { RemoteVariant } from "../lib/server-video";
import { canShareFiles, downloadVideos, prepareShareFiles, sharePreparedFiles } from "../lib/downloads";
import styles from "../reels.module.css";

export default function Downloads({ variants }: { variants: RemoteVariant[] }) {
  const [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const [files, setFiles] = useState<File[]>([]), [shareAvailable, setShareAvailable] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => { setShareAvailable(canShareFiles()); return () => controller.current?.abort(); }, []);
  async function transfer(videos: RemoteVariant[], sharing = false) {
    if (controller.current) return;
    const operation = new AbortController(); controller.current = operation;
    setBusy(true); setFiles([]); setMessage("Préparation des fichiers…");
    try {
      if (sharing) {
        const prepared = await prepareShareFiles(videos, operation.signal, done => setMessage(`Préparation : ${done}/${videos.length}`));
        if (!canShareFiles(prepared)) throw new Error("Le partage de ce lot est indisponible. Télécharge les vidéos individuellement.");
        setFiles(prepared); setMessage("Fichiers prêts. Ouvre le partage et choisis où les enregistrer.");
      } else {
        await downloadVideos(videos, operation.signal, done => setMessage(`Téléchargements demandés : ${done}/${videos.length}`));
        if (!operation.signal.aborted) setMessage("Téléchargement demandé. Vérifie les téléchargements de ton navigateur.");
      }
    } catch (error) {
      if (!operation.signal.aborted) setMessage(error instanceof Error ? error.message : "Téléchargement indisponible. Utilise le lien du fichier.");
    } finally { if (!operation.signal.aborted) setBusy(false); controller.current = null; }
  }
  async function share() {
    const outcome = await sharePreparedFiles(files);
    setMessage(outcome === "handed-off" ? "Fichiers transmis au menu de partage. L’enregistrement dépend de ton choix."
      : outcome === "cancelled" ? "Partage annulé. Les téléchargements restent disponibles." : "Partage indisponible. Télécharge les fichiers individuellement.");
    setFiles([]);
  }
  return <section className={styles.results} aria-label="Vidéos disponibles">
    <div className={styles.resultHeading}><h3>{variants.length === 6 ? "Tes 6 Reels" : `${variants.length} Reel${variants.length > 1 ? "s" : ""} disponible${variants.length > 1 ? "s" : ""}`}</h3><span>HD · 9:16</span></div>
    {variants.length > 1 && <button type="button" className={styles.primary} disabled={busy} onClick={() => void transfer(variants)}>Tout télécharger ({variants.length})</button>}
    {shareAvailable && <button type="button" className={styles.secondary} disabled={busy} onClick={() => void transfer(variants, true)}>Préparer le partage</button>}
    {message && <p role="status" className={styles.transfer}>{message}</p>}
    {!!files.length && <button type="button" className={styles.primary} onClick={() => void share()}>Ouvrir le partage</button>}
    <ol className={styles.resultList}>{variants.map(video => <li key={video.id} className={styles.resultCard}>
      <div className={styles.resultTop}><span className={styles.number}>{video.index + 1}</span><div className={styles.resultName}><strong>{video.captionPreset || `Variante ${video.index + 1}`}</strong><span>{(video.size / 1048576).toFixed(1)} Mo · MP4</span></div></div>
      <div className={styles.resultActions}><button type="button" className={styles.primary} disabled={busy} onClick={() => void transfer([video])} aria-label={`Télécharger la variante ${video.index + 1}`}>Télécharger</button><a className={styles.fileLink} href={video.downloadUrl} download={video.name} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">Ouvrir le fichier</a></div>
      <details className={styles.previewDetails}><summary>Voir la vidéo</summary><video src={video.url} controls playsInline preload="none" aria-label={`Aperçu de la variante ${video.index + 1}`} /></details>
    </li>)}</ol>
  </section>;
}
