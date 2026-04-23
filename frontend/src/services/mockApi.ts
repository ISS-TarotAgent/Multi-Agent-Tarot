import { buildCardSpread } from "../data/tarotCatalog";
import type {
  // OLD: ClarificationPrompt,  // removed — no longer exported from types.ts
  IntentTag,
  ReadingRecord,
  SessionDraft
} from "../types";

const STORAGE_KEY = "multi-agent-tarot-history";

// ClarificationPrompt type removed from types.ts; use inline shape here
const QUESTION_SET: Record<IntentTag, { id: string; question: string; helperText: string; placeholder: string }[]> = {
  career: [
    {
      id: "time-horizon",
      question: "Are you trying to solve a short-term choice or a long-term direction?",
      helperText:
        "Naming the time horizon helps the system separate immediate action from long-range planning.",
      placeholder: "Example: I care more about what I should do in the next three months."
    },
    {
      id: "core-pressure",
      question: "What are you most afraid of losing in this situation?",
      helperText:
        "The hidden fear often explains more than the visible goal.",
      placeholder:
        "Example: I am afraid of missing a better opportunity or proving I am not ready."
    },
    {
      id: "decision-window",
      question: "When does this decision actually need to move forward?",
      helperText:
        "If there is no real deadline, some of the pressure may only be self-imposed.",
      placeholder: "Example: I need to respond within two weeks."
    }
  ],
  relationship: [
    {
      id: "relationship-role",
      question:
        "Do you want to understand the other person more clearly, or understand your own boundary first?",
      helperText:
        "Relationship questions often mix curiosity about the other person with neglect of your own needs.",
      placeholder:
        "Example: I mostly want to know whether it still makes sense to stay emotionally invested."
    },
    {
      id: "recent-trigger",
      question: "What recent interaction stayed with you the most?",
      helperText:
        "A concrete event usually reveals more than a broad summary.",
      placeholder:
        "Example: A distant reply last week kept looping in my head."
    },
    {
      id: "desired-outcome",
      question: "Ideally, are you looking for clarity, repair, or distance?",
      helperText:
        "Naming the desired outcome makes the later advice more honest and practical.",
      placeholder:
        "Example: I want to know whether one serious conversation is still worth having."
    }
  ],
  study: [
    {
      id: "study-goal",
      question:
        "Are you more concerned about grades, applications, or the learning process itself?",
      helperText:
        "Different goals shift what the most useful advice should prioritize.",
      placeholder:
        "Example: My main concern is whether I am competitive enough for applications."
    },
    {
      id: "stuck-point",
      question:
        "Is the biggest blockage time management, comprehension difficulty, or execution?",
      helperText:
        "Pinpointing the bottleneck prevents the action advice from becoming generic.",
      placeholder:
        "Example: I make plans constantly, but the execution always collapses."
    },
    {
      id: "support-system",
      question: "What support resources do you already have available?",
      helperText:
        "Courses, peers, mentors, or tools can all become leverage if named clearly.",
      placeholder:
        "Example: I do have a study partner, but I am not using that support well."
    }
  ],
  emotion: [
    {
      id: "emotion-name",
      question: "If you had to name your recent emotional state, what would you call it?",
      helperText:
        "The more accurately you name the feeling, the more grounded the reflection can become.",
      placeholder:
        "Example: It feels like a constant tight anxiety, not an explosive breakdown."
    },
    {
      id: "body-signal",
      question:
        "In what situations or body signals do these feelings usually show up?",
      helperText:
        "Context and body signals often reveal the trigger faster than abstract analysis.",
      placeholder:
        "Example: I notice it most when I am alone at night and my chest feels tight."
    },
    {
      id: "needed-support",
      question:
        "What do you need most right now: rest, company, or a sense of control?",
      helperText:
        "Need identification is usually more useful than telling yourself to simply calm down.",
      placeholder:
        "Example: What I really need is a bit more control over my next steps."
    }
  ],
  growth: [
    {
      id: "focus-area",
      question: "Which area of life do you most want to move forward right now?",
      helperText:
        "Focusing the topic makes the later card spread easier to interpret.",
      placeholder:
        "Example: career, relationships, confidence, or personal rhythm."
    },
    {
      id: "current-pattern",
      question: "What pattern keeps repeating for you?",
      helperText:
        "Repeated patterns are often more valuable than one isolated event.",
      placeholder:
        "Example: I keep backing away right before I have to make a decision."
    },
    {
      id: "small-win",
      question:
        "If this reading helps, what specific change would you like to walk away with?",
      helperText:
        "A concrete hoped-for outcome makes the result more practical and testable.",
      placeholder:
        "Example: I want to leave with one small action I can actually do this week."
    }
  ]
};

