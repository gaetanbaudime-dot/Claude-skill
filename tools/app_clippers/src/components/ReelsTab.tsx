"use client";
import ReelsPanel from "@gm/reels";
import type { ReelsJob } from "@gm/reels/use-reels-job";

export default function ReelsTab({ actif, job }: { actif: boolean; job: ReelsJob }) {
  return <ReelsPanel active={actif} job={job} />;
}
