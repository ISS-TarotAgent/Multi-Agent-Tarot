// OLD: export type FlowStage = "intake" | "clarify" | "draw" | "result" | "history";
export type FlowStage = "intake" | "clarify" | "draw" | "result" | "history" | "fallback";

export type IntentTag =
  | "career"
  | "relationship"
  | "study"
  | "emotion"
  | "growth";

// OLD: ClarificationPrompt was used for local hardcoded question sets (QUESTION_SET in api.ts).
// No longer needed — clarification question now comes from backend Clarifier LLM.
// export interface ClarificationPrompt {
//   id: string;
//   question: string;
//   helperText: string;
//   placeholder: string;
// }

export interface SessionDraft {
  sessionId: string;
  // NEW: backend reading_id, needed to associate the draft with the backend record
  readingId: string;
  originalQuestion: string;
  // OLD: normalizedQuestion was set locally; backend handles normalization now
  // normalizedQuestion: string;
  intentTag: IntentTag;
  // OLD: clarificationPrompts: ClarificationPrompt[];
  // Replaced by a single string question from the backend Clarifier LLM
  clarificationQuestionText: string;
  // NEW: tracks how many times the user has been asked to clarify (1-indexed).
  // Frontend enforces a max of MAX_CLARIFICATION_TURNS to avoid infinite loops.
  clarificationTurn: number;
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
  cautionNote?: string;
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

// NEW: holds the safety fallback payload returned by the backend
export interface FallbackInfo {
  message: string;      // synthesis.summary from backend (protective fallback text)
  riskLevel: string;    // safety.risk_level
  actionTaken: string;  // safety.action_taken
}

// NEW: discriminated union returned by startSession() and completeReading()
export type ReadingResult =
  | { kind: "clarifying"; draft: SessionDraft }
  | { kind: "complete"; record: ReadingRecord }
  | { kind: "fallback"; info: FallbackInfo };

export interface ReadingRecord {
  sessionId: string;
  title: string;
  question: string;
  reframedQuestion: string;
  intentTag: IntentTag;
  // OLD: clarificationAnswers: Record<string, string>;
  // Backend single-step mode produces one clarification question → one answer
  clarificationAnswer: string;
  cards: TarotCardInsight[];
  synthesis: string;
  actionSuggestions: string[];
  reflectionQuestions: string[];
  safety: SafetyReview;
  trace: TraceStep[];
  createdAt: string;
}
