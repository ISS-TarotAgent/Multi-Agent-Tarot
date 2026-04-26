import { startTransition, useEffect, useState } from "react";
import { CardSpread } from "./components/CardSpread";
import { ClarificationPanel } from "./components/ClarificationPanel";
import { HistoryPanel } from "./components/HistoryPanel";
import { QuestionComposer } from "./components/QuestionComposer";
import { ResultPanel } from "./components/ResultPanel";
import { StageRail } from "./components/StageRail";
import { completeReading, loadHistory, startSession } from "./services/api";
// NEW: FallbackInfo for the safety fallback stage
import type { FallbackInfo, FlowStage, ReadingRecord, SessionDraft } from "./types";

function App() {
  const [stage, setStage] = useState<FlowStage>("intake");
  const [previousStage, setPreviousStage] = useState<FlowStage>("intake");
  const [draft, setDraft] = useState<SessionDraft | null>(null);
  const [reading, setReading] = useState<ReadingRecord | null>(null);
  const [history, setHistory] = useState<ReadingRecord[]>([]);
  const [isQuestionSubmitting, setIsQuestionSubmitting] = useState(false);
  const [isClarificationSubmitting, setIsClarificationSubmitting] = useState(false);
  const [isReadingLoading, setIsReadingLoading] = useState(false);
  // NEW: holds safety fallback payload when backend returns SAFE_FALLBACK_RETURNED
  const [fallback, setFallback] = useState<FallbackInfo | null>(null);

  useEffect(() => {
    void refreshHistory();
  }, []);

  async function refreshHistory() {
    const records = await loadHistory();
    setHistory(records);
  }

  // OLD: handleQuestionSubmit called startSession() which was purely local (no HTTP).
  // It returned a SessionDraft with hardcoded clarificationPrompts and always went to "clarify".
  // async function handleQuestionSubmit(question: string) {
  //   setIsQuestionSubmitting(true);
  //   try {
  //     const nextDraft = await startSession(question);
  //     setDraft(nextDraft);
  //     setReading(null);
  //     startTransition(() => setStage("clarify"));
  //   } finally {
  //     setIsQuestionSubmitting(false);
  //   }
  // }

  // NEW: startSession() now calls POST /api/v1/readings immediately.
  // Three outcomes: clarifying (show clarification page), complete (skip to draw),
  // fallback (show safety fallback page).
  async function handleQuestionSubmit(question: string, skipClarification: boolean) {
    setIsQuestionSubmitting(true);
    try {
      const result = await startSession(question, skipClarification);
      setFallback(null);

      if (result.kind === "clarifying") {
        setDraft(result.draft);
        setReading(null);
        startTransition(() => setStage("clarify"));
      } else if (result.kind === "complete") {
        setDraft(null);
        setReading(result.record);
        await refreshHistory();
        setIsReadingLoading(false);
        startTransition(() => setStage("draw"));
      } else {
        // kind === "fallback"
        setFallback(result.info);
        startTransition(() => setStage("fallback"));
      }
    } finally {
      setIsQuestionSubmitting(false);
    }
  }

  // OLD: handleClarificationSubmit received answers: Record<string, string>
  // from the multi-question local clarification form.
  // async function handleClarificationSubmit(answers: Record<string, string>) {
  //   if (!draft) return;
  //   setIsClarificationSubmitting(true);
  //   setIsReadingLoading(true);
  //   startTransition(() => setStage("draw"));
  //   try {
  //     const nextReading = await completeReading(draft, answers);
  //     setReading(nextReading);
  //     await refreshHistory();
  //   } finally {
  //     setIsClarificationSubmitting(false);
  //     setIsReadingLoading(false);
  //   }
  // }

  // NEW: receives a single answer string from the backend-driven clarification question.
  // completeReading() also returns a ReadingResult — handles rare case where backend
  // still wants another round of clarification.
  async function handleClarificationSubmit(answer: string) {
    if (!draft) return;

    setIsClarificationSubmitting(true);
    setIsReadingLoading(true);

    try {
      const result = await completeReading(draft, answer);
      setFallback(null);

      if (result.kind === "complete") {
        setReading(result.record);
        await refreshHistory();
        setIsReadingLoading(false);
        startTransition(() => setStage("draw"));
      } else if (result.kind === "clarifying") {
        setDraft(result.draft);
        startTransition(() => setStage("clarify"));
      } else {
        // kind === "fallback"
        setFallback(result.info);
        startTransition(() => setStage("fallback"));
      }
    } finally {
      setIsClarificationSubmitting(false);
      setIsReadingLoading(false);
    }
  }

  function handleRestart() {
    setDraft(null);
    setReading(null);
    setFallback(null);
    startTransition(() => setStage("intake"));
  }

  function openHistory() {
    setPreviousStage(stage === "history" ? "intake" : stage);
    startTransition(() => setStage("history"));
  }

  function openResult(record: ReadingRecord) {
    setReading(record);
    startTransition(() => setStage("result"));
  }

  function renderStage() {
    if (stage === "clarify" && draft) {
      return (
        <ClarificationPanel
          draft={draft}
          onSubmit={handleClarificationSubmit}
          onBack={() => setStage("intake")}
          isSubmitting={isClarificationSubmitting}
        />
      );
    }

    if (stage === "draw") {
      return (
        <CardSpread
          reading={reading}
          isLoading={isReadingLoading}
          onContinue={() => setStage("result")}
        />
      );
    }

    if (stage === "result" && reading) {
      return (
        <ResultPanel
          reading={reading}
          onRestart={handleRestart}
          onViewHistory={openHistory}
        />
      );
    }

    if (stage === "history") {
      return (
        <HistoryPanel
          records={history}
          onOpenRecord={openResult}
          onBack={() => setStage(previousStage)}
        />
      );
    }

    // NEW: fallback stage — shown when backend returns SAFE_FALLBACK_RETURNED
    if (stage === "fallback" && fallback) {
      return (
        <section className="panel">
          <div className="panel-copy">
            <p className="eyebrow">Safety Review</p>
            <h1>This question couldn't be processed</h1>
            <p>{fallback.message}</p>
            <p className="fallback-meta">
              Risk level: <strong>{fallback.riskLevel}</strong>
              {" · "}
              Action: <strong>{fallback.actionTaken}</strong>
            </p>
            <p className="fallback-hint">
              If you'd like to continue, try rephrasing your question with a different focus.
            </p>
          </div>
          <div className="action-row">
            <button className="primary-button" onClick={handleRestart}>
              Ask a Different Question
            </button>
          </div>
        </section>
      );
    }

    return (
      <QuestionComposer
        onSubmit={handleQuestionSubmit}
        isSubmitting={isQuestionSubmitting}
      />
    );
  }

  return (
    <div className="app-shell">
      <div className="starfield" aria-hidden="true" />
      <div className="ambient ambient--left" />
      <div className="ambient ambient--right" />
      <div className="ritual-compass" aria-hidden="true">
        <span className="ritual-compass__mark ritual-compass__mark--north">N</span>
        <span className="ritual-compass__mark ritual-compass__mark--east">E</span>
        <span className="ritual-compass__mark ritual-compass__mark--south">S</span>
        <span className="ritual-compass__mark ritual-compass__mark--west">W</span>
      </div>

      <header className="topbar">
        <div>
          <p className="eyebrow">AI Tarot · Multi-Agent Oracle</p>
          <h1 className="topbar__title">The Oracle Room</h1>
        </div>
        <div className="topbar__meta">
          <span>Three-Card Spread</span>
          <span>Live Agents</span>
          <span>Private History</span>
        </div>
      </header>

      <main className="workspace">
        <StageRail activeStage={stage} onOpenHistory={openHistory} />
        <section className="content-area">
          <div key={stage} className="stage-surface">
            {renderStage()}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
