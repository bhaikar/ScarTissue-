# ScarTissue Architecture

> **Status:** Hackathon MVP architecture  
> **Product:** ScarTissue — an organizational immune system for production incidents  
> **Primary technology requirement:** Hindsight persistent memory  
> **Audience:** Developers implementing the frontend, backend, memory layer, evaluation, and demo

---

## 1. Purpose

ScarTissue helps engineering teams learn from production incidents instead of repeatedly rediscovering the same operational lessons.

The system:

1. Accepts a simulated production alert with logs, metrics, and a recent deployment.
2. Retrieves relevant organizational experience from Hindsight.
3. Produces an evidence-linked diagnosis and recommended next actions.
4. Records engineer corrections and verified remediation outcomes.
5. Converts approved lessons into deterministic deployment checks.
6. Uses those checks to prevent risky deployments from repeating known failures.

The MVP is a **decision-support and prevention system**, not an autonomous remediation system.

### Core product claim

> ScarTissue learns what worked, what failed, and when a previous lesson should not be applied.

### Architectural consequences

- Historical memory must affect current decisions in a visible and testable way.
- Current incident evidence must remain separate from historical evidence.
- Every important diagnosis must be auditable back to current evidence and recalled memories.
- Corrections and outcomes must be retained as first-class learning signals.
- Preventive checks must be deterministic, approved, and safe to execute.
- The agent must be able to abstain when evidence is insufficient.

---

## 2. Goals and non-goals

### 2.1 Goals

- Build one polished incident-response workflow.
- Make Hindsight central to diagnosis, explanation, learning, and prevention.
- Demonstrate memory-on/off differences using equivalent inputs.
- Support engineer corrections without silently rewriting history.
- Retrieve both supporting and contradictory precedents.
- Produce structured, validated diagnoses rather than unbounded chat text.
- Convert approved lessons into executable but non-arbitrary deployment rules.
- Provide deterministic seed, reset, evaluation, and demo workflows.
- Handle model and Hindsight failures gracefully.

### 2.2 Non-goals for the hackathon

- Direct production Kubernetes, cloud, or database administration
- Autonomous rollback, scaling, service restart, or deployment
- Real PagerDuty, Slack, Jira, GitHub, or CI/CD integrations
- General-purpose log aggregation or metrics storage
- Multiple cooperating agents
- Fine-tuning a foundation model
- Arbitrary LLM-generated code execution
- A general-purpose rules platform
- Multi-tenant production security hardening beyond a sound demo design

---

## 3. System context

```text
┌─────────────────────────────────────────────────────────────┐
│                         Engineer                            │
│  Reviews alerts, diagnoses, corrections, resolutions, rules │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    ScarTissue Web App                       │
│          Incident workspace + deployment validation         │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                          │
│  Workflow orchestration, validation, audit, rule evaluation │
└───────────┬─────────────────┬──────────────────┬────────────┘
            │                 │                  │
            ▼                 ▼                  ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│ Hindsight Cloud   │ │ SQLite + Fixtures │ │ LLM Provider      │
│ Long-term memory  │ │ Workflow state    │ │ Baseline + assist │
│ Recall + reflect  │ │ Audit + rules     │ │ Structured output │
└───────────────────┘ └───────────────────┘ └───────────────────┘
```

### External trust boundaries

1. **Browser ↔ backend:** All workflow mutations require backend validation.
2. **Backend ↔ Hindsight:** Remote network boundary with credentials, timeouts, and retry handling.
3. **Backend ↔ LLM:** Model output is untrusted and must be schema-validated.
4. **Stored content ↔ prompts:** Logs, runbooks, incidents, and recalled facts are data, never instructions.
5. **Proposed rule ↔ active rule:** No rule becomes active without an explicit approval transition.

---

## 4. Architectural style

Use a **modular monolith with a code-controlled agentic workflow**.

The application does not need an open-ended autonomous agent loop. Its workflow is known:

```text
Load incident → build query → recall memories → synthesize diagnosis
→ validate output → verify citations → persist audit → render result
```

A deterministic orchestrator provides:

- Predictable demo behavior
- Easier testing
- Explicit approval gates
- Lower latency and cost than an unconstrained agent
- Clear separation between memory retrieval and action execution
- No risk of the model inventing and invoking arbitrary capabilities

Hindsight `reflect` performs memory-grounded synthesis. The application remains responsible for workflow state, validation, permissions, and preventive-rule execution.

