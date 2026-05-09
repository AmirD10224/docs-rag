"use client";

import { forwardRef, type HTMLAttributes } from "react";
import { tv, type VariantProps } from "tailwind-variants";

const badge = tv({
  base: [
    "inline-flex items-center gap-1.5",
    "h-6 px-2.5 rounded-full",
    "text-[11px] font-medium tracking-tight",
    "transition-colors duration-200",
  ],
  variants: {
    tone: {
      neutral:
        "bg-[var(--color-paper-deep)] text-[var(--color-ink-soft)] border border-[var(--color-ink-line)]",
      ink: "bg-[var(--color-ink)] text-[var(--color-paper-soft)]",
      accent:
        "bg-[var(--color-accent-soft)] text-[var(--color-accent-deep)] border border-[oklch(58%_0.18_30/0.15)]",
      forest:
        "bg-[var(--color-forest-soft)] text-[var(--color-forest)] border border-[oklch(45%_0.13_150/0.15)]",
      violet:
        "bg-[var(--color-violet-soft)] text-[var(--color-violet)] border border-[oklch(45%_0.16_290/0.15)]",
      mono:
        "bg-[var(--color-paper-deep)] text-[var(--color-ink-soft)] font-mono text-[10.5px] tracking-wide border border-[var(--color-ink-line)]",
      outline:
        "bg-transparent text-[var(--color-ink-soft)] border border-[var(--color-ink-line)]",
    },
  },
  defaultVariants: { tone: "neutral" },
});

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badge> {}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, tone, ...props }, ref) => (
    <span ref={ref} className={badge({ tone, className })} {...props} />
  ),
);
Badge.displayName = "Badge";
