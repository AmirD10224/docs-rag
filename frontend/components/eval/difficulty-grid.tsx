"use client";

import { motion } from "motion/react";
import { Card, CardBody } from "@/components/ui/card";

interface DifficultyGridProps {
  data: Record<string, { mean_faithfulness: number; n: number }> | undefined;
}

const ORDER = ["easy", "medium", "hard"] as const;
const COLORS: Record<(typeof ORDER)[number], string> = {
  easy: "var(--color-forest)",
  medium: "var(--color-amber)",
  hard: "var(--color-accent)",
};

export function DifficultyGrid({ data }: DifficultyGridProps) {
  return (
    <Card lift>
      <CardBody>
        <div className="flex items-baseline justify-between mb-6">
          <p className="label-caps">By difficulty</p>
          <span className="font-mono text-[11px] text-[var(--color-ink-faint)]">
            mean faithfulness
          </span>
        </div>

        {!data || Object.keys(data).length === 0 ? (
          <p className="text-sm text-[var(--color-ink-faint)] italic">
            No per-difficulty breakdown in the latest run.
          </p>
        ) : (
          <div className="space-y-6">
            {ORDER.filter((k) => k in data).map((key, idx) => {
              const v = data[key]!;
              const pct = v.mean_faithfulness * 100;
              return (
                <div key={key}>
                  <div className="flex items-baseline justify-between mb-2">
                    <span className="font-display text-[24px] leading-none capitalize tracking-tight">
                      {key}
                    </span>
                    <div className="flex items-baseline gap-2">
                      <span
                        className="font-display tabular-nums text-[28px] leading-none"
                        style={{ color: COLORS[key] }}
                      >
                        {pct.toFixed(0)}
                        <span className="font-display-italic text-[16px] text-[var(--color-ink-faint)] ml-0.5">
                          %
                        </span>
                      </span>
                      <span className="font-mono text-[10.5px] text-[var(--color-ink-faint)]">
                        n={v.n}
                      </span>
                    </div>
                  </div>
                  <div className="h-1.5 rounded-full bg-[var(--color-paper-deep)] overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{
                        duration: 1,
                        delay: 0.1 + idx * 0.1,
                        ease: [0.165, 0.84, 0.44, 1],
                      }}
                      className="h-full rounded-full"
                      style={{ background: COLORS[key] }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
