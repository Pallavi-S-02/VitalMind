# MedAssist AI — Detailed Implementation Plan

> **Based on:** `CLAUDE.md` PRD  
> **Agent Framework:** LangGraph  
> **Total Timeline:** ~30 weeks across 6 phases  

---

## Suggested Application Names

1. **VitalMind** — Conveys AI intelligence applied to vital health decisions; clean, memorable, clinical.
2. **ClaraMed** — "Clara" suggests clarity and care; feels approachable for both patients and clinicians.
3. **PulseIQ** — Evokes real-time monitoring and intelligent inference; modern health-tech branding.
4. **NexaCare** — "Nexa" (next/connected) + Care; signals an advanced, connected care platform.
5. **AegisHealth** — Aegis means shield/protection; conveys the safety and guardian role of the system.

---

## Phase 1 — Foundation (Weeks 1–4)

### Step 1: Repository & Project Scaffolding

Set up the monorepo structure exactly as defined in the PRD's directory tree.

- Create the root `medassist-ai/` directory with `Makefile`, `.github/workflows/` (ci.yml, cd-staging.yml, cd-production.yml, security-scan.yml).
- Initialize the `frontend/` directory as a **Next.js 14+ App Router** project with TypeScript strict mode, Tailwind CSS 3+, and shadcn/ui.
- Initialize the `backend/` directory as a **Python 3.11+ Flask 3+** project with a `requirements.txt` and `requirements-dev.txt`.
- Set up `infrastructure/` directory with placeholder Terraform modules and Kubernetes manifests.
- Create root `.env.example` mirroring all environment variables documented in the PRD (Section 10).
- Set up `.gitignore` for both Python and Node.js.
- Add a `CLAUDE.md` at the root for AI assistant context.

### Step 2: Docker Compose (Development Environment)

Create `docker-compose.yml` to spin up all infrastructure services locally.

- Services to configure: `postgres:16`, `redis:7`, `influxdb:2`, `elasticsearch:8`, `minio` (S3-compatible), `kibana`, `grafana`, `prometheus`.
- Define named volumes and health checks for each service.
- Expose ports as documented: Postgres 5432, Redis 6379, InfluxDB 8086, Elasticsearch 9200, MinIO 9000/9001.
- Add a `docker-compose.prod.yml` override for production-specific settings (no exposed ports, stricter networking).

### Step 3: Database Schema & Migrations (Backend)

Define all SQLAlchemy models and generate the initial Alembic migration.

- Create `backend/app/models/` with all model files: `user.py`, `patient.py`, `doctor.py`, `vitals.py`, `report.py`, `medication.py`, `appointment.py`, `symptom_session.py`, `care_plan.py`, `notification.py`, `audit_log.py`, `device.py`, `conversation.py`, `alert.py`.
- Model priorities (implement in this order):
  1. `user.py` — User, Role, Permission with RBAC relationships.
  2. `patient.py` — PatientProfile, MedicalHistory, Allergies.
  3. `doctor.py` — DoctorProfile, Specializations, Availability.
  4. `appointment.py` — Appointment with FK to patient and doctor.
  5. `medication.py` — Medication, Prescription with FK to patient/doctor.
  6. `report.py` — MedicalReport with S3 reference, analysis status.
  7. `symptom_session.py` — SymptomSession, SymptomEntry with FK to patient.
  8. `vitals.py` — VitalsReading with FK to patient and device; InfluxDB sync metadata.
  9. `device.py` — IoTDevice registry with FK to patient.
  10. `care_plan.py` — CarePlan, CareGoal, Milestone.
  11. `conversation.py` — ConversationLog for chat and voice sessions.
  12. `alert.py` — MonitoringAlert with severity, escalation chain, status.
  13. `notification.py` — NotificationRecord with channel type and delivery status.
  14. `audit_log.py` — AuditLog for every PHI access (HIPAA).
- Add PHI encryption utility in `backend/app/utils/encryption.py` using AES-256. Apply at model level for sensitive fields.
- Run `flask db init` and `flask db migrate` to generate the initial migration.
- Write `backend/scripts/seed_db.py` to populate test users (admin, doctor, patient roles).

### Step 4: Authentication System (Backend)

Implement JWT-based auth with RBAC.

