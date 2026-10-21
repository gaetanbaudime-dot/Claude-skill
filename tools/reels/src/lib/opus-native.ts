import type { RemoteVariant } from "./server-video";
export const CAPTION_LABELS = ["Variante 1 + Hook", "Variante 2 Verticale", "Variante 3 Bleue", "Variante 4 + Hook", "Variante 5 Classique", "Variante 6 Mouvement"] as const;
export type NativePhase = "checking" | "upload" | "preparing" | "native" | "variants" | "exports" | "cached";
export type UploadProgress = { loaded: number; total: number; elapsedSeconds: number; bytesPerSecond: number };

export type ClientConfiguration = { apiBase?: string; storageScope?: string };

// Same reviewed orchestration as TikFusion PR15. Only transport and browser
// storage scope are injected; vendor settings and rendering remain server-side.
export function createNativeClient({ apiBase = "/api", storageScope = "" }: ClientConfiguration = {}) {
  if (!/^\/api(?:\/[A-Za-z0-9_-]+)*$/.test(apiBase) || (storageScope && !/^[a-f0-9]{64}$/.test(storageScope))) {
    throw new Error("Configuration du montage invalide.");
  }
  const fetch: typeof globalThis.fetch = (input, init) => {
    const target = typeof input === "string" && /^\/api\/(?:opus|source|finish)(?:\?|$)/.test(input)
      ? apiBase + input.slice(4) : input;
    return globalThis.fetch(target, init);
  };

const API = "/api/opus";
const CAPTION_REVISION = "gm-native-clean-headline-20261014-v2";
const CHECKPOINT_PREFIX = "gm:native-job:v3:" + (storageScope ? storageScope + ":" : "");
const LEGACY_CHECKPOINT_PREFIX = "gm:native-job:v2:" + (storageScope ? storageScope + ":" : "");
// Upload capabilities expire independently. Never discard a paid project just
// because its original upload session has expired. Keep old records on refusal.
const MAX_CHECKPOINT_AGE_MS = 30 * 24 * 60 * 60 * 1000;
const UPLOAD_SESSION_MS = 24 * 60 * 60 * 1000;
const SOURCE_CONFIGURATION = "gm-mirror-h264-fr-clipanything-autohook-20261014-v1";
const FINISH_REVISION = "gm-native-polish-20261014-v1";
const POLL_MS = 3000;
const INITIAL_POLL_MS = 9000;
const MAX_NATIVE_WAIT_MS = 10 * 60 * 1000;
const API_GAP_MS = 2100;
let nextApiAt = 0;

type OpusClip = {
  projectId: string; clipId: string; title: string; durationSec: number; score: number;
  previewUrl: string | null; exportUrl: string | null; pending: boolean; styleIndex: number | null;
  editTicket?: string;
  sourceEditTicket?: string;
  editorial?: { headlineCount: number; headlineTop: boolean; remainingPauses: number } | null;
  exportPending?: boolean;
  exportKnown?: boolean;
  renderKnown?: boolean; previewRevision?: string | null; exportRevision?: string | null;
};
type Options = {
  signal?: AbortSignal; onStatus?: (value: string) => void; onProgress?: (value: number) => void;
  onVariant?: (variant: RemoteVariant) => void;
  onPhase?: (phase: NativePhase) => void;
  onResume?: (resuming: boolean) => void;
  onUploadProgress?: (value: UploadProgress) => void;
};
type PolishResult = { url: string; downloadUrl: string; size: number };
type Checkpoint = {
  profileRevision?: string;
  sourceHash?: string; sourceConfiguration?: string; finishRevision?: string;
  previousGeneration?: { profileRevision?: string; finishRevision?: string; selected: OpusClip[]; polishResults: Array<PolishResult | null>; collectionId?: string };
  createdAt: number; sourceToken?: string; mirroredBeforeCaptions?: boolean; sourceClips?: OpusClip[]; uploadId?: string; submitting?: boolean; projectId?: string;
  selected: OpusClip[]; styled: boolean[]; styleRequested: boolean[];
  duplicateRequested?: { sourceClipId: string; version: number };
  collectionSetupRequested?: boolean;
  oldPreview: Array<string | null>; oldExport: Array<string | null>; seenPending: boolean[]; seenHD: boolean[];
  collectionId?: string; exported?: boolean; polishResults: Array<PolishResult | null>;
};

function abortCheck(signal?: AbortSignal) {
  if (signal?.aborted) throw new DOMException("Annulé", "AbortError");
}
function sleep(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException("Annulé", "AbortError"));
    const cancel = () => {
      clearTimeout(timeout); signal?.removeEventListener("abort", cancel);
      reject(new DOMException("Annulé", "AbortError"));
    };
    const timeout = setTimeout(() => { signal?.removeEventListener("abort", cancel); resolve(); }, ms);
    signal?.addEventListener("abort", cancel, { once: true });
  });
}

