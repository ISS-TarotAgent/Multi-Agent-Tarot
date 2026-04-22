/**
 * Real API service — calls POST /api/v1/readings (single-step workflow).
 *
 * Flow:
 *   startSession(question)
 *     → POST /api/v1/readings
 *     → kind="clarifying"  : backend Clarifier LLM needs more context
 *     → kind="complete"    : full reading result, no clarification needed
 *     → kind="fallback"    : safety guard blocked the request
 *
 *   completeReading(draft, answer)
 *     → POST /api/v1/readings with enriched question (original + clarification answer)
 *     → same three outcomes
 */
import type {
  FallbackInfo,
  IntentTag,
  ReadingRecord,
  ReadingResult,
  SafetyReview,
  SessionDraft,
  TraceStep,
} from "../types";

const STORAGE_KEY = "multi-agent-tarot-history";

// Maximum number of clarification rounds the frontend will allow.
// If the backend keeps returning CLARIFYING beyond this limit, treat it as a fallback.
const MAX_CLARIFICATION_TURNS = 3;

// ---------------------------------------------------------------------------
// Backend response types (mirrors backend/app/schemas/api/readings.py)
// ---------------------------------------------------------------------------
interface BackendCard {
  position: "PAST" | "PRESENT" | "FUTURE";
  card_code: string;
  card_name: string;
  orientation: "UPRIGHT" | "REVERSED";
  interpretation: string;
  reflection_question?: string | null;
  caution_note?: string | null;
  keywords?: string[] | null;
}

interface BackendReadingResult {
  reading_id: string;
  session_id: string;
  status: string;
  locale: string;
  question: { raw_question: string; normalized_question: string | null };
  clarification: { required: boolean; question_text: string | null; answer_text: string | null };
  cards: BackendCard[];
  synthesis: {
    summary: string | null;
    action_advice: string | null;
    reflection_question: string | null;
  };
  // OLD: safety: { risk_level: "LOW" | "MEDIUM"; action_taken: string; review_notes: string | null };
  // Updated: risk_level can also be HIGH (e.g. SAFE_FALLBACK_RETURNED cases)
  safety: { risk_level: string; action_taken: string; review_notes: string | null };
  trace_summary: { event_count: number; warning_count: number; error_count: number };
  created_at: string;
  completed_at: string | null;
}

// ---------------------------------------------------------------------------
// OLD: QUESTION_SET — hardcoded local clarification prompts, one set per intent tag.
// Replaced by the single clarification question returned by the backend Clarifier LLM.
// ---------------------------------------------------------------------------
// const QUESTION_SET: Record<IntentTag, ClarificationPrompt[]> = {
//   career: [
//     {
//       id: "time-horizon",
//       question: "Are you trying to solve a short-term choice or a long-term direction?",
//       helperText: "Naming the time horizon helps the system separate immediate action from long-range planning.",
//       placeholder: "Example: I care more about what I should do in the next three months."
//     },
//     {
//       id: "core-pressure",
//       question: "What are you most afraid of losing in this situation?",
//       helperText: "The hidden fear often explains more than the visible goal.",
//       placeholder: "Example: I am afraid of missing a better opportunity or proving I am not ready."
//     },
//     {
//       id: "decision-window",
//       question: "When does this decision actually need to move forward?",
//       helperText: "If there is no real deadline, some of the pressure may only be self-imposed.",
//       placeholder: "Example: I need to respond within two weeks."
//     }
//   ],
//   relationship: [ ... ],
//   study: [ ... ],
//   emotion: [ ... ],
//   growth: [ ... ],
// };

// ---------------------------------------------------------------------------
// Local helpers
// ---------------------------------------------------------------------------
function detectIntentTag(question: string): IntentTag {
  const text = question.toLowerCase();
  if (/(?:工作|职业|实习|offer|求职|跳槽|career)/i.test(text)) return "career";
  if (/(?:感情|关系|喜欢|恋爱|朋友|relationship)/i.test(text)) return "relationship";
  if (/(?:学习|考试|申请|课程|研究|study)/i.test(text)) return "study";
  if (/(?:情绪|焦虑|压力|难过|内耗|emotion)/i.test(text)) return "emotion";
  return "growth";
}

function buildTitle(question: string) {
  return question.length > 22 ? `${question.slice(0, 22)}...` : question;
}

function readHistory(): ReadingRecord[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ReadingRecord[]) : [];
  } catch {
    return [];
  }
}

function writeHistory(records: ReadingRecord[]) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
}

// ---------------------------------------------------------------------------
// Backend response → frontend type mappers
// ---------------------------------------------------------------------------
const POSITION_TO_ROLE = {
  PAST: "Current",
  PRESENT: "Challenge",
  FUTURE: "Action",
} as const;