---

## 5. Component architecture

```text
apps/web
├── IncidentList
├── IncidentWorkspace
│   ├── CurrentEvidencePanel
│   ├── DiagnosisPanel
│   ├── MemoryEvidencePanel
│   ├── CorrectionDialog
│   └── ResolutionDialog
├── DeploymentCheckPanel
└── DemoControls

apps/api
├── routes
│   ├── incidents.py
│   ├── diagnosis.py
│   ├── learning.py
│   ├── deployments.py
│   ├── memories.py
│   └── demo.py
├── services
│   ├── diagnosis_service.py
│   ├── learning_service.py
│   ├── prevention_service.py
│   ├── evaluation_service.py
│   └── demo_service.py
├── integrations
│   ├── hindsight_memory.py
│   └── llm_client.py
├── repositories
│   ├── incidents.py
│   ├── diagnoses.py
│   ├── rules.py
│   └── audit.py
├── models
│   ├── domain.py
│   ├── api.py
│   └── database.py
├── prevention
│   ├── schema.py
│   ├── operators.py
│   └── evaluator.py
└── prompts
    ├── diagnosis.py
    └── prevention.py
```

### 5.1 Frontend responsibilities

- Display incident evidence without modifying it.
- Invoke diagnosis with an explicit memory mode.
- Render structured diagnoses and citations.
- Provide correction, resolution, and approval controls.
- Show memory and rule provenance.
- Display loading, empty, error, stale, and insufficient-evidence states.
- Never hold Hindsight or LLM credentials.
- Never decide whether a deployment passes; display the backend result.

### 5.2 FastAPI responsibilities

- Validate API requests and enforce workflow transitions.
- Load authoritative current incident data.
- Build bounded memory queries.
- Invoke Hindsight and the baseline LLM.
- Validate model output and citation references.
- Persist diagnoses, corrections, outcomes, rules, and audit records.
- Execute deterministic preventive checks.
- Provide idempotent seed and reset operations.
- Return safe, actionable errors to the frontend.

### 5.3 Hindsight responsibilities

- Convert retained incident content into durable memories.
- Link entities and related facts.
- Consolidate observations over related experience.
- Retrieve semantic, keyword, graph, and temporal evidence through recall.
- Synthesize evidence-grounded answers through reflect.
- Expose fact/document identifiers for citations and debugging.

Hindsight is not responsible for local approval state, rule activation, current incident status, or transactional workflow correctness.

### 5.4 SQLite responsibilities

- Current incident workflow state
- Diagnosis snapshots
- Correction records
- Resolution records
- Proposed and approved preventive rules
- Deployment evaluation results
- Local audit events
- Hindsight document references
- Idempotency keys

### 5.5 Fixture responsibilities

- Provide realistic, synthetic incident data.
- Keep test inputs deterministic and reviewable.
- Preserve raw current evidence outside the LLM prompt builder.
- Provide safe and risky deployment manifests.
- Support negative-control incidents.

---

## 6. Data ownership and source of truth

| Data | Authoritative store | Copies allowed | Notes |
|---|---|---|---|
| Raw incident fixture | Repository JSON | SQLite projection | Fixture ID is stable |
| Current incident status | SQLite | Frontend view | Never infer status from memory |
| Current logs/metrics | Fixture/SQLite | Prompt excerpt | Current evidence remains separate |
| Historical lessons | Hindsight | Recall cache for debug only | Hindsight is the long-term memory |
| Diagnosis snapshot | SQLite | Frontend view | Stores model and memory provenance |
| Engineer correction | SQLite + Hindsight | Frontend view | Local transaction then verified retain |
| Verified resolution | SQLite + Hindsight | Frontend view | Requires outcome and evidence |
| Preventive rule | SQLite | Frontend view | Approval state is authoritative locally |
| Deployment result | SQLite | Frontend view | Produced by deterministic evaluator |
| API credentials | Environment/secret manager | None | Never persist in fixtures or browser |

### Dual-write policy

Corrections and resolutions involve SQLite and Hindsight. Avoid pretending this is one atomic transaction.

Recommended flow:

1. Validate request and idempotency key.
2. Commit a local record with `memory_status = pending`.
3. Retain the corresponding structured record in Hindsight.
4. On success, save the Hindsight document ID and set `memory_status = retained`.
5. On failure, retain the local pending record and expose a retry action.
6. Retry using the same idempotency key and stable document ID.

