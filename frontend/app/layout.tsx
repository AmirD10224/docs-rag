import type { Metadata, Viewport } from "next";
import { Inter, Instrument_Serif, JetBrains_Mono } from "next/font/google";
import { Toaster } from "sonner";
import { Nav } from "@/components/shared/nav";
import { Footer } from "@/components/shared/footer";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: ["400"],
  style: ["normal", "italic"],
  variable: "--font-instrument-serif",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "DocsRAG, production RAG with citation enforcement",
  description:
    "Cited answers over your documents. Hybrid retrieval, late chunking, strict citation enforcement. Refuses to hallucinate.",
  authors: [{ name: "Amir Dhibi" }],
  openGraph: {
    title: "DocsRAG, production RAG with citation enforcement",
    description:
      "Cited answers. Zero hallucination. Eval-gated CI. Built by Amir Dhibi.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#f5f1eb",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${instrumentSerif.variable} ${jetbrainsMono.variable}`}
    >
      <body className="paper-grain relative min-h-screen">
        <Nav />
        <main className="relative z-[2]">{children}</main>
        <Footer />
        <Toaster
          theme="light"
          position="bottom-right"
          toastOptions={{
            classNames: {
              toast:
                "!bg-[var(--color-card)] !border-[var(--color-ink-line)] !text-[var(--color-ink)]",
            },
          }}
        />
      </body>
    </html>
  );
}
