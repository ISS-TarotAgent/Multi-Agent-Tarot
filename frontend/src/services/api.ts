/**
 * Real API service — calls POST /api/v1/readings (Phase-2 one-shot workflow).
 * startSession keeps local intent detection so the clarification UI still works.
 * completeReading merges clarification answers into the question and calls the backend.
 */
import type {
  ClarificationPrompt,
  IntentTag,
  ReadingRecord,
  SafetyReview,
  SessionDraft,
  TarotCardInsight,
  TraceStep,
} from "../types";

const STORAGE_KEY = "multi-agent-tarot-history";

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
  safety: { risk_level: "LOW" | "MEDIUM"; action_taken: string; review_notes: string | null };
  trace_summary: { event_count: number; warning_count: number; error_count: number };
  created_at: string;
  completed_at: string | null;
}

// ---------------------------------------------------------------------------
// Clarification question sets (kept local — backend handles its own internally)
// ---------------------------------------------------------------------------
const QUESTION_SET: Record<IntentTag, ClarificationPrompt[]> = {
  career: [
    {
      id: "time-horizon",
      question: "Are you trying to solve a short-term choice or a long-term direction?",
      helperText: "Naming the time horizon helps the system separate immediate action from long-range planning.",
      placeholder: "Example: I care more about what I should do in the next three months."
    },
    {
      id: "core-pressure",
      question: "What are you most afraid of losing in this situation?",
      helperText: "The hidden fear often explains more than the visible goal.",
      placeholder: "Example: I am afraid of missing a better opportunity or proving I am not ready."
    },
    {
      id: "decision-window",
      question: "When does this decision actually need to move forward?",
      helperText: "If there is no real deadline, some of the pressure may only be self-imposed.",
      placeholder: "Example: I need to respond within two weeks."
    }
  ],
  relationship: [
    {
      id: "relationship-role",
      question: "Do you want to understand the other person more clearly, or understand your own boundary first?",
      helperText: "Relationship questions often mix curiosity about the other person with neglect of your own needs.",
      placeholder: "Example: I mostly want to know whether it still makes sense to stay emotionally invested."
    },
    {
      id: "recent-trigger",
      question: "What recent interaction stayed with you the most?",
      helperText: "A concrete event usually reveals more than a broad summary.",
      placeholder: "Example: A distant reply last week kept looping in my head."
    },
    {
      id: "desired-outcome",
      question: "Ideally, are you looking for clarity, repair, or distance?",
      helperText: "Naming the desired outcome makes the later advice more honest and practical.",
      placeholder: "Example: I want to know whether one serious conversation is still worth having."
    }
  ],
  study: [
    {
      id: "study-goal",
      question: "Are you more concerned about grades, applications, or the learning process itself?",
      helperText: "Different goals shift what the most useful advice should prioritize.",
      placeholder: "Example: My main concern is whether I am competitive enough for applications."
    },
    {
      id: "stuck-point",
      question: "Is the biggest blockage time management, comprehension difficulty, or execution?",
      helperText: "Pinpointing the bottleneck prevents the action advice from becoming generic.",
      placeholder: "Example: I make plans constantly, but the execution always collapses."
    },
    {
      id: "support-system",
      question: "What support resources do you already have available?",
      helperText: "Courses, peers, mentors, or tools can all become leverage if named clearly.",
      placeholder: "Example: I do have a study partner, but I am not using that support well."
    }
  ],
  emotion: [
    {
      id: "emotion-name",
      question: "If you had to name your recent emotional state, what would you call it?",
      helperText: "The more accurately you name the feeling, the more grounded the reflection can become.",
      placeholder: "Example: It feels like a constant tight anxiety, not an explosive breakdown."
    },
    {
      id: "body-signal",
      question: "In what situations or body signals do these feelings usually show up?",
      helperText: "Context and body signals often reveal the trigger faster than abstract analysis.",
      placeholder: "Example: I notice it most when I am alone at night and my chest feels tight."
    },
    {
      id: "needed-support",
      question: "What do you need most right now: rest, company, or a sense of control?",
      helperText: "Need identification is usually more useful than telling yourself to simply calm down.",
      placeholder: "Example: What I really need is a bit more control over my next steps."
    }
  ],
  growth: [
    {
      id: "focus-area",
      question: "Which area of life do you most want to move forward right now?",
      helperText: "Focusing the topic makes the later card spread easier to interpret.",
      placeholder: "Example: career, relationships, confidence, or personal rhythm."
    },
    {
      id: "current-pattern",
      question: "What pattern keeps repeating for you?",
      helperText: "Repeated patterns are often more valuable than one isolated event.",
      placeholder: "Example: I keep backing away right before I have to make a decision."
    },
    {
      id: "small-win",
      question: "If this reading helps, what specific change would you like to walk away with?",
      helperText: "A concrete hoped-for outcome makes the result more practical and testable.",
      placeholder: "Example: I want to leave with one small action I can actually do this week."
    }
  ]
};

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

function mapCard(c: BackendCard, intentTag: IntentTag): TarotCardInsight {
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
  };
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

function mapToReadingRecord(
  res: BackendReadingResult,
  draft: SessionDraft,
  answers: Record<string, string>
): ReadingRecord {
  const synth = res.synthesis;
  const cards = res.cards.map((c) => mapCard(c, draft.intentTag));

  const actionSuggestions = synth.action_advice ? [synth.action_advice] : [];
  const reflectionQuestions = synth.reflection_question ? [synth.reflection_question] : [];

  return {
    sessionId: res.session_id,
    title: buildTitle(draft.originalQuestion),
    question: res.question.raw_question,
    reframedQuestion: res.question.normalized_question ?? draft.originalQuestion,
    intentTag: draft.intentTag,
    clarificationAnswers: answers,
    cards,
    synthesis: synth.summary ?? "",
    actionSuggestions,
    reflectionQuestions,
    safety: mapSafety(res.safety),
    trace: mapTrace(res.trace_summary),
    createdAt: res.created_at,
  };
}

// ---------------------------------------------------------------------------
// Public API (same signatures as mockApi.ts)
// ---------------------------------------------------------------------------
export async function loadHistory(): Promise<ReadingRecord[]> {
  return readHistory().sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export async function startSession(question: string): Promise<SessionDraft> {
  const intentTag = detectIntentTag(question);
  return {
    sessionId: crypto.randomUUID(),
    originalQuestion: question.trim(),
    normalizedQuestion: question.trim().replace(/\s+/g, " "),
    intentTag,
    clarificationPrompts: QUESTION_SET[intentTag],
    startedAt: new Date().toISOString(),
  };
}

export async function completeReading(
  draft: SessionDraft,
  answers: Record<string, string>
): Promise<ReadingRecord> {
  // Enrich question with clarification answers before sending to backend
  const answerContext = Object.entries(answers)
    .filter(([, v]) => v.trim())
    .map(([, v]) => v.trim())
    .join("; ");

  const enrichedQuestion = answerContext
    ? `${draft.originalQuestion} — additional context: ${answerContext}`
    : draft.originalQuestion;

  const response = await fetch("/api/v1/readings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: enrichedQuestion,
      locale: "zh-CN",
      spread_type: "THREE_CARD_REFLECTION",
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API error ${response.status}: ${text}`);
  }

  const data = (await response.json()) as BackendReadingResult;
  const record = mapToReadingRecord(data, draft, answers);

  const nextHistory = [record, ...readHistory()].slice(0, 12);
  writeHistory(nextHistory);

  return record;
}
