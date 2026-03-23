# Agent Module

This package contains the orchestration layer for the Multi-Agent Tarot system.

## Layout

- `core/`: shared schemas, model gateway abstraction, and prompt-loading helpers (all
  contain TODOs describing the missing fields/logic).
- `nodes/`: LangGraph node stubs for Clarifier, Draw & Interpret, Synthesis, and
  Safety Guard agents. Each file documents the responsibilities left for the
  implementation owners.
- `workflows/`: entry point to assemble LangGraph graphs via `build_tarot_workflow()`.
- `tests/`: placeholder PyTest module to enforce future workflow coverage.

Concrete agent behavior, prompt wiring, LangGraph dependencies, and persistence
hooks are intentionally left as TODOs for the engineers implementing business
logic.
