import type { FormEvent } from "react";
import { useState } from "react";
import type { SessionDraft } from "../types";

// OLD: interface ClarificationPanelProps {
//   draft: SessionDraft;
//   onSubmit: (answers: Record<string, string>) => Promise<void>;
//   onBack: () => void;
//   isSubmitting: boolean;
// }

// NEW: onSubmit now takes a single answer string (one question from backend Clarifier LLM)
interface ClarificationPanelProps {
  draft: SessionDraft;
  onSubmit: (answer: string) => Promise<void>;
  onBack: () => void;
  isSubmitting: boolean;
}

// OLD: createInitialAnswers built a Record<string, string> keyed by prompt.id
// for the multiple hardcoded prompts in draft.clarificationPrompts.
// function createInitialAnswers(draft: SessionDraft) {
//   return draft.clarificationPrompts.reduce<Record<string, string>>((accumulator, prompt) => {
//     accumulator[prompt.id] = "";
//     return accumulator;
//   }, {});
// }

export function ClarificationPanel({
  draft,
  onSubmit,
  onBack,
  isSubmitting
}: ClarificationPanelProps) {
  // OLD: const initialAnswers = useMemo(() => createInitialAnswers(draft), [draft]);
  // OLD: const [answers, setAnswers] = useState<Record<string, string>>(initialAnswers);
  // NEW: single answer string for the one question from the backend
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    // OLD: const nonEmptyCount = Object.values(answers).filter((value) => value.trim()).length;
    // OLD: if (nonEmptyCount < 2) {
    // OLD:   setError("Please answer at least two clarification prompts before moving on.");
    // OLD:   return;
    // OLD: }

    // NEW: single non-empty check
    if (!answer.trim()) {
      setError("Please provide an answer before continuing.");
      return;
    }

    setError("");
    // OLD: await onSubmit(Object.fromEntries(...));
    await onSubmit(answer.trim());
  }

  return (
    <section className="panel">
      <div className="panel-copy">
        {/* OLD: static eyebrow "Clarification" */}
        {/* NEW: shows current turn out of max (e.g. "Clarification · 1 / 3") */}
        <p className="eyebrow">Clarification · {draft.clarificationTurn} / 3</p>
        <h1>One more thing before your spread</h1>
        <p>
          The AI Clarifier Agent has reviewed your question and would like to know a bit more.
        </p>
      </div>

      <form className="clarification-form" onSubmit={handleSubmit}>
        {/* OLD: multiple prompt cards from draft.clarificationPrompts
          {draft.clarificationPrompts.map((prompt) => (
            <label key={prompt.id} className="clarification-card">
              <span className="clarification-card__title">{prompt.question}</span>
              <small>{prompt.helperText}</small>
              <textarea
                rows={3}
                value={answers[prompt.id]}
                placeholder={prompt.placeholder}
                onChange={(event) =>
                  setAnswers((current) => ({ ...current, [prompt.id]: event.target.value }))
                }
              />
            </label>
          ))}
        */}

        {/* NEW: single question card from backend */}
        <label className="clarification-card">
          <span className="clarification-card__title">{draft.clarificationQuestionText}</span>
          <small>Your answer will be used to refine the question before the cards are drawn.</small>
          <textarea
            rows={3}
            value={answer}
            placeholder="Share what feels most relevant..."
            onChange={(event) => setAnswer(event.target.value)}
          />
        </label>

        {error ? <p className="field-error">{error}</p> : null}

        <div className="action-row">
          <button type="button" className="secondary-button" onClick={onBack}>
            Back to Question
          </button>
          <button type="submit" className="primary-button" disabled={isSubmitting}>
            {isSubmitting ? "Generating spread..." : "Submit and Draw Cards"}
          </button>
        </div>
      </form>
    </section>
  );
}