const SUIT_ACCENTS: Record<string, string> = {
  cups: "linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%)",
  wands: "linear-gradient(135deg, #fddb92 0%, #d1fdff 100%)",
  swords: "linear-gradient(135deg, #c3cfe2 0%, #c3cfe2 100%)",
  pentacles: "linear-gradient(135deg, #96fbc4 0%, #f9f586 100%)",
  major: "linear-gradient(135deg, #f6d365 0%, #fda085 100%)",
};

function cardAccent(cardCode: string): string {
  const suit = cardCode.split("-")[0];
  return SUIT_ACCENTS[suit] ?? SUIT_ACCENTS.major;
}

function cardArcana(cardCode: string): "Major" | "Minor" {
  return cardCode.startsWith("major-") ? "Major" : "Minor";
}

function cardSuit(cardCode: string): string | undefined {
  const suit = cardCode.split("-")[0];
  if (suit === "major") return undefined;
  return suit.charAt(0).toUpperCase() + suit.slice(1);
}

function mapCard(c: BackendCard, intentTag: IntentTag) {
  return {
    id: c.card_code,
    name: c.card_name,
    arcana: cardArcana(c.card_code),
    suit: cardSuit(c.card_code),
    role: POSITION_TO_ROLE[c.position],
    orientation: c.orientation === "UPRIGHT" ? "upright" : "reversed",
    keywords: c.keywords ?? [],
    interpretation: c.interpretation,
    reflectionPrompt:
      c.reflection_question ??
      `Considering "${intentTag}", what does ${c.card_name} reveal about your next step?`,
    cautionNote: c.caution_note ?? undefined,
    accent: cardAccent(c.card_code),
  } as const;
}

function mapSafety(s: BackendReadingResult["safety"]): SafetyReview {
  return {
    level: s.risk_level === "MEDIUM" ? "medium" : "low",
    note: s.review_notes ?? "This result is designed for reflection, not absolute prediction.",
    boundary:
      "If the issue involves persistent distress or a high-stakes professional decision, seek real-world support first.",
  };
}

function mapTrace(t: BackendReadingResult["trace_summary"]): TraceStep[] {
  return [
    { label: "Question Intake", detail: "Captured and normalized the question.", status: "done" },
    { label: "Clarification", detail: "Assessed clarity and enriched question context.", status: "done" },
    { label: "Card Draw", detail: "Drew 3 cards with seeded random selection.", status: "done" },
    { label: "Synthesis", detail: `Generated narrative (${t.event_count} trace events).`, status: "done" },
    {
      label: "Safety Review",
      detail: `Reviewed output. Warnings: ${t.warning_count}, Errors: ${t.error_count}.`,
      status: "done",
    },
  ];
}

// OLD: mapToReadingRecord(res, draft: SessionDraft, answers: Record<string, string>)
// Updated: draft replaced by individual primitives; answers replaced by single clarificationAnswer
function mapToReadingRecord(
  res: BackendReadingResult,
  originalQuestion: string,
  intentTag: IntentTag,
  clarificationAnswer: string,
): ReadingRecord {
  const synth = res.synthesis;
  const cards = res.cards.map((c) => mapCard(c, intentTag));
  return {
    sessionId: res.session_id,
    title: buildTitle(originalQuestion),
    question: res.question.raw_question,
    reframedQuestion: res.question.normalized_question ?? originalQuestion,
    intentTag,
    // OLD: clarificationAnswers: answers,
    clarificationAnswer,
    cards,
    synthesis: synth.summary ?? "",
    actionSuggestions: synth.action_advice ? [synth.action_advice] : [],
    reflectionQuestions: synth.reflection_question ? [synth.reflection_question] : [],
    safety: mapSafety(res.safety),
    trace: mapTrace(res.trace_summary),
    createdAt: res.created_at,
  };
}

