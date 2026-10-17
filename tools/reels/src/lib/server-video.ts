export type RemoteVariant = {
  captionPreset?: string;
  id: string;
  index: number;
  name: string;
  url: string;
  downloadUrl: string;
  size: number;
  mirror: boolean;
  orientation: "vertical" | "horizontal";
};