The UI must not display “learned” while the memory status is pending or failed.

---

## 7. Domain model

### 7.1 Incident state machine

```text
OPEN
  │
  ├──────────────► TRIAGING
  │                    │
  │                    ├────────► AWAITING_EVIDENCE
  │                    │                 │
  │                    │◄────────────────┘
  │                    │
  │                    ▼
  │               DIAGNOSED
  │                    │
  │                    ▼
  │               RESOLVED
  │                    │
  │                    ▼
  │          PREVENTION_PROPOSED
  │                    │
  │                    ▼
  │           PREVENTION_APPROVED
```

Rules:

- Diagnosis can run more than once; each run creates a new immutable snapshot.
- Resolution requires a remediation result and verification evidence.
- Corrections can be added after diagnosis or resolution.
- Resolving an incident does not automatically activate a preventive rule.
- Reopening is optional for the MVP; omit unless needed by a test scenario.

### 7.2 Preventive-rule state machine

```text
PROPOSED ──approve──► ACTIVE ──disable──► DISABLED
    │                   │
    └──reject──► REJECTED
```

Only `ACTIVE` rules participate in deployment evaluation. The model cannot directly approve, activate, disable, or delete a rule.

### 7.3 Core entities

#### Incident

```text
id: string
service: string
environment: string
severity: SEV1 | SEV2 | SEV3
status: IncidentStatus
started_at: datetime
resolved_at: datetime | null
summary: string
symptoms: string[]
metrics: Metric[]
log_entries: LogEntry[]
deployment: Deployment | null
created_at: datetime
updated_at: datetime
```

#### Diagnosis

```text
id: UUID
incident_id: string
memory_enabled: boolean
summary: string
confidence: low | medium | high
hypotheses: Hypothesis[]
recommended_actions: RecommendedAction[]
approaches_to_avoid: AvoidedApproach[]
missing_evidence: string[]
recalled_fact_ids: string[]
source_incident_ids: string[]
model_id: string
memory_bank_id: string | null
raw_structured_output: JSON
created_at: datetime
```

#### LearningRecord

```text
id: UUID
incident_id: string
kind: correction | resolution
content: JSON
hindsight_document_id: string | null
memory_status: pending | retained | failed
idempotency_key: string
created_by: string
created_at: datetime
updated_at: datetime
```

#### PreventiveRule

```text
id: string
name: string
description: string
status: proposed | active | rejected | disabled
condition: RuleCondition
source_incident_ids: string[]
source_learning_record_ids: UUID[]
approved_by: string | null
approved_at: datetime | null
created_at: datetime
updated_at: datetime
```

---

## 8. Hindsight memory architecture

### 8.1 Bank layout

For the MVP, use one bank:

```text
scar-tissue-demo
```

This supports cross-service operational learning. Use tags to preserve filtering options.

Production evolution could introduce one bank per organization while retaining shared organizational learning inside that bank. Avoid one bank per incident; that would prevent cross-incident learning.

### 8.2 Memory categories

| Category | Example | Retention trigger |
|---|---|---|
| Incident experience | Symptoms and deployment for INC-017 | Verified incident fixture or resolution |
| Failed action | Increasing pool worsened saturation | Verified attempt outcome |
| Successful action | Disabling batch retries restored service | Verified resolution |
| Applicability condition | Retry increase preceded connection saturation | Postmortem |
| Contradiction condition | Lock waits indicate another cause | Postmortem/correction |
| Engineer correction | Root cause was certificate rotation, not retries | Correction submission |
| Preventive lesson | Retry budgets required above five attempts | Approved learning record |

### 8.3 Tags and metadata

Suggested tags:

```text
org:demo
service:checkout
env:prod
```

Suggested metadata:

```json
{
  "incident_id": "INC-017",
  "service": "checkout",
  "environment": "prod",
  "severity": "SEV1",
  "root_cause_category": "retry_amplification",
  "record_kind": "postmortem"
}
```

Guidelines:

- Metadata values are strings.
- Put stable IDs in both metadata and human-readable content.
- Use consistent context labels across similar records.
- Use real event timestamps rather than seed time.
- Use organization scope for cross-service recall.
- Use service scope only when deliberately testing service-specific retrieval.

### 8.4 Document identity

Use stable IDs:

```text
seed:INC-017:postmortem
incident:INC-031:postmortem
incident:INC-031:correction:001
incident:INC-031:resolution:001
```

