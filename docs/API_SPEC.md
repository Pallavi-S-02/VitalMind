# API Specification — MedAssist AI

---

## 1. General Information

- **Base URL:** `/api/v1/`
- **Authentication:** JWT Bearer token in `Authorization` header
- **Content Type:** `application/json` (unless file upload)
- **API Documentation:** Swagger/OpenAPI 3.0 via Flasgger at `/apidocs`

---

## 2. Authentication and Common Patterns

### 2.1 Auth Header

```
Authorization: Bearer <access_token>
```

### 2.2 Standard Response Format

**Success:**
```json
{
  "status": "success",
  "data": { ... },
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

**Error:**
```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable message",
    "details": [ ... ]
  }
}
```

### 2.3 HTTP Status Codes

| Code | Usage |
|------|-------|
| 200 | Successful GET, PUT |
| 201 | Successful POST (resource created) |
| 204 | Successful DELETE |
| 400 | Bad request / validation error |
| 401 | Unauthorized (missing or invalid token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Resource not found |
| 409 | Conflict (duplicate resource) |
| 422 | Unprocessable entity |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

### 2.4 Pagination

Query parameters for list endpoints:
- `page` (default: 1)
- `per_page` (default: 20, max: 100)
- `sort_by` (field name)
- `sort_order` (`asc` or `desc`)

### 2.5 Rate Limiting

| Role | Limit |
|------|-------|
| Patient | 60 requests/minute |
| Nurse | 120 requests/minute |
| Doctor | 120 requests/minute |
| Admin | 300 requests/minute |

Rate limit headers returned: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

---

## 3. Endpoints

### 3.1 Authentication (`/api/v1/auth`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/auth/register` | Register new user | No |
| POST | `/auth/login` | Login, returns JWT | No |
| POST | `/auth/logout` | Invalidate token | Yes |
| POST | `/auth/refresh` | Refresh access token | Yes (refresh token) |
| POST | `/auth/forgot-password` | Send password reset email | No |
| POST | `/auth/reset-password` | Reset password with token | No |
| POST | `/auth/verify-email` | Verify email address | No |
| POST | `/auth/mfa/enable` | Enable MFA | Yes |
| POST | `/auth/mfa/verify` | Verify MFA code | Yes |
| GET | `/auth/me` | Get current user profile | Yes |

### 3.2 Patients (`/api/v1/patients`)

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/patients` | List patients | doctor, nurse, admin |
| GET | `/patients/:id` | Get patient details | patient (own), doctor, nurse, admin |
| PUT | `/patients/:id` | Update patient profile | patient (own), admin |
| GET | `/patients/:id/medical-history` | Get medical history | patient (own), doctor, nurse |
| POST | `/patients/:id/medical-history` | Add medical history entry | doctor |
| GET | `/patients/:id/allergies` | Get allergies | patient (own), doctor, nurse |
| POST | `/patients/:id/allergies` | Add allergy | doctor, patient (own) |
| GET | `/patients/:id/timeline` | Get full patient timeline | patient (own), doctor |
| GET | `/patients/:id/summary` | AI-generated patient summary | doctor |

### 3.3 Vitals (`/api/v1/vitals`)

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/vitals/:patientId` | Get latest vitals | patient (own), doctor, nurse |
| GET | `/vitals/:patientId/history` | Get vitals history (time range) | patient (own), doctor, nurse |
| POST | `/vitals/:patientId` | Record new vitals reading | patient (own), nurse, device |
| GET | `/vitals/:patientId/trends` | Get vitals trend analysis | patient (own), doctor |
| GET | `/vitals/:patientId/anomalies` | Get detected anomalies | doctor, nurse |
| POST | `/vitals/batch` | Batch upload vitals (IoT) | device |

