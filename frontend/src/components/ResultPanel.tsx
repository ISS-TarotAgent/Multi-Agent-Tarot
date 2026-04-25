import type { ReadingRecord } from "../types";

interface ResultPanelProps {
  reading: ReadingRecord;
  onRestart: () => void;
  onViewHistory: () => void;
}

export function ResultPanel({ reading, onRestart, onViewHistory }: ResultPanelProps) {
  const hasClarification = !!(reading.clarificationQuestion || reading.clarificationAnswer);

  return (
    <section className="panel result-panel">
      <div className="panel-copy">
        <p className="eyebrow">Final Reading</p>
        <h1>{reading.title}</h1>
        <div className="question-meta">
          <div className="question-meta__row">
            <span className="question-meta__label">Your question</span>
            <p className="question-meta__text">{reading.question}</p>
          </div>
          {reading.reframedQuestion !== reading.question && (
            <div className="question-meta__row">
              <span className="question-meta__label">Reframed as</span>
              <p className="question-meta__text question-meta__text--reframed">
                {reading.reframedQuestion}
              </p>
            </div>
          )}
        </div>
      </div>

      <div className="result-grid">
        <section className="result-block result-block--wide">
          <h2>Synthesis</h2>
          <p>{reading.synthesis}</p>
        </section>

        {hasClarification && (
          <section className="result-block result-block--wide clarification-context">
            <h2>Clarification Context</h2>
            {reading.clarificationQuestion && (
              <div className="clarification-context__row">
                <span className="clarification-context__label">Asked</span>
                <p>{reading.clarificationQuestion}</p>
              </div>
            )}
            {reading.clarificationAnswer && (
              <div className="clarification-context__row">
                <span className="clarification-context__label">You answered</span>
                <p>{reading.clarificationAnswer}</p>
              </div>
            )}
          </section>
        )}

        <section className="result-block result-block--wide">
          <h2>Card Readings</h2>
          <div className="result-card-grid">
            {reading.cards.map((card) => (
              <article key={`${card.id}-${card.role}`} className="result-card">
                <div className="result-card__header">
                  <span className="result-card__role">{card.role}</span>
                  <span className="result-card__arcana">
                    {card.arcana}{card.suit ? ` · ${card.suit}` : ""}
                  </span>
                </div>
                <strong className="result-card__name">{card.name}</strong>
                <small className="result-card__orientation">{card.orientation}</small>
                {card.keywords.length > 0 && (
                  <div className="keyword-row">
                    {card.keywords.map((kw) => (
                      <span key={kw} className="keyword">{kw}</span>
                    ))}
                  </div>
                )}
                <p className="result-card__interpretation">{card.interpretation}</p>
                {card.cautionNote && (
                  <p className="card-caution">{card.cautionNote}</p>
                )}
                {card.reflectionPrompt && (
                  <p className="card-reflection">{card.reflectionPrompt}</p>
                )}
              </article>
            ))}
          </div>
        </section>

        <section className="result-block">
          <h2>Action Suggestions</h2>
          <ul className="content-list">
            {reading.actionSuggestions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>

        <section className="result-block">
          <h2>Reflection Questions</h2>
          <ul className="content-list">
            {reading.reflectionQuestions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>

        <section className="result-block">
          <h2>Safety Review</h2>
          <div className="safety-box">
            <span className={`safety-badge safety-badge--${reading.safety.level}`}>
              {reading.safety.level.toUpperCase()}
            </span>
            <p>{reading.safety.note}</p>
            <small>{reading.safety.boundary}</small>
          </div>
        </section>

        <section className="result-block">
          <h2>Trace Log</h2>
          <ol className="trace-list">
            {reading.trace.map((step) => (
              <li key={step.label}>
                <strong>{step.label}</strong>
                <p>{step.detail}</p>
              </li>
            ))}
          </ol>
        </section>
      </div>

      <div className="action-row">
        <button className="secondary-button" onClick={onViewHistory}>
          Reading History
        </button>
        <button className="primary-button" onClick={onRestart}>
          Start New Reading
        </button>
      </div>
    </section>
  );
}