// Reserve the worst case, then reconcile actual upstream calls. Signed source
// snapshots reduce repeated copy/style reads; cold/expired tickets stay safe.
async function paced(weight: number, signal: AbortSignal | undefined,
  run: () => Promise<Response>): Promise<Response> {
  let transportStarted = false;
  const invoke = async () => {
    const stored = Number(window.localStorage.getItem("gm:opus-next-api-at") || 0);
    const slot = Math.max(Date.now(), nextApiAt, Number.isFinite(stored) ? stored : 0);
    const reservedUntil = slot + weight * API_GAP_MS;
    nextApiAt = reservedUntil;
    window.localStorage.setItem("gm:opus-next-api-at", String(nextApiAt));
    await sleep(Math.max(0, slot - Date.now()), signal); abortCheck(signal);
    transportStarted = true;
    const response = await run();
    const countHeader = response.headers.get("X-GM-Upstream-Calls");
    const actualCalls = countHeader && /^\d+$/.test(countHeader) ? Number(countHeader) : NaN;
    if (Number.isInteger(actualCalls) && actualCalls >= 0 && actualCalls <= 90) {
      // Reserve the worst case before sending. Once the server has measured
      // the actual reads/retries, release unused slots before unlocking this
      // origin. A projected list can require one call instead of seven.
      const preciseWait = response.headers.get("X-GM-Api-Wait-Ms");
      const serverNext = Number(response.headers.get("X-GM-Api-Next-At"));
      const serverDate = Date.parse(response.headers.get("Date") || "");
      const serverWait = preciseWait !== null && /^\d+$/.test(preciseWait) ? Number(preciseWait) : Number.isFinite(serverNext) && Number.isFinite(serverDate)
        ? serverNext - serverDate : NaN;
      const until = Math.max(slot + actualCalls * API_GAP_MS,
        Number.isFinite(serverWait) && serverWait > 0 && serverWait <= 90 * API_GAP_MS
          ? Date.now() + serverWait : 0);
      if (nextApiAt === reservedUntil) nextApiAt = until;
      // Without Web Locks another tab may already own a later reservation.
      // Never move that tab's slot backwards.
      if (Number(window.localStorage.getItem("gm:opus-next-api-at")) === reservedUntil) {
        window.localStorage.setItem("gm:opus-next-api-at", String(until));
      }
    }
    return response;
  };
  try {
    if (navigator.locks) return await navigator.locks.request("gm:opus-api", signal ? { signal } : {}, invoke);
    return await invoke();
  } catch (cause) {
    if (transportStarted) throw cause;
    // Aborting a quota/lock wait cannot have performed the mutation. Create a
    // separate error: mutating the shared abort reason could mislabel another
    // request whose transport has already started.
    const failure = new Error(cause instanceof Error ? cause.message : "La requête n’a pas été envoyée.", { cause }) as Error & {
      definitelyRejected: boolean; upstreamNotCalled: boolean;
    };
    failure.name = cause instanceof Error ? cause.name : "Error";
    failure.definitelyRejected = true; failure.upstreamNotCalled = true;
    throw failure;
  }
}
async function request(action: string, payload: Record<string, unknown> | undefined,
  signal?: AbortSignal, query: Record<string, string> = {}) {
  const isGet = payload === undefined;
  const params = new URLSearchParams({ action, ...query });
  const weight = action === "style" || action === "duplicate" ? 2 : action === "export-pack" ? (payload?.collectionId ? 1 : 8)
    : action === "clips" && query.clipIds ? 1 + query.clipIds.split(",").length : 1;
  for (let attempt = 0; attempt < (isGet ? 3 : 1); attempt++) {
    const response = await paced(weight, signal, () => fetch(isGet ? API + "?" + params : API, {
      method: isGet ? "GET" : "POST",
      headers: isGet ? {} : { "Content-Type": "application/json" },
      ...(isGet ? {} : { body: JSON.stringify({ action, ...payload }) }),
      signal, cache: "no-store",
    }));
    const body = await response.json().catch(() => ({}));
    if (response.ok) return body;
    if (isGet && attempt < 2 && (response.status === 429 || response.status >= 500)) {
      await sleep(Math.max(5000, Math.min(60000, Number(body.retryAfterMs) || 15000)), signal); continue;
    }
    const error = new Error(String(body.error || "Le montage est momentanément indisponible (" + response.status + ").")) as Error & { definitelyRejected?: boolean; upstreamNotCalled?: boolean };
    error.definitelyRejected = body.definitelyRejected === true || [400, 401, 403, 404, 422, 429].includes(response.status);
    error.upstreamNotCalled = body.upstreamNotCalled === true;
    throw error;
  }
  throw new Error("Le suivi du montage est momentanément indisponible.");
}
const getClips = (projectId: string, signal?: AbortSignal, clipIds: string[] = [],
  target?: "preview" | "hd") => request("clips", undefined, signal, {
    projectId, ...(clipIds.length ? { clipIds: clipIds.join(",") } : {}), ...(target ? { target } : {}),
  });