function sleep(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function detectIntentTag(question: string): IntentTag {
  const text = question.toLowerCase();

  if (
    /(?:\u5de5\u4f5c|\u804c\u4e1a|\u5b9e\u4e60|offer|\u6c42\u804c|\u8df3\u69fd|career)/i.test(
      text
    )
  ) {
    return "career";
  }

  if (
    /(?:\u611f\u60c5|\u5173\u7cfb|\u559c\u6b22|\u604b\u7231|\u670b\u53cb|relationship)/i.test(
      text
    )
  ) {
    return "relationship";
  }

  if (
    /(?:\u5b66\u4e60|\u8003\u8bd5|\u7533\u8bf7|\u8bfe\u7a0b|\u7814\u7a76|study)/i.test(
      text
    )
  ) {
    return "study";
  }

  if (
    /(?:\u60c5\u7eea|\u7126\u8651|\u538b\u529b|\u96be\u8fc7|\u5185\u8017|emotion)/i.test(
      text
    )
  ) {
    return "emotion";
  }

  return "growth";
}

function buildTitle(question: string) {
  return question.length > 22 ? `${question.slice(0, 22)}...` : question;
}

function summarizeAnswers(answers: Record<string, string>) {
  return Object.values(answers)
    .filter(Boolean)
    .map((answer) => answer.trim())
    .join("; ");
}

function buildReframedQuestion(
  originalQuestion: string,
  intentTag: IntentTag,
  answers: Record<string, string>
) {
  const answerSummary = summarizeAnswers(answers);
  const prefix = {
    career: "How can I make a steadier career decision",
    relationship: "How can I see my real needs inside this relationship dynamic",
    study: "How can I rebuild momentum and structure in my study process",
    emotion: "How can I understand and hold my current emotions more gently",
    growth: "How can I turn a vague concern into a clearer next step"
  }[intentTag];

  return answerSummary
    ? `${prefix}: around "${originalQuestion}", with the added context "${answerSummary}".`
    : `${prefix}: around "${originalQuestion}".`;
}

function buildSynthesis(reframedQuestion: string, cards: ReadingRecord["cards"]) {
  const current = cards[0];
  const obstacle = cards[1];
  const action = cards[2];

  return `This spread suggests that the key issue is not finding one final answer immediately, but turning "${reframedQuestion}" into something testable. ${current.name} in the current position points to what you most need to acknowledge honestly. ${obstacle.name} in the challenge position suggests that the real drain may come from an unspoken concern or an avoided fact. ${action.name} in the action position recommends a smaller and more concrete move, so clarity comes from feedback rather than from endless internal simulation.`;
}

function buildActionSuggestions(cards: ReadingRecord["cards"]) {
  return [
    `Use ${cards[0].name} as a cue to write one precise sentence that defines the real question you are dealing with.`,
    `Use ${cards[1].name} to separate factual risk from imagined risk, and spend energy only on the first one.`,
    `Follow the direction of ${cards[2].name} by completing one minimum viable action within the next 72 hours.`
  ];
}

function buildReflectionQuestions(cards: ReadingRecord["cards"]) {
  return [
    cards[0].reflectionPrompt,
    "If you no longer had to figure everything out immediately, how would you redesign the next step?",
    "Which part of this reading feels the least comfortable, but also the most likely to be true?"
  ];
}

function buildSafetyNote(intentTag: IntentTag): ReadingRecord["safety"] {
  const note =
    intentTag === "emotion"
      ? "This result is designed for reflection and emotional organization. It is not a substitute for mental health or medical support."
      : "This result is designed for reflection and action planning, not for absolute predictions.";

  return {
    level: intentTag === "emotion" ? "medium" : "low",
    note,
    boundary:
      "If the issue involves persistent distress, risk of harm, or a professional high-stakes decision, seek real-world professional support first."
  };
}

// OLD: buildTrace(draft, answers: Record<string, string>, reframedQuestion)
// NEW: answers replaced by single answer string
function buildTrace(
  draft: SessionDraft,
  answer: string,
  reframedQuestion: string
) {
  return [
    {
      label: "Question Intake",
      detail: `Captured original question: ${draft.originalQuestion}`,
      status: "done" as const
    },
    {
      label: "Clarification",
      detail: `Detected intent: ${draft.intentTag}. Added context: ${answer.trim() || "none"}.`,
      status: "done" as const
    },
    {
      label: "Card Draw",
      detail:
        "Generated a three-card spread and attached interpretations for current, challenge, and action positions.",
      status: "done" as const
    },
    {
      label: "Synthesis",
      detail: `Reframed the topic into: ${reframedQuestion}`,
      status: "done" as const
    },
    {
      label: "Safety Review",
      detail:
        "Rewrote the output with a reflection-first tone and removed absolute or risky framing.",
      status: "done" as const
    }
  ];
}

function readHistory(): ReadingRecord[] {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return [];
  }

  try {
    return JSON.parse(raw) as ReadingRecord[];
  } catch {
    return [];
  }
}

