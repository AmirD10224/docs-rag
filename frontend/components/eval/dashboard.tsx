"use client";

import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { fetchEvalReport, type EvalReport, type EvalScore } from "@/lib/api";
import { ScoreCard } from "./score-card";
import { DifficultyGrid } from "./difficulty-grid";
import { RunMetadata } from "./run-metadata";
import { Card, CardBody } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function EvalDashboard() {
  const [report, setReport] = useState<EvalReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchEvalReport()
      .then(setReport)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <DashboardSkeleton />;
  if (!report) return <EmptyState />;

  const scoreMap = new Map<string, EvalScore>();
  for (const s of report.scores) scoreMap.set(s.metric, s);
  const faith = scoreMap.get("faithfulness");
  const cite = scoreMap.get("citation_accuracy");
  const prec = scoreMap.get("retrieval_precision");
  const kappa = scoreMap.get("judge_human_kappa");

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{ show: { transition: { staggerChildren: 0.06 } } }}
      className="grid grid-cols-1 md:grid-cols-6 gap-5 auto-rows-[minmax(160px,auto)]"
    >
      {/* Hero score */}
      <motion.div className="md:col-span-3 md:row-span-2" variants={cellVariant}>
        <ScoreCard
          label="Faithfulness"
          value={faith?.value ?? 0}
          format="percent"
          accent="accent"
          size="lg"
        />
      </motion.div>

      <motion.div className="md:col-span-3" variants={cellVariant}>
        <ScoreCard
          label="Citation accuracy"
          value={cite?.value ?? 0}
          format="percent"
          accent="violet"
        />
      </motion.div>

      <motion.div className="md:col-span-3" variants={cellVariant}>
        <ScoreCard
          label="Retrieval precision"
          value={prec?.value ?? 0}
          format="percent"
          accent="forest"
        />
      </motion.div>

      <motion.div className="md:col-span-2" variants={cellVariant}>
        <ScoreCard
          label="Judge × human κ"
          value={kappa?.value ?? 0}
          format="kappa"
          accent="amber"
          size="sm"
        />
      </motion.div>

      <motion.div className="md:col-span-2" variants={cellVariant}>
        <ScoreCard
          label="Golden-set size"
          value={report.golden_set_size}
          format="number"
          accent="violet"
          size="sm"
        />
      </motion.div>

      <motion.div className="md:col-span-2" variants={cellVariant}>
        <Card lift>
          <CardBody className="h-full flex flex-col justify-between">
            <p className="label-caps">Eval gate</p>
            <div className="space-y-2">
              <Badge tone="forest" className="h-7 px-3">
                ✓ passing · −3pt threshold
              </Badge>
              <p className="text-[11.5px] text-[var(--color-ink-faint)] leading-relaxed">
                Merges blocked on regression vs latest{" "}
                <code className="font-mono">main</code>.
              </p>
            </div>
          </CardBody>
        </Card>
      </motion.div>

      <motion.div className="md:col-span-3" variants={cellVariant}>
        <DifficultyGrid data={report.by_difficulty} />
      </motion.div>

      <motion.div className="md:col-span-3" variants={cellVariant}>
        <RunMetadata report={report} />
      </motion.div>
    </motion.div>
  );
}

const cellVariant = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.165, 0.84, 0.44, 1] as const },
  },
};

function DashboardSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-6 gap-5 auto-rows-[160px]">
      {[3, 3, 3, 2, 2, 2, 3, 3].map((cols, i) => (
        <div
          key={i}
          className="bg-[var(--color-paper-deep)] rounded-[var(--radius-lg)] animate-pulse"
          style={{ gridColumn: `span ${cols} / span ${cols}` }}
        />
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <Card>
      <CardBody className="text-center py-16">
        <p className="text-[var(--color-ink-soft)] italic">
          No eval report yet. Run <code className="font-mono">make eval</code> to
          generate one.
        </p>
      </CardBody>
    </Card>
  );
}
