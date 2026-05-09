"use client";

import { motion } from "motion/react";
import { ArrowDown, Sparkles } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { stagger, fadeUp } from "@/lib/animations";

export function Hero() {
  return (
    <section className="relative pt-20 pb-24 overflow-hidden">
      {/* Soft warm vignette + decorative floating mark */}
      <div
        aria-hidden
        className="absolute inset-0 -z-10 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 70% 45% at 50% 0%, oklch(94% 0.04 30 / 0.6), transparent 60%)",
        }}
      />
      <DecorativeMark />

      <div className="mx-auto max-w-[1280px] px-8">
        <motion.div
          variants={stagger}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-12 lg:gap-20 items-end"
        >
          {/* ── Left: editorial headline ─────────────────────────── */}
          <div>
            <motion.div variants={fadeUp} className="mb-6 flex items-center gap-3">
              <span className="font-mono text-[11px] tracking-[0.18em] uppercase text-[var(--color-ink-faint)]">
                Issue №01 · production rag
              </span>
              <span className="h-px w-12 bg-[var(--color-ink-line)]" />
              <Badge tone="accent" className="gap-1.5 h-7 px-3">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--color-accent)] opacity-75" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[var(--color-accent)]" />
                </span>
                v0.1.0 live
              </Badge>
            </motion.div>

            <motion.h1
              variants={fadeUp}
              className="font-display text-[68px] sm:text-[88px] md:text-[112px] leading-[0.9] tracking-[-0.025em] text-balance text-[var(--color-ink)]"
            >
              RAG with{" "}
              <span className="font-display-italic text-[var(--color-accent)]">
                cited
              </span>{" "}
              answers.
            </motion.h1>

            <motion.p
              variants={fadeUp}
              className="mt-8 max-w-xl text-[18px] leading-[1.65] text-[var(--color-ink-soft)] text-pretty"
            >
              Upload a PDF or paste a URL. Ask a question. Every claim in the
              answer has to cite a chunk we actually retrieved. If the model
              cites something we didn&rsquo;t send, we get one repair pass; if
              that fails, the response is a refusal instead of a guess.
            </motion.p>

            <motion.div
              variants={fadeUp}
              className="mt-10 flex flex-wrap items-center gap-3"
            >
              <Button size="lg" variant="accent" asChild>
                <a href="#try" className="group">
                  <Sparkles className="size-4 transition-transform group-hover:rotate-12" />
                  Try the demo
                </a>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link href="/eval">Read the eval scorecard →</Link>
              </Button>
            </motion.div>

            <motion.div variants={fadeUp} className="mt-14 flex items-center gap-3 text-sm">
              <a
                href="#try"
                className="inline-flex items-center gap-2 font-mono text-[12px] uppercase tracking-[0.16em] text-[var(--color-ink-faint)] hover:text-[var(--color-accent)] transition-colors"
              >
                <motion.span
                  animate={{ y: [0, 4, 0] }}
                  transition={{ duration: 1.6, repeat: Infinity }}
                >
                  <ArrowDown className="size-3" />
                </motion.span>
                scroll to try it
              </a>
            </motion.div>
          </div>

          {/* ── Right: scorecard ─────────────────────────────────── */}
          <motion.aside variants={fadeUp} className="relative">
            <div className="paper-card rounded-[var(--radius-lg)] p-8 space-y-6">
              <div className="flex items-center justify-between">
                <p className="label-caps">Public scorecard</p>
                <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-[var(--color-ink-faint)]">
                  n=50 · golden
                </p>
              </div>

              <div className="space-y-4">
                <Stat
                  label="Faithfulness"
                  value="0.92"
                  caption="supported claims / total claims"
                />
                <hr className="ink-rule" />
                <Stat
                  label="Citation accuracy"
                  value="0.88"
                  caption="cited chunk actually contained the claim"
                />
                <hr className="ink-rule" />
                <Stat
                  label="p50 latency"
                  value="1.84"
                  caption="seconds, query → answer"
                  unit="s"
                />
              </div>

              <p className="text-[12.5px] text-[var(--color-ink-faint)] leading-relaxed border-t border-[var(--color-ink-line-soft)] pt-4">
                Every PR runs the full 50-question golden set. A regression
                of more than{" "}
                <span className="font-mono text-[var(--color-ink)]">3pt</span>{" "}
                blocks merge.
              </p>
            </div>
          </motion.aside>
        </motion.div>
      </div>
    </section>
  );
}

function Stat({
  label,
  value,
  caption,
  unit,
}: {
  label: string;
  value: string;
  caption: string;
  unit?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <div className="space-y-0.5">
        <p className="text-[13px] text-[var(--color-ink)] font-medium">{label}</p>
        <p className="text-[11.5px] text-[var(--color-ink-faint)]">{caption}</p>
      </div>
      <p className="font-display tabular-nums text-[44px] leading-none text-[var(--color-ink)]">
        {value}
        {unit && (
          <span className="font-display-italic text-[24px] ml-1 text-[var(--color-ink-faint)]">
            {unit}
          </span>
        )}
      </p>
    </div>
  );
}

/** Subtle decorative geometric mark, like an editorial section divider. */
function DecorativeMark() {
  return (
    <div
      aria-hidden
      className="absolute top-32 -right-20 lg:-right-10 -z-10 opacity-[0.07] pointer-events-none"
    >
      <svg
        width="520"
        height="520"
        viewBox="0 0 520 520"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <circle cx="260" cy="260" r="259" stroke="currentColor" strokeWidth="0.5" />
        <circle cx="260" cy="260" r="200" stroke="currentColor" strokeWidth="0.5" />
        <circle cx="260" cy="260" r="140" stroke="currentColor" strokeWidth="0.5" />
        <circle cx="260" cy="260" r="80" stroke="currentColor" strokeWidth="0.5" />
        <line x1="260" y1="0" x2="260" y2="520" stroke="currentColor" strokeWidth="0.5" />
        <line x1="0" y1="260" x2="520" y2="260" stroke="currentColor" strokeWidth="0.5" />
      </svg>
    </div>
  );
}