function gcsUpload(file: File, target: string, opts: Options) {
  return new Promise<void>((resolve, reject) => {
    abortCheck(opts.signal);
    const xhr = new XMLHttpRequest();
    const started = performance.now();
    let sent = 0;
    const report = (loaded: number) => {
      sent = Math.max(sent, Math.min(file.size, Math.max(0, loaded)));
      const elapsedSeconds = Math.max(0, (performance.now() - started) / 1000);
      opts.onUploadProgress?.({ loaded: sent, total: file.size, elapsedSeconds,
        bytesPerSecond: elapsedSeconds > 0 ? sent / elapsedSeconds : 0 });
      opts.onProgress?.(Math.round(5 + sent / file.size * 20));
    };
    xhr.open("PUT", target); xhr.timeout = 10 * 60 * 1000;
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = event => {
      if (event.lengthComputable) report(event.loaded);
    };
    const stop = () => xhr.abort();
    opts.signal?.addEventListener("abort", stop, { once: true });
    xhr.onloadend = () => opts.signal?.removeEventListener("abort", stop);
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) { report(file.size); resolve(); }
      else reject(new Error("L'envoi du rush a échoué (" + xhr.status + ")."));
    };
    xhr.onerror = () => reject(new Error("L'envoi du rush est bloqué par le navigateur."));
    xhr.ontimeout = () => reject(new Error("L'envoi du rush a dépassé le délai autorisé."));
    xhr.onabort = () => reject(new DOMException("Annulé", "AbortError"));
    report(0);
    xhr.send(file);
  });
}
async function sourceRequest(payload: Record<string, unknown>, opts: Options) {
  const response = await fetch('/api/source', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload), signal: opts.signal, cache: 'no-store' });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(String(data.error || 'Préparation du rush indisponible.'));
  return data;
}
async function uploadPreparedSource(file: File, state: Checkpoint, save: () => void, opts: Options): Promise<string> {
  opts.onPhase?.("upload");
  opts.onStatus?.('IA G&M · préparation de l’envoi du rush…');
  if (!state.sourceToken) {
    const created = await sourceRequest({ action: 'create', size: file.size, extension: file.name.split('.').pop()?.toLowerCase() }, opts);
    if (!created.sourceToken) throw new Error('Session du rush absente.');
    state.sourceToken = String(created.sourceToken); save();
  }
  const target = await sourceRequest({ action: 'target', sourceToken: state.sourceToken }, opts);
  if (target.ready && target.uploadId) { state.mirroredBeforeCaptions = true; save(); return String(target.uploadId); }
  if (!target.uploaded) {
    opts.onStatus?.('IA G&M · envoi du rush…');
    try { await gcsUpload(file, String(target.uploadUrl), opts); }
    catch (error) {
      abortCheck(opts.signal);
      // A mobile connection may disappear after storage accepted the complete
      // PUT. Read its exact-sized object before asking for another transfer.
      // Never replay a raw upload or paid import on an ambiguous response.
      const confirmation = await sourceRequest({ action: 'target', sourceToken: state.sourceToken }, opts).catch(() => null);
      abortCheck(opts.signal);
      if (confirmation?.ready && confirmation.uploadId) {
        state.mirroredBeforeCaptions = true; save(); return String(confirmation.uploadId);
      }
      if (!confirmation?.uploaded) throw error;
      opts.onUploadProgress?.({ loaded: file.size, total: file.size, elapsedSeconds: 0, bytesPerSecond: 0 });
      opts.onProgress?.(25);
    }
  }
  opts.onStatus?.('IA G&M · retournement du rush avant les sous-titres…');
  opts.onPhase?.("preparing");
  const prepared = await sourceRequest({ action: 'prepare', sourceToken: state.sourceToken }, opts);
  if (!prepared.ready || !prepared.uploadId || !prepared.mirroredBeforeCaptions) throw new Error('Le retournement du rush n’a pas été confirmé.');
  state.mirroredBeforeCaptions = true; save();
  return String(prepared.uploadId);
}
async function checkpointKey(file: File, signal?: AbortSignal) {
  // Full-content SHA prevents another rush with the same name/size from
  // inheriting paid edits. Preserve existing jobs when removing the code gate.
  let digest: ArrayBuffer | Uint8Array;
  if (file.size > 8 * 1024 * 1024 && typeof file.slice === "function") {
    // A phone must not retain a 250 MiB ArrayBuffer before upload. The vetted
    // incremental implementation produces the exact same full-file SHA-256;
    // only one 1 MiB slice is read at a time. Yield so paint/cancel stay usable.
    const { sha256 } = await import("@noble/hashes/sha2.js");
    const hash = sha256.create();
    const chunkSize = 1024 * 1024;
    for (let offset = 0; offset < file.size; offset += chunkSize) {
      abortCheck(signal);
      hash.update(new Uint8Array(await file.slice(offset, offset + chunkSize).arrayBuffer()));
      if ((offset / chunkSize + 1) % 4 === 0) await sleep(0, signal);
    }
    abortCheck(signal);
    digest = hash.digest();
  } else {
    digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  }
  const hex = (value: ArrayBuffer | Uint8Array) => Array.from(value instanceof Uint8Array ? value : new Uint8Array(value), n => n.toString(16).padStart(2, "0")).join("");
  const sourceHash = hex(digest);
  return CHECKPOINT_PREFIX + sourceHash;
}
function readCheckpoint(key: string): Checkpoint | null {
  const sourceHash = key.slice(CHECKPOINT_PREFIX.length);
  let serialized = window.localStorage.getItem(key);
  if (serialized === null) {
    const candidates: string[] = [];
    for (let i = 0; i < window.localStorage.length; i++) {
      const oldKey = window.localStorage.key(i);
      if (!oldKey?.startsWith(LEGACY_CHECKPOINT_PREFIX) || !oldKey.endsWith(":" + sourceHash)) continue;
      candidates.push(window.localStorage.getItem(oldKey) || "");
    }
    // v2 included separate access scopes. Never pick the newest record across
    // several scopes, merge their IDs, or overwrite an existing v3 checkpoint.
    if (candidates.length > 1) throw new Error("Plusieurs anciens montages correspondent à ce rush dans ce navigateur. Les progressions sont conservées ; aucun nouvel import n’a été lancé.");
    serialized = candidates[0] ?? null;
  }
  if (serialized === null) return null;
  let value: Checkpoint;
  try { value = JSON.parse(serialized); }
  catch { throw new Error("La progression enregistrée est illisible. Elle est conservée ; aucun nouvel import n’a été lancé."); }
  if (!value || !Number.isFinite(value.createdAt) || value.createdAt <= 0 || value.createdAt > Date.now() + 60000 ||
      ![value.selected, value.styled, value.styleRequested, value.oldPreview, value.oldExport, value.seenPending, value.polishResults].every(Array.isArray) ||
      (value.sourceHash !== undefined && value.sourceHash !== sourceHash) ||
      (value.sourceClips !== undefined && !Array.isArray(value.sourceClips)) ||
      [value.projectId, value.uploadId, value.sourceToken].some(id => id !== undefined && (typeof id !== "string" || !id)) ||
      (value.submitting !== undefined && typeof value.submitting !== "boolean") ||
      [...value.selected, ...(value.sourceClips || [])].some(clip => !clip || typeof clip.clipId !== "string" ||
        !clip.clipId || !value.projectId || clip.projectId !== value.projectId)) {
    throw new Error("La progression ne correspond pas à ce rush ou est incomplète. Elle est conservée ; aucun nouvel import n’a été lancé.");
  }
  if (Date.now() - value.createdAt >= MAX_CHECKPOINT_AGE_MS) {
    throw new Error("Ce montage a atteint la limite de reprise de 30 jours. Ses références sont conservées. Vérifie sa disponibilité avant de demander explicitement un nouvel import.");
  }
  if (value.sourceConfiguration !== undefined && value.sourceConfiguration !== SOURCE_CONFIGURATION) {
    throw new Error("Les réglages de préparation de ce montage ont changé. Sa progression est conservée ; aucun nouvel import n’a été lancé.");
  }
  // Only the known shipped generation can be assigned its historical source
  // configuration. Unknown old formats must not silently acquire new settings.
  if (value.sourceConfiguration === undefined && value.profileRevision !== CAPTION_REVISION) {
    throw new Error("Les réglages de cet ancien montage ne sont pas identifiés. Sa progression est conservée ; aucun nouvel import n’a été lancé.");
  }
  return value;
}

