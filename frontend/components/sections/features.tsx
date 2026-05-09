"use client";

import { motion } from "motion/react";

const FEATURES = [
  {
    num: "01",
    title: "Citation check.",
    body: "Every claim has to cite a chunk_id we sent. If the model cites something we didn't, one repair pass, then refuse.",
  },
  {
    num: "02",
    title: "PR-level eval gate.",
    body: "GitHub Actions runs the 50-question golden set on each PR. If faithfulness or citation accuracy drops more than 3 points, the merge gets blocked.",
  },
  {
    num: "03",
    title: "Hybrid retrieval.",
    body: "BM25 over the full corpus, dense (Jina v3 with late chunking), RRF fusion, then Cohere Rerank 3.5. Not the version that just re-sorts dense by sparse.",
  },
  {
    num: "04",
    title: "Cost + traces.",
    body: "Per-call dollar cost from API usage, structlog JSON. Langfuse traces. Retry with repair on schema errors. Daily Anthropic spend cap with a circuit breaker.",
  },
  {
    num: "05",
    title: "URL ingestion isn't an SSRF.",
    body: "RFC1918, link-local, loopback, and cloud-metadata IPs are rejected at the URL handler. Per-IP rate limits via slowapi. PDF size capped before buffering.",
  },
  {
    num: "06",
    title: "Strict typing all the way through.",
    body: "Pydantic v2 strict on every endpoint, mypy --strict, ruff. Coverage gate at 75%. Fresh clone runs make ci clean.",
  },
] as const;

export function FeaturesSection() {
  return (
    <section className="relative mx-auto max-w-[1280px] px-8 py-24">
      <motion.header
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-100px" }}
        transition={{ duration: 0.6 }}
        className="mb-16 max-w-3xl"
      >
        <div className="flex items-center gap-4 mb-6">
          <span className="font-mono text-[11px] tracking-[0.18em] uppercase text-[var(--color-ink-faint)]">
            §03. How it's built
          </span>
          <span className="h-px w-16 bg-[var(--color-ink)]" />
        </div>
        <h2 className="font-display text-[56px] sm:text-[72px] leading-[0.95] tracking-[-0.025em] text-[var(--color-ink)] text-balance">
          Six pieces of plumbing that{" "}
          <span className="font-display-italic text-[var(--color-accent)]">
            keep this honest
          </span>{" "}
          in CI.
        </h2>
      </motion.header>

      {/* Editorial 2-column list with serif numbers */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-16 gap-y-2">
        {FEATURES.map((f, i) => (
          <motion.article
            key={f.num}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ duration: 0.5, delay: i * 0.06 }}
            className="group py-8 border-t border-[var(--color-ink-line)] flex gap-6"
          >
            <span className="font-display text-[44px] leading-none text-[var(--color-accent)] tabular-nums shrink-0 group-hover:translate-x-[-3px] transition-transform duration-300">
              {f.num}
            </span>
            <div>
              <h3 className="font-display text-[28px] leading-[1.1] tracking-tight text-[var(--color-ink)] mb-2">
                {f.title}
              </h3>
              <p className="text-[15.5px] leading-[1.65] text-[var(--color-ink-soft)] text-pretty">
                {f.body}
              </p>
            </div>
          </motion.article>
        ))}
      </div>
    </section>
  );
}
