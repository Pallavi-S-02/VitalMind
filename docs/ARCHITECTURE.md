# Architecture Document — MedAssist AI

---

## 1. Architecture Overview

MedAssist AI follows a layered architecture with four primary tiers, plus an Agentic AI layer that sits between the backend services and the data stores. All communication between the client and backend flows through an API Gateway. The system is designed for HIPAA compliance, horizontal scalability, and real-time responsiveness.

---

## 2. High-Level Architecture Diagram

```
+-----------------------------------------------------------------------+
|                        CLIENT LAYER (Next.js)                          |
|                                                                         |
|  +----------+ +----------+ +----------+ +----------+ +--------------+  |
|  | Patient  | | Doctor   | | Admin    | | Voice    | | Monitoring   |  |
|  | Portal   | | Dashboard| | Panel    | | Assistant| | Dashboard    |  |
|  +----+-----+ +----+-----+ +----+-----+ +----+-----+ +------+------+  |
|       |             |            |             |              |         |
|       +-------------+------------+-------------+--------------+         |
|                              |  WebSocket + REST                        |
+------------------------------+------------------------------------------+
                               |
                    +----------v----------+
                    |    API Gateway       |
                    |  (Kong / Nginx)      |
                    +----------+----------+
                               |
+------------------------------+------------------------------------------+
|                     BACKEND LAYER (Flask)                                |
|                                                                         |
|  +-------------+  +-------------+  +-------------+  +--------------+   |
|  | Auth        |  | Patient API |  | Monitoring  |  | Reports API  |   |
|  | Service     |  | Service     |  | Service     |  | Service      |   |
|  +-------------+  +-------------+  +-------------+  +--------------+   |
|                                                                         |
|  +-------------+  +-------------+  +-------------+  +--------------+   |
|  | Appointment |  | Notification|  | Telemedicine|  | Analytics    |   |
|  | Service     |  | Service     |  | Service     |  | Service      |   |
|  +-------------+  +-------------+  +-------------+  +--------------+   |
|                                                                         |
|                    +----------------------+                             |
|                    |   WebSocket Server   |                             |
|                    |  (Flask-SocketIO)    |                             |
|                    +----------------------+                             |
+------------------------------+------------------------------------------+
                               |
+------------------------------+------------------------------------------+
|                     AGENTIC AI LAYER                                    |
|                                                                         |
|  +---------------------------------------------------------------+     |
|  |                    Agent Orchestrator                          |     |
|  |         (Routes tasks to specialized agents)                  |     |
|  +---+------+------+------+------+------+------+----------------+     |
|      |      |      |      |      |      |      |                      |
|  +---v--+ +-v----+ +v-----+ +---v--+ +-v----+ +v------+ +------+     |
|  |Sympt.| |Report| |Triage| |Voice | |Drug  | |Monitor| |Follow|     |
|  |Analys| |Reader| |Agent | |Agent | |Inter.| |Agent  | |Up    |     |
|  |Agent | |Agent | |      | |      | |Agent | |       | |Agent |     |
|  +------+ +------+ +------+ +------+ +------+ +-------+ +------+     |
|                                                                         |
|  +---------------------------------------------------------------+     |
|  |         Shared Context / Memory Store (Redis + Pinecone)      |     |
|  +---------------------------------------------------------------+     |
+------------------------------+------------------------------------------+
                               |
+------------------------------+------------------------------------------+
|                       DATA LAYER                                        |
|                                                                         |
|  +------------+ +----------+ +-----------+ +----------+ +-----------+  |
|  | PostgreSQL | | Redis    | | InfluxDB  | | Pinecone | | S3/MinIO  |  |
|  | (Primary)  | | (Cache)  | | (Vitals)  | | (Vectors)| | (Files)   |  |
|  +------------+ +----------+ +-----------+ +----------+ +-----------+  |
|                                                                         |
|  +---------------------+  +-------------------------------------+      |
|  | Elasticsearch       |  | Celery + Redis (Task Queue)         |      |
|  | (Full-text Search)  |  |                                     |      |
|  +---------------------+  +-------------------------------------+      |
+------------------------------------------------------------------------+
```