- Create `backend/app/api/v1/auth.py` with endpoints: `POST /register`, `POST /login`, `POST /refresh`, `POST /logout`, `POST /forgot-password`, `POST /verify-email`.
- Implement `backend/app/services/auth_service.py` with token generation, refresh logic, and email verification flow.
- Create `backend/app/middleware/auth_middleware.py` with JWT validation decorator and role-guard decorator (`@require_role(['doctor', 'admin'])`).
- Implement RBAC: roles are `patient`, `doctor`, `nurse`, `admin`. Permissions are resource-level (`read:patient_records`, `write:prescriptions`, etc.).
- Integrate OAuth2 for social login (optional at this stage, scaffold the flow).
- Write unit tests in `backend/tests/unit/test_services/test_auth_service.py`.

### Step 5: Core Backend Services & API Scaffolding

Build out the service-layer pattern and register all API blueprints.

- Create `backend/app/services/` files: `patient_service.py`, `doctor_service.py`, `appointment_service.py`, `medication_service.py`, `report_service.py`.
- Register all blueprints in `backend/app/api/v1/__init__.py` for routes: `/auth`, `/patients`, `/doctors`, `/appointments`, `/medications`, `/reports`, `/health`.
- Implement global middleware: `cors.py`, `rate_limiter.py`, `request_logger.py` (structlog), `error_handler.py`, `hipaa_audit.py`.
- Set up Flasgger (Swagger/OpenAPI 3.0) with base config and document the auth endpoints.
- Create `backend/app/integrations/openai_client.py` — a singleton wrapper around the OpenAI SDK with retry logic and error handling.
- Create clients: `pinecone_client.py`, `influxdb_client.py`, `elasticsearch_client.py`, `s3_client.py`.

### Step 6: Frontend Auth & Shell UI

Build the Next.js authentication flows and the application shell.

- Configure NextAuth.js with JWT strategy; connect to the Flask `/api/v1/auth` endpoints as a custom credentials provider.
- Build auth pages: `(auth)/login/page.tsx`, `(auth)/register/page.tsx`, `(auth)/forgot-password/page.tsx`, `(auth)/verify-email/page.tsx`.
- Build the root `layout.tsx` with Zustand store providers and React Query (`TanStack Query`) client setup.
- Create the shared navigation components: `Sidebar`, `TopNav`, `UserAvatarMenu`, `NotificationBell` (non-functional shell).
- Implement three layout wrappers: `(patient)/layout.tsx`, `(doctor)/layout.tsx`, `(admin)/layout.tsx`, each with role-guarded route protection.
- Build a basic `(patient)/dashboard/page.tsx` and `(doctor)/dashboard/page.tsx` as placeholder pages with skeleton loaders.
- Set up Zod schemas in `src/lib/schemas/` for all API responses.
- Configure `next-intl` for internationalization with English as the default locale.

---

## Phase 2 — Core AI Features (Weeks 5–10)

### Step 7: LangGraph Agent Infrastructure

Set up the LangGraph-based agent framework — the foundation all 7 agents will build upon.

- Install LangGraph and LangChain in the backend. Add to `requirements.txt`.
- Create `backend/app/agents/base_agent.py`: a base class encapsulating LangGraph `StateGraph` construction, tool binding, memory integration, and a standard `invoke(input, config)` interface.
- Define a shared `AgentState` TypedDict in `base_agent.py` with fields: `messages`, `patient_id`, `session_id`, `intent`, `context`, `tool_outputs`, `final_response`.
- Create `backend/app/agents/memory/context_manager.py`: manages short-term conversation state in Redis (keyed by `session_id`).
- Create `backend/app/agents/memory/knowledge_store.py`: wraps Pinecone for semantic search over medical knowledge embeddings.
- Create `backend/app/agents/memory/patient_memory.py`: retrieves and caches patient-specific context (history, allergies, medications) from PostgreSQL + Redis.
- Create `backend/app/agents/prompts/system_prompts.py` with system prompt templates for all 7 agents.
- Write `backend/scripts/seed_knowledge_base.py` to chunk, embed (via `text-embedding-3-large`), and upsert a starter medical knowledge corpus into Pinecone.

### Step 8: Agent Orchestrator (LangGraph)

Build the central router that dispatches requests to specialist agents.

