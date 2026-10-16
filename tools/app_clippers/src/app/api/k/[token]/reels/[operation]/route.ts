import { clipperParJeton } from "@/lib/clippers";
import { jetonGoogle } from "@/lib/google";
import { forwardReelsRequest, createSheetsOwnershipStore } from "@gm/reels/server";

const ownership = createSheetsOwnershipStore("clippers", jetonGoogle, { workbookId: process.env.REELS_OWNERSHIP_SPREADSHEET_ID });

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 300;

async function handle(request: Request, { params }: { params: { token: string; operation: string } }) {
  const user = await clipperParJeton(params.token).catch(() => null);
  if (!user) return Response.json({ error: "Lien invalide." }, { status: 404, headers: { "Cache-Control": "private, no-store" } });
  return forwardReelsRequest(request, params.operation, { app: "clippers", id: user.cle }, ownership);
}

export const GET = handle;
export const POST = handle;
