import type { IntentTag, TarotCardInsight } from "../types";

type Role = TarotCardInsight["role"];
type Orientation = TarotCardInsight["orientation"];

interface TarotSeed {
  id: string;
  name: string;
  arcana: "Major" | "Minor";
  suit?: string;
  uprightKeywords: string[];
  reversedKeywords: string[];
  lightMeaning: string;
  shadowMeaning: string;
  accent: string;
}

const CARD_LIBRARY: TarotSeed[] = [
  {
    id: "the-fool",
    name: "The Fool",
    arcana: "Major",
    uprightKeywords: ["fresh start", "curiosity", "openness"],
    reversedKeywords: ["hesitation", "impulse", "blurred focus"],
    lightMeaning:
      "A beginner's mindset may be more useful right now than forcing a perfect answer.",
    shadowMeaning:
      "Pressure to decide quickly may be pushing you away from what you actually want to test.",
    accent: "linear-gradient(135deg, #f6d365 0%, #fda085 100%)"
  },
  {
    id: "the-magician",
    name: "The Magician",
    arcana: "Major",
    uprightKeywords: ["agency", "resourcefulness", "expression"],
    reversedKeywords: ["scatter", "overreach", "surface control"],
    lightMeaning:
      "The most useful move is not waiting for better timing, but reorganizing what is already in your hands.",
    shadowMeaning:
      "A strong performance can hide the fact that the execution gap is still unresolved.",
    accent: "linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%)"
  },
  {
    id: "the-hermit",
    name: "The Hermit",
    arcana: "Major",
    uprightKeywords: ["reflection", "discernment", "pause"],
    reversedKeywords: ["withdrawal", "stalling", "avoidance"],
    lightMeaning:
      "A half-step back could help you see the pattern before you rush into action.",
    shadowMeaning:
      "Thinking for a little longer may actually be functioning as a polished form of delay.",
    accent: "linear-gradient(135deg, #cfd9df 0%, #e2ebf0 100%)"
  },
  {
    id: "strength",
    name: "Strength",
    arcana: "Major",
    uprightKeywords: ["calm courage", "stability", "gentle control"],
    reversedKeywords: ["fatigue", "self-strain", "overcompensation"],
    lightMeaning:
      "Real strength here is not suppressing emotion, but staying steady while emotion is present.",
    shadowMeaning:
      "If you keep acting as if everything is fine, unmet needs will surface somewhere else.",
    accent: "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)"
  },
  {
    id: "star",
    name: "The Star",
    arcana: "Major",
    uprightKeywords: ["repair", "hope", "long horizon"],
    reversedKeywords: ["idealization", "doubt", "wavering trust"],
    lightMeaning:
      "What you need may not be an instant solution, but a direction worth trusting for a while.",
    shadowMeaning:
      "If recovery is imagined as smooth and immediate, any friction may feel like failure.",
    accent: "linear-gradient(135deg, #5ee7df 0%, #b490ca 100%)"
  },
  {
    id: "two-of-cups",
    name: "Two of Cups",
    arcana: "Minor",
    suit: "Cups",
    uprightKeywords: ["connection", "mutuality", "response"],
    reversedKeywords: ["misread signals", "expectation gap", "emotional mismatch"],
    lightMeaning:
      "The central question may be less about who is right and more about whether needs are being expressed clearly.",
    shadowMeaning:
      "You may be decoding the other person's behavior without naming your own limits.",
    accent: "linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%)"
  },
  {
    id: "three-of-wands",
    name: "Three of Wands",
    arcana: "Minor",
    suit: "Wands",
    uprightKeywords: ["range", "planning", "outer opportunity"],
    reversedKeywords: ["delay", "timing drift", "unlaunched plan"],
    lightMeaning:
      "This is a good time to zoom out and ask what larger direction deserves your time.",
    shadowMeaning:
      "You may have spent so long planning the next step that the current step never truly began.",
    accent: "linear-gradient(135deg, #fddb92 0%, #d1fdff 100%)"
  },
  {
    id: "queen-of-swords",
    name: "Queen of Swords",
    arcana: "Minor",
    suit: "Swords",
    uprightKeywords: ["clarity", "boundary", "judgment"],
    reversedKeywords: ["defensiveness", "sharpness", "emotional cut-off"],
    lightMeaning:
      "Clear boundaries are not cold. They make both relationships and decisions more honest.",
    shadowMeaning:
      "If logic is used only to cut away uncertainty, the exhaustion beneath it will remain.",
    accent: "linear-gradient(135deg, #c3cfe2 0%, #c3cfe2 100%)"
  },
  {
    id: "six-of-pentacles",
    name: "Six of Pentacles",
    arcana: "Minor",
    suit: "Pentacles",
    uprightKeywords: ["resource balance", "exchange", "support"],
    reversedKeywords: ["uneven effort", "dependence", "transaction stress"],
    lightMeaning:
      "The issue may be less about trying harder and more about whether the resource balance is sustainable.",
    shadowMeaning:
      "When giving and receiving stay uneven for too long, resentment can quietly replace intention.",
    accent: "linear-gradient(135deg, #96fbc4 0%, #f9f586 100%)"
  },
  {
    id: "page-of-pentacles",
    name: "Page of Pentacles",
    arcana: "Minor",
    suit: "Pentacles",
    uprightKeywords: ["small trial", "learning", "grounded action"],
    reversedKeywords: ["delay", "distraction", "overpreparation"],
    lightMeaning:
      "A small executable move may create more clarity than another round of evaluation.",
    shadowMeaning:
      "Preparation may have become so complete that the actual starting point keeps moving away.",
    accent: "linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)"
  }
];

const ROLE_SUMMARY: Record<Role, string> = {
  Current: "This position highlights what is most active and honest in your current state.",
  Challenge:
    "This position points to the drain, bias, or unresolved friction shaping your experience.",
  Action:
    "This position suggests the next posture to test, not a rigid prediction or command."
};

const INTENT_HINT: Record<IntentTag, string> = {
  career: "career direction and decision-making",
  relationship: "relationship dynamics and boundaries",
  study: "study rhythm and goal management",
  emotion: "emotional regulation and inner stability",
  growth: "personal growth and direction-finding"
};

function sampleUniqueCards(count: number): TarotSeed[] {
  const pool = [...CARD_LIBRARY];
  const selected: TarotSeed[] = [];

  while (selected.length < count && pool.length > 0) {
    const index = Math.floor(Math.random() * pool.length);
    const [card] = pool.splice(index, 1);
    selected.push(card);
  }

  return selected;
}

export function buildCardSpread(
  intentTag: IntentTag,
  reframedQuestion: string
): TarotCardInsight[] {
  const roles: Role[] = ["Current", "Challenge", "Action"];

  return sampleUniqueCards(3).map((card, index) => {
    const orientation: Orientation = Math.random() > 0.45 ? "upright" : "reversed";
    const keywords =
      orientation === "upright" ? card.uprightKeywords : card.reversedKeywords;
    const meaning =
      orientation === "upright" ? card.lightMeaning : card.shadowMeaning;
    const role = roles[index];

    return {
      id: card.id,
      name: card.name,
      arcana: card.arcana,
      suit: card.suit,
      role,
      orientation,
      keywords,
      accent: card.accent,
      interpretation: `${card.name} appears in the ${role.toLowerCase()} position. Within the theme of ${INTENT_HINT[intentTag]}, it suggests that ${meaning} ${ROLE_SUMMARY[role]}`,
      reflectionPrompt: `If you break "${reframedQuestion}" into smaller tests, what is the first adjustment worth making?`
    };
  });
}