- Create `backend/app/agents/orchestrator.py` as a LangGraph `StateGraph`.
- Define nodes:
  - `classify_intent` — calls GPT-4o with function calling to classify the incoming request into one of 7 intents (symptom_check, report_analysis, triage, voice_interaction, drug_interaction, monitoring_query, care_plan).
  - `route_to_agent` — a conditional edge function that maps intent to the appropriate specialist agent node.
  - `aggregate_context` — fetches patient memory and injects it into the state before routing.
  - `synthesize_response` — merges outputs from parallel agent invocations if multiple agents were called.
  - `format_output` — converts agent output to the standardized API response format.
- Add edges: `START → aggregate_context → classify_intent → route_to_agent → [specialist agents] → synthesize_response → format_output → END`.
- Expose the orchestrator via a service: `backend/app/services/agent_orchestrator_service.py`.
- Connect to `backend/app/api/v1/chat.py` endpoint: `POST /api/v1/chat/message`.

### Step 9: Symptom Analyst Agent (LangGraph)

Build the multi-turn symptom interview and differential diagnosis agent.

- Create `backend/app/agents/symptom_analyst.py` as a LangGraph `StateGraph`.
- Define the graph nodes:
  - `gather_initial_symptoms` — first turn; prompts patient for primary complaint.
  - `ask_followup_questions` — dynamically generates targeted follow-up questions based on reported symptoms using GPT-4o.
  - `search_medical_kb` — tool node calling `search_medical_knowledge_base` (RAG via Pinecone).
  - `query_patient_history` — tool node fetching prior diagnoses, allergies, medications.
  - `calculate_urgency` — tool node for rule-based urgency scoring; if score ≥ critical threshold, route to Triage Agent.
  - `generate_differential` — structured output node; GPT-4o returns ranked list of conditions as JSON.
  - `recommend_specialist` — maps top diagnosis to specialist type.
  - `finalize_response` — formats the final patient-facing response.
- Implement conditional edge from `calculate_urgency`: if emergency symptoms detected, jump to Triage Agent immediately.
- Create all tools in `backend/app/agents/tools/medical_kb.py`, `patient_history.py`, and `urgency_scoring.py`.
- Create `backend/app/agents/prompts/symptom_prompts.py`.
- Expose via `backend/app/api/v1/symptoms.py`: `POST /api/v1/symptoms/start`, `POST /api/v1/symptoms/{sessionId}/respond`.
- Write unit tests for each tool and integration test for the full graph.

### Step 10: Medical Report Reader Agent (LangGraph)

Build the vision-based report ingestion and interpretation agent.

- Create `backend/app/agents/report_reader.py` as a LangGraph `StateGraph`.
- Define the graph nodes:
  - `ingest_report` — accepts file from S3/MinIO; determines input type (PDF, image, text).
  - `extract_text` — for images, calls GPT-4o Vision (`extract_text_from_image` tool); for PDFs, uses text extraction.
  - `parse_lab_values` — structured extraction of (test_name, value, unit, reference_range, status) tuples.
  - `identify_abnormalities` — flags values outside reference range with severity (normal/borderline/critical).
  - `correlate_with_history` — compares current values with patient's historical lab trend from Pinecone memory.
  - `generate_patient_explanation` — plain-language explanation for patient audience.
  - `generate_doctor_summary` — structured clinical summary for physician.
  - `suggest_followup_tests` — recommendations based on abnormalities.
- Create tools in `backend/app/agents/tools/report_parsing.py`.
- Create `backend/app/agents/prompts/report_prompts.py`.
- Implement S3/MinIO upload in `backend/app/services/file_storage_service.py` and `backend/app/integrations/s3_client.py`.
- Set up Celery task `backend/app/tasks/report_processing.py` for async analysis triggered after upload.
- Expose via `backend/app/api/v1/reports.py`: `POST /api/v1/reports/upload`, `GET /api/v1/reports/{reportId}`, `GET /api/v1/reports/{reportId}/analysis`.
- Build frontend report upload UI: `(patient)/reports/upload/page.tsx` with react-pdf preview and `(patient)/reports/[reportId]/page.tsx` with analysis display (color-coded abnormalities, plain-language tab).

### Step 11: Drug Interaction Agent (LangGraph)

Build the medication safety analysis agent.

