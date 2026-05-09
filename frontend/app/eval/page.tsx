import { EvalDashboard } from "@/components/eval/dashboard";
import { Badge } from "@/components/ui/badge";

export default function EvalPage() {
  return (
    <section className="mx-auto max-w-[1280px] px-8 pt-16 pb-24">
      <header className="mb-14 max-w-3xl">
        <div className="flex items-center gap-4 mb-6">
          <span className="font-mono text-[11px] tracking-[0.18em] uppercase text-[var(--color-ink-faint)]">
            §04. Public scorecard
          </span>
          <span className="h-px w-16 bg-[var(--color-ink)]" />
          <Badge tone="forest" className="ml-auto">
            ✓ live
          </Badge>
        </div>

        <h1 className="font-display text-[64px] sm:text-[88px] leading-[0.95] tracking-[-0.025em] text-[var(--color-ink)] text-balance">
          Latest <span className="font-display-italic text-[var(--color-accent)]">eval</span> run.
        </h1>

        <p className="mt-6 text-[16.5px] leading-relaxed text-[var(--color-ink-soft)] max-w-2xl text-pretty">
          Faithfulness, citation accuracy, retrieval precision, and judge
          calibration on the 50-question golden set. Every PR runs this and
          gets blocked on regression. The metrics that ship here are exactly
          what gets posted as a PR comment.
        </p>
      </header>

      <EvalDashboard />
    </section>
  );
}