Hindsight document IDs support idempotent upsert behavior. A repeated seed operation must use the same ID.

Prefer separate correction documents over silently replacing the original postmortem. This preserves the learning timeline.

### 8.5 Retain pipeline

```text
Resolution or seed fixture
          │
          ▼
Structured postmortem renderer
          │
          ▼
Schema + required-field validation
          │
          ▼
Hindsight retain
  - stable document_id
  - consistent context
  - real timestamp
  - metadata + tags
  - synchronous for live learning
          │
          ▼
Save document ID + retained status locally
```

### 8.6 Recall pipeline

Construct a bounded query containing:

- Service and environment
- Primary symptoms
- Distinctive error signatures
- Relevant metric changes
- Recent deployment changes
- Current hypothesis, if the user supplied one

Do not include entire raw logs. Keep recall queries below Hindsight's documented limit.

Request:

- `world`, `experience`, and `observation` memories
- Source facts for observations
- High retrieval budget for the demo diagnosis
- Organization tag scope
- Bounded output tokens

Persist returned fact IDs and document IDs in the diagnosis audit record.

### 8.7 Reflect pipeline

Provide reflect with:

- Current incident evidence
- A request to compare relevant and contradictory precedents
- A strict response schema
- A request for supporting facts

Validate:

- Structured output exists and parses.
- Confidence is one of the allowed values.
- Every action is a recommendation, not a claimed execution.
- Cited incident IDs occur in current or retrieved evidence.
- Empty evidence produces low confidence rather than invented precedent.

### 8.8 Observation timing

Do not make the live demo depend on immediate observation consolidation. Synchronous retain verifies the retain operation, but the UI and diagnosis must still work using underlying world and experience facts.

Pre-seed historical incidents before the demo. Use the live retain to demonstrate a new correction or resolution, then verify it through direct fact recall.

---

## 9. Diagnosis sequence

```text
Engineer         Web          API         SQLite       Hindsight       LLM
   │              │            │              │              │             │
   │ Diagnose     │            │              │              │             │
   ├─────────────►│            │              │              │             │
   │              │ POST       │              │              │             │
   │              ├───────────►│              │              │             │
   │              │            │ Load current │              │             │
   │              │            ├─────────────►│              │             │
   │              │            │              │              │             │
   │              │            │ Memory on?   │              │             │
   │              │            ├──────────────┼─────────────►│             │
   │              │            │              │   recall     │             │
   │              │            │              │◄─────────────┤             │
   │              │            │              │   reflect    │             │
   │              │            │              │◄─────────────┤             │
   │              │            │              │              │             │
   │              │            │ Memory off: equivalent baseline request     │
   │              │            ├──────────────┼──────────────┼────────────►│
   │              │            │              │              │             │
   │              │            │ Validate schema + citations │             │
   │              │            │ Persist diagnosis snapshot  │             │
   │              │            ├─────────────►│              │             │
   │              │◄───────────┤              │              │             │
   │◄─────────────┤ Structured result         │              │             │
```

### Memory-off comparison requirements

Keep these identical:

- Incident and current evidence
- Model and generation settings
- Core instructions
- Response schema
- Validation rules

Only historical memory access changes. Store both outputs so the comparison is reproducible.

---

## 10. Learning sequence

```text
Diagnosis snapshot
       │
       ▼
Engineer correction or verified resolution
       │
       ▼
Backend validation + idempotency check
       │
       ▼
Local learning record: memory_status=pending
       │
       ▼
Render structured learning content
       │
       ▼
Hindsight retain with stable document ID
       │
       ├──── success ──► memory_status=retained
       │
       └──── failure ──► memory_status=failed + safe retry
       │
       ▼
Optional proposed preventive rule
       │
       ▼
Human approval required
```

A correction should identify:

- Which diagnosis or hypothesis was wrong
- The corrected fact
- Evidence supporting the correction
- The engineer's confidence
- Whether previous guidance should be narrowed or superseded

A resolution should identify:

- Action taken
- Outcome: succeeded, failed, partial
- Verification evidence
- Confirmed root cause
- Conditions for future applicability
- Conditions indicating a different cause

---

## 11. Prevention architecture

### 11.1 Why deterministic rules?

LLM output is appropriate for proposing lessons, but deployment validation must be reproducible and testable. A deterministic evaluator guarantees that the same rule and deployment always produce the same result.

