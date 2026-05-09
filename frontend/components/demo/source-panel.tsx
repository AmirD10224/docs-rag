"use client";

import { motion, AnimatePresence } from "motion/react";
import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { fetchCitation, type CitationLookup } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

interface SourcePanelProps {
  chunk_id: string | null;
  onClose: () => void;
}

export function SourcePanel({ chunk_id, onClose }: SourcePanelProps) {
  const [data, setData] = useState<CitationLookup | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!chunk_id) {
      setData(null);
      return;
    }
    setLoading(true);
    fetchCitation(chunk_id)
      .then(setData)
      .finally(() => setLoading(false));
  }, [chunk_id]);

  return (
    <AnimatePresence>
      {chunk_id && (
        <>
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            onClick={onClose}
            className="fixed inset-0 z-30 bg-[var(--color-ink)]/10 backdrop-blur-[2px]"
          />
          <motion.aside
            key="panel"
            initial={{ x: "100%", opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: "100%", opacity: 0 }}
            transition={{ duration: 0.45, ease: [0.19, 1, 0.22, 1] }}
            className="paper-card fixed top-6 right-6 bottom-6 w-[420px] z-40 rounded-[var(--radius-lg)] overflow-hidden flex flex-col"
            style={{
              boxShadow:
                "0 24px 60px -20px oklch(20% 0.015 264 / 0.25)",
            }}
          >
            <header className="flex items-start justify-between p-6 pb-4 border-b border-[var(--color-ink-line-soft)]">
              <div>
                <p className="label-caps">Source span</p>
                <code className="mt-1 inline-block font-mono text-[11.5px] text-[var(--color-ink-soft)]">
                  {chunk_id}
                </code>
              </div>
              <button
                onClick={onClose}
                className="flex h-8 w-8 items-center justify-center rounded-full hover:bg-[var(--color-paper-deep)] transition-colors"
                aria-label="Close source panel"
              >
                <X className="size-3.5" />
              </button>
            </header>

            <div className="flex-1 overflow-y-auto no-scrollbar p-6">
              {loading && (
                <p className="text-sm text-[var(--color-ink-faint)] italic">Loading…</p>
              )}
              {data && (
                <div className="space-y-5">
                  <div className="flex flex-wrap gap-1.5">
                    <Badge tone="mono">page {data.span.page}</Badge>
                    <Badge tone="mono">
                      {data.span.char_end - data.span.char_start} chars
                    </Badge>
                  </div>

                  {data.section_path.length > 0 && (
                    <div>
                      <p className="label-caps mb-1.5">Section</p>
                      <p className="font-mono text-[12px] text-[var(--color-ink-soft)] leading-relaxed">
                        {data.section_path.join("  ›  ")}
                      </p>
                    </div>
                  )}

                  <div>
                    <p className="label-caps mb-2">Excerpt</p>
                    <p className="text-[15px] leading-[1.7] text-[var(--color-ink)] dropcap">
                      {data.text}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
