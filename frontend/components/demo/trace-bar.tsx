"use client";

import { motion } from "motion/react";
import { Search, Layers, MessageSquare } from "lucide-react";
import type { QueryTrace } from "@/lib/api";

interface TraceBarProps {
  trace: QueryTrace;
}

export function TraceBar({ trace }: TraceBarProps) {
  const total = Math.max(trace.total_ms, 1);
  const stages = [
    {
      label: "Retrieve",
      ms: trace.retrieval_ms,
      color: "var(--color-violet)",
      icon: Search,
    },
    {
      label: "Rerank",
      ms: trace.rerank_ms,
      color: "var(--color-accent)",
      icon: Layers,
    },
    {
      label: "Synthesize",
      ms: trace.synthesis_ms,
      color: "var(--color-forest)",
      icon: MessageSquare,
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.2 }}
      className="space-y-4"
    >
      <div className="flex items-baseline justify-between">
        <p className="label-caps">Trace</p>
        <div className="flex items-baseline gap-4">
          <span className="font-mono text-[11px] text-[var(--color-ink-faint)]">
            <span className="text-[var(--color-ink)] font-semibold">
              {trace.total_ms}
            </span>
            ms total
          </span>
          <span className="font-mono text-[11px] text-[var(--color-ink-faint)]">
            <span className="text-[var(--color-ink)] font-semibold">
              ${trace.cost_usd.toFixed(4)}
            </span>
          </span>
        </div>
      </div>

      {/* Stacked latency ribbon */}
      <div className="flex h-2 rounded-full overflow-hidden">
        {stages.map((s, i) => {
          const pct = (s.ms / total) * 100;
          return (
            <motion.div
              key={s.label}
              initial={{ width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{
                duration: 0.7,
                delay: 0.25 + i * 0.1,
                ease: [0.165, 0.84, 0.44, 1],
              }}
              className="h-full"
              style={{ background: s.color }}
            />
          );
        })}
      </div>

      {/* Per-stage detail row, editorial labels */}
      <div className="grid grid-cols-3 gap-px bg-[var(--color-ink-line)] rounded-[var(--radius-sm)] overflow-hidden">
        {stages.map((s) => {
          const Icon = s.icon;
          return (
            <div
              key={s.label}
              className="bg-[var(--color-paper-soft)] px-4 py-3"
            >
              <div className="flex items-center gap-1.5">
                <Icon className="size-3" style={{ color: s.color }} />
                <p className="label-caps !text-[10px]">{s.label}</p>
              </div>
              <p className="mt-1.5 font-display tabular-nums text-[26px] leading-none text-[var(--color-ink)]">
                {s.ms}
                <span className="font-display-italic text-[14px] text-[var(--color-ink-faint)] ml-0.5">
                  ms
                </span>
              </p>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}
