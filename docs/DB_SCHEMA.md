# Database Schema Document — MedAssist AI

---

## 1. Overview

MedAssist AI uses a polyglot persistence strategy:

| Store | Purpose | Data |
|-------|---------|------|
| PostgreSQL 16 | Primary relational store | Users, profiles, medical records, appointments, care plans, audit logs |
| InfluxDB | Time-series store | Raw vitals data from IoT devices |
| Pinecone | Vector database | Medical knowledge embeddings for RAG |
| Redis 7 | Cache and broker | Session cache, agent short-term memory, Celery broker |
| Elasticsearch | Full-text search | Medical records, audit logs, clinical notes |
| S3/MinIO | Object storage | Report files (PDF, images), recordings |

---

## 2. PostgreSQL Schema

### 2.1 Users and Authentication

```sql
-- Users table (polymorphic -- patients, doctors, admins, nurses)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('patient', 'doctor', 'admin', 'nurse')),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    avatar_url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_secret VARCHAR(255),
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Patient profiles
CREATE TABLE patient_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    date_of_birth DATE NOT NULL,
    gender VARCHAR(20),
    blood_type VARCHAR(5),
    height_cm DECIMAL(5,2),
    weight_kg DECIMAL(5,2),
    emergency_contact_name VARCHAR(200),
    emergency_contact_phone VARCHAR(20),
    insurance_provider VARCHAR(200),
    insurance_policy_number VARCHAR(100),
    primary_physician_id UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Doctor profiles
CREATE TABLE doctor_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    license_number VARCHAR(100) UNIQUE NOT NULL,
    specialization VARCHAR(200) NOT NULL,
    department VARCHAR(200),
    hospital_affiliation VARCHAR(300),
    years_of_experience INTEGER,
    consultation_fee DECIMAL(10,2),
    available_for_telemedicine BOOLEAN DEFAULT TRUE,
    bio TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 2.2 Medical Records

```sql
-- Medical history
CREATE TABLE medical_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patient_profiles(id) ON DELETE CASCADE,
    condition_name VARCHAR(300) NOT NULL,
    icd10_code VARCHAR(10),
    diagnosis_date DATE,
    status VARCHAR(20) CHECK (status IN ('active', 'resolved', 'chronic', 'in_remission')),
    notes TEXT,
    diagnosed_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Allergies
CREATE TABLE allergies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patient_profiles(id) ON DELETE CASCADE,
    allergen VARCHAR(200) NOT NULL,
    reaction_type VARCHAR(100),
    severity VARCHAR(20) CHECK (severity IN ('mild', 'moderate', 'severe', 'life_threatening')),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Medications
CREATE TABLE medications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patient_profiles(id) ON DELETE CASCADE,
    prescribed_by UUID REFERENCES users(id),
    drug_name VARCHAR(300) NOT NULL,
    generic_name VARCHAR(300),
    dosage VARCHAR(100) NOT NULL,
    frequency VARCHAR(100) NOT NULL,
    route VARCHAR(50),
    start_date DATE NOT NULL,
    end_date DATE,
    status VARCHAR(20) CHECK (status IN ('active', 'completed', 'discontinued', 'on_hold')),
    reason TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Medical reports
CREATE TABLE medical_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patient_profiles(id) ON DELETE CASCADE,
    uploaded_by UUID REFERENCES users(id),
    report_type VARCHAR(50) NOT NULL CHECK (report_type IN ('lab', 'imaging', 'pathology', 'cardiology', 'radiology', 'other')),
    title VARCHAR(300) NOT NULL,
    file_url TEXT NOT NULL,
    file_type VARCHAR(20),
    file_size_bytes BIGINT,
    report_date DATE,
    ordering_physician UUID REFERENCES users(id),
    ai_analysis_status VARCHAR(20) DEFAULT 'pending' CHECK (ai_analysis_status IN ('pending', 'processing', 'completed', 'failed')),
    ai_analysis JSONB,
    ai_summary TEXT,
    abnormalities JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Lab values (extracted from reports)