---

## 3. Layer Descriptions

### 3.1 Client Layer (Next.js 14+ App Router)
- **Technology:** React 18+, Tailwind CSS, shadcn/ui, Zustand, React Query, Socket.IO Client, Daily.co SDK
- **Role:** Renders all user interfaces (Patient Portal, Doctor Dashboard, Admin Panel, Voice Assistant, Monitoring Dashboard). Manages client state, handles real-time WebSocket subscriptions, and provides WebRTC video calling.
- **Auth:** NextAuth.js with JWT tokens from the backend.
- **Real-time:** Socket.IO client for vitals streaming, chat, alerts, and notifications.

### 3.2 API Gateway (Kong / Nginx)
- **Role:** Single entry point for all client requests. Handles TLS termination, request routing, rate limiting, CORS, and load balancing across backend service instances.
- **Rate limiting:** Configurable per user role (patients, doctors, admins have different limits).

### 3.3 Backend Layer (Flask 3+)
- **Technology:** Python 3.11+, Flask, SQLAlchemy 2.0, Flask-SocketIO, Flask-JWT-Extended, Celery
- **Role:** RESTful API services organized by domain (auth, patients, vitals, reports, medications, appointments, telemedicine, monitoring, analytics, admin). WebSocket server for real-time events.
- **Pattern:** Service layer architecture. API controllers call service classes, which call ORM models. No business logic in controllers.
- **Async work:** Any operation exceeding 500ms is offloaded to Celery (report analysis, notification delivery, embedding updates, analytics computation).
- **Middleware:** JWT validation, HIPAA audit logging, rate limiting, CORS, structured request logging, global error handling.

### 3.4 Agentic AI Layer
- **Role:** Houses the 7 specialized AI agents and the Agent Orchestrator. Each agent has its own tools, memory access, and decision-making capabilities. See section 4 for full agent definitions.
- **Shared context:** Short-term conversation context in Redis, long-term medical knowledge in Pinecone vector store.

### 3.5 Data Layer
- **PostgreSQL 16:** Primary relational store for users, profiles, medical records, appointments, care plans, audit logs.
- **Redis 7:** Caching layer, session store, short-term agent memory, Celery broker, and pub/sub for real-time events.
- **InfluxDB:** Time-series store for raw vitals data from IoT devices. High-write throughput, retention policies, continuous queries for downsampling.
- **Pinecone:** Vector database for medical knowledge base embeddings (symptoms, drug info, clinical guidelines) used by agents via RAG.
- **S3/MinIO:** Object storage for medical report files (PDFs, images), telemedicine recordings, and other binary assets. AES-256 encryption at rest.
- **Elasticsearch:** Full-text search across medical records, audit logs, and clinical notes.
- **Celery + Redis:** Distributed task queue for asynchronous processing.

---

## 4. Agent Definitions

### Agent Orchestrator
- **Model:** GPT-4o with function calling
- **Role:** Central router that receives all incoming requests, classifies intent, and dispatches to the appropriate specialist agent(s). Can invoke multiple agents in parallel for complex queries.
- **Tools:** Agent registry, task router, context aggregator, response synthesizer
- **Memory:** Short-term conversation buffer (Redis), long-term patient context (Pinecone)

### Agent 1: Symptom Analyst Agent
- **Model:** GPT-4o
- **Role:** Conducts multi-turn symptom interviews, builds differential diagnosis lists, assigns urgency scores, and recommends next steps.
- **Tools:** `search_medical_knowledge_base`, `query_patient_history`, `calculate_urgency_score`, `generate_differential_diagnosis`, `recommend_specialist`
- **Behavior:** Asks follow-up questions to narrow symptoms. Considers patient history, age, sex, pre-existing conditions. Outputs ranked conditions with confidence scores. Flags emergency symptoms immediately.

