import type { Metadata } from "next";
import { Geist_Mono, Outfit, Syne } from "next/font/google";

import "./globals.css";

const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin"],
});

const syne = Syne({
  variable: "--font-syne",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "OmniRAG Studio",
  description:
    "Multi-source RAG dashboard for document ingestion and grounded chat.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`dark ${outfit.variable} ${syne.variable} ${geistMono.variable} h-full`}
    >
      <body className="flex min-h-full flex-col font-sans text-zinc-100">
        {children}
      </body>
    </html>
  );
}
