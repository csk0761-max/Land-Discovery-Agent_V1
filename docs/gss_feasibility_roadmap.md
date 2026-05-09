# GSS Feasibility Roadmap

This roadmap describes the staged implementation for a system that analyzes scanned or selected GSS documents and estimates whether a substation can evacuate solar power.

## Phase 1: Rules + OCR + Extraction

### Objective
Convert documents into structured engineering facts and a deterministic feasibility decision.

### Inputs
- Scanned PDFs
- Images of utility letters or drawings
- One-line diagrams
- Tabular load and bay schedules

### Outputs
- Structured GSS profile
- Field-level confidence scores
- Rule-based feasibility result
- Clear reasons for pass/fail

### Suggested pipeline
1. Document upload
2. OCR and layout parsing
3. Field extraction into a typed schema
4. Validation and unit normalization
5. Engineering rule checks
6. Final deterministic score

### Suggested rules
- Transformer spare capacity must exceed proposed solar export
- Busbar and feeder ratings must support expected export current
- Voltage level must match the intended interconnection design
- Protection scheme must be compatible with the export arrangement
- Missing critical data should reduce confidence and suppress automatic approval

### Suggested extracted fields
- GSS name
- Voltage level
- Transformer ratings
- Existing load
- Spare capacity
- Bay count
- Busbar rating
- Feeder rating
- Protection details
- Interconnection voltage
- Document source and OCR confidence

## Phase 2: Agent-Based Explanation

### Objective
Use an LLM or CrewAI workflow to explain the structured decision.

### Agent role
- Summarize extracted facts
- Explain the feasibility result
- Identify missing or conflicting data
- Draft an engineer-friendly technical note

### Important constraint
The agent should not be the primary decision-maker. It should only explain the output of the rules engine.

## Phase 3: Prediction Model

### Objective
Learn a probability of feasibility from historical cases.

### Training data
- Extracted features
- Rules-based score
- Human review outcome
- Final utility decision
- Reason codes for approval or rejection

### Model output
- Probability of evacuation feasibility
- Confidence score
- Feature contributions

### Model governance
- Keep the rules engine in place
- Use ML for ranking and probability only
- Retrain only with labeled historical cases

## Recommended Build Order
1. Define schema and rules
2. Add OCR and extraction
3. Expose a single API for analysis
4. Add explanation agent
5. Collect labeled decisions
6. Train the prediction model