- Create `backend/app/agents/drug_interaction_agent.py` as a LangGraph `StateGraph`.
- Define the graph nodes:
  - `load_patient_medications` — fetches current medication list from patient profile.
  - `check_pairwise_interactions` — calls `check_drug_interactions` tool for all medication pairs.
  - `verify_dosages` — validates each dosage against patient age/weight/renal function.
  - `check_allergy_crossref` — cross-references medications against patient allergy profile.
  - `search_drug_db` — RAG over drug knowledge embeddings in Pinecone.
  - `classify_severity` — assigns mild/moderate/severe/contraindicated to each interaction.
  - `suggest_alternatives` — GPT-4o generates alternative medication options for conflicts.
  - `generate_medication_schedule` — creates an optimized dosing schedule.
  - `alert_prescriber` — if severe interaction found, triggers notification to prescribing physician.
- Create tools in `backend/app/agents/tools/drug_database.py`.
- Embed drug interaction data (e.g., from DrugBank or public FDA datasets) into Pinecone via the seeding script.
- Expose via `backend/app/api/v1/medications.py`: `POST /api/v1/medications/check-interactions`, `GET /api/v1/medications/{patientId}/schedule`.
- Build frontend: `(patient)/medications/interactions/page.tsx` with interaction severity table and `(doctor)/patients/[patientId]/medications/page.tsx`.

### Step 12: Chat UI with Streaming (Frontend)

Build the patient-facing AI chat interface that streams responses from the orchestrator.

- Set up `Flask-SocketIO` WebSocket server in `backend/app/api/websocket/chat_stream.py`.
- Implement SSE or Socket.IO streaming from the orchestrator's LangGraph graph using LangGraph's streaming callbacks.
- Build `(patient)/chat/page.tsx` and `(doctor)/ai-assistant/page.tsx` with a full-screen chat interface.
- Components to build: `ChatMessageBubble`, `TypingIndicator`, `StreamingText`, `AgentBadge` (shows which agent responded), `SuggestionChips`.
- Integrate Zustand store `useChatStore` to manage message history, session ID, and loading state.
- Connect Socket.IO client (`socket.io-client`) to the WebSocket server.

---

## Phase 3 — Monitoring & Real-Time (Weeks 11–16)

### Step 13: IoT Device Integration & Vitals Ingestion Pipeline

Build the real-time vitals data pipeline from devices to InfluxDB.

- Create `backend/app/integrations/iot_gateway.py` — handles device registration, authentication (device tokens), and incoming vitals payloads.
- Create `backend/app/integrations/influxdb_client.py` — wrapper for writing and querying time-series vitals data (heart rate, SpO2, blood pressure, temperature, respiration rate, glucose).
- Create `backend/app/api/v1/devices.py`: `POST /api/v1/devices/register`, `POST /api/v1/devices/{deviceId}/vitals` (ingestion endpoint).
- Create `backend/app/api/v1/vitals.py`: `GET /api/v1/vitals/{patientId}/current`, `GET /api/v1/vitals/{patientId}/history`.
- Implement `backend/app/services/vitals_service.py` that writes to InfluxDB and mirrors latest values to Redis for fast access.
- Create `backend/app/models/device.py` and `vitals.py` PostgreSQL models for device registry and vitals metadata.

### Step 14: Patient Monitoring Agent (LangGraph)

Build the continuous anomaly detection and alerting agent.

- Create `backend/app/agents/monitoring_agent.py` as a LangGraph `StateGraph`.
- Define the graph nodes:
  - `ingest_vitals_stream` — polls InfluxDB for new readings; runs as a Celery periodic task.
  - `compute_baseline` — adaptive per-patient normal range using rolling statistics.
  - `detect_anomaly` — statistical anomaly detection (Z-score, IQR) + GPT-4o-mini for contextual interpretation.
  - `compute_early_warning_score` — NEWS2 and MEWS score calculation node.
  - `evaluate_alert_threshold` — compares scores against configurable thresholds.
  - `correlate_with_medications` — checks if vitals changes align with recent medication schedule.
  - `trigger_alert` — publishes alert event to Redis pub/sub; calls `notification_tools.py` for push/SMS.
  - `generate_vitals_summary` — periodic trend report for shift handoff.
