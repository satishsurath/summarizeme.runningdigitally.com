/**
 * TypeScript contracts for 9-section structured summaries, timestamps, and evidence citations.
 *
 * These types mirror the Pydantic models in services/contracts.py.
 * The Python backend is authoritative — update TS to match Python, not the reverse.
 */

export interface EvidenceReference {
  id: string;
  start_seconds: number;
  end_seconds: number;
  speaker?: string | null;
  excerpt: string;
  youtube_url?: string | null;
}

export interface ExecutiveOverviewSection {
  text: string;
  evidence_ids?: string[];
}

export interface MainThesisSection {
  statement: string;
  evidence_ids?: string[];
}

export interface TopicSection {
  topic: string;
  importance: "high" | "medium" | "low";
  summary: string;
  evidence_ids?: string[];
}

export interface ChapterSection {
  title: string;
  start_seconds: number;
  end_seconds: number;
  bullets: string[];
  evidence_ids?: string[];
}

export interface ImportantDetailSection {
  statement: string;
  classification: "fact" | "opinion" | "prediction" | "recommendation";
  speaker?: string | null;
  evidence_ids?: string[];
}

export interface DecisionSection {
  decision: string;
  rationale?: string | null;
  evidence_ids?: string[];
}

export interface RecommendationSection {
  recommendation: string;
  target_audience?: string | null;
  evidence_ids?: string[];
}

export interface ActionItemSection {
  action: string;
  owner?: string | null;
  due_date?: string | null;
  evidence_ids?: string[];
}

export interface GlossaryTerm {
  term: string;
  definition: string;
  evidence_ids?: string[];
}

export interface OpenQuestionItem {
  question: string;
  evidence_ids?: string[];
}

export interface CaveatItem {
  statement: string;
  evidence_ids?: string[];
}

export interface StructuredSummaryV3 {
  schema_version: "summary.v3";
  executive_overview: ExecutiveOverviewSection;
  main_thesis: MainThesisSection;
  topics: TopicSection[];
  chapters: ChapterSection[];
  important_details: ImportantDetailSection[];
  decisions: DecisionSection[];
  recommendations: RecommendationSection[];
  action_items: ActionItemSection[];
  glossary: GlossaryTerm[];
  open_questions: OpenQuestionItem[];
  caveats: CaveatItem[];
  evidence: EvidenceReference[];
}

export interface SummaryRun {
  id: string;
  video_id: string;
  model_name: string;
  reasoning_effort: string;
  status: "completed" | "failed" | "processing";
  reasoning_content?: string | null;
  structured_summary?: StructuredSummaryV3 | null;
  prompt_tokens: number;
  completion_tokens: number;
  reasoning_tokens: number;
  latency_ms: number;
  created_at: string;
}
