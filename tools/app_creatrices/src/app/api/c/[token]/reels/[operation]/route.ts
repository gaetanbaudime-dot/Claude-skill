import { creatriceParJeton } from "@/lib/config";
import { forwardReelsRequest } from "@gm/reels/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 300;

async function handle(request: Request, { params }: { params: { token: string; operation: string } }) {
  const user = creatriceParJeton(params.token);
  if (!user) return Response.json({ error: "Lien invalide." }, { status: 404, headers: { "Cache-Control": "private, no-store" } });
  return forwardReelsRequest(request, params.operation);
}

export const GET = handle;
export const POST = handle;
