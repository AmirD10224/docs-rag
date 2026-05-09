"use client";

import { Card, CardBody } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { EvalReport } from "@/lib/api";

interface RunMetadataProps {
  report: EvalReport;
}

export function RunMetadata({ report }: RunMetadataProps) {
  const created = new Date(report.created_at).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });

  const items: { label: string; value: React.ReactNode }[] = [
    { label: "Run", value: created },
    { label: "Git", value: <code className="font-mono">{report.git_sha}</code> },
    {
      label: "Synthesis model",
      value: <code className="font-mono">{report.synthesis_model || "-"}</code>,
    },
    {
      label: "Prompt version",
      value: <code className="font-mono">{report.prompt_version || "-"}</code>,
    },
    { label: "Duration", value: `${report.duration_seconds.toFixed(1)}s` },
    { label: "Cost", value: `$${report.cost_usd.toFixed(4)}` },
  ];

  return (
    <Card lift>
      <CardBody>
        <div className="flex items-baseline justify-between mb-6">
          <p className="label-caps">Run metadata</p>
          {report.mock_providers ? (
            <Badge tone="accent">mock</Badge>
          ) : (
            <Badge tone="forest">live</Badge>
          )}
        </div>

        <dl className="grid grid-cols-2 gap-x-6 gap-y-5">
          {items.map((it) => (
            <div key={it.label} className="space-y-1">
              <dt className="label-caps">{it.label}</dt>
              <dd className="text-[13.5px] text-[var(--color-ink)]">{it.value}</dd>
            </div>
          ))}
        </dl>
      </CardBody>
    </Card>
  );
}
