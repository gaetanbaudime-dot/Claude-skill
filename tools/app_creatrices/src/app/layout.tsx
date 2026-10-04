import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "G&M",
  description: "Ton espace créatrice G&M : Drive, Reels, statistiques.",
  manifest: "/manifest.webmanifest",
  applicationName: "G&M",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "G&M", startupImage: ["/icones/splash-1170x2532.png"] },
  icons: { icon: [{ url: "/favicon.ico" }, { url: "/icones/icone-192.png", sizes: "192x192", type: "image/png" }], apple: "/apple-touch-icon.png" },
  robots: { index: false, follow: false },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = { themeColor: "#070f1c", width: "device-width", initialScale: 1, maximumScale: 1, viewportFit: "cover" };

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="fond font-sf">{children}</body>
    </html>
  );
}
