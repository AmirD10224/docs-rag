"use client";

import { type HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: "paper" | "soft" | "outline";
  lift?: boolean;
}

/**
 * Editorial paper card. No glass, soft warm background with a thin
 * ink line and a delicate shadow. Optional `lift` for hover elevation.
 */
export function Card({
  className,
  variant = "paper",
  lift = false,
  children,
  ...props
}: CardProps) {
  return (
    <div
      className={cn(
        "relative rounded-[var(--radius-lg)]",
        variant === "paper" && "paper-card",
        variant === "soft" && "paper-card-soft",
        variant === "outline" && "border border-[var(--color-ink-line)] bg-transparent",
        lift && "lift cursor-default",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "px-6 pt-5 pb-4 border-b border-[var(--color-ink-line-soft)]",
        className,
      )}
      {...props}
    />
  );
}

export function CardBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-6", className)} {...props} />;
}

export function CardFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "px-6 py-4 border-t border-[var(--color-ink-line-soft)] flex items-center gap-2",
        className,
      )}
      {...props}
    />
  );
}
