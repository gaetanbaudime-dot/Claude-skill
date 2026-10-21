import { createHash } from "node:crypto";

export type Owner = { app: "clippers" | "creatrices"; id: string };
export type Kind = "source" | "upload" | "project" | "clip" | "collection" | "collection-set" | "export" | "final";
export type Claim = { kind: Kind; resource: string; parent: string };
export type OwnershipRow = Claim & { owner: string };
export interface OwnershipStore {
  read(): Promise<OwnershipRow[]>;
  append(rows: OwnershipRow[]): Promise<void>;
}
export class OwnershipDenied extends Error {}
export class OwnershipUnavailable extends Error {}
export const fingerprint = (value: unknown) => createHash("sha256").update(JSON.stringify(value)).digest("hex");
export const resource = (kind: Kind, ...ids: string[]) => fingerprint([kind, ...ids]);
const text = (value: unknown, max = 8192): string => {
  if (typeof value !== "string" || !value || value.length > max) throw new OwnershipDenied();
  return value;
};
const object = (value: unknown): Record<string, unknown> => {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new OwnershipUnavailable();
  return value as Record<string, unknown>;
};
const url = (value: unknown): string => {
  const raw = text(value); let parsed: URL;
  try { parsed = new URL(raw); } catch { throw new OwnershipDenied(); }
  if (parsed.protocol !== "https:" || parsed.username || parsed.password || parsed.hash) throw new OwnershipDenied();
  return raw; // Exact signed URL, not a hostname or a caller-selected prefix.
};
const clipSet = (value: unknown): string[] => {
  if (!Array.isArray(value) || value.length !== 6) throw new OwnershipDenied();
  const ids = value.map(v => text(v, 500));
  if (new Set(ids).size !== 6) throw new OwnershipDenied();
  return ids.sort();
};