- Implement escalation chain logic: level 1 → nurse push notification; level 2 → attending physician SMS; level 3 → on-call specialist page.
- Create tools in `backend/app/agents/tools/vitals_analysis.py` and `notification_tools.py`.
- Create `backend/app/tasks/monitoring_tasks.py` as a Celery beat periodic task invoking the monitoring agent every 30 seconds.

### Step 15: Real-Time Monitoring Dashboard & Alert System (Frontend + WebSocket)

Build the live monitoring wall for doctors/nurses.

- Implement `backend/app/api/websocket/vitals_stream.py` — subscribes to Redis pub/sub and pushes vitals updates to connected Socket.IO clients.
- Implement `backend/app/api/websocket/monitoring_events.py` — pushes alert events to the appropriate physician's Socket.IO room.
- Build `(doctor)/monitoring/page.tsx` — the monitoring wall showing all active patients' vitals cards.
- Components: `VitalsCard` (real-time updating), `VitalsChart` (Recharts line chart with D3.js annotations), `AlertBanner`, `EWSBadge` (color-coded NEWS2 score), `PatientStatusGrid`.
- Build `(doctor)/monitoring/[patientId]/page.tsx` — individual patient deep-dive with all vital streams.
- Build `(nurse)/monitoring/page.tsx` — simplified ward-level view.
- Implement `backend/app/api/v1/monitoring.py` REST endpoints for alert history and acknowledgment: `GET /api/v1/monitoring/alerts`, `POST /api/v1/monitoring/alerts/{alertId}/acknowledge`.

### Step 16: Triage Agent (LangGraph)

Build the fast emergency triage agent.

- Create `backend/app/agents/triage_agent.py` as a LangGraph `StateGraph`.
- Design for speed — use GPT-4o-mini throughout. Maximum latency target: 2 seconds.
- Define the graph nodes:
  - `collect_triage_inputs` — pulls symptom report + current vitals from state.
  - `check_red_flags` — pattern-matches against a curated emergency symptom database (chest pain, stroke symptoms, anaphylaxis, etc.).
  - `evaluate_esi_level` — computes ESI level 1–5 with structured output.
  - `route_emergency` — if ESI 1 or 2: triggers `notify_on_call_physician` tool and creates emergency alert; if ESI 3–5: `assign_priority_queue`.
  - `generate_triage_report` — logs triage decision with all inputs for audit.
- Create `backend/app/agents/prompts/triage_prompts.py`.
- The Triage Agent is also callable directly from the Symptom Analyst Agent's conditional edge.
- Expose via `backend/app/api/v1/symptoms.py` (already created): `POST /api/v1/triage/evaluate`.

### Step 17: Notification Service

Build the multi-channel notification infrastructure.

- Create `backend/app/services/notification_service.py` — fan-out dispatcher supporting push, SMS (Twilio), and email (SendGrid) channels.
- Implement `backend/app/integrations/twilio_client.py` and `sendgrid_client.py`.
- Create `backend/app/tasks/notification_tasks.py` — Celery tasks for async notification delivery with retry logic.
- Implement Web Push API subscription management in `backend/app/api/v1/notifications.py`: `POST /subscribe`, `GET /notifications`, `POST /notifications/{id}/read`.
- Set up `backend/app/api/websocket/notification_stream.py` for real-time in-app notifications.
- Build frontend `NotificationPanel` component and notification bell with unread badge.

---

## Phase 4 — Voice & Telemedicine (Weeks 17–22)

### Step 18: Voice Interaction Agent (LangGraph)

Build the full voice pipeline: STT → NLP → TTS.

- Create `backend/app/agents/voice_agent.py` as a LangGraph `StateGraph`.
- Define the graph nodes:
  - `receive_audio_chunk` — accepts binary audio from WebSocket stream.
  - `transcribe_audio` — calls OpenAI Whisper API; supports streaming transcription.
  - `detect_language` — language identification for multi-language support.
  - `extract_medical_entities` — NER pass to identify symptoms, body parts, medications from transcript.
  - `process_voice_command` — routes the extracted intent to the Agent Orchestrator.
  - `manage_voice_session` — tracks multi-turn voice context in Redis.
  - `synthesize_speech` — calls OpenAI TTS API (configurable voice: alloy/nova, speed).
  - `stream_audio_response` — streams TTS audio back over WebSocket.