async function availableFinal(item: PolishResult, opts: Options): Promise<boolean> {
  let url: URL, download: URL;
  try { url = new URL(item.url); download = new URL(item.downloadUrl); }
  catch { throw new Error("Le lien du fichier enregistré est invalide. La progression est conservée."); }
  if (url.protocol !== "https:" || url.username || url.password || download.username || download.password || download.origin !== url.origin ||
      download.pathname !== url.pathname || !Number.isSafeInteger(item.size) || item.size <= 0) {
    throw new Error("Le fichier enregistré est incohérent. La progression est conservée.");
  }
  const timeout = AbortSignal.timeout(15000);
  const signal = opts.signal ? AbortSignal.any([opts.signal, timeout]) : timeout;
  const response = await fetch(item.url, { method: "HEAD", signal, cache: "no-store" }).catch(() => null);
  abortCheck(opts.signal);
  if (response?.status === 404 || response?.status === 410) return false;
  if (!response?.ok || Number(response.headers.get("Content-Length")) !== item.size ||
      !/^video\/mp4(?:\s*;|$)/i.test(response.headers.get("Content-Type") || "")) {
    throw new Error("La disponibilité d’un fichier enregistré n’a pas pu être confirmée. Réessaie plus tard : aucun traitement supplémentaire n’a été lancé.");
  }
  return true;
}
async function storageHealth(opts: Options) {
  const signal = opts.signal
    ? AbortSignal.any([opts.signal, AbortSignal.timeout(30000)]) : AbortSignal.timeout(30000);
  const reply = await fetch("/api/finish", { method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "health" }), signal, cache: "no-store" });
  const storage = await reply.json().catch(() => ({}));
  if (!reply.ok || storage.ready !== true) {
    throw new Error(String(storage.error || "Le service de téléchargement est momentanément indisponible. Le rush n'a pas été envoyé."));
  }
}
function hasCheckpointHistory() {
  for (let index = 0; index < window.localStorage.length; index++) {
    const key = window.localStorage.key(index);
    if (key?.startsWith(CHECKPOINT_PREFIX) || key?.startsWith(LEGACY_CHECKPOINT_PREFIX)) return true;
  }
  return false;
}
function artifactIdentity(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    const version = url.searchParams.get("v");
    return url.origin + url.pathname + (version ? "?v=" + encodeURIComponent(version) : "");
  } catch { return null; }
}
function fresh(clip: OpusClip, index: number, checkpoint: Checkpoint, requireHD: boolean) {
  const current = requireHD ? clip.exportRevision || artifactIdentity(clip.exportUrl)
    : clip.previewRevision || artifactIdentity(clip.previewUrl);
  const previous = artifactIdentity(requireHD ? checkpoint.oldExport[index] : checkpoint.oldPreview[index]);
  // A signing-token change, fresh preview, or observed pending cycle cannot
  // prove that the HD file was replaced. Each target needs its own new output.
  return !!current && current !== previous;
}
function editorialReady(clip: OpusClip, index: number) {
  return !!clip.editorial && clip.editorial.headlineCount === (index === 0 || index === 3 ? 1 : 0) &&
    clip.editorial.headlineTop && clip.editorial.remainingPauses === 0;
}
async function waitForNative(checkpoint: Checkpoint, key: string, opts: Options, requireHD: boolean,
  onReady?: (index: number) => void, checkFinishes?: () => void, requestExport?: () => Promise<void>,
  readyTargets = new Set<number>(), singlePass = false) {
  const deadline = Date.now() + MAX_NATIVE_WAIT_MS;
  for (;;) {
    abortCheck(opts.signal);
    checkFinishes?.();
    // A target's exact style and fresh HD identity are proven before it enters
    // finishing. Keep polling only unresolved targets; do not fetch its native
    // detail again while its final MP4 is being encoded.
    // During submission, inspect only enough targets to fill the two finishing
    // slots. Reading four ready details here would delay the remaining styles
    // in the same rate-limited API queue without increasing encode capacity.
    const selected = checkpoint.selected.filter((_, index) => checkpoint.styled[index] && (!requireHD || !readyTargets.has(index)))
      .slice(0, singlePass ? 2 : 6);
    if (!selected.length) return;
    const requestedIds = selected.map(c => c.clipId);
    const found = await getClips(checkpoint.projectId!, opts.signal,
      requestedIds, requireHD ? "hd" : "preview");
    checkFinishes?.();
    const rows: OpusClip[] = Array.isArray(found.clips) ? found.clips : [];
    let ready = requireHD ? readyTargets.size : 0;
    for (let index = 0; index < checkpoint.selected.length; index++) {
      if (!checkpoint.styled[index] || (requireHD && readyTargets.has(index))) continue;
      if (!requestedIds.includes(checkpoint.selected[index].clipId)) continue;
      const current = rows.find(c => c.clipId === checkpoint.selected[index].clipId);
      if (!current) continue;
      if (current.pending) checkpoint.seenPending[index] = true;
      if (current.exportPending) checkpoint.seenHD[index] = true;
      checkpoint.selected[index] = current;
      if (!current.pending && current.renderKnown === true && current.styleIndex === index && editorialReady(current, index) &&
          fresh(current, index, checkpoint, requireHD) &&
          (requireHD ? current.exportKnown === true && !current.exportPending && !!current.exportUrl : !!current.previewUrl)) {
        ready++;
        if (requireHD) readyTargets.add(index);
        onReady?.(index);
      }
    }
    window.localStorage.setItem(key, JSON.stringify(checkpoint));
    if (!onReady) opts.onProgress?.(Math.min(90, (requireHD ? 83 : 72) + ready * 1.2));
    opts.onStatus?.("IA G&M · " + (requireHD ? "exports HD et finitions" : "sous-titres natifs") + " (" + ready + "/6 prêts)…");
    if (ready === 6) {
      checkpoint.exported = true;
      window.localStorage.setItem(key, JSON.stringify(checkpoint));
      return;
    }
    // Deliver each verified HD immediately. A slow sibling must not hold up
    // finishing. Do not request another export while native HD is rendering.
    if (singlePass) return;
    if (requestExport && !checkpoint.exported && checkpoint.styled.filter(Boolean).length === 6 && checkpoint.selected.every((clip, index) =>
      !clip.pending && clip.renderKnown === true && clip.styleIndex === index &&
      !!clip.previewUrl && fresh(clip, index, checkpoint, false))) await requestExport();
    if (Date.now() >= deadline) throw new Error("Les six " + (requireHD ? "exports HD" : "montages natifs") +
      " ne sont pas encore prêts. Réessaie avec ce même rush pour reprendre le projet sans nouvel import.");
    await sleep(POLL_MS, opts.signal);
  }
}