### 11.2 MVP rule model

Support a deliberately small expression language:

```json
{
  "all": [
    {
      "field": "retry_attempts",
      "operator": ">",
      "value": 5
    },
    {
      "field": "retry_budget",
      "operator": "not_exists"
    }
  ]
}
```

Allowlisted fields for the MVP:

```text
service
retry_attempts
retry_budget
timeout_seconds
connection_pool_size
feature_flags.batch_retries
```

Allowlisted operators:

```text
eq
neq
gt
gte
lt
lte
exists
not_exists
```

Only support `all` initially. Add `any` or nesting only if a demo scenario needs it.

### 11.3 Rule evaluation

```text
Deployment manifest
       │
       ▼
Validate manifest schema
       │
       ▼
Load ACTIVE rules only
       │
       ▼
For each rule:
  - verify field allowlist
  - read typed values without eval
  - evaluate allowlisted operators
  - attach source incident evidence
       │
       ▼
PASS or BLOCKED + violations
```

### 11.4 Safety requirements

- Never use Python `eval`, `exec`, dynamic imports, or shell commands.
- Reject unknown fields, operators, and value types.
- Bound the number and complexity of rules.
- Require explicit human approval.
- Store rule provenance and approval identity.
- Return an explainable result for every violation.
- Test both a blocking fixture and a safe control fixture.

---

## 12. API design

### 12.1 Endpoints

```text
POST /api/demo/reset
GET  /api/health
GET  /api/incidents
GET  /api/incidents/{incident_id}

POST /api/incidents/{incident_id}/diagnoses
GET  /api/incidents/{incident_id}/diagnoses/{diagnosis_id}

POST /api/incidents/{incident_id}/corrections
POST /api/incidents/{incident_id}/resolution

POST /api/incidents/{incident_id}/preventive-rules
POST /api/preventive-rules/{rule_id}/approval

POST /api/deployments/evaluate
GET  /api/memories?incident_id=...
GET  /api/learning-records?incident_id=...
```

### 12.2 Diagnose request

```json
{
  "memory_enabled": true
}
```

### 12.3 Diagnose response

```json
{
  "diagnosis_id": "7a04...",
  "incident_id": "INC-101",
  "memory_enabled": true,
  "summary": "Retry amplification is the leading hypothesis.",
  "confidence": "medium",
  "hypotheses": [],
  "recommended_actions": [],
  "approaches_to_avoid": [],
  "missing_evidence": [],
  "memory_evidence": [
    {
      "fact_id": "fact_123",
      "document_id": "seed:INC-017:postmortem",
      "incident_id": "INC-017",
      "text": "...",
      "type": "experience"
    }
  ],
  "created_at": "2026-11-14T12:00:00Z"
}
```

### 12.4 Resolution request

```json
{
  "idempotency_key": "INC-101-resolution-v1",
  "root_cause": "Retry amplification after deploy-901",
  "action_taken": "Disabled batch retries and rolled back deploy-901",
  "outcome": "succeeded",
  "verification_evidence": [
    "Connection utilization returned below 60%",
    "Checkout p99 returned below 500ms for ten minutes"
  ],
  "applicability_conditions": [
    "Retries increased before saturation"
  ],
  "contradiction_conditions": [
    "Lock-wait evidence indicates a different cause"
  ]
}
```

### 12.5 Deployment evaluation response

```json
{
  "deployment_id": "deploy-901",
  "decision": "BLOCKED",
  "violations": [
    {
      "rule_id": "CHK-RETRY-001",
      "message": "retry_attempts is 20 and retry_budget is missing",
      "source_incident_ids": ["INC-017"]
    }
  ]
}
```

### 12.6 Error model

```json
{
  "error": {
    "code": "MEMORY_UNAVAILABLE",
    "message": "Historical memory is temporarily unavailable. Retry or run the baseline diagnosis.",
    "retryable": true,
    "request_id": "req_..."
  }
}
```

Suggested codes:

```text
INCIDENT_NOT_FOUND
INVALID_STATE_TRANSITION
VALIDATION_ERROR
MODEL_OUTPUT_INVALID
CITATION_VALIDATION_FAILED
MEMORY_UNAVAILABLE
MODEL_UNAVAILABLE
RULE_NOT_APPROVED
RULE_DEFINITION_INVALID
IDEMPOTENCY_CONFLICT
INTERNAL_ERROR
```

---

