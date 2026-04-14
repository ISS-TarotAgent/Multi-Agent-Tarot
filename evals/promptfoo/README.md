# Promptfoo Regression Suite

This directory contains the phase 5 regression suite for the backend reading flow.

## Run

From the repository root:

```bash
npx promptfoo@latest eval -c evals/promptfoo/promptfooconfig.yaml
```

The provider now bootstraps `backend/.venv` site-packages automatically, so the suite can still import backend-only dependencies such as `langgraph` even when Promptfoo starts from a different Python runtime.

If your local Promptfoo setup still resolves the wrong interpreter on Windows, you can force the backend virtual environment explicitly:

```powershell
$env:PROMPTFOO_PYTHON = ".\\backend\\.venv\\Scripts\\python.exe"
npx promptfoo@latest eval -c evals/promptfoo/promptfooconfig.yaml
```

The provider uses FastAPI `TestClient` with an in-memory SQLite database, so it does not require a separately running backend service.
