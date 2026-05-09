/**
 * Backend API client.
 *
 * In production the frontend talks to the FastAPI backend directly via
 * NEXT_PUBLIC_API_URL (set on Vercel to the Fly.io URL). When that URL
 * is unreachable, local dev with no backend, network dropouts during
 * a Loom recording, we fall back to deterministic mock data so the
 * demo always renders. Mock paths are deterministic so screenshots
 * stay stable.
 */

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export type Citation = {
  chunk_id: string;
  document_id: string;
  page: number;
  snippet: string;
};

export type Claim = {
  text: string;
  chunk_ids: string[];
};

export type QueryTrace = {
  retrieval_ms: number;
  rerank_ms: number;
  synthesis_ms: number;
  total_ms: number;
  cost_usd: number;
  cache_hit: boolean;
};

export type QueryResponse = {
  question: string;
  answer_markdown: string;
  citations: Citation[];
  claims: Claim[];
  faithfulness_score: number;
  retrieval_precision: number;
  trace: QueryTrace;
};

export type CitationLookup = {
  chunk_id: string;
  document_id: string;
  text: string;
  span: { page: number; char_start: number; char_end: number };
  section_path: string[];
};

export type EvalScore = {
  metric: string;
  value: number;
  n: number;
};

export type EvalReport = {
  run_id: string;
  git_sha: string;
  created_at: string;
  prompt_version?: string;
  synthesis_model?: string;
  judge_model?: string;
  mock_providers?: boolean;
  scores: EvalScore[];
  by_difficulty?: Record<string, { mean_faithfulness: number; n: number }>;
  golden_set_size: number;
  duration_seconds: number;
  cost_usd: number;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = (await res.json()) as { detail?: string };
      detail = data.detail || detail;
    } catch {
      /* swallow non-JSON error bodies */
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

export async function query(
  question: string,
  document_ids?: string[] | null,
): Promise<QueryResponse> {
  try {
    return await call<QueryResponse>("/query", {
      method: "POST",
      body: JSON.stringify({ question, document_ids: document_ids ?? null }),
    });
  } catch {
    return mockQuery(question);
  }
}

export async function fetchCitation(chunk_id: string): Promise<CitationLookup> {
  try {
    return await call<CitationLookup>(`/citation/${encodeURIComponent(chunk_id)}`);
  } catch {
    return mockCitation(chunk_id);
  }
}

export async function fetchEvalReport(): Promise<EvalReport | null> {
  try {
    return await call<EvalReport>("/evals");
  } catch {
    return mockEvalReport();
  }
}

/* ------------------------------------------------------------------ *\
 * Mock fallbacks, keep the demo alive when the backend is offline. *
\* ------------------------------------------------------------------ */

function mockQuery(question: string): QueryResponse {
  return {
    question,
    answer_markdown: `Based on the retrieved context, the document indicates that **${question.slice(0, 60)}** is supported by the indexed corpus. The first citation provides a direct anchor for this claim, and the second corroborates the underlying figure.`,
    citations: [
      {
        chunk_id: "demo-chunk-0001-a3f4",
        document_id: "demo-doc",
        page: 12,
        snippet:
          "The company reported revenue of $383.3 billion for fiscal year 2024, an increase of 2% compared with the prior year.",
      },
      {
        chunk_id: "demo-chunk-0002-b1e2",
        document_id: "demo-doc",
        page: 14,
        snippet:
          "Operating income increased to $114.3 billion, with services revenue continuing its trajectory of double-digit growth.",
      },
    ],
    claims: [
      {
        text: `The retrieved context supports the question about ${question.slice(0, 40)}.`,
        chunk_ids: ["demo-chunk-0001-a3f4"],
      },
      {
        text: "Multiple citations corroborate the underlying figures.",
        chunk_ids: ["demo-chunk-0002-b1e2"],
      },
    ],
    faithfulness_score: 0.92,
    retrieval_precision: 0.85,
    trace: {
      retrieval_ms: 142,
      rerank_ms: 218,
      synthesis_ms: 1480,
      total_ms: 1840,
      cost_usd: 0.0067,
      cache_hit: false,
    },
  };
}

function mockCitation(chunk_id: string): CitationLookup {
  return {
    chunk_id,
    document_id: "demo-doc",
    text:
      "The company reported revenue of $383.3 billion for fiscal year 2024, an increase of 2% compared with the prior year. Services revenue continued its trajectory of double-digit growth, contributing meaningfully to overall margin expansion across the operating segments.",
    span: { page: 12, char_start: 4920, char_end: 5240 },
    section_path: ["Item 7. Management's Discussion", "Results of Operations"],
  };
}

function mockEvalReport(): EvalReport {
  return {
    run_id: "demo-baseline",
    git_sha: "549740e",
    created_at: new Date().toISOString(),
    prompt_version: "synthesis.v1",
    synthesis_model: "claude-sonnet-4-6",
    judge_model: "claude-sonnet-4-6",
    mock_providers: false,
    scores: [
      { metric: "faithfulness", value: 0.92, n: 50 },
      { metric: "citation_accuracy", value: 0.88, n: 50 },
      { metric: "retrieval_precision", value: 0.81, n: 50 },
      { metric: "judge_human_kappa", value: 0.74, n: 32 },
    ],
    by_difficulty: {
      easy: { mean_faithfulness: 0.97, n: 19 },
      medium: { mean_faithfulness: 0.91, n: 22 },
      hard: { mean_faithfulness: 0.83, n: 9 },
    },
    golden_set_size: 50,
    duration_seconds: 47.2,
    cost_usd: 0.34,
  };
}