## 13. Frontend information architecture

### 13.1 Incident workspace

```text
┌──────────────────────────────────────────────────────────────┐
│ INC-101 · checkout · SEV1       [Memory ON/OFF] [Diagnose]   │
├──────────────────┬───────────────────────┬───────────────────┤
│ Current evidence │ Diagnosis             │ Memory evidence   │
│                  │                       │                   │
│ Symptoms         │ Summary + confidence  │ Recalled incidents│
│ Metrics          │ Hypotheses            │ Supporting facts  │
│ Logs             │ Current evidence      │ Contradictions    │
│ Deployment diff  │ Recommended actions   │ Learning timeline │
│                  │ Approaches to avoid   │                   │
│                  │ Missing evidence      │                   │
│                  │ [Correct] [Resolve]   │                   │
└──────────────────┴───────────────────────┴───────────────────┘
```

### 13.2 Required UI states

- Initial: incident loaded, no diagnosis
- Loading: diagnosis running with memory mode visible
- Success: validated diagnosis rendered
- Empty memory: no relevant precedent found
- Insufficient evidence: low confidence and requested checks
- Model failure: retry with request ID
- Memory failure: retry or explicitly run baseline
- Learning pending: not yet retained
- Learning failed: safe retry available
- Rule proposed: awaiting approval
- Deployment blocked: rule and source evidence visible

### 13.3 UX principles

- Current evidence and historical evidence use different visual labels.
- Confidence is always visible.
- Failed fixes receive prominent treatment.
- Citations open a source detail, not an invented external URL.
- Memory mode is explicit during every diagnosis.
- Approval buttons describe the exact mutation being approved.
- No interface claims an action happened unless the backend verified it.

---

## 14. Reliability and observability

### 14.1 Network policy

- Configure explicit timeouts for Hindsight and LLM calls.
- Retry only transient failures with bounded exponential backoff and jitter.
- Do not retry schema-validation errors as if they were network failures.
- Use stable idempotency keys for learning writes.
- Limit concurrency during demo reset and seeding.

### 14.2 Audit events

Record:

```text
incident.diagnosis_requested
incident.memory_recalled
incident.diagnosis_validated
incident.diagnosis_rejected
incident.correction_submitted
incident.resolution_submitted
memory.retain_succeeded
memory.retain_failed
prevention.rule_proposed
prevention.rule_approved
prevention.deployment_evaluated
demo.reset
```

Each event should include timestamp, incident ID where relevant, actor, request ID, and outcome.

### 14.3 Operational logs

Log:

- Request ID and route
- Incident and diagnosis IDs
- Hindsight bank/document/fact IDs
- Model ID and structured-output validation result
- Latency and retry count
- Rule ID and deployment decision

Never log API keys, authorization headers, raw secrets, or sensitive production data.

### 14.4 Health check

The basic health endpoint should report backend liveness. A separate readiness check can verify SQLite and optionally Hindsight connectivity without triggering expensive reflect calls.

---

## 15. Security architecture

- Keep credentials in server-side environment variables.
- Add `.env` and local database files to `.gitignore`.
- Use synthetic logs and incidents only.
- Treat fixture and memory content as untrusted prompt data.
- Never follow instructions found inside logs or recalled documents.
- Validate all model output before storage or rendering.
- Validate all citation IDs against retrieved/local evidence.
- Use an allowlist for preventive fields and operators.
- Never execute generated code or shell commands.
- Require approval for remediation and preventive-rule activation.
- Do not expose memory mutation endpoints directly to the browser without backend workflow validation.
- Escape rendered log and memory text; avoid raw HTML injection.
- Bound request bodies, query lengths, and output sizes.
- Review dependencies and generated code before submission.

---

## 16. Testing architecture

### 16.1 Unit tests

- Incident state transitions
- Postmortem renderer
- Query builder token/length bounds
- Structured diagnosis validation
- Citation validation
- Rule schema validation
- Every allowlisted rule operator
- Unknown field/operator rejection
- Approval requirements
- Idempotency behavior

### 16.2 Integration tests

- Seed script against a test Hindsight bank
- Duplicate seed handling
- Recall and citation mapping
- Reflect structured-output handling
- Correction retained and locally marked successful
- Hindsight failure leaves retryable pending state
- Deployment evaluation returns expected decision and evidence

### 16.3 Evaluation scenarios