- Build `backend/app/api/v1/voice.py`: `POST /api/v1/voice/start-session`, `WebSocket /api/v1/voice/stream`.
- Implement ambient listening mode as an opt-in session type with explicit patient consent logging.
- Build `backend/app/api/websocket/` voice stream handler.

### Step 19: Voice UI (Frontend)

Build the voice-based patient and doctor interfaces.

- Build `(patient)/voice-assistant/page.tsx` — full-screen voice interaction UI.
- Components: `VoicePulseAnimation` (animated waveform), `TranscriptDisplay` (real-time streaming text), `VoiceControlBar` (mute, end, language selector), `VoiceResponsePlayer`.
- Integrate the Web Speech API for browser-native fallback transcription.
- Build `(doctor)/consultation/[sessionId]/ambient-notes/page.tsx` — ambient mode UI showing live transcript and extracted clinical entities.
- Implement the audio capture pipeline using the browser `MediaRecorder` API and stream chunks to the backend WebSocket.

### Step 20: Clinical Note Generation from Voice

Add structured clinical note auto-generation to the Voice Agent's output.

- Add a `generate_clinical_note` node to the Voice Agent graph (or as a post-processing Celery task).
- Node uses GPT-4o to convert a completed voice session transcript into a structured SOAP note (Subjective, Objective, Assessment, Plan).
- Store generated notes in `backend/app/models/conversation.py` with structured JSON fields.
- Build `(doctor)/patients/[patientId]/notes/page.tsx` — note viewer and editor.
- Allow doctors to edit and approve auto-generated notes before they enter the medical record.

### Step 21: Telemedicine — Video Calls (WebRTC via Daily.co)

Integrate video consultation infrastructure.

- Create `backend/app/services/telemedicine_service.py` — wraps Daily.co REST API to create/join/end rooms and generate access tokens.
- Implement `backend/app/integrations/` Daily.co client.
- Expose via `backend/app/api/v1/telemedicine.py`: `POST /api/v1/telemedicine/rooms/create`, `POST /api/v1/telemedicine/rooms/{roomName}/join`, `POST /api/v1/telemedicine/rooms/{roomName}/end`.
- Build `(patient)/telemedicine/[sessionId]/page.tsx` — patient video call interface.
- Build `(doctor)/telemedicine/[sessionId]/page.tsx` — doctor interface with sidebar showing patient vitals, AI assistant panel, and note-taking area.
- Implement the in-call AI assistant: a side panel connected to the Agent Orchestrator that answers doctor queries during the call.
- Add appointment-based room creation: rooms auto-created 15 minutes before scheduled appointment.

### Step 22: Appointment Scheduling System

Build the full appointment booking and management flow.

- Complete `backend/app/services/appointment_service.py` with booking, cancellation, and rescheduling logic.
- Integrate `backend/app/agents/tools/scheduling.py` for the Follow-Up Agent to programmatically book appointments.
- Build `(patient)/appointments/page.tsx` — appointment list and booking UI.
- Build `(patient)/appointments/book/page.tsx` — slot picker with doctor availability calendar.
- Build `(doctor)/schedule/page.tsx` — doctor's appointment calendar view.
- Implement Celery reminder tasks in `notification_tasks.py` for 24-hour and 1-hour appointment reminders.

---

## Phase 5 — Care Plans & Analytics (Weeks 23–26)

### Step 23: Follow-Up & Care Plan Agent (LangGraph)

Build the long-term care management agent.

- Create `backend/app/agents/followup_agent.py` as a LangGraph `StateGraph`.
- Define the graph nodes:
  - `assess_patient_state` — reviews diagnosis, treatment history, and current vitals from patient memory.
  - `generate_care_plan` — GPT-4o creates a structured care plan with goals, milestones, and success metrics.
  - `schedule_followup` — calls `scheduling.py` tool to book next appointment.
  - `generate_patient_education` — creates condition-specific educational content (lifestyle tips, warning signs).
  - `track_adherence` — checks medication fill history and appointment attendance.
  - `detect_deviation` — identifies patients not meeting care plan milestones.
  - `adjust_care_plan` — dynamically revises the plan based on progress.
  - `send_reminder` — calls `notification_tools.py` for adherence reminders.
  - `generate_progress_report` — structured progress report for patient and physician.
