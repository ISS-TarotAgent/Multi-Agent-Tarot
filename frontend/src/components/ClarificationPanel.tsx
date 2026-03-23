import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import type { SessionDraft } from "../types";

interface ClarificationPanelProps {
  draft: SessionDraft;
  onSubmit: (answers: Record<string, string>) => Promise<void>;
  onBack: () => void;
  isSubmitting: boolean;
}

function createInitialAnswers(draft: SessionDraft) {
  return draft.clarificationPrompts.reduce<Record<string, string>>((accumulator, prompt) => {
    accumulator[prompt.id] = "";
    return accumulator;
  }, {});
}

export function ClarificationPanel({
  draft,
  onSubmit,
  onBack,
  isSubmitting
}: ClarificationPanelProps) {
  const initialAnswers = useMemo(() => createInitialAnswers(draft), [draft]);
  const [answers, setAnswers] = useState<Record<string, string>>(initialAnswers);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const nonEmptyCount = Object.values(answers).filter((value) => value.trim()).length;
    if (nonEmptyCount < 2) {
      setError("Please answer at least two clarification prompts before moving on.");
      return;
    }

    setError("");
    await onSubmit(
      Object.fromEntries(
        Object.entries(answers).map(([key, value]) => [key, value.trim()])
      )
    );
  }

  return (
    <section className="panel">
      <div className="panel-copy">
        <p className="eyebrow">Clarification</p>
        <h1>Clarify the question before the spread</h1>
        <p>
          The current intent is <strong>{draft.intentTag}</strong>. This screen simulates the Clarifier Agent by converting a broad concern into a more interpretable prompt.
        </p>
      </div>

      <form className="clarification-form" onSubmit={handleSubmit}>
        {draft.clarificationPrompts.map((prompt) => (
          <label key={prompt.id} className="clarification-card">
            <span className="clarification-card__title">{prompt.question}</span>
            <small>{prompt.helperText}</small>
            <textarea
              rows={3}
              value={answers[prompt.id]}
              placeholder={prompt.placeholder}
              onChange={(event) =>
                setAnswers((current) => ({
                  ...current,
                  [prompt.id]: event.target.value
                }))
              }
            />
          </label>
        ))}

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
