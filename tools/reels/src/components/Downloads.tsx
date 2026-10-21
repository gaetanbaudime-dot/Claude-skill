"use client";
import { memo, useEffect, useRef, useState, type MouseEvent } from "react";
import type { RemoteVariant } from "../lib/server-video";
import { canShareFiles, createVideoFileCache, downloadPreparedFiles, sharePreparedFiles, shouldPrefetchVideos } from "../lib/downloads";
import { variantFileName, variantLabel } from "../lib/variant-labels";
import styles from "../reels.module.css";

function Downloads({ variants }: { variants: RemoteVariant[] }) {
  const [sharingAvailable, setSharingAvailable] = useState(false);
  const [device, setDevice] = useState<"apple" | "android" | "other">("other");
  const [selection, setSelection] = useState<RemoteVariant[]>([]), [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const [, refreshCache] = useState(0);
  const cache = useRef<ReturnType<typeof createVideoFileCache> | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const request = useRef(0), sharing = useRef(false);
  const playing = useRef<HTMLVideoElement | null>(null);
  useEffect(() => {
    const operation = new AbortController();
    cache.current = createVideoFileCache(operation.signal);
    let lastProgress = 0;
    const unsubscribe = cache.current.subscribe(complete => {
      // A stream can emit hundreds of chunks per second on Wi-Fi. Render
      // progress at most ten times a second, plus every completed file.
      const now = Date.now();
      if (complete || now - lastProgress >= 100) { lastProgress = now; refreshCache(value => value + 1); }
    });
    setSharingAvailable(canShareFiles());
    setDevice(/iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
      ? "apple" : /Android/.test(navigator.userAgent) ? "android" : "other");
    return () => { ++request.current; unsubscribe(); operation.abort(); cache.current = null; };
  }, []);
  useEffect(() => {
    const connection = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string; type?: string; downlink?: number } }).connection;
    const mobile = /iPhone|iPad|iPod|Android/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    // Never compete with preview playback by pulling six complete HD files
    // over cellular, Data Saver, or an unknown mobile connection.
    if (sharingAvailable && shouldPrefetchVideos(variants, mobile, connection)) {
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
      }, () => current === request.current);
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
  const transfer = cache.current?.progress(selection);
  const transferPercent = transfer?.totalBytes ? Math.min(100, Math.floor(transfer.loadedBytes / transfer.totalBytes * 100)) : 0;
  const previewPlaying = (video: HTMLVideoElement) => {
    if (playing.current && playing.current !== video) playing.current.pause();
    playing.current = video;
  };
  return <section className={styles.results} aria-label="Vidéos disponibles">
    <div className={styles.resultHeading}><h3>{variants.length === 6 ? "Tes 6 Reels" : `${variants.length} Reel${variants.length > 1 ? "s" : ""} disponible${variants.length > 1 ? "s" : ""}`}</h3><span>HD · 9:16</span></div>
    {sharingAvailable && variants.length > 1 && <button type="button" className={styles.primary} disabled={busy} onClick={() => void choose(variants)}><ShareIcon />{device === "apple" ? `Enregistrer les ${variants.length} dans Photos` : `Enregistrer les ${variants.length} vidéos`}</button>}
    <p className={styles.hint}>{device === "apple" ? "Enregistre tes vidéos dans Photos, en une fois ou une par une."
      : device === "android" ? "MP4 compatibles avec ton téléphone. Partage-les ou télécharge-les une par une." : "Enregistre chaque MP4 ou partage le lot depuis ton téléphone."}</p>
    {message && !selection.length && <p role="status" className={styles.transfer}>{message}</p>}
    <ol className={styles.resultList}>{variants.map(video => <li key={video.id} className={styles.resultCard}>
      <div className={styles.resultTop}><span className={styles.number}>{video.index + 1}</span><div className={styles.resultName}><strong>{variantLabel(video.index)}</strong><span>{(video.size / 1048576).toFixed(1)} Mo · MP4</span></div></div>
      <ResultPreview video={video} file={cache.current?.get([video])?.[0]} onPlay={previewPlaying} />
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
      {busy && <><div className={styles.track} role="progressbar" aria-label="Préparation des vidéos" aria-valuemin={0} aria-valuemax={100} aria-valuenow={transferPercent}>
        <div className={styles.fill} style={{ width: `${transferPercent}%` }} /></div>
        <p className={styles.hint}>{transferPercent} % · {((transfer?.loadedBytes || 0) / 1048576).toFixed(1)} / {((transfer?.totalBytes || 0) / 1048576).toFixed(1)} Mo · qualité HD conservée</p></>}
      {canShareSelection && <><p className={styles.hint}>{instructions}</p><button type="button" className={styles.primary} disabled={busy} onClick={() => void share(files)}><ShareIcon />{device === "apple" ? "Enregistrer dans Photos" : "Ouvrir le partage"}</button></>}
      <div className={styles.downloadFallback}>{selection.map(video => <a key={video.id} className={styles.fileLink} href={video.downloadUrl} download={variantFileName(video.index)} onClick={event => download(event, video)} referrerPolicy="no-referrer">Télécharger le MP4{selection.length > 1 ? ` · Variante ${video.index + 1}` : ""}</a>)}</div>
    </dialog>}
  </section>;
}

// Generation updates its elapsed timer every second. An unchanged result set
// must not redraw six native players just to refresh that separate timer.
export default memo(Downloads);

function ResultPreview({ video, file, onPlay }: { video: RemoteVariant; file?: File; onPlay: (video: HTMLVideoElement) => void }) {
  const element = useRef<HTMLVideoElement>(null);
  const [nearViewport, setNearViewport] = useState(false), [observing, setObserving] = useState(false);
  const [localUrl, setLocalUrl] = useState<string>();
  const [playing, setPlaying] = useState(false), [playbackFile, setPlaybackFile] = useState<File>();
  const position = useRef(0);
  useEffect(() => {
    if (!element.current || typeof IntersectionObserver === "undefined") return;
    setObserving(true);
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) { setNearViewport(true); observer.disconnect(); }
    }, { rootMargin: "120px" });
    observer.observe(element.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    // A save can finish while this remote player is running. Keep its current
    // source alive until pause; replacing src mid-play stops and rewinds it.
    if (!playing) setPlaybackFile(file);
  }, [file, playing]);
  useEffect(() => {
    position.current = element.current?.currentTime || 0;
    if (!playbackFile || (observing && !nearViewport)) { setLocalUrl(undefined); return; }
    // Saving and playback share the exact same HD bytes instead of issuing a
    // second remote request. Revoke the view URL when that file is replaced.
    const url = URL.createObjectURL(playbackFile); setLocalUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [playbackFile, observing, nearViewport]);
  return <video ref={element} className={styles.resultPreview} src={localUrl || (!observing || nearViewport ? video.url : undefined)}
    controls playsInline preload={nearViewport ? "metadata" : "none"} onPointerDown={() => setNearViewport(true)}
    onPlay={event => { setPlaying(true); onPlay(event.currentTarget); }} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)}
    onLoadedMetadata={event => {
      const player = event.currentTarget;
      if (position.current > 0 && position.current < player.duration) player.currentTime = position.current;
      position.current = 0;
    }} aria-label={`Aperçu — ${variantLabel(video.index)}`} />;
}

function ShareIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 16V3m-5 5 5-5 5 5M4 14v6a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-6" /></svg>;
}

