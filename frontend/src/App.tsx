import { startTransition, useEffect, useState } from "react";
import { CardSpread } from "./components/CardSpread";
import { ClarificationPanel } from "./components/ClarificationPanel";
import { HistoryPanel } from "./components/HistoryPanel";
import { QuestionComposer } from "./components/QuestionComposer";
import { ResultPanel } from "./components/ResultPanel";
import { StageRail } from "./components/StageRail";
import { completeReading, loadHistory, startSession } from "./services/mockApi";
import type { FlowStage, ReadingRecord, SessionDraft } from "./types";

function App() {
  const [stage, setStage] = useState<FlowStage>("intake");
  const [previousStage, setPreviousStage] = useState<FlowStage>("intake");
  const [draft, setDraft] = useState<SessionDraft | null>(null);
  const [reading, setReading] = useState<ReadingRecord | null>(null);
  const [history, setHistory] = useState<ReadingRecord[]>([]);
  const [isQuestionSubmitting, setIsQuestionSubmitting] = useState(false);
  const [isClarificationSubmitting, setIsClarificationSubmitting] = useState(false);
  const [isReadingLoading, setIsReadingLoading] = useState(false);

  useEffect(() => {
    void refreshHistory();
  }, []);

  async function refreshHistory() {
    const records = await loadHistory();
    setHistory(records);
  }

  async function handleQuestionSubmit(question: string) {
    setIsQuestionSubmitting(true);

    try {
      const nextDraft = await startSession(question);
      setDraft(nextDraft);
      setReading(null);
      startTransition(() => setStage("clarify"));
    } finally {
      setIsQuestionSubmitting(false);
    }
  }

  async function handleClarificationSubmit(answers: Record<string, string>) {
    if (!draft) return;

    setIsClarificationSubmitting(true);
    setIsReadingLoading(true);
    startTransition(() => setStage("draw"));

    try {
      const nextReading = await completeReading(draft, answers);
      setReading(nextReading);
      await refreshHistory();
    } finally {
      setIsClarificationSubmitting(false);
      setIsReadingLoading(false);
    }
  }

  function handleRestart() {
    setDraft(null);
    setReading(null);
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

    return (
      <QuestionComposer
        onSubmit={handleQuestionSubmit}
        isSubmitting={isQuestionSubmitting}
      />
    );
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient--left" />
      <div className="ambient ambient--right" />

      <header className="topbar">
        <div>
          <p className="eyebrow">AI Tarot Multi-Agent System</p>
          <h1 className="topbar__title">Frontend Module</h1>
        </div>
        <div className="topbar__meta">
          <span>TypeScript UI</span>
          <span>Mock API</span>
          <span>Local History</span>
        </div>
      </header>

      <main className="workspace">
        <StageRail activeStage={stage} onOpenHistory={openHistory} />
        <section className="content-area">{renderStage()}</section>
      </main>
    </div>
  );
}

export default App;
