# Voice AI Agent — Patient Registration Service
**Technical Take-Home Assessment Submission**

A production-oriented, telephony-integrated voice AI agent that registers U.S. patients through natural conversational dialogue, validates demographics server-side, persists records to a relational database, and exposes management operations via a companion RESTful API and live dashboard.

---

## 📞 Live Submission Details

| Item | Value |
| :--- | :--- |
| **Real U.S. Phone Number** | `+1 (318) 833 9857` |
| **Live API Base URL** | `https://partnerships-charitable-extreme-marina.trycloudflare.com` |
| **Interactive API Documentation** | `https://partnerships-charitable-extreme-marina.trycloudflare.com/docs` |
| **Live Web Intake Dashboard** | `https://partnerships-charitable-extreme-marina.trycloudflare.com/` |

---

## 🏛️ System Architecture

```text
Phone Call (Caller) 
      ↕ Telephony (Vapi / PSTN)
Voice AI Agent (Deepgram STT + LLM Prompt + ElevenLabs/Cartesia TTS)
      ↓ Webhook / Tool Calling (HTTPS)
Companion Web Service (Python FastAPI)
      ↕ Server-Side Pydantic Validation & CRUD
Persistent Relational Database (SQLite `patients.db`)
```

### Separation of Concerns
1. **Telephony & Conversational Voice Layer (`Vapi.ai`)**:
   - Connects to real PSTN carriers via a dedicated U.S. phone number (`+1 318 833 9857`).
   - Uses sub-500ms real-time Speech-to-Text (STT) and natural Text-to-Speech (TTS).
   - Driven by a carefully engineered system prompt designed to behave like an empathetic, human medical intake coordinator.
   - Enforces confirmation read-back before executing external tools.

2. **REST Web Service Layer (`main.py` - FastAPI)**:
   - Exposes RESTful endpoints conforming strictly to specification.
   - Returns consistent JSON envelopes: `{ "data": {...}, "error": null }`.
   - Handles both raw JSON REST requests and Vapi tool-call payload structures.
   - Serves an auto-refreshing real-time Web Dashboard at `/` for visual auditability.

3. **Data Modeling & Validation Layer (`models.py` - Pydantic)**:
   - Server-side validation independent of the voice layer.
   - Enforces:
     - Alphabetic names with hyphens/apostrophes (1–50 chars).
     - Valid `MM/DD/YYYY` dates strictly in the past (non-future).
     - Standardized 10-digit U.S. phone numbers.
     - Sex enumeration (`Male`, `Female`, `Other`, `Decline to Answer`).
     - Valid 2-letter U.S. state abbreviations and 5-digit ZIP codes.

4. **Persistence Layer (`database.py` - SQLite)**:
   - File-backed persistent storage (`patients.db`) surviving server restarts.
   - Generates auto-assigned UUIDv4 identifiers, UTC timestamps (`created_at`, `updated_at`), and `deleted_at` timestamps for soft-deletions.

---

## 📋 Patient Demographic Data Model

| Field | Type | Validation / Constraints | Required |
| :--- | :--- | :--- | :---: |
| `patient_id` | UUIDv4 | Unique primary key, auto-generated | Auto |
| `first_name` | String | 1–50 chars, alphabetic + hyphens/apostrophes | Yes |
| `last_name` | String | 1–50 chars, alphabetic + hyphens/apostrophes | Yes |
| `date_of_birth` | Date | `MM/DD/YYYY`, valid past date | Yes |
| `sex` | Enum | `Male`, `Female`, `Other`, `Decline to Answer` | Yes |
| `phone_number` | String | 10-digit U.S. phone number | Yes |
| `email` | String | Valid RFC 5322 email format | No |
| `address_line_1` | String | Street address | Yes |
| `address_line_2` | String | Apt/Suite/Unit | No |
| `city` | String | 1–100 characters | Yes |
| `state` | String | Valid 2-letter U.S. state code (e.g., NY, PA, CA) | Yes |
| `zip_code` | String | 5-digit U.S. ZIP format (or ZIP+4) | Yes |
| `insurance_provider` | String | Insurance carrier name | No |
| `insurance_member_id`| String | Alphanumeric member ID | No |
| `preferred_language` | String | Default: English | No |
| `emergency_contact_name` | String | Full contact name | No |
| `emergency_contact_phone`| String | 10-digit U.S. phone number | No |
| `created_at` | Timestamp | UTC ISO 8601 auto-generated | Auto |
| `updated_at` | Timestamp | UTC ISO 8601 auto-generated | Auto |
| `deleted_at` | Timestamp | Soft-delete timestamp (NULL if active) | Auto |

