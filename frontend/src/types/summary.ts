/**
 * TypeScript contracts for 9-section structured summaries, timestamps, and evidence citations.
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
  thesis: string;
  core_takeaways: string[];
  target_audience?: string | null;
  evidence_ids?: string[];
}

export interface KeyTopicSection {
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

export interface TechnicalDetailSection {
  topic: string;
  category: "architecture" | "configuration" | "metric" | "code_pattern" | "other";
  details: string;
  evidence_ids?: string[];
}

export interface RecommendationSection {
  recommendation: string;
  priority: "critical" | "high" | "medium" | "low";
  rationales: string[];
  evidence_ids?: string[];
}

export interface GlossaryTerm {
  term: string;
  definition: string;
  context?: string | null;
}

export interface CaveatItem {
  statement: string;
  evidence_ids?: string[];
}

export interface StructuredSummaryV3 {
  schema_version: "3.0.0";
  video_id: string;
  title: string;
  channel_name?: string | null;
  duration_seconds: number;
  executive_overview: ExecutiveOverviewSection;
  key_topics: KeyTopicSection[];
  chapters: ChapterSection[];
  technical_details: TechnicalDetailSection[];
  recommendations: RecommendationSection[];
  glossary: GlossaryTerm[];
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
