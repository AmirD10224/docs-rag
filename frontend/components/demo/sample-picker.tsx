"use client";

import { motion } from "motion/react";
import { FileText, Brain, Scale, Check } from "lucide-react";
import { SAMPLES, type SampleDoc } from "@/lib/samples";
import { cn } from "@/lib/cn";

const ICONS = {
  apple_10k_fy2024: FileText,
  attention_is_all_you_need: Brain,
  gitlab_msa: Scale,
};

const ACCENTS: Record<
  SampleDoc["accent"],
  { dot: string; label: string }
> = {
  cyan: { dot: "var(--color-violet)", label: "Filing" },
  violet: { dot: "var(--color-accent)", label: "Paper" },
  amber: { dot: "var(--color-forest)", label: "Contract" },
};

interface SamplePickerProps {
  active: string | null;
  onSelect: (doc: SampleDoc) => void;
}

export function SamplePicker({ active, onSelect }: SamplePickerProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {SAMPLES.map((doc, idx) => {
        const Icon = ICONS[doc.id as keyof typeof ICONS];
        const accent = ACCENTS[doc.accent];
        const isActive = active === doc.id;

        return (
          <motion.button
            key={doc.id}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 * idx, duration: 0.5 }}
            onClick={() => onSelect(doc)}
            className={cn(
              "group relative text-left p-5 rounded-[var(--radius-lg)]",
              "lift",
              isActive
                ? "paper-card border-[var(--color-ink)]"
                : "paper-card",
            )}
          >
            <div className="flex items-start justify-between gap-3 mb-4">
              <div className="flex items-center gap-2">
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ background: accent.dot }}
                />
                <span className="label-caps">{accent.label}</span>
              </div>
              <span className="font-mono text-[10.5px] text-[var(--color-ink-faint)] tracking-wide">
                {doc.pages}pp
              </span>
            </div>

            <Icon className="size-5 text-[var(--color-ink-soft)] mb-3" />

            <h3 className="font-display text-[22px] leading-[1.15] text-[var(--color-ink)] tracking-tight">
              {doc.title}
            </h3>
            <p className="mt-1.5 text-[12.5px] text-[var(--color-ink-faint)] font-mono tracking-wide">
              {doc.source}
            </p>

            {isActive && (
              <motion.span
                layoutId="sample-active"
                className="absolute top-3 right-3 flex h-6 w-6 items-center justify-center rounded-full bg-[var(--color-ink)]"
              >
                <Check className="size-3.5 text-[var(--color-paper-soft)]" />
              </motion.span>
            )}
          </motion.button>
        );
      })}
    </div>
  );
}
