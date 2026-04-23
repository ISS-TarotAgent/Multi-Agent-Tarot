import type { ReadingRecord } from "../types";

interface ResultPanelProps {
  reading: ReadingRecord;
  onRestart: () => void;
  onViewHistory: () => void;
}

export function ResultPanel({
  reading,
  onRestart,
  onViewHistory
}: ResultPanelProps) {
  return (
    <section className="panel result-panel">
      <div className="panel-copy">
        <p className="eyebrow">Final Reading</p>
        <h1>{reading.title}</h1>
        <p>{reading.reframedQuestion}</p>
      </div>

      <div className="result-grid">
        <section className="result-block result-block--wide">
          <h2>Synthesis</h2>
          <p>{reading.synthesis}</p>
        </section>

        <section className="result-block">
          <h2>Card Evidence</h2>
          <div className="mini-card-list">
            {reading.cards.map((card) => (
              <article key={`${card.id}-${card.role}`} className="mini-card">
                <span>{card.role}</span>
                <strong>{card.name}</strong>
                <small>{card.orientation}</small>
                {card.keywords.length > 0 && (
                  <div className="keyword-row">
                    {card.keywords.map((kw) => (
                      <span key={kw} className="keyword">{kw}</span>
                    ))}
                  </div>
                )}
                {card.reflectionPrompt && (
                  <p className="card-reflection">{card.reflectionPrompt}</p>
                )}
                {card.cautionNote && (
                  <p className="card-caution">{card.cautionNote}</p>
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
          Open History Page
        </button>
        <button className="primary-button" onClick={onRestart}>
          Start New Reading
        </button>
      </div>
    </section>
  );
}