function writeHistory(records: ReadingRecord[]) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
}

export async function loadHistory(): Promise<ReadingRecord[]> {
  await sleep(180);
  return readHistory().sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export async function startSession(question: string): Promise<SessionDraft> {
  await sleep(700);
  const intentTag = detectIntentTag(question);

  // OLD: returned normalizedQuestion and clarificationPrompts (hardcoded local set)
  // return {
  //   sessionId: crypto.randomUUID(),
  //   originalQuestion: question.trim(),
  //   normalizedQuestion: question.trim().replace(/\s+/g, " "),
  //   intentTag,
  //   clarificationPrompts: QUESTION_SET[intentTag],
  //   startedAt: new Date().toISOString()
  // };

  // NEW: mock returns single clarificationQuestionText to match real API shape
  return {
    sessionId: crypto.randomUUID(),
    readingId: crypto.randomUUID(),
    originalQuestion: question.trim(),
    intentTag,
    clarificationQuestionText: QUESTION_SET[intentTag]?.[0]?.question ?? "Could you share more context?",
    clarificationTurn: 1,
    startedAt: new Date().toISOString()
  };
}

// OLD: completeReading(draft, answers: Record<string, string>)
// NEW: completeReading(draft, answer: string) — single clarification answer
export async function completeReading(
  draft: SessionDraft,
  answer: string
): Promise<ReadingRecord> {
  await sleep(1200);

  // OLD: buildReframedQuestion used the full answers Record
  // const reframedQuestion = buildReframedQuestion(draft.originalQuestion, draft.intentTag, answers);
  const reframedQuestion = answer.trim()
    ? `${draft.originalQuestion} — additional context: ${answer.trim()}`
    : draft.originalQuestion;

  const cards = buildCardSpread(draft.intentTag, reframedQuestion);

  const record: ReadingRecord = {
    sessionId: draft.sessionId,
    title: buildTitle(draft.originalQuestion),
    question: draft.originalQuestion,
    reframedQuestion,
    intentTag: draft.intentTag,
    // OLD: clarificationAnswers: answers,
    clarificationAnswer: answer.trim(),
    cards,
    synthesis: buildSynthesis(reframedQuestion, cards),
    actionSuggestions: buildActionSuggestions(cards),
    reflectionQuestions: buildReflectionQuestions(cards),
    safety: buildSafetyNote(draft.intentTag),
    trace: buildTrace(draft, answer, reframedQuestion),
    createdAt: new Date().toISOString()
  };

  const nextHistory = [record, ...readHistory()].slice(0, 12);
  writeHistory(nextHistory);

  return record;
}
