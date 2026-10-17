import type { RemoteVariant } from './server-video';

export const MAX_SHARE_BYTES = 128 * 1024 * 1024;

export function canShareFiles(files = [new File([''], 'video.mp4', { type: 'video/mp4' })]) {
  try { return typeof navigator.share === 'function' && navigator.canShare?.({ files }) === true; }
  catch { return false; }
}

export async function downloadVideos(videos: RemoteVariant[], signal = new AbortController().signal,
  onProgress?: (done: number) => void) {
  // Browsers can silently refuse multiple automatic downloads. Do not report
  // them as saved; the UI always keeps individual user-activated links.
  for (let index = 0; index < videos.length; index++) {
    const video = videos[index];
    // Cross-origin anchors ignore `download` and concurrent navigations cancel
    // each other. Transfer one existing MP4 at a time, then download a local
    // object URL. Memory stays bounded to the current file, without encoding.
    const [file] = await prepareShareFiles([video], signal);
    signal.throwIfAborted();
    const url = URL.createObjectURL(file);
    const link = document.createElement('a');
    link.href = url; link.download = video.name; link.rel = 'noopener';
    document.body.appendChild(link); link.click(); link.remove();
    await new Promise(resolve => setTimeout(resolve, 1000));
    URL.revokeObjectURL(url);
    onProgress?.(index + 1);
  }
}

export async function prepareShareFiles(videos: RemoteVariant[], signal: AbortSignal,
  onProgress?: (done: number) => void): Promise<File[]> {
  if (!videos.length || videos.some(v => v.size <= 0) ||
      videos.reduce((total, v) => total + v.size, 0) > MAX_SHARE_BYTES) {
    throw new Error('Ce lot est trop volumineux pour le partage mobile. Télécharge les vidéos individuellement.');
  }
  const files: File[] = [];
  // One fetch at a time bounds temporary memory on phones. These are the final
  // MP4 bytes: no rendering, transcoding or new server-side job.
  for (const video of videos) {
    const url = new URL(video.url);
    if (url.pathname.startsWith('/media/')) url.searchParams.set('share', '1');
    const response = await fetch(url, { signal });
    if (!response.ok || !response.body || !/^video\/mp4(?:\s*;|$)/i.test(response.headers.get('Content-Type') || '')) {
      throw new Error('La vidéo ne peut pas être préparée pour le partage. Utilise le téléchargement individuel.');
    }
    const reader = response.body.getReader();
    const chunks: Uint8Array<ArrayBuffer>[] = [];
    let size = 0;
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > video.size) throw new Error('La taille de la vidéo a changé. Relance le téléchargement individuel.');
        chunks.push(new Uint8Array(value));
      }
    } finally { await reader.cancel().catch(() => undefined); }
    if (size !== video.size) throw new Error('La vidéo reçue est incomplète. Réessaie le téléchargement.');
    files.push(new File(chunks, video.name, { type: 'video/mp4' }));
    onProgress?.(files.length);
  }
  return files;
}

export async function sharePreparedFiles(files: File[]): Promise<'handed-off' | 'cancelled' | 'unavailable'> {
  if (!files.length || !canShareFiles(files)) return 'unavailable';
  try {
    // Called directly by a fresh click after preparation. Safari must retain
    // transient user activation; never await a download before this call.
    await navigator.share({ files });
    return 'handed-off';
  } catch (error) {
    return error instanceof DOMException && error.name === 'AbortError' ? 'cancelled' : 'unavailable';
  }
}
