import { authorize, OwnershipDenied, type Owner, type OwnershipStore } from "./ownership";
export { createSheetsOwnershipStore } from "./ownership-sheets";

const BACKEND = "https://duplicateur-de-reels.vercel.app";
const OPERATIONS = new Set(["opus", "source", "finish"]);
const QUERY_KEYS: Record<string, string[]> = {
  recover: ["action", "uploadId"], clips: ["action", "projectId", "clipIds", "target"], "project-state": ["action", "projectId"],
};
const ACTIONS: Record<string, Set<string>> = {
  opus: new Set(["submit", "duplicate", "style", "export-pack"]),
  source: new Set(["create", "target", "prepare"]),
  finish: new Set(["health"]),
};
const READ_ACTIONS = new Set(["recover", "clips", "project-state"]);
const BODY_KEYS: Record<string, string[]> = {
  "source:create": ["action", "size", "extension"],
  "source:target": ["action", "sourceToken"], "source:prepare": ["action", "sourceToken"],
  "finish:health": ["action"], "finish:render": ["url", "index"],
  "opus:submit": ["action", "uploadId", "title", "sourceToken"],
  "opus:duplicate": ["action", "projectId", "clipId", "sourceEditTicket"],
  "opus:style": ["action", "projectId", "clipId", "index", "editTicket"],
  "opus:export-pack": ["action", "projectId", "clipIds", "collectionId"],
};
const MAX_JSON_BYTES = 256 * 1024;
const error = (status: number, message: string) => Response.json({ error: message }, { status, headers: { "Cache-Control": "private, no-store" } });
// Only this host can attest that it stopped before contacting the provider.
const rejected = (status: number, message: string) => Response.json({ error: message, definitelyRejected: true, upstreamNotCalled: true },
  { status, headers: { "Cache-Control": "private, no-store" } });

// Called only after the host app's existing token guard. Never accepts an
// upstream URL, forwards app credentials, retries mutations, or adds CORS.
export async function forwardReelsRequest(request: Request, operation: string, owner: Owner, store: OwnershipStore): Promise<Response> {
  if (!OPERATIONS.has(operation)) return rejected(404, "Route de montage inconnue.");
  if (request.method !== "GET" && request.method !== "POST") return rejected(405, "Méthode non autorisée.");
  const incoming = new URL(request.url), origin = request.headers.get("Origin");
  if (origin && origin !== incoming.origin) return rejected(403, "Origine non autorisée.");
  const target = new URL("/api/" + operation, BACKEND);
  let body: string | undefined;
  let input: Record<string, unknown> = {};
  if (request.method === "GET") {
    if (operation !== "opus" || !READ_ACTIONS.has(incoming.searchParams.get("action") || "")) return rejected(400, "Action de suivi inconnue.");
    for (const [key, value] of incoming.searchParams) {
      if (!QUERY_KEYS[incoming.searchParams.get("action")!].includes(key) || value.length > 1000 || target.searchParams.has(key)) return rejected(400, "Paramètres de suivi invalides.");
      target.searchParams.set(key, value);
      input[key] = value;
    }
  } else {
    if (!/^application\/json(?:;|$)/i.test(request.headers.get("Content-Type") || "")) return rejected(415, "Requête JSON requise.");
    if (Number(request.headers.get("Content-Length")) > MAX_JSON_BYTES) return rejected(413, "Requête trop volumineuse.");
    const reader = request.body?.getReader();
    if (!reader) return rejected(400, "Requête vide.");
    const parts: Uint8Array[] = []; let size = 0;
    try {
      for (;;) {
        const part = await reader.read(); if (part.done) break;
        size += part.value.byteLength;
        if (size > MAX_JSON_BYTES) return rejected(413, "Requête trop volumineuse.");
        parts.push(part.value);
      }
    } finally { await reader.cancel().catch(() => undefined); }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const part of parts) { bytes.set(part, offset); offset += part.byteLength; }
    try {
      const value = JSON.parse(new TextDecoder().decode(bytes));
      if (!value || typeof value !== "object" || Array.isArray(value)) return rejected(400, "Requête invalide.");
      if (!(operation === "finish" && value.action === undefined) && !ACTIONS[operation].has(value.action)) return rejected(400, "Action de montage inconnue.");
      const allowed = BODY_KEYS[operation + ":" + (value.action ?? "render")];
      if (!allowed || Object.keys(value).some(key => !allowed.includes(key))) return rejected(400, "Paramètres de montage invalides.");
      body = JSON.stringify(value);
      input = value;
    } catch { return rejected(400, "Requête JSON invalide."); }
  }
  const action = String(input.action ?? "render");
  let recordReply: (reply: unknown) => Promise<void>;
  try { recordReply = await authorize(owner, store, operation, action, input); }
  catch (failure) {
    return failure instanceof OwnershipDenied
      ? rejected(403, "Ce montage n’est pas disponible pour ce compte.")
      : rejected(503, "Le registre des montages est indisponible. Aucun appel au service de montage n’a été envoyé.");
  }
  try {
    const upstream = await fetch(target, { method: request.method, body,
      headers: { "Accept": "application/json", ...(body ? { "Content-Type": "application/json" } : {}) },
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(290000)]), cache: "no-store", redirect: "error" });
    if (!/^application\/json(?:;|$)/i.test(upstream.headers.get("Content-Type") || "")) {
      await upstream.body?.cancel(); return error(502, "Le service de montage ne peut pas être joint. La progression est conservée.");
    }
    const headers = new Headers({ "Content-Type": "application/json", "Cache-Control": "private, no-store" });
    for (const key of ["X-GM-Upstream-Calls", "X-GM-Api-Next-At", "X-GM-Api-Wait-Ms", "Retry-After", "Date", "Server-Timing"]) {
      const value = upstream.headers.get(key); if (value !== null) headers.set(key, value);
    }
    const payload = await upstream.json();
    // Never accept the host-only no-transfer signal from an upstream reply,
    // including a 429 after a partially completed multi-step collection.
    if (payload && typeof payload === "object") delete payload.upstreamNotCalled;
    if (upstream.ok) {
      try { await recordReply(payload); }
      catch {
        // The provider may already have acted. Do not return definitelyRejected
        // or retry; withhold capabilities that were not durably associated.
        return error(502, "L’enregistrement du montage n’a pas été confirmé. Aucun appel n’a été rejoué.");
      }
    }
    return Response.json(payload, { status: upstream.status, headers });
  } catch {
    return error(502, "La réponse du montage n’a pas été confirmée. La progression est conservée ; aucun appel n’a été rejoué.");
  }
}