### Agent 2: Medical Report Reader Agent
- **Model:** GPT-4o Vision
- **Role:** Ingests and interprets medical reports (lab results, imaging, pathology) using vision and text analysis.
- **Tools:** `extract_text_from_image`, `parse_lab_values`, `identify_abnormalities`, `explain_report_in_plain_language`, `correlate_with_history`, `generate_report_summary`
- **Behavior:** Accepts PDF/image/text reports. Extracts structured data. Highlights abnormal values with severity. Generates trend analysis from historical data.

### Agent 3: Triage Agent
- **Model:** GPT-4o-mini (fast inference)
- **Role:** Real-time emergency triage. Assigns ESI levels (1-5).
- **Tools:** `evaluate_esi_level`, `check_red_flags`, `route_to_emergency`, `assign_priority_queue`, `notify_on_call_physician`
- **Behavior:** Responds in < 2 seconds. Conservative bias (errs toward higher urgency). Auto-escalates ESI 1-2 to emergency protocols.

### Agent 4: Voice Interaction Agent
- **Model:** Whisper API (STT) + GPT-4o (processing) + TTS API (speech output)
- **Role:** Handles all voice interactions -- speech-to-text, command processing, spoken responses.
- **Tools:** `transcribe_audio`, `detect_language`, `synthesize_speech`, `extract_medical_entities`, `manage_voice_session`
- **Behavior:** 50+ language support. Real-time streaming transcription. Medical terminology-aware. Ambient clinical note generation with SOAP format output.

### Agent 5: Drug Interaction Agent
- **Model:** GPT-4o
- **Role:** Analyzes medication lists for interactions, contraindications, dosage verification, and allergy cross-references.
- **Tools:** `check_drug_interactions`, `verify_dosage`, `check_allergy_crossreference`, `search_drug_database`, `suggest_alternatives`, `generate_medication_schedule`
- **Behavior:** Real-time checking on prescription. Severity classification. Patient-specific factors considered. Evidence-based citations.

### Agent 6: Patient Monitoring Agent
- **Model:** GPT-4o-mini (fast pattern recognition)
- **Role:** Continuously monitors incoming patient vitals, detects anomalies, predicts deterioration, and triggers alerts.
- **Tools:** `ingest_vitals_stream`, `detect_anomaly`, `predict_deterioration`, `trigger_alert`, `generate_vitals_report`, `correlate_vitals_with_medications`
- **Behavior:** 24/7 monitoring with configurable thresholds. Adaptive baselines. Predictive alerts 30-60 min before deterioration. Escalation chains (nurse, attending, specialist).

### Agent 7: Follow-Up and Care Plan Agent
- **Model:** GPT-4o
- **Role:** Generates personalized care plans, schedules follow-ups, sends reminders, tracks treatment adherence.
- **Tools:** `generate_care_plan`, `schedule_followup`, `send_reminder`, `track_adherence`, `adjust_care_plan`, `generate_patient_education`
- **Behavior:** Evidence-based care plans with measurable goals. Adaptive scheduling. Chronic disease management. Progress reports for patients and physicians.

---

## 5. Agent Orchestration Pattern

```
User Request
     |
     v
+--------------------+
| Agent Orchestrator  |
| (Intent Classifier) |
+----+-------+-------+
     |       |       |
     |  (parallel dispatch for complex queries)
     v       v       v
  Agent A  Agent B  Agent C
     |       |       |
     v       v       v
+----+-------+-------+
| Response Synthesizer |
| (Merge agent outputs)|
+----------------------+
     |
     v
  Final Response
```

1. Orchestrator receives the request and classifies intent.
2. Dispatches to one or more agents (parallel execution for multi-faceted queries).
3. Each agent uses its tools and accesses shared context (Redis for short-term, Pinecone for long-term knowledge).
4. Orchestrator aggregates results and synthesizes a unified response.

---

## 6. Data Flow Examples

### 6.1 Symptom Check Flow

