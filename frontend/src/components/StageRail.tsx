import type { FlowStage } from "../types";

const STAGES: Array<{ id: Exclude<FlowStage, "history">; label: string; desc: string }> = [
  { id: "intake", label: "01 Intake", desc: "Capture the original question" },
  { id: "clarify", label: "02 Clarify", desc: "Add context and constraints" },
  { id: "draw", label: "03 Draw", desc: "Reveal the three-card spread" },
  { id: "result", label: "04 Result", desc: "Review synthesis and guidance" }
];

interface StageRailProps {
  activeStage: FlowStage;
  onOpenHistory: () => void;
}

export function StageRail({ activeStage, onOpenHistory }: StageRailProps) {
  return (
    <aside className="stage-rail">
      <div className="stage-rail__intro">
        <p className="eyebrow">Tarot Reflection Flow</p>
        <h2>Multi-Agent Reflection Flow</h2>
        <p>
          The README defines five frontend pages. This sidebar turns them into one continuous single-page flow.
        </p>
      </div>

      <ol className="stage-rail__list">
        {STAGES.map((stage, index) => {
          const isActive = activeStage === stage.id;
          const isDone =
            STAGES.findIndex((item) => item.id === activeStage) > index ||
            activeStage === "history";

          return (
            <li
              key={stage.id}
              className={`stage-chip ${isActive ? "is-active" : ""} ${
                isDone ? "is-done" : ""
              }`}
            >
              <span>{stage.label}</span>
              <small>{stage.desc}</small>
            </li>
          );
        })}
      </ol>

      <button className="secondary-button secondary-button--full" onClick={onOpenHistory}>
        Open History Page
      </button>
    </aside>
  );
}
