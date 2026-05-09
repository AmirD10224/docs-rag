"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { toast } from "sonner";
import { Card, CardBody } from "@/components/ui/card";
import { SamplePicker } from "./sample-picker";
import { QuestionInput } from "./question-input";
import { AnswerPane } from "./answer-pane";
import { CitationList } from "./citation-list";
import { TraceBar } from "./trace-bar";
import { SourcePanel } from "./source-panel";
import { query, type QueryResponse } from "@/lib/api";
import { SAMPLES, HERO_QUESTIONS, type SampleDoc } from "@/lib/samples";

export function DemoSection() {
  const [activeDoc, setActiveDoc] = useState<SampleDoc | null>(SAMPLES[0]);
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeChunk, setActiveChunk] = useState<string | null>(null);

  async function ask() {
    if (!question.trim()) return;
    setLoading(true);
    setResponse(null);
    setActiveChunk(null);
    try {
      const result = await query(question);
      setResponse(result);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Query failed");
    } finally {
      setLoading(false);
    }
  }

  const suggestions = activeDoc?.questions ?? HERO_QUESTIONS;

  return (
    <section
      id="try"
      className="relative scroll-mt-24 mx-auto max-w-[1280px] px-8 py-24"
    >
      {/* Section header, editorial style */}
      <motion.header
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-100px" }}
        transition={{ duration: 0.6 }}
        className="mb-14"
      >
        <div className="flex items-center gap-4 mb-6">
          <span className="font-mono text-[11px] tracking-[0.18em] uppercase text-[var(--color-ink-faint)]">
            §02. Try it
          </span>
          <span className="h-px w-16 bg-[var(--color-ink)]" />
        </div>
        <h2 className="font-display text-[56px] sm:text-[72px] leading-[0.95] tracking-[-0.025em] text-[var(--color-ink)] text-balance max-w-3xl">
          Pick a document. <br />
          Ask <span className="font-display-italic text-[var(--color-accent)]">anything</span>.
        </h2>
        <p className="mt-6 max-w-xl text-[16px] leading-relaxed text-[var(--color-ink-soft)] text-pretty">
          Each answer comes back with chunk-id citations that exist in the
          retrieval context, a faithfulness score, and a full latency trace.
        </p>
      </motion.header>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-8">
        {/* Main column */}
        <div className="space-y-10">
          {/* Sample picker */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <p className="label-caps">Sample documents</p>
              <span className="h-px flex-1 bg-[var(--color-ink-line)]" />
            </div>
            <SamplePicker
              active={activeDoc?.id ?? null}
              onSelect={(d) => setActiveDoc(d)}
            />
          </div>

          {/* Question input */}
          <QuestionInput
            value={question}
            onChange={setQuestion}
            onSubmit={ask}
            suggestions={suggestions}
            loading={loading}
          />

          {/* Answer */}
          {(response || loading) && (
            <Card lift={false} className="p-2">
              <CardBody className="space-y-8">
                <AnswerPane response={response} loading={loading} />
                {response && <TraceBar trace={response.trace} />}
              </CardBody>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <aside className="space-y-6">
          {response && response.citations.length > 0 ? (
            <Card>
              <CardBody>
                <CitationList
                  citations={response.citations}
                  onSelect={setActiveChunk}
                  active={activeChunk}
                />
              </CardBody>
            </Card>
          ) : (
            <PlaceholderPanel />
          )}
        </aside>
      </div>

      <SourcePanel chunk_id={activeChunk} onClose={() => setActiveChunk(null)} />
    </section>
  );
}

function PlaceholderPanel() {
  const steps = [
    "Embed query · BM25 + dense retrieval over the full corpus",
    "RRF fusion · Cohere Rerank 3.5 to top-8",
    "Claude synthesizes with strict JSON · forced chunk-id citations",
    "Validator rejects unknown chunks · one repair attempt · refuse if it fails",
  ];
  return (
    <Card variant="outline" lift={false}>
      <CardBody>
        <p className="label-caps mb-4">What happens when you ask</p>
        <ol className="space-y-4">
          {steps.map((line, i) => (
            <li key={i} className="flex gap-4">
              <span className="font-display text-[28px] leading-none text-[var(--color-accent)] tabular-nums shrink-0 w-8">
                {String(i + 1).padStart(2, "0")}
              </span>
              <p className="text-[13.5px] leading-[1.6] text-[var(--color-ink-soft)] pt-1">
                {line}
              </p>
            </li>
          ))}
        </ol>
      </CardBody>
    </Card>
  );
}
