import { useDeferredValue, useMemo, useState } from "react";
import type { ReadingRecord } from "../types";

interface HistoryPanelProps {
  records: ReadingRecord[];
  onOpenRecord: (record: ReadingRecord) => void;
  onBack: () => void;
}

const INTENT_LABEL: Record<ReadingRecord["intentTag"], string> = {
  career: "Career",
  relationship: "Relationship",
  study: "Study",
  emotion: "Emotion",
  growth: "Growth"
};

export function HistoryPanel({
  records,
  onOpenRecord,
  onBack
}: HistoryPanelProps) {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);

  const filteredRecords = useMemo(() => {
    const keyword = deferredQuery.trim().toLowerCase();
    if (!keyword) {
      return records;
    }

    return records.filter((record) =>
      [record.title, record.question, record.reframedQuestion]
        .join(" ")
        .toLowerCase()
        .includes(keyword)
    );
  }, [records, deferredQuery]);

  return (
    <section className="panel">
      <div className="panel-copy">
        <p className="eyebrow">History</p>
        <h1>Reading History</h1>
        <p>
          Your past readings are stored locally in this browser. Up to 12 sessions are kept.
        </p>
      </div>

      <div className="history-toolbar">
        <input
          className="history-search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search by title, original question, or reframed prompt"
        />
        <button className="secondary-button" onClick={onBack}>
          Back to Flow
        </button>
      </div>

      {filteredRecords.length === 0 ? (
        <div className="empty-state">
          <strong>No matching history yet</strong>
          <p>Complete one reading first. The latest 12 sessions are stored locally.</p>
        </div>
      ) : (
        <div className="history-list">
          {filteredRecords.map((record) => (
            <article key={record.sessionId} className="history-card">
              <div>
                <span className="history-card__tag">{INTENT_LABEL[record.intentTag]}</span>
                <h2>{record.title}</h2>
                <p>{record.reframedQuestion}</p>
                <small>
                  {new Date(record.createdAt).toLocaleString("en-US", {
                    hour12: false
                  })}
                </small>
              </div>
              <button className="primary-button" onClick={() => onOpenRecord(record)}>
                Open Result
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
