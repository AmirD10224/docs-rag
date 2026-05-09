"use client";

import { motion } from "motion/react";
import type { Citation } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

interface CitationListProps {
  citations: Citation[];
  onSelect: (chunk_id: string) => void;
  active: string | null;
}

export function CitationList({ citations, onSelect, active }: CitationListProps) {
  if (citations.length === 0) return null;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="label-caps">Citations</p>
        <Badge tone="mono">{citations.length}</Badge>
      </div>

      <ol className="space-y-3">
        {citations.map((c, idx) => (
          <motion.li
            key={c.chunk_id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.07, duration: 0.4 }}
          >
            <button
              onClick={() => onSelect(c.chunk_id)}
              className={`group w-full text-left p-4 rounded-[var(--radius-md)] transition-all duration-200
                ${
                  active === c.chunk_id
                    ? "bg-[var(--color-accent-soft)] border border-[oklch(58%_0.18_30/0.3)]"
                    : "bg-[var(--color-paper-soft)] border border-[var(--color-ink-line)] hover:border-[var(--color-ink-faint)]"
                }
              `}
            >
              <div className="flex items-baseline gap-3 mb-2">
                <span className="font-display text-[28px] leading-none text-[var(--color-accent)] tabular-nums">
                  {String(idx + 1).padStart(2, "0")}
                </span>
                <code className="font-mono text-[10.5px] text-[var(--color-ink-faint)] tracking-wide">
                  {c.chunk_id}
                </code>
                <span className="ml-auto font-mono text-[10.5px] text-[var(--color-ink-faint)]">
                  p.{c.page}
                </span>
              </div>
              <p className="text-[13.5px] leading-[1.55] text-[var(--color-ink)] line-clamp-3">
                {c.snippet}
              </p>
              <p className="mt-2 font-mono text-[10.5px] text-[var(--color-ink-faint)] group-hover:text-[var(--color-accent)] transition-colors">
                Read full span →
              </p>
            </button>
          </motion.li>
        ))}
      </ol>
    </div>
  );
}