async function generate(file: File, opts: Options, key: string, preflight?: Promise<void>) {
  const started = performance.now();
  const previous = readCheckpoint(key);
  opts.onResume?.(!!previous);
  const state: Checkpoint = previous || { createdAt: Date.now(), selected: [], styled: [], styleRequested: [],
      oldPreview: [], oldExport: [], seenPending: [], seenHD: [], polishResults: [] };
  const profileChanged = state.profileRevision !== CAPTION_REVISION;
  if (profileChanged && previous && (state.duplicateRequested || state.collectionSetupRequested ||
      state.styleRequested.some((requested, index) => requested && !state.styled[index]))) {
    throw new Error("Une opération de l’ancien montage n’a pas été confirmée. Sa progression est conservée avant tout changement de réglages.");
  }
  if (profileChanged) {
    // Preserve original masters separately from edited copies. Historical jobs
    // without source IDs can resume unchanged, but cannot invent new masters.
    if (state.selected.length) {
      if (!state.sourceClips?.length || state.sourceClips.some(source => state.selected.some(copy => copy.clipId === source.clipId))) {
        throw new Error("Les clips sources originaux de cet ancien montage ne sont pas identifiés. Ses copies sont conservées ; aucun nouvel import ni remplacement de source n’a été lancé.");
      }
      state.previousGeneration = { profileRevision: state.profileRevision, finishRevision: state.finishRevision, selected: state.selected,
        polishResults: state.polishResults, collectionId: state.collectionId };
      state.selected = [];
      delete state.collectionId; delete state.collectionSetupRequested;
    }
    state.profileRevision = CAPTION_REVISION;
    state.styled = []; state.styleRequested = [];
    state.oldPreview = []; state.oldExport = [];
    state.seenPending = []; state.seenHD = [];
    state.polishResults = [];
    state.exported = false;
  }
  // A finishing-only change needs fresh finishes, never another source import.
  if (state.finishRevision && state.finishRevision !== FINISH_REVISION) {
    if (!profileChanged) state.previousGeneration = { profileRevision: state.profileRevision, finishRevision: state.finishRevision,
      selected: state.selected, polishResults: state.polishResults, collectionId: state.collectionId };
    state.polishResults = [];
  }
  state.sourceHash = key.slice(CHECKPOINT_PREFIX.length);
  state.sourceConfiguration = SOURCE_CONFIGURATION;
  state.finishRevision = FINISH_REVISION;
  state.seenHD ||= [];
  state.polishResults ||= [];
  const save = () => window.localStorage.setItem(key, JSON.stringify(state));
  save(); // Fail before any paid work if resumability storage is unavailable.
  const baseName = file.name.replace(/\.[^.]+$/, "").replace(/[^a-z0-9_-]+/gi, "-") || "reel";
  const variant = (item: PolishResult, index: number): RemoteVariant => ({
    id: state.selected[index].clipId, index, name: baseName + "-variante-" + (index + 1) + ".mp4",
    captionPreset: CAPTION_LABELS[index], url: item.url, downloadUrl: item.downloadUrl,
    size: item.size, mirror: false, orientation: "vertical",
  });
  const result = (items: PolishResult[]) => ({ variants: items.map(variant), processingMs: performance.now() - started,
    jobId: state.projectId!, notice: "6 vidéos HD avec sous-titres natifs et finitions vidéo G&M, prêtes à télécharger." +
      (state.mirroredBeforeCaptions ? " Rush retourné avant les sous-titres." : " Reprise d’un ancien montage : retournement source non vérifié."),
    projectUrl: "https://clip.opus.pro/editor-ux/" + state.projectId + "." + state.selected[0].clipId +
      "?clipId=" + encodeURIComponent(state.selected[0].clipId) });
  const verifiedFinals = new Set<number>();
  const missingFinals = new Set<number>();
  const cachedFinals = state.polishResults.filter((item): item is PolishResult => !!item);
  // Finishes can complete before the last copies exist. Restore those downloads
  // before a native lookup or an unconfirmed copy can stop the remaining work.
  if (state.projectId && state.selected.length > 0 && state.selected.length <= 6 &&
      new Set(state.selected.map(c => c.clipId)).size === state.selected.length &&
      state.selected.every(clip => clip.projectId === state.projectId) &&
      state.polishResults.length <= 6 && cachedFinals.length > 0) {
    opts.onStatus?.("IA G&M · vérification des vidéos déjà terminées…");
    opts.onPhase?.("cached");
    // No native read is needed to retrieve immutable, same-revision final files.
    const validations = await Promise.allSettled(state.polishResults.map(async (item, index) => {
      if (!item) return;
      if (!state.selected[index] || state.styled[index] !== true ||
          state.polishResults.some((other, otherIndex) => otherIndex !== index && other?.url === item.url)) {
        throw new Error("Le fichier enregistré est incohérent. La progression est conservée.");
      }
      if (await availableFinal(item, opts)) {
        verifiedFinals.add(index);
        opts.onVariant?.(variant(item, index));
      } else missingFinals.add(index);
    }));
    // Each available file is useful even if another cannot be checked. Drain all
    // checks before failing so no callbacks arrive after the attempt has ended.
    const unavailable = validations.find(check => check.status === "rejected");
    if (unavailable?.status === "rejected") throw unavailable.reason;
    if (verifiedFinals.size === 6) {
      const ready = result(state.polishResults as PolishResult[]);
      opts.onProgress?.(100);
      return ready;
    }
  }
  if (!state.projectId && !state.submitting && Date.now() - state.createdAt >= UPLOAD_SESSION_MS) {
    throw new Error("La session d’envoi de ce rush a expiré. Sa progression est conservée ; aucun nouvel import n’a été lancé.");
  }
  opts.onStatus?.("IA G&M · préparation du montage…");
  // Await the read-only storage preflight before any upload/create/prepare or
  // paid mutation. Cached final files above still bypass storage health.
  await (preflight || storageHealth(opts));
  if (!state.projectId && !state.submitting && !state.uploadId) { state.uploadId = await uploadPreparedSource(file, state, save, opts); save(); }
  if (!state.projectId && state.submitting) {
    opts.onPhase?.("checking");
    if (!state.uploadId) throw new Error("La confirmation de l’ancien import et sa référence d’envoi sont manquantes. La progression est conservée ; aucun nouvel import n’a été lancé.");
    const recovered = await request("recover", undefined, opts.signal, { uploadId: state.uploadId });
    if (!recovered.projectId) throw new Error("Le précédent import a été envoyé mais sa confirmation est manquante. " +
      "Aucun nouvel import payant n'a été lancé. Consulte le projet dans ton compte avant de recommencer.");
    state.projectId = String(recovered.projectId); state.submitting = false; save();
  }
  if (!state.projectId) {
    opts.onPhase?.("native");
    opts.onProgress?.(26); opts.onStatus?.("IA G&M · détection des accroches et montage français…");
    state.submitting = true; save();
    let submitted;
    try { submitted = await request("submit", { uploadId: state.uploadId, title: file.name, ...(state.sourceToken ? { sourceToken: state.sourceToken } : {}) }, opts.signal); }
    catch (error) {
      if ((error as Error & { definitelyRejected?: boolean }).definitelyRejected) { state.submitting = false; save(); }
      throw error;
    }
    if (!submitted.projectId) throw new Error("Le projet de montage n'a pas retourné de confirmation.");
    state.projectId = String(submitted.projectId); state.submitting = false; save();
  }
  const projectId = state.projectId;
  if (previous && (profileChanged || Date.now() - state.createdAt >= UPLOAD_SESSION_MS)) {
    opts.onPhase?.("checking");
    const found = await getClips(projectId, opts.signal, [], "preview");
    const ids = new Set((Array.isArray(found.clips) ? found.clips : []).map((clip: OpusClip) => clip.clipId));
    const references = [...(state.sourceClips || []), ...state.selected];
    if (!ids.size || references.some(clip => clip.projectId !== projectId || !ids.has(clip.clipId))) {
      throw new Error("Les clips de ce montage ne sont plus tous disponibles. Ses références sont conservées ; aucun nouvel import n’a été lancé.");
    }
  }
  if (!state.selected.length && !state.sourceClips?.length) {
    opts.onPhase?.("native");
    const deadline = Date.now() + MAX_NATIVE_WAIT_MS;
    let previousCount = 0, stable = 0;
    for (;;) {
      const found = await getClips(projectId, opts.signal);
      const clips: OpusClip[] = (Array.isArray(found.clips) ? found.clips : [])
        .filter((c: OpusClip) => c.clipId && c.previewUrl && !c.pending);
      stable = clips.length > 0 && clips.length === previousCount ? stable + 1 : 0;
      previousCount = clips.length;
      opts.onProgress?.(Math.min(60, 28 + clips.length * 5)); opts.onStatus?.("IA G&M · analyse et montage natif…");
      const nextPollAt = Date.now() + INITIAL_POLL_MS;
      let complete = false;
      if (clips.length > 0 && clips.length < 6 && stable === 0) {
        // The verified project listing exposes COMPLETE + clipCount. Use that
        // positive signal instead of two artificial stability intervals.
        const project = await request('project-state', undefined, opts.signal, { projectId });
        complete = project.stage === 'COMPLETE' && Number.isInteger(project.clipCount) &&
          project.clipCount > 0 && clips.length >= project.clipCount;
      }
      if (complete || clips.length >= 6 || (clips.length > 0 && stable >= 2)) {
        state.sourceClips = clips.sort((a, b) => b.score - a.score).slice(0, 6); save(); break;
      }
      if (Date.now() >= deadline) throw new Error("Le premier montage est encore en attente. Réessaie avec ce même rush pour reprendre sans nouvel import.");
      await sleep(Math.max(0, nextPollAt - Date.now()), opts.signal);
    }
  }
  // Resolve uncertain copies before any new mutation, including styles on
  // earlier copies. A lost non-idempotent reply must never create a duplicate.
  if (state.selected.length < 6 && state.duplicateRequested) throw new Error("La copie de la variante " +
      state.duplicateRequested.version + " n'a pas été confirmée. Aucun doublon n'a été relancé. " +
      "Vérifie les clips du projet " + projectId + " avant de reprendre.");
  if (new Set(state.selected.map(c => c.clipId)).size !== state.selected.length) {
    throw new Error("Six variantes distinctes sont requises.");
  }
  async function prepareCopy(index: number) {
    if (state.selected[index]) return;
    if (state.selected.length !== index) throw new Error("L'ordre des variantes est incohérent.");
    const parent = state.sourceClips?.length ? state.sourceClips[state.selected.length % state.sourceClips.length] : state.selected[0];
    opts.onStatus?.("IA G&M · préparation de la variante " + (state.selected.length + 1) + "/6…");
    state.duplicateRequested = { sourceClipId: parent.clipId, version: state.selected.length + 1 }; save();
    let duplicate: OpusClip;
    try { duplicate = await request("duplicate", { projectId, clipId: parent.clipId,
      sourceEditTicket: parent.sourceEditTicket }, opts.signal) as OpusClip; }
    catch (error) {
      if ((error as Error & { definitelyRejected?: boolean }).definitelyRejected) {
        delete state.duplicateRequested; save();
      }
      throw error;
    }
    if (!duplicate.clipId || state.selected.some(c => c.clipId === duplicate.clipId)) {
      throw new Error("La préparation des six variantes a retourné un identifiant incohérent.");
    }
    if (duplicate.sourceEditTicket) parent.sourceEditTicket = duplicate.sourceEditTicket;
    delete duplicate.sourceEditTicket;
    state.selected.push(duplicate); delete state.duplicateRequested; save();
  }
  async function requestNativeExport() {
    if (state.exported) return;
    if (!state.collectionId && state.collectionSetupRequested) throw new Error(
      "La création du groupe d'exports n'a pas été confirmée. Aucun groupe supplémentaire n'a été créé. " +
      "Vérifie les collections du projet " + projectId + " avant de reprendre.");
    opts.onStatus?.("IA G&M · préparation des exports HD manquants…");
    if (!state.collectionId) { state.collectionSetupRequested = true; save(); }
    let pack;
    try { pack = await request("export-pack", { projectId, clipIds: state.selected.map(c => c.clipId),
      ...(state.collectionId ? { collectionId: state.collectionId } : {}) }, opts.signal); }
    catch (error) {
      // A provider 429 can follow collection creation. Only a host rejection
      // before transfer proves that creating a collection can be retried.
      if ((error as Error & { upstreamNotCalled?: boolean }).upstreamNotCalled) {
        delete state.collectionSetupRequested; save();
      }
      throw error;
    }
    if (!pack.collectionId) throw new Error("La préparation des exports HD n'a pas été confirmée.");
    state.collectionId = String(pack.collectionId); state.exported = true;
    delete state.collectionSetupRequested; save();
  }
  // Re-read Opus after requesting the export. Never retain a pre-style URI or
  // treat a low-resolution preview as an HD download.
  const headers = { "Content-Type": "application/json" };
  const finished: Array<PolishResult | null> = Array.from({ length: 6 }, () => null);
  async function finishOne(index: number) {
    const cached = state.polishResults[index];
    if (cached?.url && cached.downloadUrl && cached.size > 0) {
      if (verifiedFinals.has(index) || (!missingFinals.has(index) && await availableFinal(cached, opts))) {
        finished[index] = cached;
        if (!verifiedFinals.has(index)) {
          verifiedFinals.add(index); opts.onVariant?.(variant(cached, index));
        }
        return;
      }
    }
    const sourceUrl = state.selected[index].exportUrl;
    if (!sourceUrl) throw new Error("L'export HD de la variante " + (index + 1) + " est manquant.");
    const controller = new AbortController();
    const cancel = () => controller.abort();
    opts.signal?.addEventListener("abort", cancel, { once: true });
    const timer = setTimeout(cancel, 280000);
    try {
      abortCheck(opts.signal);
      let reply: Response | undefined;
      let item: Record<string, any> = {};
      for (let attempt = 0; attempt < 4; attempt++) {
        reply = await fetch("/api/finish", { method: "POST", headers,
          body: JSON.stringify({ url: sourceUrl, index }), signal: controller.signal, cache: "no-store" });
        item = await reply.json().catch(() => ({}));
        // Capacity 429 is sent before /api/finish downloads, encodes or
        // stores anything. Network/5xx responses may be ambiguous: never
        // retry them automatically and duplicate completed work.
        if (reply.status !== 429 || attempt === 3) break;
        const retry = reply.headers.get("Retry-After");
        const seconds = retry && /^\d+(?:\.\d+)?$/.test(retry) ? Number(retry)
          : retry ? (Date.parse(retry) - Date.now()) / 1000 : 5;
        opts.onStatus?.("IA G&M · moteur occupé, reprise de la variante " + (index + 1) + "/6…");
        await sleep(Math.max(1000, Math.min(15000, (Number.isFinite(seconds) ? seconds : 5) * 1000)), controller.signal);
      }
      if (!reply?.ok) throw new Error(String(item.error || "Les finitions de la variante " + (index + 1) + " ont échoué. Le projet natif est conservé."));
      if (!item.url || !item.downloadUrl || Number(item.size) <= 0) throw new Error("Le MP4 final de la variante " + (index + 1) + " est incomplet.");
      finished[index] = { url: String(item.url), downloadUrl: String(item.downloadUrl), size: Number(item.size) };
      state.polishResults[index] = finished[index]; save();
      opts.onVariant?.(variant(finished[index]!, index));
    } catch (error) {
      abortCheck(opts.signal);
      if (controller.signal.aborted) throw new Error("La finition vidéo a dépassé le délai autorisé. Réessaie avec ce même rush pour reprendre sans nouvel import.");
      throw error;
    } finally { clearTimeout(timer); opts.signal?.removeEventListener("abort", cancel); }
  }
  const queue: number[] = [];
  const finishing: Promise<void>[] = [];
  let active = 0;
  let failure: unknown;
  let hasFailed = false;
  const failed = (error: unknown) => {
    if (!hasFailed) { failure = error; hasFailed = true; }
  };
  const checkFinishes = () => { if (hasFailed) throw failure; };
  function startReadyFinishes() {
    while (active < 2 && queue.length && !hasFailed) {
      const index = queue.shift()!;
      active++;
      // Start a new target as soon as either slot frees up. Each target still
      // requires its own fresh HD output and exact native caption profile.
      const task = finishOne(index).then(() => {
        const count = finished.filter(Boolean).length;
        opts.onProgress?.(Math.min(97, 83 + count * 2));
        opts.onStatus?.("IA G&M · finitions vidéo (" + count + "/6 terminées)…");
      }).catch(failed).finally(() => {
        active--;
        startReadyFinishes();
      });
      finishing.push(task);
    }
  }
  const readyTargets = new Set<number>();
  const receiveReady = (index: number) => { queue.push(index); startReadyFinishes(); };
  try {
    opts.onPhase?.(state.selected.length === 6 && state.selected.every((_, index) => state.styled[index]) ? "exports" : "variants");
    // Legacy partial checkpoints can use their first selected clip as the
    // duplication source. Finish those copies before editing that same clip;
    // current checkpoints keep separate sourceClips and can safely interleave.
    if (!state.sourceClips?.length) {
      while (state.selected.length < 6) await prepareCopy(state.selected.length);
    }
    for (let index = 0; index < 6; index++) {
      checkFinishes();
      // Start this copy's native render before preparing the next one. The
      // same paced API queue and signed source snapshot still govern every
      // request; only ordering changes, never render quality or concurrency.
      await prepareCopy(index);
      checkFinishes();
      if (state.styled[index]) continue;
      if (state.styleRequested[index]) {
        const found = await getClips(projectId, opts.signal, [state.selected[index].clipId], "preview");
        const current = (found.clips as OpusClip[]).find(c => c.clipId === state.selected[index].clipId);
        if (!current || current.styleIndex !== index || !editorialReady(current, index)) throw new Error("La confirmation du style " + (index + 1) +
          " est manquante. Aucun rendu payant n'a été relancé automatiquement.");
        state.styled[index] = true; save(); continue;
      }
      opts.onStatus?.("IA G&M · sous-titres natifs, variante " + (index + 1) + "/6…");
      state.oldPreview[index] = state.selected[index].previewRevision || state.selected[index].previewUrl;
      state.oldExport[index] = state.selected[index].exportRevision || state.selected[index].exportUrl;
      state.styleRequested[index] = true; save();
      try { await request("style", { projectId, clipId: state.selected[index].clipId, index, editTicket: state.selected[index].editTicket }, opts.signal); }
      catch (error) {
        if ((error as Error & { definitelyRejected?: boolean }).definitelyRejected) { state.styleRequested[index] = false; save(); }
        throw error;
      }
      state.styled[index] = true;
      delete state.selected[index].editTicket;
      state.selected[index] = { ...state.selected[index], pending: true, previewUrl: null, exportUrl: null };
      save(); opts.onProgress?.(62 + index * 2);
      if (index === 3) await waitForNative(state, key, opts, true, receiveReady, checkFinishes, undefined, readyTargets, true);
    }
    if (state.selected.length !== 6 || new Set(state.selected.map(c => c.clipId)).size !== 6) {
      throw new Error("Six variantes distinctes sont requises.");
    }
    opts.onPhase?.("exports");
    await waitForNative(state, key, opts, true, receiveReady, checkFinishes, requestNativeExport, readyTargets);
    // The list grows when a slot starts its next target. Waiting for its final
    // task also drains the queued targets started by earlier completions.
    for (let index = 0; index < finishing.length; index++) await finishing[index];
    checkFinishes();
  } catch (error) {
    failed(error);
    // Settle every started finish before surfacing an error, so checkpoints
    // cannot change behind a later resume and paid work is never replayed.
    await Promise.allSettled(finishing);
    throw failure;
  }
  const urls = finished.map(item => {
    if (!item) throw new Error("Les six finitions vidéo n'ont pas été terminées.");
    if (new URL(item.url).protocol !== "https:") throw new Error("Une adresse vidéo finale est incorrecte.");
    return item.url;
  });
  if (new Set(urls).size !== 6) throw new Error("Six fichiers MP4 finals distincts sont requis.");
  opts.onProgress?.(100);
  return result(finished as PolishResult[]);
}