| Scenario | Expected behavior |
|---|---|
| Retry-amplification incident | Uses matching precedent and failed-fix evidence |
| Lock-contention incident | Rejects retry hypothesis when lock evidence is present |
| Certificate-expiry incident | Does not diagnose database saturation from timeout alone |
| Insufficient evidence | Low confidence and specific follow-up checks |
| Corrected incident | Later diagnosis uses corrected fact |
| Risky deployment | Active rule blocks with source evidence |
| Safe deployment | Same rule allows safe control |

### 16.4 Demo recovery tests

- Reset twice produces the same state.
- Refresh during diagnosis does not corrupt workflow state.
- Duplicate resolution click does not duplicate memory.
- Malformed model response produces a recoverable error.
- Hindsight timeout does not activate any rule.
- Recorded backup follows the same scenario and claims.

---

## 17. Deployment topology

### Local development

```text
Browser → Vite dev server → FastAPI → SQLite
                               ├────→ Hindsight Cloud
                               └────→ LLM provider
```

### Demo deployment

- Frontend: static hosting
- Backend: one managed Python web service
- Database: persistent SQLite volume for a demo, or managed Postgres if already available
- Hindsight: Cloud
- Secrets: hosting provider secret configuration

Do not introduce Docker Compose, Kubernetes, Redis, Kafka, or a service mesh unless the team already has a working reason to use them.

### Rollback

- Pin application dependencies.
- Tag the known-good demo commit.
- Keep fixture versions in source control.
- Record the Hindsight bank and seed version.
- Preserve a backup video and screenshots.
- If a deployment fails, revert to the tagged application release and rerun the deterministic seed/reset process.

---

## 18. Performance and cost boundaries

- Cache incident fixture reads where useful, but do not cache mutable workflow state incorrectly.
- Do not resend the entire dataset to the model.
- Use recall to bound memory context.
- Use reflect only for diagnosis, not for rendering every page.
- Avoid repeated diagnosis calls from button double-clicks.
- Pre-seed historical incidents before the presentation.
- Keep raw logs short and representative in prompts; full fixtures remain available locally.
- Store model and memory latency for debugging.
- Reuse one model and schema for memory-on/off comparisons.

---

## 19. Key design decisions

### ADR-001: Controlled workflow instead of autonomous agent

**Decision:** Backend code orchestrates diagnosis and learning.  
**Reason:** Predictability, approval gating, testability, and lower implementation risk.

### ADR-002: Hindsight for long-term memory, SQLite for workflow state

**Decision:** Separate durable operational learning from transactional application state.  
**Reason:** Clear ownership and fewer consistency errors.

### ADR-003: One shared memory bank for the demo organization

**Decision:** Use one bank with tags.  
**Reason:** Enables cross-service learning while preserving scoped retrieval.

### ADR-004: Corrections are new records

**Decision:** Do not silently rewrite the original diagnosis history.  
**Reason:** Auditable learning and preservation of negative evidence.

### ADR-005: Preventive rules are deterministic

**Decision:** LLM proposes; human approves; allowlisted evaluator executes.  
**Reason:** Reproducibility and safety.

### ADR-006: Memory-off baseline differs only in memory access

**Decision:** Keep all other inputs and generation parameters equivalent.  
**Reason:** Makes the Hindsight contribution credible.

### ADR-007: No autonomous production action

**Decision:** Simulate incidents and deployment evaluation.  
**Reason:** Safe demo, smaller scope, and clear human control.

---

## 20. MVP completion criteria

The architecture is successfully implemented when:

1. A new incident can be diagnosed using Hindsight.
2. Supporting memories and source incident IDs are visible.
3. A similar but different incident does not receive the same unsupported diagnosis.
4. An engineer correction or verified resolution is retained successfully.
5. A later diagnosis changes because of that retained learning.
6. A proposed rule requires approval before activation.
7. An active deterministic rule blocks a risky deployment with evidence.
8. Memory-off and memory-on results can be compared fairly.
9. Failures, retries, reset, and idempotency have been tested.
10. The live demo and backup recording tell the same evidence-based story.

---

## References

- Hindsight documentation: https://hindsight.vectorize.io/
- Hindsight Python SDK: https://hindsight.vectorize.io/sdks/python
- Retain: https://hindsight.vectorize.io/developer/api/retain
- Recall: https://hindsight.vectorize.io/developer/api/recall
- Reflect: https://hindsight.vectorize.io/developer/api/reflect
