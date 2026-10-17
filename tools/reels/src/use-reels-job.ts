"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createNativeClient, type NativePhase } from "./lib/opus-native";
import type { RemoteVariant } from "./lib/server-video";
import { elapsedSince } from "./lib/processing-status";

export type Stage = "idle" | "ready" | "processing" | "error" | "done";
const MAX_BYTES = 250 * 1024 * 1024;

// Owned by App, not by its active tab. Hiding Reels never ends this hook/job.
export function useReelsJob({ apiBase }: { apiBase: string }) {
  const [stage, setStage] = useState<Stage>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [phase, setPhase] = useState<NativePhase>("checking");
  const [resuming, setResuming] = useState<boolean | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [variants, setVariants] = useState<RemoteVariant[]>([]);
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const started = useRef(0);
  const mounted = useRef(true);
  const previewRef = useRef<string | null>(null);
  const account = useRef(apiBase);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; controller.current?.abort(); if (previewRef.current) URL.revokeObjectURL(previewRef.current); };
  }, []);
  useEffect(() => {
    if (account.current === apiBase) return;
    account.current = apiBase;
    controller.current?.abort(); controller.current = null;
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    previewRef.current = null;
    setFile(null); setPreview(null); setDuration(null); setVariants([]); setStage("idle");
    setError(null); setElapsed(0); setPhase("checking"); setResuming(null);
  }, [apiBase]);
  useEffect(() => {
    if (stage !== "processing") return;
    const timer = window.setInterval(() => setElapsed(elapsedSince(started.current, performance.now())), 1000);
    return () => window.clearInterval(timer);
  }, [stage]);

  const choose = useCallback((next?: File) => {
    if (!next || controller.current) return;
    if (!/\.(mp4|mov)$/i.test(next.name) || next.size <= 0 || next.size > MAX_BYTES) {
      setError("Choisis une vidéo MP4 ou MOV de 250 Mo maximum."); return;
    }
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    previewRef.current = URL.createObjectURL(next);
    setFile(next); setPreview(previewRef.current); setDuration(null);
    setStage("ready"); setError(null); setVariants([]); setElapsed(0); setResuming(null); setPhase("checking");
  }, []);
  const metadata = useCallback((seconds: number) => {
    if (controller.current) return;
    if (!Number.isFinite(seconds) || seconds <= 0) { setDuration(null); setError("La durée de cette vidéo ne peut pas être lue. Choisis un autre fichier."); return; }
    setDuration(seconds);
    setError(seconds > 180 ? "Cette vidéo dépasse 3 minutes. Choisis un rush plus court." : null);
  }, []);
  const reset = useCallback(() => {
    if (controller.current) return;
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    previewRef.current = null;
    setFile(null); setPreview(null); setDuration(null); setStage("idle"); setError(null); setVariants([]); setElapsed(0);
  }, []);
  const run = useCallback(async () => {
    if (!file || duration === null || duration > 180 || controller.current) return;
    const operation = new AbortController(); controller.current = operation;
    const current = () => mounted.current && controller.current === operation;
    started.current = performance.now(); setElapsed(0); setPhase("checking"); setResuming(null); setError(null); setStage("processing");
    // Keep already verified downloads visible while retrying this same file.
    try {
      window.localStorage.setItem("gm:reels-storage-check", "1"); window.localStorage.removeItem("gm:reels-storage-check");
      const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(apiBase));
      operation.signal.throwIfAborted();
      const storageScope = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
      const client = createNativeClient({ apiBase, storageScope });
      const result = await client.generateOpusVariations(file, {
        signal: operation.signal,
        onPhase: value => { if (current()) setPhase(value); },
        onResume: value => { if (current()) setResuming(value); },
        onVariant: value => { if (current()) setVariants(previous => [...previous.filter(v => v.index !== value.index), value].sort((a,b) => a.index-b.index)); },
      });
      if (current()) { setVariants(result.variants); setStage("done"); }
    } catch (failure) {
      if (current()) {
        setError(operation.signal.aborted ? "Le suivi est arrêté. Les fichiers déjà prêts sont conservés. Reprends avec ce même rush."
          : failure instanceof Error ? failure.message : "Le montage n’a pas pu se terminer. Réessaie avec ce même rush.");
        setStage("error");
      }
    } finally {
      if (current()) { setElapsed(elapsedSince(started.current, performance.now())); controller.current = null; }
    }
  }, [apiBase, file, duration]);
  return { stage, file, preview, duration, phase, resuming, elapsed, variants, error, choose, metadata, reset, run,
    stop: () => controller.current?.abort() };
}
export type ReelsJob = ReturnType<typeof useReelsJob>;