---

## 🚀 API Endpoints Reference

All endpoints return HTTP status codes and uniform JSON responses:

### 1. List Patients
- **`GET /patients`**
- Optional Query Parameters:
  - `?last_name=Scott`
  - `?date_of_birth=03/15/1965`
  - `?phone_number=2125550123`
  - `?include_deleted=false`
- **Response `200 OK`**:
```json
{
  "data": [
    {
      "patient_id": "8372b2cd-ff8d-4f99-89b5-94ac05235e8b",
      "first_name": "Michael",
      "last_name": "Scott",
      "date_of_birth": "03/15/1965",
      "sex": "Male",
      "phone_number": "2125550123",
      "city": "Scranton",
      "state": "PA",
      "zip_code": "18503",
      "created_at": "2026-11-03T11:52:10.855544+00:00",
      "updated_at": "2026-11-03T11:52:10.855544+00:00",
      "deleted_at": null
    }
  ],
  "error": null
}
```

### 2. Retrieve Single Patient
- **`GET /patients/{id}`**
- Returns `200 OK` or `404 Not Found` if missing/soft-deleted.

### 3. Create Patient
- **`POST /patients`**
- Validates payload via Pydantic model.
- Returns `201 Created` with generated record and UUID.

### 4. Update Patient (Partial Updates Allowed)
- **`PUT /patients/{id}`**
- Accepts partial demographic payload, updates `updated_at`.
- Returns `200 OK` with updated record.

### 5. Soft-Delete Patient
- **`DELETE /patients/{id}`**
- Sets `deleted_at` timestamp without destroying the record.
- Returns `200 OK`.

### 6. Voice Agent Integration Endpoints
- **`POST /api/voice/register-patient`**: Invoked by Vapi when caller confirms registration details.
- **`POST /api/voice/check-patient`**: Duplicate caller detection by phone number (Bonus).

---

## 💬 Conversational Design & Prompt Engineering

The system prompt enforces:
1. **Natural Dialogue vs. Rigid Menus**: Avoids robotic IVR phrasing; greets warmly and adapts to unstructured caller statements.
2. **Explicit Clarification & Spelling**: Prompts callers to spell non-standard names.
3. **Graceful Re-prompting**: If an invalid DOB (e.g., year in the future) or an incomplete phone number is given, the agent re-prompts specifically for that field.
4. **Conversational Opt-in for Optional Fields**:
   > *"I can also collect your insurance information, emergency contact, and preferred language. Would you like to provide any of those?"*
5. **Read-Back Confirmation**: Before executing any database persistence, reads back the collected profile and asks for explicit confirmation.
6. **Graceful Completion**:
   > *"You're all set, [First Name]! Your registration is complete. Thank you for choosing CareCloud Health Clinic. Have a wonderful day!"*

---

## 🛠️ Local Setup & Reproduction Instructions

### Prerequisites
- Python 3.10+
- `pip`

### 1. Clone & Install Dependencies
```bash
pip install fastapi uvicorn pydantic[email] python-dotenv
```

### 2. Initialize Persistent Database
```bash
python database.py
```
*(Creates `patients.db` with schema and demonstration seed patient).*

### 3. Start REST API Server
```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
- Dashboard: `http://localhost:8000/`
- Swagger Docs: `http://localhost:8000/docs`

---

## ⚖️ Trade-offs and Architectural Decisions

1. **Vapi Platform vs. Scratch STT/TTS**:
   - *Decision*: Adopted Vapi for telephony orchestration.
   - *Rationale*: Sub-3-hour time constraint prioritized solid LLM tool integration, audio latency minimization, and reliable PSTN connectivity over low-level WebRTC/SIP plumbing.
2. **SQLite vs. Hosted PostgreSQL**:
   - *Decision*: File-based SQLite with WAL mode.
   - *Rationale*: Zero external credentials required for local reproducibility, instant setup, satisfies persistence surviving server restarts without cloud DB provisioning latency.
3. **Cloudflare Tunnel (`cloudflared`) vs. Temporary Forwarders**:
   - *Decision*: Embedded Cloudflare edge tunnel.
   - *Rationale*: Guarantees persistent, high-throughput HTTPS connectivity from carrier telephony to local API without dropping or expiring.

---

## 🌟 Bonus Features Implemented

- [x] **Live Web Dashboard**: Interactive UI at root `/` displaying registered patients in real-time.
- [x] **Duplicate Detection**: Endpoint `/api/voice/check-patient` to recognize existing callers by phone number.
- [x] **Server-side Input Normalization**: Resilient adapter in the API that gracefully parses both flat and nested JSON schemas from the voice caller.