// ---------------------------------------------------------------------------
// Shared internal call — POST /api/v1/readings and parse the result
// ---------------------------------------------------------------------------
async function callReadingsApi(
  question: string,
  skipClarification = false,
): Promise<BackendReadingResult> {
  const response = await fetch("/api/v1/readings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      locale: "zh-CN",
      spread_type: "THREE_CARD_REFLECTION",
      skip_clarification: skipClarification,
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API error ${response.status}: ${text}`);
  }

  return (await response.json()) as BackendReadingResult;
}

// parseResult is synchronous for all cases except MAX_CLARIFICATION_TURNS,
// which needs to fire an extra API call — handled in the async wrappers below.
function parseResult(
  data: BackendReadingResult,
  originalQuestion: string,
  intentTag: IntentTag,
  clarificationAnswer: string,
  currentTurn: number,
): ReadingResult | "force_draw" {
  if (data.status === "SAFE_FALLBACK_RETURNED") {
    const info: FallbackInfo = {
      message: data.synthesis.summary ?? "Your question triggered a safety review. Please try rephrasing.",
      riskLevel: data.safety.risk_level,
      actionTaken: data.safety.action_taken,
    };
    return { kind: "fallback", info };
  }

  if (data.status === "CLARIFYING") {
    // OLD: when currentTurn >= MAX_CLARIFICATION_TURNS, returned a fallback error.
    // NEW: return a sentinel so the caller re-sends with skip_clarification=true.
    if (currentTurn >= MAX_CLARIFICATION_TURNS) {
      return "force_draw";
    }

    const draft: SessionDraft = {
      sessionId: data.session_id,
      readingId: data.reading_id,
      originalQuestion,
      intentTag,
      clarificationQuestionText:
        data.clarification.question_text ?? "Could you share more context about your situation?",
      clarificationTurn: currentTurn + 1,
      startedAt: new Date().toISOString(),
    };
    return { kind: "clarifying", draft };
  }

  // COMPLETED (or any other terminal status)
  const record = mapToReadingRecord(data, originalQuestion, intentTag, clarificationAnswer);
  const nextHistory = [record, ...readHistory()].slice(0, 12);
  writeHistory(nextHistory);
  return { kind: "complete", record };
}

// Resolves the "force_draw" sentinel by re-sending with skip_clarification=true.
async function forceDrawResult(
  question: string,
  originalQuestion: string,
  intentTag: IntentTag,
  clarificationAnswer: string,
): Promise<ReadingResult> {
  const data = await callReadingsApi(question, true);
  const result = parseResult(data, originalQuestion, intentTag, clarificationAnswer, 0);
  // skip_clarification guarantees backend won't return CLARIFYING again
  return result === "force_draw" ? { kind: "fallback", info: {
    message: "Unable to process the question after maximum attempts. Please try rephrasing.",
    riskLevel: "LOW",
    actionTaken: "FORCE_DRAW_FAILED",
  }} : result;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------
export async function loadHistory(): Promise<ReadingRecord[]> {
  return readHistory().sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

// OLD: startSession was purely local — no HTTP call, returned SessionDraft directly.
// export async function startSession(question: string): Promise<SessionDraft> {
//   const intentTag = detectIntentTag(question);
//   return {
//     sessionId: crypto.randomUUID(),
//     originalQuestion: question.trim(),
//     normalizedQuestion: question.trim().replace(/\s+/g, " "),
//     intentTag,
//     clarificationPrompts: QUESTION_SET[intentTag],
//     startedAt: new Date().toISOString(),
//   };
// }

// NEW: immediately calls POST /api/v1/readings; returns ReadingResult discriminated union
export async function startSession(question: string): Promise<ReadingResult> {
  const trimmed = question.trim();
  const intentTag = detectIntentTag(trimmed);
  const data = await callReadingsApi(trimmed);
  const result = parseResult(data, trimmed, intentTag, "", 0);
  // turn=0 on first call so force_draw cannot trigger here (would need turn >= 3)
  return result === "force_draw"
    ? forceDrawResult(trimmed, trimmed, intentTag, "")
    : result;
}

// OLD: completeReading took (draft: SessionDraft, answers: Record<string, string>)
// and always called the backend once with all answers concatenated.
// export async function completeReading(
//   draft: SessionDraft,
//   answers: Record<string, string>
// ): Promise<ReadingRecord> {
//   const answerContext = Object.entries(answers)
//     .filter(([, v]) => v.trim())
//     .map(([, v]) => v.trim())
//     .join("; ");
//   const enrichedQuestion = answerContext
//     ? `${draft.originalQuestion} — additional context: ${answerContext}`
//     : draft.originalQuestion;
//   const response = await fetch("/api/v1/readings", { ... });
//   ...
// }

// NEW: takes a single clarification answer string; re-calls POST /api/v1/readings
// with the enriched question (original + answer context).
// Passes draft.clarificationTurn so parseResult can enforce MAX_CLARIFICATION_TURNS.
export async function completeReading(
  draft: SessionDraft,
  answer: string,
): Promise<ReadingResult> {
  const trimmedAnswer = answer.trim();
  const enrichedQuestion = trimmedAnswer
    ? `${draft.originalQuestion} — additional context: ${trimmedAnswer}`
    : draft.originalQuestion;

  const data = await callReadingsApi(enrichedQuestion);
  const result = parseResult(data, draft.originalQuestion, draft.intentTag, trimmedAnswer, draft.clarificationTurn);
  if (result === "force_draw") {
    // Max turns reached: re-send with skip_clarification=true so backend finalizes immediately
    return forceDrawResult(enrichedQuestion, draft.originalQuestion, draft.intentTag, trimmedAnswer);
  }
  return result;
}
