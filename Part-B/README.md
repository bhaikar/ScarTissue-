# ScarTissue

ScarTissue learns from production incidents, failed fixes, verified resolutions, and engineer corrections. Approved lessons become deterministic deployment checks.

## Part B local run

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[test]"
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Tests

```bash
cd backend
pytest -q
```

Initial Part B build uses fake memory and diagnosis services. Part A replaces these seams with Hindsight and the selected LLM service.

## Safety

- Synthetic incident data only.
- Credentials stay in environment variables.
- Rules use allowlisted fields and operators.
- Unapproved rules never evaluate.
- No generated code, shell commands, or dynamic expressions execute.
- Current evidence stays separate from recalled historical evidence.
