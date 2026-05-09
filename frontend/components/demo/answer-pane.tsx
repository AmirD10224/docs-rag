"use client";

import { motion } from "motion/react";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ShieldCheck, ShieldAlert } from "lucide-react";
import type { QueryResponse } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

interface AnswerPaneProps {
  response: QueryResponse | null;
  loading: boolean;
}

export function AnswerPane({ response, loading }: AnswerPaneProps) {
  if (loading) return <SkeletonAnswer />;
  if (!response) return null;

  return (
    <motion.article
      key={response.question}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.165, 0.84, 0.44, 1] }}
      className="space-y-6"
    >
      <header className="flex items-center gap-2 flex-wrap">
        <FaithfulnessBadge score={response.faithfulness_score} />
        <Badge tone="mono">
          {response.citations.length} citation
          {response.citations.length === 1 ? "" : "s"}
        </Badge>
        {response.trace.cache_hit && <Badge tone="violet">cache hit</Badge>}
      </header>

      {/* The actual question, set in display serif as a pull-quote */}
      <p className="font-display-italic text-[22px] leading-snug text-[var(--color-ink-soft)] text-balance border-l-2 border-[var(--color-accent)] pl-5">
        &ldquo;{response.question}&rdquo;
      </p>

      <div className="prose-answer space-y-4">
        <Typewriter text={response.answer_markdown} />
      </div>
    </motion.article>
  );
}

function FaithfulnessBadge({ score }: { score: number }) {
  const high = score >= 0.85;
  const Icon = high ? ShieldCheck : ShieldAlert;
  return (
    <Badge tone={high ? "forest" : "accent"} className="gap-1.5 h-7 px-3">
      <Icon className="size-3" />
      <span className="font-mono">faithfulness {(score * 100).toFixed(0)}%</span>
    </Badge>
  );
}

function Typewriter({ text }: { text: string }) {
  const [shown, setShown] = useState("");
  useEffect(() => {
    setShown("");
    let i = 0;
    const id = setInterval(() => {
      i += 4;
      setShown(text.slice(0, i));
      if (i >= text.length) clearInterval(id);
    }, 14);
    return () => clearInterval(id);
  }, [text]);

  return (
    <div className="text-[17px] leading-[1.7] text-[var(--color-ink)]">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{shown}</ReactMarkdown>
      {shown.length < text.length && (
        <span
          className="inline-block w-[2px] h-[1.1em] bg-[var(--color-accent)] align-middle ml-0.5"
          style={{ animation: "typing-cursor 1s step-end infinite" }}
        />
      )}
    </div>
  );
}

function SkeletonAnswer() {
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <ShimmerLine className="h-7 w-32 rounded-full" />
        <ShimmerLine className="h-7 w-24 rounded-full" />
      </div>
      <ShimmerLine className="h-5 w-3/4" />
      <div className="space-y-2.5 pt-2">
        <ShimmerLine className="h-3.5 w-[88%]" />
        <ShimmerLine className="h-3.5 w-[95%]" />
        <ShimmerLine className="h-3.5 w-[72%]" />
      </div>
    </div>
  );
}

function ShimmerLine({ className }: { className?: string }) {
  return (
    <div className={`relative overflow-hidden bg-[var(--color-paper-deep)] rounded-md ${className}`}>
      <motion.div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(90deg, transparent, oklch(86% 0.008 80 / 0.7), transparent)",
        }}
        animate={{ x: ["-100%", "100%"] }}
        transition={{ duration: 1.4, repeat: Infinity, ease: "linear" }}
      />
    </div>
  );
}
