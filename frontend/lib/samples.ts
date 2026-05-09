/**
 * Pre-loaded sample documents and "try this" questions for the demo.
 * Visitors who don't have their own PDF can click these to see the
 * pipeline run end-to-end in 30 seconds.
 */

export type SampleDoc = {
  id: string;
  title: string;
  short: string;
  source: string;
  pages: number;
  questions: string[];
  accent: "cyan" | "violet" | "amber";
};

export const SAMPLES: SampleDoc[] = [
  {
    id: "apple_10k_fy2024",
    title: "Apple FY2024 10-K",
    short: "Annual report",
    source: "SEC EDGAR",
    pages: 81,
    accent: "cyan",
    questions: [
      "What was Apple's iPhone revenue in fiscal year 2024?",
      "How did services revenue grow year over year?",
      "What are the principal risk factors disclosed?",
    ],
  },
  {
    id: "attention_is_all_you_need",
    title: "Attention Is All You Need",
    short: "Foundational paper",
    source: "arXiv 1706.03762",
    pages: 15,
    accent: "violet",
    questions: [
      "What is multi-head attention and why is it useful?",
      "How does the model handle positional information?",
      "What datasets were used for training?",
    ],
  },
  {
    id: "gitlab_msa",
    title: "GitLab MSA",
    short: "Subscription agreement",
    source: "Public legal terms",
    pages: 22,
    accent: "amber",
    questions: [
      "What are the indemnification obligations?",
      "How long is the data retention period after termination?",
      "Which jurisdiction governs the agreement?",
    ],
  },
];

export const HERO_QUESTIONS = [
  "What was iPhone revenue in FY2024?",
  "How does multi-head attention work?",
  "What is the indemnification clause?",
  "Compare R&D spend YoY",
  "What jurisdictions govern this contract?",
];
