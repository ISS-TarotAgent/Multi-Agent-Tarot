import type { FormEvent } from "react";
import { useState } from "react";

interface QuestionComposerProps {
  onSubmit: (question: string, skipClarification: boolean) => Promise<void>;
  isSubmitting: boolean;
}

const SAMPLE_QUESTIONS = [
  "I am stuck between two job offers and cannot tell what to prioritize.",
  "我不确定是否该继续这段关系，想更清楚地了解自己真正的需求。",
  "My semester rhythm has fallen apart and I want to know how to rebuild momentum.",
  "我最近情绪很低落，感觉内耗严重，想知道怎么找回状态。",
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
            <strong>AI 引导澄清</strong>
            <span>让 AI 提问，帮你聚焦问题核心</span>
          </button>
          <button
            type="button"
            className={`mode-chip ${skipClarification ? "mode-chip--active" : ""}`}
            onClick={() => setSkipClarification(true)}
          >
            <strong>直接抽牌</strong>
            <span>跳过澄清，直接进入牌阵解读</span>
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
