"use client";

import { motion, useSpring, useTransform } from "motion/react";
import { useEffect } from "react";
import { Card, CardBody } from "@/components/ui/card";
import { cn } from "@/lib/cn";

interface ScoreCardProps {
  label: string;
  value: number;
  format?: "percent" | "number" | "kappa";
  delta?: number;
  size?: "sm" | "md" | "lg";
  accent?: "accent" | "violet" | "forest" | "amber";
}

const COLOR: Record<NonNullable<ScoreCardProps["accent"]>, string> = {
  accent: "var(--color-accent)",
  violet: "var(--color-violet)",
  forest: "var(--color-forest)",
  amber: "var(--color-amber)",
};

export function ScoreCard({
  label,
  value,
  format = "percent",
  delta,
  size = "md",
  accent = "accent",
}: ScoreCardProps) {
  const display = useSpring(0, { stiffness: 70, damping: 20 });
  const formatted = useTransform(display, (v) => formatValue(v, format));

  useEffect(() => {
    display.set(value);
  }, [display, value]);

  const fontSize = {
    sm: "text-[56px]",
    md: "text-[88px]",
    lg: "text-[140px]",
  }[size];

  return (
    <Card lift>
      <CardBody className="h-full flex flex-col justify-between">
        <p className="label-caps">{label}</p>
        <motion.span
          className={cn(
            "font-display tabular-nums leading-none mt-4 block",
            fontSize,
          )}
          style={{ color: COLOR[accent] }}
        >
          {formatted}
        </motion.span>
        {delta !== undefined && (
          <p
            className={cn(
              "mt-3 font-mono text-[11px]",
              delta >= 0 ? "text-[var(--color-forest)]" : "text-[var(--color-accent)]",
            )}
          >
            {delta >= 0 ? "↑" : "↓"} {Math.abs(delta * 100).toFixed(2)}pt vs prev
          </p>
        )}
      </CardBody>
    </Card>
  );
}

function formatValue(v: number, format: ScoreCardProps["format"]) {
  if (format === "percent") return `${(v * 100).toFixed(1)}%`;
  if (format === "kappa") return v.toFixed(2);
  return Math.round(v).toString();
}
