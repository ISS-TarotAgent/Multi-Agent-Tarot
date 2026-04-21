import { useEffect, useMemo, useState } from "react";
import type { ReadingRecord } from "../types";

interface CardSpreadProps {
  reading: ReadingRecord | null;
  isLoading: boolean;
  onContinue: () => void;
}

export function CardSpread({ reading, isLoading, onContinue }: CardSpreadProps) {
  const [revealedCount, setRevealedCount] = useState(0);

  useEffect(() => {
    setRevealedCount(0);
  }, [reading?.sessionId]);

  const allRevealed = useMemo(
    () => (reading ? revealedCount >= reading.cards.length : false),
    [reading, revealedCount]
  );

  if (isLoading || !reading) {
    return (
      <section className="panel">
        <div className="panel-copy">
          <p className="eyebrow">Card Draw</p>
          <h1>Drawing the spread</h1>
          <p>
            The Draw & Interpret Agent mock is running. The interface will reveal the current, challenge, and action positions next.
          </p>
        </div>
        <div className="spread-grid">
          {[0, 1, 2].map((item) => (
            <article key={item} className="tarot-card tarot-card--loading">
              <span className="tarot-card__role">Tarot Card</span>
              <strong>Shuffling...</strong>
            </article>
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel-copy">
        <p className="eyebrow">Card Draw</p>
        <h1>The three cards are ready</h1>
        <p>
          This spread uses current, challenge, and action positions. Reveal each card to inspect its keywords and interpretation before moving to the final result.
        </p>
      </div>

      <div className="spread-grid">
        {reading.cards.map((card, index) => {
          const isRevealed = index < revealedCount;
          return (
            <article
              key={`${card.id}-${card.role}`}
              className={`tarot-card ${isRevealed ? "is-revealed" : ""}`}
              style={isRevealed ? { backgroundImage: card.accent } : undefined}
            >
              <span className="tarot-card__role">{card.role}</span>
              <strong>{isRevealed ? card.name : "Arcana"}</strong>
              <small>{isRevealed ? card.orientation : "Tap into uncertainty"}</small>
              {isRevealed ? (
                <>
                  {card.keywords.length > 0 && (
                    <div className="keyword-row">
                      {card.keywords.map((keyword) => (
                        <span key={keyword} className="keyword">
                          {keyword}
                        </span>
                      ))}
                    </div>
                  )}
                  <p>{card.interpretation}</p>
                  {card.cautionNote && (
                    <p className="card-caution">{card.cautionNote}</p>
                  )}
                  {card.reflectionPrompt && (
                    <p className="card-reflection">{card.reflectionPrompt}</p>
                  )}
                </>
              ) : (
                <p>The meaning of this position stays hidden until you actively reveal it.</p>
              )}
            </article>
          );
        })}
      </div>

      <div className="action-row">
        {!allRevealed ? (
          <button
            className="primary-button"
            onClick={() => setRevealedCount((count) => count + 1)}
          >
            Reveal card {revealedCount + 1}
          </button>
        ) : (
          <button className="primary-button" onClick={onContinue}>
            Open Final Result
          </button>
        )}
      </div>
    </section>
  );
}
