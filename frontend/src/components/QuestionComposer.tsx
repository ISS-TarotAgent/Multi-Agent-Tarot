import type { FormEvent } from "react";
import { useState } from "react";

interface QuestionComposerProps {
  onSubmit: (question: string, skipClarification: boolean) => Promise<void>;
  isSubmitting: boolean;
}

const SAMPLE_QUESTIONS = [
  "I am stuck between two job offers and cannot tell what to prioritize.",
  "I am unsure whether to keep investing in this relationship and want to understand my real needs more clearly.",
  "My semester rhythm has fallen apart and I want to know how to rebuild momentum.",
  "I have been feeling emotionally drained lately and want to know how to get back on track.",
];

export function QuestionComposer({ onSubmit, isSubmitting }: QuestionComposerProps) {
  const [question, setQuestion] = useState("");
  const [error, setError] = useState("");
  const [skipClarification, setSkipClarification] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextQuestion = question.trim();

    if (nextQuestion.length < 8) {
      setError("Please provide a slightly fuller question or situation.");
      return;
    }

    setError("");
    await onSubmit(nextQuestion, skipClarification);
  }

  return (
    <section className="panel hero-panel">
      <div className="panel-copy">
        <p className="eyebrow">Question Intake</p>
        <h1>Name the uncertainty before interpreting it</h1>
        <p>
          This system uses Tarot as a structured reflection interface, not a prediction engine.
          Start with the question or situation you want to work on.
        </p>
      </div>

      <form className="question-form" onSubmit={handleSubmit}>
        <label className="field-label" htmlFor="question">
          Your question
        </label>
        <textarea
          id="question"
          className="question-input"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Example: I keep going back and forth between staying in my internship path and applying for graduate school, and I cannot tell whether I need stability or growth more."
          rows={6}
        />
        {error ? <p className="field-error">{error}</p> : null}

        <div className="pill-row">
          {SAMPLE_QUESTIONS.map((sample) => (
            <button
              key={sample}
              type="button"
              className="pill-button"
              onClick={() => setQuestion(sample)}
            >
              {sample}
            </button>
          ))}
        </div>

        <div className="mode-row">
          <button
            type="button"
            className={`mode-chip ${!skipClarification ? "mode-chip--active" : ""}`}
            onClick={() => setSkipClarification(false)}
          >
            <strong>AI-Guided Clarification</strong>
            <span>Let AI ask follow-up questions to sharpen your focus.</span>
          </button>
          <button
            type="button"
            className={`mode-chip ${skipClarification ? "mode-chip--active" : ""}`}
            onClick={() => setSkipClarification(true)}
          >
            <strong>Draw Cards Directly</strong>
            <span>Skip clarification and go straight to the spread reading.</span>
          </button>
        </div>

        <button className="primary-button" type="submit" disabled={isSubmitting}>
          {isSubmitting
            ? "Evaluating your question…"
            : skipClarification
            ? "Draw Cards Now"
            : "Begin Reading"}
        </button>
      </form>
    </section>
  );
}