### 3.4 Medical Reports (`/api/v1/reports`)

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/reports/:patientId` | List patient reports | patient (own), doctor, nurse |
| POST | `/reports/:patientId/upload` | Upload new report | patient (own), doctor, nurse |
| GET | `/reports/:reportId` | Get report details + AI analysis | patient (own), doctor, nurse |
| POST | `/reports/:reportId/analyze` | Trigger AI analysis | doctor, patient (own) |
| GET | `/reports/:reportId/lab-values` | Get extracted lab values | patient (own), doctor |
| GET | `/reports/:reportId/summary` | Get AI-generated summary | patient (own), doctor |
| GET | `/reports/:patientId/compare` | Compare reports over time | doctor, patient (own) |
| DELETE | `/reports/:reportId` | Delete report | patient (own), admin |

### 3.5 Symptoms and Triage (`/api/v1/symptoms`)

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| POST | `/symptoms/session` | Start new symptom check session | patient |
| POST | `/symptoms/session/:id/message` | Send message in symptom session | patient |
| GET | `/symptoms/session/:id` | Get session details and diagnosis | patient (own), doctor |
| PUT | `/symptoms/session/:id/complete` | Complete symptom session | patient |
| GET | `/symptoms/history/:patientId` | Get past symptom sessions | patient (own), doctor |
| POST | `/symptoms/triage` | Quick triage assessment | patient |
| POST | `/symptoms/body-map` | Submit body map selections | patient |

### 3.6 Medications (`/api/v1/medications`)

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/medications/:patientId` | List patient medications | patient (own), doctor, nurse |
| POST | `/medications/:patientId` | Add medication / prescription | doctor |
| PUT | `/medications/:medicationId` | Update medication | doctor |
| DELETE | `/medications/:medicationId` | Discontinue medication | doctor |
| POST | `/medications/interaction-check` | Check drug interactions | patient, doctor, nurse |
| GET | `/medications/:patientId/schedule` | Get medication schedule | patient (own), nurse |
| POST | `/medications/:medicationId/adherence` | Log medication taken/missed | patient |
| GET | `/medications/search` | Search drug database | doctor, nurse, patient |

### 3.7 Appointments (`/api/v1/appointments`)

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/appointments` | List appointments (filtered) | patient, doctor, nurse, admin |
| POST | `/appointments` | Book new appointment | patient, nurse |
| GET | `/appointments/:id` | Get appointment details | patient (own), doctor (own), nurse |
| PUT | `/appointments/:id` | Update appointment | patient (own), doctor (own), nurse |
| PUT | `/appointments/:id/cancel` | Cancel appointment | patient (own), doctor (own) |
| GET | `/appointments/availability/:doctorId` | Get doctor availability | patient, nurse |
| GET | `/appointments/upcoming/:patientId` | Get upcoming appointments | patient (own), doctor, nurse |

### 3.8 Telemedicine (`/api/v1/telemedicine`)

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| POST | `/telemedicine/session` | Create telemedicine session | doctor |
| GET | `/telemedicine/session/:id` | Get session details | patient, doctor |
| POST | `/telemedicine/session/:id/join` | Join video session | patient, doctor |
| PUT | `/telemedicine/session/:id/end` | End session | doctor |
| GET | `/telemedicine/session/:id/transcript` | Get AI transcription | doctor |
| GET | `/telemedicine/session/:id/notes` | Get AI clinical notes | doctor |

### 3.9 Care Plans (`/api/v1/care-plans`)

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/care-plans/:patientId` | List patient care plans | patient (own), doctor |
| POST | `/care-plans/:patientId` | Create care plan | doctor |
| GET | `/care-plans/:planId` | Get care plan details | patient (own), doctor |
| PUT | `/care-plans/:planId` | Update care plan | doctor |
| POST | `/care-plans/:planId/goals` | Add goal to care plan | doctor |
| PUT | `/care-plans/:planId/goals/:goalId` | Update goal progress | patient, doctor |
| POST | `/care-plans/:patientId/generate` | AI-generate care plan | doctor |
| GET | `/care-plans/:planId/adherence` | Get adherence report | patient (own), doctor |

### 3.10 Chat and Voice (`/api/v1/chat`, `/api/v1/voice`)

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| POST | `/chat/message` | Send chat message to AI | patient, doctor |
| GET | `/chat/conversations` | List past conversations | patient, doctor |
| GET | `/chat/conversations/:id` | Get conversation history | patient (own), doctor |
| POST | `/voice/transcribe` | Transcribe audio file | patient, doctor |
| POST | `/voice/synthesize` | Generate speech from text | patient, doctor |
| POST | `/voice/session/start` | Start voice session | patient, doctor |
| POST | `/voice/session/:id/audio` | Send audio chunk in session | patient, doctor |
| PUT | `/voice/session/:id/end` | End voice session | patient, doctor |

