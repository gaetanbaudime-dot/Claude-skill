"use client";
import { useEffect, useState } from "react";
import { modeApp, signaler } from "@/lib/signal";

/** « Mets l'app sur ton écran d'accueil », affiché tant que l'app tourne dans un navigateur (jamais une fois installée).
 *  Trois cas, détectés sur le téléphone :
 *  - navigateur intégré (WhatsApp, Instagram, Facebook, Messenger, Telegram, TikTok…) : aucun ne sait installer une app,
 *    on dit d'abord comment ouvrir le lien dans Safari ou Chrome ;
 *  - iPhone / iPad (Safari) : Apple n'offre aucune invite, on montre les trois gestes (Partager → Sur l'écran d'accueil → Ajouter) ;
 *  - Android (Chrome, Samsung Internet) : si le navigateur propose l'installation (`beforeinstallprompt`), un seul bouton
 *    ouvre la fenêtre d'installation ; sinon les gestes du menu.
 *  « Plus tard » cache la carte pour la session ; « C'est fait » pour 30 jours ; l'app installée (`appinstalled` ou mode
 *  standalone) ne la montre plus jamais. */
type Cas = "inapp" | "ios" | "android" | "autre";
type InvitePrompt = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: "accepted" | "dismissed" }> };

function detecter(): { cas: Cas; samsung: boolean } {
  const ua = navigator.userAgent || "";
  const ios = /iPhone|iPad|iPod/i.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const inapp = /WhatsApp|Instagram|FBAN|FBAV|FB_IAB|Messenger|Telegram|TikTok|Snapchat|Line\//i.test(ua);
  const samsung = /SamsungBrowser/i.test(ua);
  if (inapp) return { cas: "inapp", samsung };
  if (ios) return { cas: "ios", samsung };
  if (/Android/i.test(ua)) return { cas: "android", samsung };
  return { cas: "autre", samsung };
}

const CLE_FAIT = "gm-clipper-installe", CLE_TARD = "gm-clipper-plus-tard";

function Geste({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2.5">
      <span className="shrink-0 w-6 h-6 rounded-full text-[12px] font-bold flex items-center justify-center" style={{ background: "rgba(122,167,255,0.18)" }}>{n}</span>
      <span className="text-[13px] leading-snug pt-0.5">{children}</span>
    </li>
  );
}
const Partager = () => <svg className="inline -mt-0.5 mx-0.5" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12M8 7l4-4 4 4" /><path d="M5 11v8a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-8" /></svg>;
const Plus = () => <svg className="inline -mt-0.5 mx-0.5" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="3" y="3" width="18" height="18" rx="5" /><path d="M12 8v8M8 12h8" /></svg>;
const Points = () => <span className="inline-block font-black mx-0.5">⋮</span>;

