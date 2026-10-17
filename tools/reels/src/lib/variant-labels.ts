// Public names are independent of the rendering provider and of old checkpoints.
export const VARIANT_LABELS = [
  "Variante 1 + Hook", "Variante 2 Verticale", "Variante 3 Bleue",
  "Variante 4 + Hook", "Variante 5 Classique", "Variante 6 Mouvement",
] as const;

export function variantLabel(index: number): string {
  return VARIANT_LABELS[index] || `Variante ${index + 1}`;
}

export function variantFileName(index: number): string {
  return `GM-${variantLabel(index).replace(/ \+ /g, "-").replace(/ /g, "-")}.mp4`;
}