CREATE TABLE lab_values (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID REFERENCES medical_reports(id) ON DELETE CASCADE,
    patient_id UUID REFERENCES patient_profiles(id),
    test_name VARCHAR(200) NOT NULL,
    loinc_code VARCHAR(20),
    value DECIMAL(15,5),
    value_text VARCHAR(200),
    unit VARCHAR(50),
    reference_range_low DECIMAL(15,5),
    reference_range_high DECIMAL(15,5),
    is_abnormal BOOLEAN DEFAULT FALSE,
    abnormality_severity VARCHAR(20),
    recorded_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 2.3 Vitals and Monitoring

```sql
-- Vitals readings (summary in PostgreSQL; raw data in InfluxDB)
CREATE TABLE vitals_readings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patient_profiles(id) ON DELETE CASCADE,
    device_id UUID REFERENCES devices(id),
    heart_rate INTEGER,
    systolic_bp INTEGER,
    diastolic_bp INTEGER,
    spo2 DECIMAL(5,2),
    temperature DECIMAL(4,1),
    respiratory_rate INTEGER,
    blood_glucose DECIMAL(6,2),
    weight_kg DECIMAL(5,2),
    pain_level INTEGER CHECK (pain_level BETWEEN 0 AND 10),
    source VARCHAR(30) CHECK (source IN ('manual', 'device', 'wearable', 'bedside_monitor')),
    recorded_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- IoT devices
CREATE TABLE devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patient_profiles(id),
    device_type VARCHAR(50) NOT NULL,
    device_name VARCHAR(200),
    manufacturer VARCHAR(200),
    model VARCHAR(200),
    serial_number VARCHAR(200),
    firmware_version VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    last_sync_at TIMESTAMP,
    battery_level INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Monitoring alerts
CREATE TABLE monitoring_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patient_profiles(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('info', 'warning', 'critical', 'emergency')),
    title VARCHAR(300) NOT NULL,
    description TEXT,
    vital_type VARCHAR(50),
    vital_value DECIMAL(15,5),
    threshold_breached VARCHAR(200),
    ai_assessment TEXT,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'acknowledged', 'resolved', 'escalated', 'false_alarm')),
    acknowledged_by UUID REFERENCES users(id),
    acknowledged_at TIMESTAMP,
    resolved_by UUID REFERENCES users(id),
    resolved_at TIMESTAMP,
    escalation_level INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 2.4 Symptoms and Triage

```sql
-- Symptom check sessions
CREATE TABLE symptom_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patient_profiles(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'abandoned')),
    initial_complaint TEXT NOT NULL,
    conversation_log JSONB,
    reported_symptoms JSONB,
    differential_diagnosis JSONB,
    urgency_score INTEGER CHECK (urgency_score BETWEEN 1 AND 10),
    esi_level INTEGER CHECK (esi_level BETWEEN 1 AND 5),
    recommended_action VARCHAR(50),
    recommended_specialist VARCHAR(200),
    ai_confidence DECIMAL(4,3),
    reviewed_by UUID REFERENCES users(id),
    review_notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

### 2.5 Appointments and Telemedicine

```sql
-- Appointments
CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patient_profiles(id) ON DELETE CASCADE,
    doctor_id UUID REFERENCES doctor_profiles(id) ON DELETE CASCADE,
    appointment_type VARCHAR(30) CHECK (appointment_type IN ('in_person', 'telemedicine', 'follow_up', 'emergency')),
    status VARCHAR(20) DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show')),
    scheduled_at TIMESTAMP NOT NULL,
    duration_minutes INTEGER DEFAULT 30,
    reason TEXT,
    notes TEXT,
    priority INTEGER DEFAULT 3,
    symptom_session_id UUID REFERENCES symptom_sessions(id),
    telemedicine_room_id VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Telemedicine sessions
CREATE TABLE telemedicine_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id UUID REFERENCES appointments(id) ON DELETE CASCADE,
    room_id VARCHAR(200) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'waiting' CHECK (status IN ('waiting', 'active', 'ended')),
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    duration_seconds INTEGER,
    recording_url TEXT,
    ai_transcription TEXT,
    ai_clinical_notes TEXT,
    ai_summary TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 2.6 Care Plans

```sql
-- Care plans
CREATE TABLE care_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patient_profiles(id) ON DELETE CASCADE,
    created_by UUID REFERENCES users(id),
    title VARCHAR(300) NOT NULL,
    description TEXT,
    condition VARCHAR(300),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('draft', 'active', 'paused', 'completed', 'discontinued')),
    start_date DATE NOT NULL,
    target_end_date DATE,
    actual_end_date DATE,
    ai_generated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Care plan goals
CREATE TABLE care_plan_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_plan_id UUID REFERENCES care_plans(id) ON DELETE CASCADE,
    title VARCHAR(300) NOT NULL,
    description TEXT,
    target_value VARCHAR(200),
    current_value VARCHAR(200),
    unit VARCHAR(50),
    status VARCHAR(20) DEFAULT 'in_progress' CHECK (status IN ('not_started', 'in_progress', 'achieved', 'missed')),
    target_date DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Care plan activities/tasks
