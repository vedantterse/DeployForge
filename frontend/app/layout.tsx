import type { Metadata } from "next";
import { Geist, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

/**
 * JetBrains Mono for every identifier the product shows: image refs, commit
 * SHAs, container names, and the two log panes. A deployment platform is read
 * as much as it is used, and those strings have to be unambiguous — a monospace
 * face with distinct zero and one is not decoration here.
 */
const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "DeployForge",
  description:
    "Connect a GitHub repository. DeployForge works out how it should be built, builds it, and runs it behind its own URL.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        {/* Film grain over everything, so large dark areas have a surface.
            Fixed and inert — attached to a scrolling container it would
            repaint on every frame. */}
        <div className="grain" aria-hidden />
        {children}
      </body>
    </html>
  );
}
