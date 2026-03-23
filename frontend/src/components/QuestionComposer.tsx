import type { FormEvent } from "react";
import { useState } from "react";

interface QuestionComposerProps {
  onSubmit: (question: string) => Promise<void>;
  isSubmitting: boolean;
}

const SAMPLE_QUESTIONS = [
  "I am stuck between two job opportunities and cannot tell what I should prioritize.",
  "I am unsure whether to keep investing in this relationship and want to understand my real need.",
  "My semester rhythm has fallen apart and I want to know how to rebuild momentum."
];

export function QuestionComposer({
  onSubmit,
  isSubmitting
}: QuestionComposerProps) {
  const [question, setQuestion] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextQuestion = question.trim();

    if (nextQuestion.length < 8) {
      setError("Please provide a slightly fuller question or situation.");
      return;
    }

    setError("");
    await onSubmit(nextQuestion);
  }

  return (
    <section className="panel hero-panel">
      <div className="panel-copy">
        <p className="eyebrow">Question Intake</p>
        <h1>Name the uncertainty before interpreting it</h1>
        <p>
          This frontend does not treat Tarot as a prediction engine. It uses Tarot as a structured reflection interface. Start with the question you want to work on.
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

        <button className="primary-button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Preparing clarification..." : "Start Clarification"}
        </button>
      </form>
    </section>
  );
}