export async function authorize(owner: Owner, store: OwnershipStore, operation: string, action: string, input: Record<string, unknown>) {
  if (!owner || !["clippers", "creatrices"].includes(owner.app) || !owner.id?.trim()) throw new OwnershipDenied();
  const ownerHash = fingerprint([owner.app, owner.id]);
  const rows = await store.read(); // No process/browser cache is an authority.
  const has = (claim: Claim, snapshot = rows) => {
    const matches = snapshot.filter(row => row.kind === claim.kind && row.resource === claim.resource);
    return matches.length > 0 && matches.every(row => row.owner === ownerHash && row.parent === claim.parent);
  };
  const requireClaim = (kind: Kind, id: string, parent = "-") => {
    const claim = { kind, resource: id, parent };
    if (!has(claim)) throw new OwnershipDenied();
    return claim;
  };
  const own = (kind: Kind, id: string) => {
    const matches = rows.filter(row => row.kind === kind && row.resource === id);
    if (!matches.length || matches.some(row => row.owner !== ownerHash || row.parent !== matches[0].parent)) throw new OwnershipDenied();
    return matches[0];
  };
  let project = "", source = "", upload = "", ids: string[] = [];
  if (operation === "source" && action !== "create") {
    source = resource("source", text(input.sourceToken)); requireClaim("source", source);
  } else if (operation === "opus" && action === "submit") {
    source = resource("source", text(input.sourceToken)); requireClaim("source", source);
    upload = resource("upload", text(input.uploadId, 500)); requireClaim("upload", upload, source);
  } else if (operation === "opus" && action === "recover") {
    upload = resource("upload", text(input.uploadId, 500)); own("upload", upload);
  } else if (operation === "opus") {
    const projectId = text(input.projectId, 500); project = resource("project", projectId); own("project", project);
    if (action === "duplicate" || action === "style") requireClaim("clip", resource("clip", projectId, text(input.clipId, 500)), project);
    if (action === "clips" && input.clipIds !== undefined) {
      const requested = text(input.clipIds, 1000).split(",");
      if (requested.length > 6 || new Set(requested).size !== requested.length) throw new OwnershipDenied();
      for (const id of requested) requireClaim("clip", resource("clip", projectId, text(id, 500)), project);
    }
    if (action === "export-pack") {
      ids = clipSet(input.clipIds);
      for (const id of ids) requireClaim("clip", resource("clip", projectId, id), project);
      if (input.collectionId !== undefined) {
        const collectionId = text(input.collectionId, 500), collection = resource("collection", collectionId);
        requireClaim("collection", collection, project);
        requireClaim("collection-set", resource("collection-set", collectionId, ...ids), collection);
      }
    }
  } else if (operation === "finish" && action === "render") {
    own("export", resource("export", url(input.url)));
    if (!Number.isInteger(input.index) || Number(input.index) < 0 || Number(input.index) > 5) throw new OwnershipDenied();
  }

  // Register only successful, structurally valid replies from the fixed backend,
  // after the referenced parent was authorized. Never register caller claims.
  return async function recordReply(reply: unknown) {
    const data = object(reply), claims: Claim[] = [];
    const add = (kind: Kind, id: string, parent = "-") => { claims.push({ kind, resource: id, parent }); return id; };
    const addExport = (value: unknown, clip: string) => {
      if (value !== null && value !== undefined) add("export", resource("export", url(value)), clip);
    };
    const addClip = (value: unknown) => {
      const clip = object(value);
      if (clip.projectId !== input.projectId) throw new OwnershipUnavailable();
      const key = add("clip", resource("clip", text(clip.projectId, 500), text(clip.clipId, 500)), project);
      if (clip.pending === false) addExport(clip.exportUrl, key);
    };
    if (operation === "source" && action === "create") add("source", resource("source", text(data.sourceToken)));
    if (operation === "source" && action !== "create" && data.ready === true) add("upload", resource("upload", text(data.uploadId, 500)), source);
    if (operation === "opus" && ["submit", "recover"].includes(action) && data.projectId !== null) {
      add("project", resource("project", text(data.projectId, 500)), upload);
    }
    if (operation === "opus" && action === "clips") {
      if (data.projectId !== input.projectId || !Array.isArray(data.clips)) throw new OwnershipUnavailable();
      for (const clip of data.clips) addClip(clip);
    }
    if (operation === "opus" && action === "duplicate") addClip(data);
    if (operation === "opus" && action === "export-pack") {
      const collectionId = text(data.collectionId, 500);
      if (input.collectionId !== undefined && collectionId !== input.collectionId) throw new OwnershipUnavailable();
      const collection = add("collection", resource("collection", collectionId), project);
      add("collection-set", resource("collection-set", collectionId, ...ids), collection);
      if (!Array.isArray(data.clips)) throw new OwnershipUnavailable();
      for (const value of data.clips) {
        const item = object(value);
        const clip = ids.find(id => item.id === input.projectId + "." + id);
        if (!clip) throw new OwnershipUnavailable();
        addExport(item.exportUrl, resource("clip", text(input.projectId, 500), clip));
      }
    }
    if (operation === "finish" && action === "render") {
      const parent = resource("export", url(input.url));
      add("final", resource("final", url(data.url)), parent);
      add("final", resource("final", url(data.downloadUrl)), parent);
    }
    if (!claims.length) return;
    const fresh = await store.read();
    const additions: OwnershipRow[] = [];
    for (const claim of claims) {
      const matches = fresh.filter(row => row.kind === claim.kind && row.resource === claim.resource);
      if (matches.length && !has(claim, fresh)) throw new OwnershipUnavailable();
      if (!matches.length && !additions.some(row => row.kind === claim.kind && row.resource === claim.resource && row.parent === claim.parent)) additions.push({ ...claim, owner: ownerHash });
    }
    // Existing claims were all revalidated against the fresh durable snapshot.
    // Polls do not write anything, so another identical confirmation read adds
    // latency without confirming a mutation. New claims still require append
    // followed by an independent durable read before capabilities leave host.
    if (!additions.length) return;
    await store.append(additions);
    const confirmed = await store.read();
    if (claims.some(claim => !has(claim, confirmed))) throw new OwnershipUnavailable();
  };
}