- Create `backend/app/agents/prompts/care_plan_prompts.py`.
- Expose via `backend/app/api/v1/care_plans.py`: `POST /api/v1/care-plans/generate`, `GET /api/v1/care-plans/{patientId}`, `PATCH /api/v1/care-plans/{planId}`.
- Set up a daily Celery beat task that runs the adherence-tracking sub-graph for all active care plans.

### Step 24: Care Plan & Patient Education UI (Frontend)

Build the patient care plan interface.

- Build `(patient)/care-plan/page.tsx` — visual care plan timeline with goal progress indicators.
- Components: `CareGoalCard`, `MilestoneTimeline`, `AdherenceProgressBar`, `EducationContentCard`, `MedicationReminderList`.
- Build `(doctor)/patients/[patientId]/care-plan/page.tsx` — doctor's view with editing and approval workflow.
- Build `(patient)/education/page.tsx` — condition-specific educational content library generated by the agent.

### Step 25: Analytics Dashboards

Build data analytics for all three user roles.

- Implement `backend/app/services/analytics_service.py` with query methods for patient trends, doctor caseloads, and system health metrics.
- Create `backend/app/tasks/analytics_tasks.py` — Celery beat tasks for nightly aggregation into pre-computed summary tables.
- Create `backend/app/api/v1/analytics.py` endpoints: `GET /api/v1/analytics/patient/{id}`, `GET /api/v1/analytics/doctor/{id}`, `GET /api/v1/analytics/admin/overview`.
- Build `(patient)/dashboard/page.tsx` (complete version) — health trend charts (Recharts): vitals over time, upcoming appointments, medication adherence score, care plan progress ring.
- Build `(doctor)/dashboard/page.tsx` (complete version) — active patients count, pending alerts, today's schedule, patient risk distribution chart.
- Build `(admin)/analytics/page.tsx` — system-level dashboard: total users, active sessions, agent invocation counts, API latency percentiles (using Prometheus data), resource utilization.
- Integrate Grafana embed or custom Prometheus query component for real-time system metrics.

---

## Phase 6 — Polish & Compliance (Weeks 27–30)

### Step 26: HIPAA Compliance Hardening

Ensure the platform meets HIPAA technical safeguard requirements.

- Audit every API endpoint for PHI access; ensure `hipaa_audit.py` middleware logs: who accessed what, when, from where, and why.
- Ensure all PHI fields are encrypted at rest using the AES-256 utility from `encryption.py`.
- Implement data de-identification pipeline in `backend/app/utils/` — removes/masks PHI from analytics and export datasets.
- Enforce TLS 1.3 for all transport (configure in Nginx/Kong gateway).
- Implement automatic session timeout (15 minutes of inactivity) on the frontend.
- Add role-based field masking: patients can't see other patients' data; nurses see limited PHI; admins have full audit access.
- Review and tighten CORS policy in `cors.py`.
- Store all secrets in AWS Secrets Manager / HashiCorp Vault — remove all `.env` secret usage from production configs.
- Implement data retention policy enforcement via `backend/app/tasks/cleanup_tasks.py`.

### Step 27: Search Integration (Elasticsearch)

Implement full-text search across medical records.

- Create `backend/app/services/search_service.py` wrapping `backend/app/integrations/elasticsearch_client.py`.
- Index: patient records (de-identified for search), medical reports, care plans, conversation summaries.
- Implement `backend/app/api/v1/` search endpoints (attach to appropriate resource endpoints).
- Build global search UI component `GlobalSearchBar` in the navigation shell.
- Set up Logstash pipeline to feed structured logs from structlog into the ELK stack for operational search.

### Step 28: Performance Optimization

Profile and optimize the full stack for production readiness.

- Implement Redis caching for all frequently-read patient context queries (`patient_service.py`, `vitals_service.py`).
- Add pagination to all list endpoints; enforce `limit/offset` or cursor-based pagination.
- Optimize SQLAlchemy queries: add indexes on FK columns, add composite indexes for common query patterns (patient_id + created_at).
- Implement Next.js `loading.tsx` and skeleton screens for all data-fetching pages.
- Add React Query `staleTime` and `cacheTime` configuration for all queries.
- Profile LangGraph agent graphs; identify and optimize the slowest nodes (add intermediate caching where safe).
- Implement request coalescing in the WebSocket server to prevent duplicate alert storms.
- Configure Celery concurrency, worker pools, and rate limits for production throughput.