export default function Installer({ jeton }: { jeton: string }) {
  const [visible, setVisible] = useState(false);
  const [cas, setCas] = useState<Cas>("autre");
  const [samsung, setSamsung] = useState(false);
  const [invite, setInvite] = useState<InvitePrompt | null>(null);

  useEffect(() => {
    if (modeApp() === "app") return;
    try {
      const fait = Number(localStorage.getItem(CLE_FAIT) || 0);
      if (fait && Date.now() - fait < 30 * 24 * 3600 * 1000) return;
      if (sessionStorage.getItem(CLE_TARD)) return;
    } catch { /* navigation privée : on affiche */ }
    const d = detecter();
    if (d.cas === "autre") return;
    setCas(d.cas); setSamsung(d.samsung); setVisible(true);
    signaler(jeton, "install:affiche");
    const capter = (e: Event) => { e.preventDefault(); setInvite(e as InvitePrompt); };
    const installe = () => { setVisible(false); try { localStorage.setItem(CLE_FAIT, String(Date.now())); } catch { /* rien */ } signaler(jeton, "install:ok"); };
    window.addEventListener("beforeinstallprompt", capter);
    window.addEventListener("appinstalled", installe);
    return () => { window.removeEventListener("beforeinstallprompt", capter); window.removeEventListener("appinstalled", installe); };
  }, [jeton]);

  if (!visible) return null;
  const plusTard = () => { setVisible(false); try { sessionStorage.setItem(CLE_TARD, "1"); } catch { /* rien */ } signaler(jeton, "install:plus_tard"); };
  const fait = () => { setVisible(false); try { localStorage.setItem(CLE_FAIT, String(Date.now())); } catch { /* rien */ } signaler(jeton, "install:fait"); };
  const installer = async () => {
    if (!invite) return;
    signaler(jeton, "install:prompt");
    try {
      await invite.prompt();
      const r = await invite.userChoice;
      signaler(jeton, r.outcome === "accepted" ? "install:accepte" : "install:refuse");
      if (r.outcome === "accepted") fait();
    } catch { /* le navigateur a refusé l'invite : les gestes du menu restent affichés */ }
    setInvite(null);
  };

  return (
    <div className="carte apparait relative p-4 mb-4" style={{ border: "1px solid rgba(122,167,255,0.35)" }}>
      <div className="flex items-start gap-3">
        <img src="/icones/icone-192.png" alt="" width={44} height={44} className="rounded-xl shrink-0" style={{ boxShadow: "0 6px 18px rgba(0,0,0,0.4)" }} />
        <div className="flex-1 min-w-0">
          <div className="text-[15px] font-bold leading-tight">Mets {"l'app"} sur ton écran {"d'accueil"}</div>
          <div className="text-[12px] text-argent2 mt-0.5 leading-snug">Comme une vraie app, en 10 secondes. Tu {"l'ouvres"} {"d'un"} doigt, sans chercher le lien.</div>
        </div>
      </div>

      {cas === "inapp" && (
        <ol className="mt-3 space-y-2">
          <Geste n={1}>Ce lien {"s'est"} ouvert dans {"l'application"} qui te {"l'a"} envoyé. Ouvre-le dans ton navigateur : touche <Points /> en haut à droite puis <b>« Ouvrir dans Chrome »</b>, ou sur iPhone {"l'icône"} <b>Safari</b> en bas à droite.</Geste>
          <Geste n={2}>Là, suis les gestes qui {"s'affichent"} pour {"l'ajouter"} à ton écran {"d'accueil"}.</Geste>
        </ol>
      )}
      {cas === "ios" && (
        <ol className="mt-3 space-y-2">
          <Geste n={1}>Touche <b>Partager</b> <Partager /> en bas de Safari.</Geste>
          <Geste n={2}>Descends et touche <b>« Sur {"l'écran d'accueil"} »</b> <Plus />.</Geste>
          <Geste n={3}>Touche <b>Ajouter</b> en haut à droite. {"C'est"} tout.</Geste>
        </ol>
      )}
      {cas === "android" && !invite && (
        <ol className="mt-3 space-y-2">
          {samsung ? (
            <>
              <Geste n={1}>Touche le menu <b>≡</b> en bas de Samsung Internet.</Geste>
              <Geste n={2}>Touche <b>« Ajouter la page à »</b> puis <b>« Écran {"d'accueil"} »</b>, puis <b>Ajouter</b>.</Geste>
            </>
          ) : (
            <>
              <Geste n={1}>Touche <Points /> en haut à droite de Chrome.</Geste>
              <Geste n={2}>Touche <b>« Ajouter à {"l'écran d'accueil"} »</b> (ou <b>« Installer {"l'application"} »</b>), puis <b>Installer</b>.</Geste>
            </>
          )}
        </ol>
      )}
      {cas === "android" && invite && (
        <button onClick={installer} className="mt-3 w-full rounded-2xl py-3 text-[15px] font-bold text-white" style={{ background: "linear-gradient(135deg,#2b6cff,#7aa7ff)" }}>Installer {"l'app"}</button>
      )}

      <div className="flex items-center justify-end gap-2 mt-3">
        <button onClick={plusTard} className="text-[12px] font-semibold text-argent2 px-3 py-2 rounded-xl" style={{ background: "rgba(255,255,255,0.05)" }}>Plus tard</button>
        <button onClick={fait} className="text-[12px] font-bold text-accent px-3 py-2 rounded-xl" style={{ background: "rgba(122,167,255,0.12)" }}>{"C'est"} fait</button>
      </div>
    </div>
  );
}