CREATE TABLE care_plan_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    care_plan_id UUID REFERENCES care_plans(id) ON DELETE CASCADE,
    title VARCHAR(300) NOT NULL,
    description TEXT,
    activity_type VARCHAR(50) CHECK (activity_type IN ('medication', 'exercise', 'diet', 'appointment', 'test', 'lifestyle', 'other')),
    frequency VARCHAR(100),
    time_of_day VARCHAR(50),
    is_completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 2.7 Conversations and Audit

```sql
-- Conversations (chat and voice)
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patient_profiles(id),
    user_id UUID REFERENCES users(id),
    conversation_type VARCHAR(20) CHECK (conversation_type IN ('chat', 'voice', 'symptom_check')),
    agent_type VARCHAR(50),
    messages JSONB,
    metadata JSONB,
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- HIPAA audit log
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id UUID,
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Notifications
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(300) NOT NULL,
    body TEXT,
    data JSONB,
    channel VARCHAR(20) CHECK (channel IN ('push', 'sms', 'email', 'in_app')),
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP,
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 3. Relationships Diagram (Text)

```
users (1) ---< patient_profiles (1)
users (1) ---< doctor_profiles (1)
users (1) ---< audit_logs (many)
users (1) ---< notifications (many)
users (1) ---< conversations (many)

patient_profiles (1) ---< medical_history (many)
patient_profiles (1) ---< allergies (many)
patient_profiles (1) ---< medications (many)
patient_profiles (1) ---< medical_reports (many)
patient_profiles (1) ---< vitals_readings (many)
patient_profiles (1) ---< devices (many)
patient_profiles (1) ---< monitoring_alerts (many)
patient_profiles (1) ---< symptom_sessions (many)
patient_profiles (1) ---< appointments (many)
patient_profiles (1) ---< care_plans (many)
patient_profiles (1) ---< conversations (many)

doctor_profiles (1) ---< appointments (many)

medical_reports (1) ---< lab_values (many)

appointments (1) ---< telemedicine_sessions (1)
appointments (1) ---  symptom_sessions (optional FK)

care_plans (1) ---< care_plan_goals (many)
care_plans (1) ---< care_plan_activities (many)

devices (1) ---< vitals_readings (many)
```

---

## 4. Index Strategy

```sql
-- Users
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- Patient profiles
CREATE INDEX idx_patient_profiles_user_id ON patient_profiles(user_id);
CREATE INDEX idx_patient_profiles_primary_physician ON patient_profiles(primary_physician_id);

-- Doctor profiles
CREATE INDEX idx_doctor_profiles_user_id ON doctor_profiles(user_id);
CREATE INDEX idx_doctor_profiles_specialization ON doctor_profiles(specialization);

-- Medical history
CREATE INDEX idx_medical_history_patient ON medical_history(patient_id);
CREATE INDEX idx_medical_history_icd10 ON medical_history(icd10_code);

-- Medications
CREATE INDEX idx_medications_patient ON medications(patient_id);
CREATE INDEX idx_medications_status ON medications(status);

-- Medical reports
CREATE INDEX idx_medical_reports_patient ON medical_reports(patient_id);
CREATE INDEX idx_medical_reports_type ON medical_reports(report_type);
CREATE INDEX idx_medical_reports_ai_status ON medical_reports(ai_analysis_status);

-- Lab values
CREATE INDEX idx_lab_values_report ON lab_values(report_id);
CREATE INDEX idx_lab_values_patient ON lab_values(patient_id);
CREATE INDEX idx_lab_values_test ON lab_values(test_name);
CREATE INDEX idx_lab_values_loinc ON lab_values(loinc_code);

-- Vitals readings
CREATE INDEX idx_vitals_patient ON vitals_readings(patient_id);
CREATE INDEX idx_vitals_recorded_at ON vitals_readings(recorded_at);
CREATE INDEX idx_vitals_patient_time ON vitals_readings(patient_id, recorded_at DESC);

-- Monitoring alerts
CREATE INDEX idx_alerts_patient ON monitoring_alerts(patient_id);
CREATE INDEX idx_alerts_status ON monitoring_alerts(status);
CREATE INDEX idx_alerts_severity ON monitoring_alerts(severity);
CREATE INDEX idx_alerts_created ON monitoring_alerts(created_at);

-- Symptom sessions
CREATE INDEX idx_symptom_sessions_patient ON symptom_sessions(patient_id);

-- Appointments
CREATE INDEX idx_appointments_patient ON appointments(patient_id);
CREATE INDEX idx_appointments_doctor ON appointments(doctor_id);
CREATE INDEX idx_appointments_scheduled ON appointments(scheduled_at);
CREATE INDEX idx_appointments_status ON appointments(status);

