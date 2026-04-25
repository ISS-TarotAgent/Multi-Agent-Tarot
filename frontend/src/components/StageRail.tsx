import type { FlowStage } from "../types";

const STAGES: Array<{ id: Exclude<FlowStage, "history">; label: string; desc: string }> = [
  { id: "intake", label: "01 Intake", desc: "Describe your question or situation" },
  { id: "clarify", label: "02 Clarify", desc: "Add context so the agents can focus" },
  { id: "draw", label: "03 Draw", desc: "Reveal the three-card spread" },
  { id: "result", label: "04 Result", desc: "Read the synthesis and card guidance" },
  { id: "fallback", label: "Safety", desc: "Question could not be processed" },
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
        <h2>Multi-Agent Reading</h2>
        <p>
          Your question passes through a pipeline of AI agents — security, clarification, card draw, synthesis, and safety review.
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
