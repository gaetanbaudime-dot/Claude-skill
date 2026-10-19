"use client";
import { useEffect, useRef, useState, type MouseEvent } from "react";
import type { RemoteVariant } from "../lib/server-video";
import { MAX_SHARE_BYTES, canShareFiles, createVideoFileCache, downloadPreparedFiles, sharePreparedFiles } from "../lib/downloads";
import { variantFileName, variantLabel } from "../lib/variant-labels";
import styles from "../reels.module.css";

export default function Downloads({ variants }: { variants: RemoteVariant[] }) {
  const [sharingAvailable, setSharingAvailable] = useState(false);
  const [device, setDevice] = useState<"apple" | "android" | "other">("other");
  const [selection, setSelection] = useState<RemoteVariant[]>([]), [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const cache = useRef<ReturnType<typeof createVideoFileCache> | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const request = useRef(0), sharing = useRef(false);
  useEffect(() => {
    const operation = new AbortController();
    cache.current = createVideoFileCache(operation.signal);
    setSharingAvailable(canShareFiles());
    setDevice(/iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
      ? "apple" : /Android/.test(navigator.userAgent) ? "android" : "other");
    return () => { ++request.current; operation.abort(); cache.current = null; };
  }, []);
  useEffect(() => {
    // Prepare existing MP4s while the user reviews the completed pack.
    if (sharingAvailable && variants.length === 6 && variants.reduce((sum, video) => sum + video.size, 0) <= MAX_SHARE_BYTES) {
      void cache.current?.prepare(variants).catch(() => undefined);
    }
  }, [variants, sharingAvailable]);
  useEffect(() => {
    if (selection.length && dialog.current && !dialog.current.open) dialog.current.showModal();
  }, [selection]);
  const instructions = device === "apple"
    ? "Dans le menu de partage, choisis « Enregistrer la vidéo » ou « Enregistrer les vidéos » pour les ajouter à Photos."
    : device === "android"
      ? "Choisis une application dans le menu de partage. Pour garder le MP4 sur ton Samsung, utilise « Télécharger le MP4 »."
      : "Choisis où enregistrer ou partager tes vidéos. Le téléchargement MP4 reste disponible.";
  const close = () => { ++request.current; dialog.current?.close(); setSelection([]); setFiles([]); setBusy(false); };
  async function share(prepared: File[]) {
    if (sharing.current) return;
    sharing.current = true;
    // Invoke Web Share synchronously within the tap, before any fetch or await.
    const result = sharePreparedFiles(prepared);
    setBusy(true);
    try {
      const outcome = await result;
      setMessage(outcome === "handed-off" ? "Menu de partage fermé. Tu peux enregistrer une autre variante."
        : outcome === "cancelled" ? "Partage annulé. Tes vidéos restent prêtes, tu peux réessayer."
          : "Le partage est indisponible dans ce navigateur. Utilise « Télécharger le MP4 » ci-dessous.");
      if (outcome === "unavailable") setSharingAvailable(false);
    } finally { sharing.current = false; setBusy(false); }
  }
  async function choose(videos: RemoteVariant[]) {
    if (busy || sharing.current || !cache.current) return;
    const prepared = cache.current.get(videos);
    if (prepared && canShareFiles(prepared)) { void share(prepared); return; }
    const current = ++request.current;
    setSelection(videos); setFiles(prepared || []); setBusy(!prepared); setMessage(prepared ? instructions : `Préparation : 0/${videos.length}`);
    try {
      const ready = prepared || await cache.current.prepare(videos, done => {
        if (current === request.current) setMessage(`Préparation : ${done}/${videos.length}`);
      });
      if (current !== request.current) return;
      setFiles(ready);
      setMessage(canShareFiles(ready) ? "Tes vidéos sont prêtes. Appuie sur le bouton ci-dessous."
        : "Utilise les boutons MP4 ci-dessous pour enregistrer tes vidéos une par une.");
    } catch (error) {
      if (current === request.current) setMessage(error instanceof Error ? error.message : "Préparation indisponible. Utilise le téléchargement MP4.");
    } finally { if (current === request.current) setBusy(false); }
  }
  function download(event: MouseEvent<HTMLAnchorElement>, video: RemoteVariant) {
    const prepared = cache.current?.get([video]);
    if (prepared) { event.preventDefault(); downloadPreparedFiles(prepared); }
    setMessage(device === "apple"
      ? "Téléchargement demandé. Dans Fichiers → Téléchargements, ouvre le MP4 puis Partager → Enregistrer la vidéo."
      : device === "android"
        ? "Téléchargement demandé. Retrouve le MP4 dans Mes fichiers → Téléchargements. S’il manque dans Galerie, déplace-le dans Movies."
        : "Téléchargement demandé. Retrouve le MP4 dans les téléchargements de ton navigateur.");
  }
  const saveLabel = device === "apple" ? "Enregistrer dans Photos" : sharingAvailable ? "Enregistrer / partager" : "Enregistrer la vidéo";
  const canShareSelection = files.length > 0 && canShareFiles(files);
  return <section className={styles.results} aria-label="Vidéos disponibles">
    <div className={styles.resultHeading}><h3>{variants.length === 6 ? "Tes 6 Reels" : `${variants.length} Reel${variants.length > 1 ? "s" : ""} disponible${variants.length > 1 ? "s" : ""}`}</h3><span>HD · 9:16</span></div>
    {sharingAvailable && variants.length > 1 && <button type="button" className={styles.primary} disabled={busy} onClick={() => void choose(variants)}><ShareIcon />{device === "apple" ? `Enregistrer les ${variants.length} dans Photos` : `Enregistrer les ${variants.length} vidéos`}</button>}
    <p className={styles.hint}>{device === "apple" ? "Enregistre tes vidéos dans Photos, en une fois ou une par une."
      : device === "android" ? "MP4 compatibles avec ton téléphone. Partage-les ou télécharge-les une par une." : "Enregistre chaque MP4 ou partage le lot depuis ton téléphone."}</p>
    {message && !selection.length && <p role="status" className={styles.transfer}>{message}</p>}
    <ol className={styles.resultList}>{variants.map(video => <li key={video.id} className={styles.resultCard}>
      <div className={styles.resultTop}><span className={styles.number}>{video.index + 1}</span><div className={styles.resultName}><strong>{variantLabel(video.index)}</strong><span>{(video.size / 1048576).toFixed(1)} Mo · MP4</span></div></div>
      <video className={styles.resultPreview} src={video.url} controls playsInline preload="metadata" aria-label={`Aperçu — ${variantLabel(video.index)}`} />
      <div className={styles.resultActions}>
        {sharingAvailable && <button type="button" className={styles.primary} disabled={busy} onClick={() => void choose([video])} aria-label={`${saveLabel} — ${variantLabel(video.index)}`}><ShareIcon />{saveLabel}</button>}
        <a className={sharingAvailable ? styles.fileLink : styles.primary} href={video.downloadUrl} download={variantFileName(video.index)} onClick={event => download(event, video)} referrerPolicy="no-referrer">Télécharger le MP4</a>
      </div>
    </li>)}</ol>
    <details className={styles.saveHelp}><summary>Retrouver mes vidéos sur mon téléphone</summary>
      <p><strong>iPhone :</strong> utilise Enregistrer dans Photos, puis « Enregistrer la vidéo » dans le menu de partage. Si tu télécharges le MP4 : Fichiers → Téléchargements → ouvre la vidéo → Partager → Enregistrer la vidéo.</p>
      <p><strong>Samsung :</strong> après le téléchargement, ouvre Mes fichiers → Téléchargements. Si la vidéo ne s’affiche pas dans Galerie, déplace le MP4 dans le dossier Movies.</p>
      <p>Si le partage est bloqué dans une autre application, ouvre ton lien dans Safari ou Chrome.</p>
    </details>
    {!!selection.length && <dialog ref={dialog} onCancel={close} aria-labelledby="gm-save-title" className={styles.saveDialog}>
      <div className={styles.saveDialogHeading}><h3 id="gm-save-title">{selection.length === 1 ? variantLabel(selection[0].index) : `Enregistrer les ${selection.length} vidéos`}</h3><button type="button" onClick={close} aria-label="Fermer" className={styles.closeDialog}>×</button></div>
      <p role="status" aria-live="polite" className={styles.transfer}>{message}</p>
      {busy && <div className={styles.track} aria-label="Préparation des vidéos"><div className={styles.indeterminate} /></div>}
      {canShareSelection && <><p className={styles.hint}>{instructions}</p><button type="button" className={styles.primary} disabled={busy} onClick={() => void share(files)}><ShareIcon />{device === "apple" ? "Enregistrer dans Photos" : "Ouvrir le partage"}</button></>}
      <div className={styles.downloadFallback}>{selection.map(video => <a key={video.id} className={styles.fileLink} href={video.downloadUrl} download={variantFileName(video.index)} onClick={event => download(event, video)} referrerPolicy="no-referrer">Télécharger le MP4{selection.length > 1 ? ` · Variante ${video.index + 1}` : ""}</a>)}</div>
    </dialog>}
  </section>;
}

function ShareIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 16V3m-5 5 5-5 5 5M4 14v6a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-6" /></svg>;
}

