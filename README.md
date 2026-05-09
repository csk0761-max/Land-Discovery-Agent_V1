# Land Discovery Agent

The Land Discovery Agent is a powerful tool for discovering and analyzing land parcels using AI and Geospatial data. It consists of a Fastapi/Python backend that drives the AI agents and tools, and a React-based frontend for the user interface.

## Project Structure

- `frontend/`: The React application providing the map and UI.
- `main.py` / `api.py`: FastAPI endpoints that interact with the AI agents.
- `*_agent.py` & `*_tools.py`: AI Agent implementations and their respective tools.

## Setup Instructions

### Environment Variables

You need to provide API keys for the AI agent to function properly. 

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
2. Open `.env` and fill in your actual API keys (e.g., `GEMINI_API_KEY`).

### Running the Backend

The backend is built in Python. Note that it depends on Earth Engine and other geospatial APIs. To run it:

1. Ensure you have the required dependencies (consider creating a `venv`):
```bash
pip install -r requirements.txt
```
2. Start the API server:
```bash
uvicorn api:app --reload
```

### Running the Frontend

The React UI is built with Vite.

1. In a new terminal, navigate to the `frontend` directory:
```bash
cd frontend
```
2. Install dependencies:
```bash
npm install
```
3. Run the development server:
```bash
npm run dev
```

The frontend will typically be accessible at `http://localhost:5173` and the backend at `http://localhost:8000`.

## GSS Feasibility Roadmap

This codebase can support a GSS technical feasibility workflow for scanned or selected grid substations. The recommended build order is:

1. Rules + OCR + extraction first
2. Agent-based explanation second
3. Prediction model third, once enough labeled cases exist

### Phase 1: Rules + OCR + Extraction

Goal: turn scanned GSS documents into structured technical facts and a deterministic feasibility score.

Core inputs:
- Scanned PDFs and images
- Single-line diagrams
- Utility letters, load reports, bay details, transformer schedules

Core outputs:
- Extracted fields such as voltage level, transformer MVA, spare capacity, bay count, bus rating, feeder loading, and protection notes
- Document confidence per field
- A rules-based feasibility score with pass/fail reasons

Suggested implementation:
- OCR layer: `pytesseract`, `pdfplumber`, `pymupdf`, or a cloud OCR provider
- Extraction layer: structured schema with validated fields
- Rules layer: deterministic engineering checks with explainable outcomes

### Phase 2: Agent-Based Explanation

Goal: use an LLM or CrewAI workflow to explain the structured result, not to replace the technical rules.

Agent responsibilities:
- Summarize the extracted GSS data
- Explain why the site is feasible or not feasible
- Highlight missing documents and ambiguous values
- Draft a technical note for human review

Recommended pattern:
- OCR and extraction run first
- Rules engine produces the primary score
- Agent receives the structured output and writes the explanation

### Phase 3: Prediction Model

Goal: learn from historical utility decisions after the system has collected enough labeled cases.

Training data needed:
- Input document fields
- Rule-based score
- Final human decision
- Actual utility approval / rejection outcome
- Reason codes for rejection

Model output:
- Probability that a GSS can evacuate the proposed solar capacity
- Confidence band
- Top contributing factors

### Practical Note

For production, the safest design is:
- rules for technical truth
- OCR for document understanding
- agent for explanation
- ML model for probability only after enough data is available

That keeps the system auditable and reduces the risk of a persuasive but incorrect answer.