### Step 29: Accessibility, Internationalization & Testing

Ensure the platform is accessible, multilingual, and thoroughly tested.

- Conduct WCAG 2.1 AA audit: keyboard navigation, ARIA labels, color contrast, screen reader support.
- Add `aria-live` regions for real-time vitals updates and alert banners.
- Complete `next-intl` translations for all UI strings (start with English + Hindi + Spanish).
- Write backend unit tests targeting ≥80% coverage (`pytest --cov=app`).
- Write frontend component tests with Jest + React Testing Library for all critical components.
- Write Cypress E2E tests for the three critical user journeys: (1) patient symptom check → AI response → triage, (2) doctor reviewing patient vitals → alert acknowledgment, (3) report upload → AI analysis → report view.
- Implement GitHub Actions CI pipeline: lint, type-check, unit tests, integration tests, security scan (Bandit for Python, npm audit for Node).

### Step 30: Production Infrastructure, Load Testing & Documentation

Prepare the platform for production deployment.

- Finalize `infrastructure/terraform/` modules for EKS cluster, RDS (PostgreSQL), ElastiCache (Redis), S3, CloudFront CDN, and Kong API Gateway.
- Write Kubernetes manifests in `infrastructure/kubernetes/` for all services with Horizontal Pod Autoscaler (HPA) configs.
- Configure Prometheus metrics collection from Flask (via `prometheus_flask_exporter`) and Next.js.
- Build Grafana dashboards for: API latency (p50/p95/p99), agent response time, WebSocket connection count, alert delivery latency, DB query time.
- Run load tests with `locust` or `k6`: simulate 500 concurrent patients in symptom sessions, 100 concurrent monitoring streams.
- Document all API endpoints in Swagger (Flasgger) — ensure 100% endpoint coverage.
- Write operational runbooks for: incident response, database backup/restore, Celery worker scaling, agent failure fallback.
- Configure CD pipelines: `cd-staging.yml` auto-deploys from `main` branch; `cd-production.yml` requires manual approval gate.

---

## Summary: Build Order at a Glance

| # | What | Why First |
|---|------|-----------|
| 1 | Repo scaffolding & Docker Compose | Everything else depends on this |
| 2 | DB schema & Alembic migrations | Agents and APIs need data models |
| 3 | Auth system (JWT + RBAC) | All endpoints need security |
| 4 | Core services & API blueprints | Backend skeleton for feature work |
| 5 | Frontend auth & shell UI | Enables frontend-backend connection |
| 6 | LangGraph base + memory infrastructure | Foundation all 7 agents build on |
| 7 | Agent Orchestrator | Central router must exist before agents |
| 8 | Symptom Analyst Agent | Highest-value AI feature for patients |
| 9 | Medical Report Reader Agent | Second highest-value AI feature |
| 10 | Drug Interaction Agent | Critical safety feature |
| 11 | Chat UI with streaming | Makes agents accessible in the UI |
| 12 | IoT vitals pipeline + InfluxDB | Real-time data layer before monitoring |
| 13 | Patient Monitoring Agent | Depends on vitals pipeline |
| 14 | Monitoring dashboard + WebSocket | Makes monitoring agent visible |
| 15 | Triage Agent | Built after symptom + monitoring context |
| 16 | Notification service | Required by monitoring, triage, follow-up |
| 17 | Voice Agent + UI | Complex; built after text flows are stable |
| 18 | Clinical note generation | Extension of voice agent |
| 19 | Telemedicine (WebRTC) | Depends on auth, scheduling, voice |
| 20 | Appointment scheduling | Prerequisite for telemedicine |
| 21 | Follow-Up & Care Plan Agent | Depends on all prior clinical data |
| 22 | Analytics dashboards | Needs data from all prior features |
| 23 | HIPAA hardening | Applied across the whole system |
| 24 | Elasticsearch search | Needs indexed data from prior features |
| 25 | Performance optimization | After features are stable |
| 26 | Accessibility + i18n + testing | Final polish layer |
| 27 | Production infra + load test + docs | Last step before launch |