```
Patient submits symptoms (chat/voice/body map)
  -> API Gateway
  -> Backend /api/v1/symptoms/session (POST)
  -> Orchestrator classifies intent: "symptom_analysis"
  -> Dispatches to Symptom Analyst Agent + Triage Agent (parallel)
  -> Symptom Analyst:
       - Queries patient history (PostgreSQL)
       - Searches medical knowledge base (Pinecone RAG)
       - Generates differential diagnosis (GPT-4o)
  -> Triage Agent:
       - Evaluates ESI level (GPT-4o-mini)
       - Checks red flags
  -> Orchestrator merges results
  -> Response: diagnosis list, urgency score, ESI level, recommended action
  -> Saved to symptom_sessions table
  -> If ESI 1-2: immediate alert via WebSocket + SMS to on-call physician
```

### 6.2 Report Analysis Flow

```
User uploads report (PDF/image)
  -> API Gateway
  -> Backend /api/v1/reports/:patientId/upload (POST)
  -> File stored in S3/MinIO (AES-256 encrypted)
  -> Celery task queued for async processing
  -> Report Reader Agent:
       - GPT-4o Vision extracts text/structure
       - Identifies report type
       - Parses lab values into structured data
       - Compares against reference ranges
       - Flags abnormalities
       - Generates patient summary + clinical summary
       - Checks for trends if historical data exists
  -> Results stored in medical_reports + lab_values tables
  -> WebSocket notification: "Report analysis complete"
  -> Patient sees color-coded results in UI
```

### 6.3 Vitals Monitoring Flow

```
IoT device / wearable sends vitals
  -> MQTT -> IoT Gateway -> InfluxDB (raw time-series data)
  -> Monitoring Agent polls InfluxDB (every 30s default)
  -> Per-patient anomaly detection:
       - Statistical methods (z-score, moving average)
       - Adaptive baseline comparison
       - LLM reasoning for complex patterns
  -> If anomaly detected:
       - Calculate NEWS2/MEWS score
       - Determine alert severity (info/warning/critical/emergency)
       - Store alert in monitoring_alerts table
       - Trigger escalation chain via WebSocket + push/SMS/pager
  -> Summary vitals snapshot stored in PostgreSQL vitals_readings
  -> Real-time update pushed to Monitoring Wall via WebSocket
```

---

## 7. Security Architecture

### 7.1 Authentication and Authorization
- JWT-based auth with access tokens (15 min expiry) and refresh tokens (7 day expiry)
- OAuth2 integration for SSO (Google, Microsoft)
- RBAC with roles: Patient, Doctor, Nurse, Admin
- Resource-level authorization (patients access only their own data)
- Brute force protection with account lockout
- MFA mandatory for healthcare providers

### 7.2 HIPAA Compliance
- AES-256 encryption at rest for all PHI
- TLS 1.3 in transit
- Audit logging of every PHI access (user, action, resource, timestamp, IP)
- Data de-identification before LLM calls (PII stripped, anonymized tokens, re-hydrated on response)
- Configurable retention policies with automated purging
- BAA with all cloud providers

### 7.3 Network Security
- API Gateway handles TLS termination
- Internal service communication within VPC
- Network policies in Kubernetes restricting pod-to-pod communication
- WAF rules at API Gateway level

---

## 8. Scalability

### 8.1 Kubernetes (EKS) Horizontal Scaling
- Backend services deployed as Kubernetes Deployments with HPA (Horizontal Pod Autoscaler)
- Celery workers scale based on queue depth
- Frontend served via CloudFront CDN with origin at container or static build
- Database scaling: RDS read replicas for PostgreSQL, ElastiCache cluster for Redis

### 8.2 Target Performance
- 10,000+ concurrent WebSocket connections
- < 200ms p95 API response time
- < 2s triage response time
- < 3s AI chat response time

### 8.3 Infrastructure as Code
- Terraform modules for VPC, EKS, RDS, ElastiCache, S3, monitoring
- Separate environments: staging, production
- GitHub Actions CI/CD pipelines for automated build, test, and deploy
