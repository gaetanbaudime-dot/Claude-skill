import { notFound } from "next/navigation";
import { creatriceParJeton } from "@/lib/config";
import App from "@/components/App";

export const dynamic = "force-dynamic";

export default function Espace({ params }: { params: { token: string } }) {
  const c = creatriceParJeton(params.token);
  if (!c) notFound();
  return <App prenom={c.prenom} jeton={c.jeton} mym={Boolean(c.feed || c.scripts)} />;
}
