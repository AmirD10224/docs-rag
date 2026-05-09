"use client";

import { Slot } from "@radix-ui/react-slot";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { tv, type VariantProps } from "tailwind-variants";

const button = tv({
  base: [
    "relative inline-flex items-center justify-center gap-2",
    "font-medium tracking-tight whitespace-nowrap select-none",
    "transition-all duration-200 ease-[var(--ease-out-quart)]",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-paper)]",
    "disabled:pointer-events-none disabled:opacity-40",
    "[&_svg]:size-4 [&_svg]:shrink-0",
  ],
  variants: {
    variant: {
      primary: [
        "bg-[var(--color-ink)] text-[var(--color-paper-soft)]",
        "hover:bg-[var(--color-accent-deep)]",
        "active:translate-y-[1px]",
      ],
      accent: [
        "bg-[var(--color-accent)] text-[var(--color-paper-soft)]",
        "hover:bg-[var(--color-accent-deep)]",
        "active:translate-y-[1px]",
      ],
      ghost: [
        "bg-transparent text-[var(--color-ink-soft)]",
        "hover:text-[var(--color-ink)] hover:bg-[var(--color-paper-deep)]",
      ],
      outline: [
        "border border-[var(--color-ink-line)] bg-[var(--color-card)]",
        "text-[var(--color-ink)] hover:bg-[var(--color-paper-deep)] hover:border-[var(--color-ink-faint)]",
      ],
      paper: [
        "bg-[var(--color-paper-deep)] text-[var(--color-ink)]",
        "border border-transparent hover:border-[var(--color-ink-line)]",
      ],
    },
    size: {
      sm: "h-8 px-3 text-[13px] rounded-[var(--radius-sm)]",
      md: "h-10 px-4 text-[14px] rounded-[var(--radius-md)]",
      lg: "h-12 px-6 text-[15px] rounded-[var(--radius-pill)]",
      icon: "h-10 w-10 rounded-[var(--radius-md)]",
    },
  },
  defaultVariants: {
    variant: "primary",
    size: "md",
  },
});

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof button> {
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={button({ variant, size, className })}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
