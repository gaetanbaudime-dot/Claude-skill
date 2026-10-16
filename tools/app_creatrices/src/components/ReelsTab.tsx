"use client";

import { useEffect, useState } from "react";

// Keep the module on its own origin. Never pass the personal app token here.
const DUPLICATEUR_URL = "https://duplicateur-de-reels.vercel.app/";

export default function ReelsTab({ actif }: { actif: boolean }) {
  const [ouvert, setOuvert] = useState(false);
  const [charge, setCharge] = useState(false);

  useEffect(() => { if (actif) setOuvert(true); }, [actif]);

  // Load on the first visit, then keep the same iframe mounted across tabs.
  // Unmounting it would interrupt uploads, polling and in-flight finishes.
  return (
    <section hidden={!actif} aria-label="Duplicateur de Reels" className="mt-2">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="titre-argent text-lg font-bold">IA G&M · Reels</h2>
        <a href={DUPLICATEUR_URL} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer"
           className="text-xs text-argent2 underline underline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white">
          Plein écran<span className="sr-only"> — ouvre un nouvel onglet</span>
        </a>
      </div>
      {!charge && <p role="status" className="mb-3 text-sm text-argent2">Chargement du montage…</p>}
      {ouvert && <iframe
        src={DUPLICATEUR_URL}
        title="Montage vidéo IA G&M"
        allow="fullscreen; web-share"
        allowFullScreen
        referrerPolicy="no-referrer"
        onLoad={() => setCharge(true)}
        className="block w-full rounded-2xl border-0 bg-[#F3F5F8]"
        style={{ height: "calc(100dvh - 210px)", minHeight: 640 }}
      />}
      <p className="mt-3 text-xs leading-relaxed text-argent2">Tu peux changer d’onglet dans cette app : ton montage reste ouvert. Garde cette page ouverte jusqu’à la fin.</p>
    </section>
  );
}