-- Care plans
CREATE INDEX idx_care_plans_patient ON care_plans(patient_id);
CREATE INDEX idx_care_plans_status ON care_plans(status);

-- Audit logs
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);

-- Notifications
CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_notifications_unread ON notifications(user_id, is_read) WHERE is_read = FALSE;

-- Conversations
CREATE INDEX idx_conversations_patient ON conversations(patient_id);
CREATE INDEX idx_conversations_user ON conversations(user_id);
```

---

## 5. Migration Strategy (Alembic)

Alembic is used for all PostgreSQL schema migrations.

```
backend/
  migrations/
    alembic.ini
    env.py
    versions/
      001_initial_schema.py
      002_add_care_plans.py
      ...
```

### Commands

```bash
# Generate a new migration after model changes
flask db migrate -m "description of change"

# Apply pending migrations
flask db upgrade

# Rollback one migration
flask db downgrade -1

# View migration history
flask db history
```

### Conventions
- Each migration is a single atomic change.
- Always provide a descriptive message.
- Test migrations in staging before production.
- Never modify a migration that has been applied to staging or production -- create a new one instead.

---

## 6. InfluxDB Schema (Time-Series Vitals)

InfluxDB is used for high-frequency raw vitals data from IoT devices. PostgreSQL `vitals_readings` stores periodic summaries.

### Measurement: `patient_vitals`

| Field | Type | Description |
|-------|------|-------------|
| heart_rate | integer | Beats per minute |
| systolic_bp | integer | mmHg |
| diastolic_bp | integer | mmHg |
| spo2 | float | Oxygen saturation % |
| temperature | float | Celsius |
| respiratory_rate | integer | Breaths per minute |
| blood_glucose | float | mg/dL |

### Tags

| Tag | Description |
|-----|-------------|
| patient_id | UUID of patient profile |
| device_id | UUID of source device |
| device_type | Type of device (wearable, bedside_monitor, etc.) |
| source | Data source identifier |

### Retention Policies

| Policy | Duration | Purpose |
|--------|----------|---------|
| raw | 30 days | Full-resolution data (every reading) |
| downsampled_1h | 1 year | Hourly averages for trend analysis |
| downsampled_1d | 7 years | Daily averages for long-term storage (HIPAA) |

### Continuous Queries

```
-- Downsample to hourly averages
CREATE CONTINUOUS QUERY cq_hourly ON medassist
BEGIN
  SELECT mean(heart_rate), mean(systolic_bp), mean(diastolic_bp),
         mean(spo2), mean(temperature), mean(respiratory_rate),
         mean(blood_glucose)
  INTO downsampled_1h.patient_vitals
  FROM raw.patient_vitals
  GROUP BY time(1h), patient_id, device_id
END

-- Downsample to daily averages
CREATE CONTINUOUS QUERY cq_daily ON medassist
BEGIN
  SELECT mean(heart_rate), mean(systolic_bp), mean(diastolic_bp),
         mean(spo2), mean(temperature), mean(respiratory_rate),
         mean(blood_glucose)
  INTO downsampled_1d.patient_vitals
  FROM downsampled_1h.patient_vitals
  GROUP BY time(1d), patient_id
END
```

---

## 7. Pinecone Index (Medical Knowledge Embeddings)

### Index: `medical-knowledge`

| Parameter | Value |
|-----------|-------|
| Dimension | 3072 (text-embedding-3-large) |
| Metric | cosine |
| Pod type | p1.x1 (or serverless) |

### Metadata Fields

| Field | Type | Description |
|-------|------|-------------|
| source | string | Source document (e.g., "icd10", "drug_interactions", "clinical_guidelines") |
| category | string | Medical category (e.g., "cardiology", "endocrinology") |
| content_type | string | Type: "symptom", "condition", "drug", "guideline", "lab_reference" |
| icd10_code | string | Associated ICD-10 code (if applicable) |
| last_updated | string | ISO timestamp of last embedding refresh |

### Namespaces

| Namespace | Content |
|-----------|---------|
| symptoms | Symptom-to-disease mappings |
| drugs | Drug information, interactions, dosages |
| lab_references | Lab test reference ranges and interpretations |
| clinical_guidelines | Evidence-based clinical guidelines |
| icd10 | ICD-10 code descriptions and relationships |

### Seeding

```bash
python scripts/seed_knowledge_base.py
```

This script reads from `data/medical_knowledge/` (JSON files for ICD-10 codes, drug interactions, lab reference ranges, symptom-disease mappings), generates embeddings via OpenAI `text-embedding-3-large`, and upserts into Pinecone with metadata.