### 3.11 Monitoring (`/api/v1/monitoring`)

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/monitoring/patients` | Get all monitored patients | doctor, nurse |
| GET | `/monitoring/patients/:id/status` | Get patient monitoring status | doctor, nurse |
| GET | `/monitoring/alerts` | List active alerts | doctor, nurse |
| PUT | `/monitoring/alerts/:id/acknowledge` | Acknowledge alert | doctor, nurse |
| PUT | `/monitoring/alerts/:id/resolve` | Resolve alert | doctor, nurse |
| PUT | `/monitoring/alerts/:id/escalate` | Escalate alert | nurse |
| POST | `/monitoring/thresholds/:patientId` | Set monitoring thresholds | doctor |
| GET | `/monitoring/dashboard` | Get monitoring wall data | doctor, nurse |

### 3.12 Devices (`/api/v1/devices`)

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/devices/:patientId` | List patient devices | patient (own), doctor, nurse |
| POST | `/devices/:patientId` | Register new device | patient (own), nurse |
| PUT | `/devices/:deviceId` | Update device | patient (own), nurse |
| DELETE | `/devices/:deviceId` | Remove device | patient (own), nurse, admin |
| POST | `/devices/:deviceId/data` | Ingest device data | device |

### 3.13 Notifications (`/api/v1/notifications`)

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/notifications` | Get user notifications | all |
| PUT | `/notifications/:id/read` | Mark as read | all |
| PUT | `/notifications/read-all` | Mark all as read | all |
| GET | `/notifications/preferences` | Get notification preferences | all |
| PUT | `/notifications/preferences` | Update notification preferences | all |

### 3.14 Analytics (`/api/v1/analytics`)

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/analytics/patient/:id/overview` | Patient health analytics | patient (own), doctor |
| GET | `/analytics/doctor/:id/overview` | Doctor performance analytics | doctor (own), admin |
| GET | `/analytics/system/overview` | System-wide analytics | admin |
| GET | `/analytics/ai/usage` | AI agent usage statistics | admin |
| GET | `/analytics/ai/accuracy` | AI prediction accuracy metrics | admin |

### 3.15 Admin (`/api/v1/admin`)

| Method | Endpoint | Description | Roles |
|--------|----------|-------------|-------|
| GET | `/admin/users` | List all users | admin |
| PUT | `/admin/users/:id/role` | Change user role | admin |
| PUT | `/admin/users/:id/activate` | Activate/deactivate user | admin |
| GET | `/admin/audit-logs` | View audit logs | admin |
| GET | `/admin/system-health` | System health dashboard | admin |
| PUT | `/admin/ai-config` | Update AI agent configuration | admin |

---

## 4. WebSocket Events

Connection URL: `ws://<host>/socket.io`

Authentication: Pass JWT token as query parameter or in handshake auth.

| Event | Direction | Description |
|-------|-----------|-------------|
| `vitals:update` | Server to Client | Real-time vitals data push |
| `vitals:alert` | Server to Client | Vitals threshold breach alert |
| `monitoring:alert` | Server to Client | Monitoring alert notification |
| `monitoring:status` | Server to Client | Patient status change |
| `chat:message` | Bidirectional | Chat message in/out |
| `chat:typing` | Bidirectional | Typing indicator |
| `chat:stream` | Server to Client | Streaming AI response tokens |
| `voice:transcript` | Server to Client | Real-time transcription |
| `notification:new` | Server to Client | New notification |
| `appointment:reminder` | Server to Client | Appointment reminder |
| `telemedicine:signal` | Bidirectional | WebRTC signaling |
| `device:status` | Server to Client | Device connection status |

### WebSocket Rooms

- `patient:<patient_id>` -- patient-specific vitals and alerts
- `doctor:<doctor_id>` -- doctor-specific notifications
- `monitoring:wall` -- monitoring wall feed (all monitored patients)
- `telemedicine:<room_id>` -- telemedicine session signaling
- `chat:<conversation_id>` -- chat session

---

## 5. Health Check

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/v1/health` | Service health check | No |

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "database": "up",
    "redis": "up",
    "influxdb": "up",
    "elasticsearch": "up",
    "celery": "up"
  },
  "timestamp": "2026-03-16T12:00:00Z"
}
```
