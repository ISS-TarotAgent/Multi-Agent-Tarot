/**
 * API service — uses the session-oriented workflow endpoints.
 *
 * Flow:
 *   startSession(question)
 *     → POST /api/v1/sessions                      (create session)
 *     → POST /api/v1/sessions/{id}/question        (evaluate question)
 *     → kind="clarifying"  : Clarifier LLM needs more context
 *     → kind="complete"    : READY_FOR_DRAW → POST /sessions/{id}/run
 *     → kind="fallback"    : safety guard blocked at input stage
 *
 *   completeReading(draft, answer)
 *     → POST /api/v1/sessions/{id}/clarifications  (submit clarification)
 *     → kind="clarifying"  : another round needed
 *     → kind="complete"    : READY_FOR_DRAW → POST /sessions/{id}/run
 *     → kind="fallback"    : safety guard blocked
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

// Maximum number of clarification rounds before forcing a draw.
const MAX_CLARIFICATION_TURNS = 3;

// ---------------------------------------------------------------------------
// Backend response types
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
  safety: { risk_level: string; action_taken: string; review_notes: string | null };
  trace_summary: { event_count: number; warning_count: number; error_count: number };
  created_at: string;
  completed_at: string | null;
}

interface CreateSessionResponse {
  session_id: string;
  status: string;
}

interface SubmitQuestionResponse {
  session_id: string;
  status: string;
  normalized_question: string | null;
  clarification_required: boolean;
  clarifier_question: string | null;
  updated_at: string;
}

interface SubmitClarificationResponse {
  session_id: string;
  status: string;
  normalized_question: string | null;
  clarification_required: boolean;
  next_clarifier_question: string | null;
  updated_at: string;
}

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

function detectLocale(question: string) {
  return /[\u4e00-\u9fff]/.test(question) ? "zh-CN" : "en";
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
  const r = s.risk_level.toUpperCase();
  const level = r === "HIGH" ? "high" : r === "MEDIUM" ? "medium" : "low";
  return {
    level,
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
    clarificationQuestion: res.clarification.question_text ?? null,
    clarificationAnswer: res.clarification.answer_text ?? clarificationAnswer,
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
// Session API calls
// ---------------------------------------------------------------------------
async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API error ${response.status}: ${text}`);
  }
  return (await response.json()) as T;
}

async function createSession(locale = "zh-CN"): Promise<CreateSessionResponse> {
  return apiPost<CreateSessionResponse>("/api/v1/sessions", {
    locale,
    spread_type: "THREE_CARD_REFLECTION",
  });
}

async function submitQuestion(
  sessionId: string,
  rawQuestion: string,
  skipClarification = false,
): Promise<SubmitQuestionResponse> {
  return apiPost<SubmitQuestionResponse>(`/api/v1/sessions/${sessionId}/question`, {
    raw_question: rawQuestion,
    skip_clarification: skipClarification,
  });
}

async function submitClarification(
  sessionId: string,
  answerText: string,
  turnIndex: number,
): Promise<SubmitClarificationResponse> {
  return apiPost<SubmitClarificationResponse>(`/api/v1/sessions/${sessionId}/clarifications`, {
    answer_text: answerText,
    turn_index: turnIndex,
  });
}

async function runSession(sessionId: string): Promise<BackendReadingResult> {
  return apiPost<BackendReadingResult>(`/api/v1/sessions/${sessionId}/run`, {});
}

// ---------------------------------------------------------------------------
// Result routing helpers
// ---------------------------------------------------------------------------
function buildFallbackFromReadingResult(res: BackendReadingResult): ReadingResult {
  return {
    kind: "fallback",
    info: {
      message: res.synthesis.summary ?? "Your question triggered a safety review. Please try rephrasing.",
      riskLevel: res.safety.risk_level,
      actionTaken: res.safety.action_taken,
    },
  };
}

function buildGenericInputFallback(): ReadingResult {
  return {
    kind: "fallback",
    info: {
      message: "你的问题包含了一些无法处理的内容，请换一种方式重新描述你想问的主题。",
      riskLevel: "HIGH",
      actionTaken: "BLOCK_AND_FALLBACK",
    },
  };
}

async function resolveReadyState(
  sessionId: string,
  originalQuestion: string,
  intentTag: IntentTag,
  clarificationAnswer: string,
): Promise<ReadingResult> {
  const res = await runSession(sessionId);
  if (res.status === "SAFE_FALLBACK_RETURNED") {
    return buildFallbackFromReadingResult(res);
  }
  const record = mapToReadingRecord(res, originalQuestion, intentTag, clarificationAnswer);
  const nextHistory = [record, ...readHistory()].slice(0, 12);
  writeHistory(nextHistory);
  return { kind: "complete", record };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------
export async function loadHistory(): Promise<ReadingRecord[]> {
  return readHistory().sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export async function startSession(
  question: string,
  skipClarification = false,
): Promise<ReadingResult> {
  const trimmed = question.trim();
  const intentTag = detectIntentTag(trimmed);
  const locale = detectLocale(trimmed);

  const session = await createSession(locale);
  const sessionId = session.session_id;

  const evalResult = await submitQuestion(sessionId, trimmed, skipClarification);

  if (evalResult.status === "SAFE_FALLBACK_RETURNED") {
    return buildGenericInputFallback();
  }

  if (evalResult.status === "CLARIFYING") {
    const draft: SessionDraft = {
      sessionId,
      readingId: "",
      originalQuestion: trimmed,
      intentTag,
      clarificationQuestionText:
        evalResult.clarifier_question ?? "Could you share more context about your situation?",
      clarificationTurn: 1,
      startedAt: new Date().toISOString(),
    };
    return { kind: "clarifying", draft };
  }

  // READY_FOR_DRAW
  return resolveReadyState(sessionId, trimmed, intentTag, "");
}

export async function completeReading(
  draft: SessionDraft,
  answer: string,
): Promise<ReadingResult> {
  const trimmedAnswer = answer.trim();

  const clarResult = await submitClarification(draft.sessionId, trimmedAnswer, draft.clarificationTurn);

  if (clarResult.status === "SAFE_FALLBACK_RETURNED") {
    return buildGenericInputFallback();
  }

  if (clarResult.status === "CLARIFYING") {
    // If we've hit the max turns, stop asking and force a draw regardless.
    if (draft.clarificationTurn >= MAX_CLARIFICATION_TURNS) {
      return resolveReadyState(draft.sessionId, draft.originalQuestion, draft.intentTag, trimmedAnswer);
    }
    const updatedDraft: SessionDraft = {
      ...draft,
      clarificationQuestionText:
        clarResult.next_clarifier_question ?? "Can you add more context?",
      clarificationTurn: draft.clarificationTurn + 1,
    };
    return { kind: "clarifying", draft: updatedDraft };
  }

  // READY_FOR_DRAW
  return resolveReadyState(draft.sessionId, draft.originalQuestion, draft.intentTag, trimmedAnswer);
}
