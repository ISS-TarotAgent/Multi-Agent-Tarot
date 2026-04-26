import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import type { ReadingRecord } from "../types";
import { getTarotCardImageUrl } from "../utils/tarotCardImages";

interface CardSpreadProps {
  reading: ReadingRecord | null;
  isLoading: boolean;
  onContinue: () => void;
}

export function CardSpread({ reading, isLoading, onContinue }: CardSpreadProps) {
  const [revealedCount, setRevealedCount] = useState(0);
  const [flippingIndex, setFlippingIndex] = useState<number | null>(null);
  const revealTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (revealTimerRef.current !== null) {
      window.clearTimeout(revealTimerRef.current);
    }
    setRevealedCount(0);
    setFlippingIndex(null);
  }, [reading?.sessionId]);

  useEffect(() => {
    return () => {
      if (revealTimerRef.current !== null) {
        window.clearTimeout(revealTimerRef.current);
      }
    };
  }, []);

  const allRevealed = useMemo(
    () => (reading ? revealedCount >= reading.cards.length : false),
    [reading, revealedCount]
  );

  function revealNextCard() {
    if (!reading || flippingIndex !== null || allRevealed) {
      return;
    }

    const nextIndex = revealedCount;
    setFlippingIndex(nextIndex);

    revealTimerRef.current = window.setTimeout(() => {
      setRevealedCount((count) => count + 1);
      setFlippingIndex(null);
      revealTimerRef.current = null;
    }, 860);
  }

  if (isLoading || !reading) {
    return (
      <section className="panel">
        <div className="panel-copy">
          <p className="eyebrow">Card Draw</p>
          <h1>Drawing the spread</h1>
          <p>
            The Draw & Interpret Agent is selecting and interpreting your three cards. The current, challenge, and action positions will be ready to reveal shortly.
          </p>
        </div>
        <div className="spread-grid">
          {[0, 1, 2].map((item) => (
            <article key={item} className="tarot-card tarot-card--loading">
              <div className="tarot-card__stage">
                <div className="tarot-card__frame">
                  <div className="tarot-card__back">
                    <span className="tarot-card__sigil" />
                    <span className="tarot-card__role">Tarot Card</span>
                    <strong>Shuffling...</strong>
                  </div>
                </div>
              </div>
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
          const isFlipping = index === flippingIndex;
          const imageUrl = getTarotCardImageUrl(card.id);
          return (
            <article
              key={`${card.id}-${card.role}`}
              className={`tarot-card ${isRevealed ? "is-revealed" : ""} ${
                isFlipping ? "is-flipping" : ""
              } ${
                card.orientation === "reversed" ? "is-reversed" : ""
              }`}
              style={{ "--card-accent": card.accent } as CSSProperties}
              aria-label={`${card.role} card ${isRevealed ? card.name : "hidden"}`}
            >
              <div className="tarot-card__stage">
                <div className="tarot-card__frame">
                  <div className="tarot-card__back" aria-hidden={isRevealed || isFlipping}>
                    <span className="tarot-card__sigil" />
                    <span className="tarot-card__role">{card.role}</span>
                    <strong>Unrevealed</strong>
                    <small>Drawn into position</small>
                  </div>

                  <div className="tarot-card__face" aria-hidden={!isRevealed && !isFlipping}>
                    <div className="tarot-card__image-shell">
                      {imageUrl ? (
                        <img
                          className="tarot-card__image"
                          src={imageUrl}
                          alt={`${card.name} tarot card`}
                        />
                      ) : (
                        <div className="tarot-card__image tarot-card__image--fallback">
                          <span>{card.name}</span>
                        </div>
                      )}
                      <span className="tarot-card__position">{card.role}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div
                className={`tarot-card__details ${isRevealed ? "is-visible" : ""}`}
                aria-hidden={!isRevealed}
              >
                <div className="tarot-card__details-inner">
                  <div className="tarot-card__content">
                    <div className="tarot-card__meta">
                      <span className="tarot-card__role">{card.role}</span>
                      <span className="tarot-card__arcana">
                        {card.arcana}{card.suit ? ` · ${card.suit}` : ""}
                      </span>
                    </div>
                    <strong className="tarot-card__name">{card.name}</strong>
                    <small className="tarot-card__orientation">{card.orientation}</small>
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
                  </div>
                </div>
              </div>

              <p
                className={`tarot-card__hidden-hint ${
                  isFlipping || isRevealed ? "is-hidden" : ""
                }`}
              >
                Reveal to inspect this card's name, orientation, and reading.
              </p>
            </article>
          );
        })}
      </div>

      <div className="action-row">
        {!allRevealed ? (
          <button
            className="primary-button"
            onClick={revealNextCard}
            disabled={flippingIndex !== null}
          >
            {flippingIndex !== null ? "Revealing..." : `Reveal card ${revealedCount + 1}`}
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
