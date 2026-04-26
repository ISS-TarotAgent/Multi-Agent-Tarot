const NUMBER_WORDS: Record<string, string> = {
  ace: "ace",
  one: "ace",
  two: "2",
  three: "3",
  four: "4",
  five: "5",
  six: "6",
  seven: "7",
  eight: "8",
  nine: "9",
  ten: "10",
  page: "page",
  knight: "knight",
  queen: "queen",
  king: "king",
};

function normalizeLegacyCardId(cardId: string): string {
  const normalized = cardId.trim().toLowerCase();
  if (normalized.startsWith("major-")) return normalized;
  if (normalized.startsWith("the-")) return `major-${normalized.slice(4)}`;

  const minorMatch = normalized.match(
    /^(ace|one|two|three|four|five|six|seven|eight|nine|ten|page|knight|queen|king)-of-(cups|wands|swords|pentacles)$/
  );
  if (minorMatch) {
    return `${minorMatch[2]}-${NUMBER_WORDS[minorMatch[1]]}`;
  }

  return normalized;
}

export function getTarotCardImageUrl(cardId: string): string | undefined {
  const normalizedId = normalizeLegacyCardId(cardId);
  return `/tarot-cards/images/${normalizedId}.png`;
}
