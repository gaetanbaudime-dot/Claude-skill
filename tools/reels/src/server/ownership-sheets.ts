import { OwnershipUnavailable, type OwnershipStore, type OwnershipRow } from "./ownership";

const SHEET = "Reels ownership v1";
const HEADER = ["version", "owner_sha256", "kind", "resource_sha256", "parent_sha256"];
const KINDS = new Set(["source", "upload", "project", "clip", "collection", "collection-set", "export", "final"]);
const HASH = /^[a-f0-9]{64}$/;

// Uses only the existing Google service-account token and the existing internal
// usage workbook. This adapter never creates files/tabs or changes permissions.
// Missing/ambiguous/malformed/unavailable storage blocks before provider access.
export function createSheetsOwnershipStore(app: "clippers" | "creatrices", googleToken: () => Promise<string>): OwnershipStore {
  let workbook: string | undefined;
  async function call(url: string, init: RequestInit = {}) {
    const token = await googleToken();
    const response = await fetch(url, { ...init, headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      cache: "no-store", redirect: "error", signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw new OwnershipUnavailable();
    return response.json();
  }
  async function base() {
    if (!workbook) {
      const name = app === "clippers" ? "App clippers · usage" : "App créatrices · usage";
      const q = `name='${name}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false`;
      const found = await call("https://www.googleapis.com/drive/v3/files?" + new URLSearchParams({ q, fields: "files(id),nextPageToken", pageSize: "2", supportsAllDrives: "true", includeItemsFromAllDrives: "true" }));
      if (found.nextPageToken || !Array.isArray(found.files) || found.files.length !== 1 || typeof found.files[0]?.id !== "string" || !/^[a-zA-Z0-9_-]+$/.test(found.files[0].id)) throw new OwnershipUnavailable();
      workbook = found.files[0].id;
    }
    return `https://sheets.googleapis.com/v4/spreadsheets/${workbook}/values/`;
  }
  return {
    async read() {
      const data = await call((await base()) + encodeURIComponent(`'${SHEET}'!A1:E50002`));
      if (!Array.isArray(data.values) || data.values.length > 50001 || JSON.stringify(data.values[0]) !== JSON.stringify(HEADER)) throw new OwnershipUnavailable();
      return data.values.slice(1).map((cells: unknown[]) => {
        if (!Array.isArray(cells) || cells.length !== 5 || cells[0] !== "v1" || !HASH.test(String(cells[1])) || !KINDS.has(String(cells[2])) || !HASH.test(String(cells[3])) || !(cells[4] === "-" || HASH.test(String(cells[4])))) throw new OwnershipUnavailable();
        return { owner: cells[1], kind: cells[2], resource: cells[3], parent: cells[4] } as OwnershipRow;
      });
    },
    async append(rows) {
      if (!rows.length) return;
      const result = await call((await base()) + encodeURIComponent(`'${SHEET}'!A:E`) + ":append?valueInputOption=RAW&insertDataOption=INSERT_ROWS", {
        method: "POST", body: JSON.stringify({ values: rows.map(row => ["v1", row.owner, row.kind, row.resource, row.parent]) }),
      });
      if (result.updates?.updatedRows !== rows.length) throw new OwnershipUnavailable();
    },
  };
}
