"use client";

import { motion, AnimatePresence } from "motion/react";
import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/cn";

interface QuestionInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  suggestions?: string[];
  disabled?: boolean;
  loading?: boolean;
}

export function QuestionInput({
  value,
  onChange,
  onSubmit,
  suggestions = [],
  disabled = false,
  loading = false,
}: QuestionInputProps) {
  const [focused, setFocused] = useState(false);
  const [placeholderIdx, setPlaceholderIdx] = useState(0);

  useEffect(() => {
    if (suggestions.length === 0 || focused || value) return;
    const id = setInterval(() => {
      setPlaceholderIdx((i) => (i + 1) % suggestions.length);
    }, 3200);
    return () => clearInterval(id);
  }, [focused, suggestions, value]);

  const placeholder = suggestions[placeholderIdx] || "Ask a question…";

  function handleKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey && value.trim() && !loading) {
      e.preventDefault();
      onSubmit();
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="label-caps">Ask</span>
        <span className="h-px flex-1 bg-[var(--color-ink-line)]" />
      </div>

      <div
        className={cn(
          "relative flex items-baseline gap-3 pb-2",
          "border-b transition-colors duration-200",
          focused
            ? "border-[var(--color-ink)]"
            : "border-[var(--color-ink-line)] hover:border-[var(--color-ink-faint)]",
        )}
      >
        <span className="font-display text-[40px] leading-none text-[var(--color-accent)] select-none">
          &mdash;
        </span>

        <div className="relative flex-1 min-w-0">
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKey}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            disabled={disabled || loading}
            className="w-full bg-transparent font-display text-[28px] sm:text-[36px] leading-tight tracking-[-0.01em] text-[var(--color-ink)] placeholder:text-transparent outline-none disabled:opacity-50 py-1"
          />
          {!value && (
            <AnimatePresence mode="wait">
              <motion.span
                key={placeholder}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.4 }}
                className="absolute inset-y-0 left-0 flex items-center font-display text-[28px] sm:text-[36px] leading-tight tracking-[-0.01em] text-[var(--color-ink-faint)] pointer-events-none truncate italic"
              >
                {placeholder}
              </motion.span>
            </AnimatePresence>
          )}
        </div>

        <button
          onClick={onSubmit}
          disabled={disabled || loading || !value.trim()}
          aria-label="Submit question"
          className={cn(
            "shrink-0 inline-flex items-center justify-center h-12 w-12 rounded-full",
            "bg-[var(--color-ink)] text-[var(--color-paper-soft)]",
            "hover:bg-[var(--color-accent-deep)] disabled:opacity-30 disabled:cursor-not-allowed",
            "transition-all duration-200",
          )}
        >
          {loading ? <LoadingDots /> : <ArrowRight className="size-4" />}
        </button>
      </div>

      <p className="font-mono text-[11px] text-[var(--color-ink-faint)] tracking-wide">
        Press{" "}
        <kbd className="px-1.5 py-0.5 rounded bg-[var(--color-paper-deep)] border border-[var(--color-ink-line)] font-mono text-[10.5px]">
          Enter
        </kbd>{" "}
        to ask · samples shown above are pre-loaded
      </p>
    </div>
  );
}

function LoadingDots() {
  return (
    <span className="flex gap-0.5">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="size-1 rounded-full bg-current"
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.15 }}
        />
      ))}
    </span>
  );
}
