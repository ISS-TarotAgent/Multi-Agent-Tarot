export type FlowStage = "intake" | "clarify" | "draw" | "result" | "history";

export type IntentTag =
  | "career"
  | "relationship"
  | "study"
  | "emotion"
  | "growth";

export interface ClarificationPrompt {
  id: string;
  question: string;
  helperText: string;
  placeholder: string;
}

export interface SessionDraft {
  sessionId: string;
  originalQuestion: string;
  normalizedQuestion: string;
  intentTag: IntentTag;
  clarificationPrompts: ClarificationPrompt[];
  startedAt: string;
}

export interface TarotCardInsight {
  id: string;
  name: string;
  arcana: "Major" | "Minor";
  suit?: string;
  role: "Current" | "Challenge" | "Action";
  orientation: "upright" | "reversed";
  keywords: string[];
  interpretation: string;
  reflectionPrompt: string;
  accent: string;
}

export interface SafetyReview {
  level: "low" | "medium";
  note: string;
  boundary: string;
}

export interface TraceStep {
  label: string;
  detail: string;
  status: "done";
}

export interface ReadingRecord {
  sessionId: string;
  title: string;
  question: string;
  reframedQuestion: string;
  intentTag: IntentTag;
  clarificationAnswers: Record<string, string>;
  cards: TarotCardInsight[];
  synthesis: string;
  actionSuggestions: string[];
  reflectionQuestions: string[];
  safety: SafetyReview;
  trace: TraceStep[];
  createdAt: string;
}