async function generateOpusVariations(file: File, opts: Options = {}) {
  abortCheck(opts.signal);
  opts.onPhase?.("checking");
  const started = performance.now();
  if (!navigator.locks) throw new Error("Ton navigateur ne permet pas de protéger la reprise entre deux onglets. Ouvre le module dans un navigateur récent avant de lancer le montage.");
  const preflightController = new AbortController();
  // A first-time owner cannot have cached finals. Overlap only this read-only
  // check with fingerprinting; existing jobs retain their six-HEAD fast path.
  const preflight = !hasCheckpointHistory() ? storageHealth({ ...opts, signal: opts.signal
    ? AbortSignal.any([opts.signal, preflightController.signal]) : preflightController.signal }) : undefined;
  // Hashing may fail or be cancelled before the preflight is awaited.
  void preflight?.catch(() => undefined);
  try {
    const key = await checkpointKey(file, opts.signal);
    abortCheck(opts.signal);
    const result = await navigator.locks.request(key, opts.signal ? { signal: opts.signal } : {}, () => generate(file, opts, key, preflight));
    return { ...result, processingMs: performance.now() - started };
  } finally { preflightController.abort(); }
}


  return { generateOpusVariations };
}

export const generateOpusVariations = createNativeClient().generateOpusVariations;

