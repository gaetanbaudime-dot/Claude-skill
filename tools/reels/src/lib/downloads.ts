import type { RemoteVariant } from './server-video';
import { variantFileName } from './variant-labels';

export const MAX_SHARE_BYTES = 128 * 1024 * 1024;

export function canShareFiles(files = [new File(['0'], 'video.mp4', { type: 'video/mp4' })]) {
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
    downloadPreparedFiles([file]);
    await new Promise(resolve => setTimeout(resolve, 1000));
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
    files.push(new File(chunks, variantFileName(video.index), { type: 'video/mp4' }));
    onProgress?.(files.length);
  }
  return files;
}

// Use already prepared bytes inside the tap handler. In particular, do not
// revoke Safari's object URL while the download/share UI is still opening.
export function downloadPreparedFiles(files: File[]) {
  for (const file of files) {
    const url = URL.createObjectURL(file);
    const link = document.createElement('a');
    link.href = url; link.download = file.name; link.rel = 'noopener';
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }
}

// One bounded cache per mounted result set. Background preparation and taps
// reuse the same in-flight request; cancelling the share sheet keeps the files.
export function createVideoFileCache(signal: AbortSignal) {
  const files = new Map<string, File>(), pending = new Map<string, Promise<File>>();
  let pendingBytes = 0;
  const key = (video: RemoteVariant) => `${video.id}:${video.index}:${video.url}:${video.size}`;
  const get = (videos: RemoteVariant[]) => {
    const found = videos.map(video => files.get(key(video)));
    return found.every((file): file is File => !!file) ? found : null;
  };
  async function prepare(videos: RemoteVariant[], onProgress?: (done: number) => void) {
    if (!videos.length || videos.some(video => video.size <= 0) || videos.reduce((sum, video) => sum + video.size, 0) > MAX_SHARE_BYTES) {
      throw new Error('Ce lot est trop volumineux. Enregistre les vidéos une par une.');
    }
    // A large pack is never prefetched. For successive individual saves, keep
    // at most one share budget rather than retaining six 100 MiB files.
    const retained = [...files.values()].reduce((sum, file) => sum + file.size, 0);
    const missing = videos.filter(video => !files.has(key(video)) && !pending.has(key(video))).reduce((sum, video) => sum + video.size, 0);
    if (retained + pendingBytes + missing > MAX_SHARE_BYTES) {
      if (pendingBytes) throw new Error('Une vidéo se prépare déjà. Patiente un instant puis réessaie.');
      files.clear();
    }
    const prepared: File[] = [];
    for (const video of videos) {
      signal.throwIfAborted();
      const id = key(video);
      let file = files.get(id);
      if (!file) {
        let request = pending.get(id);
        if (!request) {
          pendingBytes += video.size;
          request = prepareShareFiles([video], signal).then(([ready]) => { signal.throwIfAborted(); files.set(id, ready); return ready; })
            .finally(() => { pending.delete(id); pendingBytes -= video.size; });
          pending.set(id, request);
        }
        file = await request;
      }
      prepared.push(file); onProgress?.(prepared.length);
    }
    return prepared;
  }
  signal.addEventListener('abort', () => { files.clear(); pending.clear(); }, { once: true });
  return { get, prepare };
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

