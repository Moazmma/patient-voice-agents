import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, status, Query
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from database import get_connection, init_db
from models import PatientCreate, PatientUpdate

# Setup Logging (Observability requirement)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("patient_api")

app = FastAPI(
    title="Voice AI Patient Registration API",
    description="REST API for Patient Registration Voice Agent",
    version="1.0.0"
)

# CORS allow karein taake kahin se bhi call ho sakay
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Application started. Database initialized.")

# Custom Validation Error Handler (Consistent Envelope { "data": null, "error": ... })
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [f"{err['loc'][-1]}: {err['msg']}" for err in exc.errors()]
    error_msg = "; ".join(errors)
    logger.warning(f"Validation failed: {error_msg}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"data": None, "error": error_msg}
    )

# Custom HTTP Error Handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"data": None, "error": exc.detail}
    )

# -------------------------------------------------------------
# REST API ENDPOINTS
# -------------------------------------------------------------

# 1. GET /patients (List all patients with optional search filters)
@app.get("/patients", status_code=status.HTTP_200_OK)
def list_patients(
    last_name: Optional[str] = Query(None),
    date_of_birth: Optional[str] = Query(None),
    phone_number: Optional[str] = Query(None),
    include_deleted: bool = False
):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM patients WHERE 1=1"
    params = []
    
    if not include_deleted:
        query += " AND deleted_at IS NULL"
    if last_name:
        query += " AND LOWER(last_name) = LOWER(?)"
        params.append(last_name.strip())
    if date_of_birth:
        query += " AND date_of_birth = ?"
        params.append(date_of_birth.strip())
    if phone_number:
        # Normalize digits
        clean_phone = "".join(filter(str.isdigit, phone_number))
        query += " AND phone_number LIKE ?"
        params.append(f"%{clean_phone}%")
        
    query += " ORDER BY created_at DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    patients = [dict(row) for row in rows]
    return {"data": patients, "error": None}

# 2. GET /patients/:id (Retrieve single patient by UUID)
@app.get("/patients/{patient_id}", status_code=status.HTTP_200_OK)
def get_patient(patient_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients WHERE patient_id = ? AND deleted_at IS NULL", (patient_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Patient with ID {patient_id} not found")
        
    return {"data": dict(row), "error": None}

# 3. POST /patients (Create a new patient record)
@app.post("/patients", status_code=status.HTTP_201_CREATED)
def create_patient(payload: PatientCreate):
    conn = get_connection()
    cursor = conn.cursor()
    
    patient_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    cursor.execute("""
    INSERT INTO patients (
        patient_id, first_name, last_name, date_of_birth, sex,
        phone_number, email, address_line_1, address_line_2,
        city, state, zip_code, insurance_provider, insurance_member_id,
        preferred_language, emergency_contact_name, emergency_contact_phone,
        created_at, updated_at, deleted_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
    """, (
        patient_id, payload.first_name, payload.last_name, payload.date_of_birth, payload.sex.value,
        payload.phone_number, payload.email, payload.address_line_1, payload.address_line_2,
        payload.city, payload.state, payload.zip_code, payload.insurance_provider, payload.insurance_member_id,
        payload.preferred_language, payload.emergency_contact_name, payload.emergency_contact_phone,
        now, now
    ))
    conn.commit()
    
    # Retrieve created record
    cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
    created_record = dict(cursor.fetchone())
    conn.close()
    
    logger.info(f"Registered new patient: {payload.first_name} {payload.last_name} (ID: {patient_id})")
    return {"data": created_record, "error": None}

# 4. PUT /patients/:id (Update patient record - partial updates allowed)
@app.put("/patients/{patient_id}", status_code=status.HTTP_200_OK)
def update_patient(patient_id: str, payload: PatientUpdate):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM patients WHERE patient_id = ? AND deleted_at IS NULL", (patient_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Patient with ID {patient_id} not found")
        
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        conn.close()
        return {"data": dict(existing), "error": None}
        
    set_clauses = []
    params = []
    for field, value in updates.items():
        set_clauses.append(f"{field} = ?")
        params.append(value.value if hasattr(value, "value") else value)
        
    now = datetime.now(timezone.utc).isoformat()
    set_clauses.append("updated_at = ?")
    params.append(now)
    params.append(patient_id)
    
    query = f"UPDATE patients SET {', '.join(set_clauses)} WHERE patient_id = ?"
    cursor.execute(query, params)
    conn.commit()
    
    cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
    updated_record = dict(cursor.fetchone())
    conn.close()
    
    logger.info(f"Updated patient {patient_id}: {list(updates.keys())}")
    return {"data": updated_record, "error": None}

# 5. DELETE /patients/:id (Soft-delete patient record)
@app.delete("/patients/{patient_id}", status_code=status.HTTP_200_OK)
def delete_patient(patient_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM patients WHERE patient_id = ? AND deleted_at IS NULL", (patient_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Patient with ID {patient_id} not found")
        
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute("UPDATE patients SET deleted_at = ?, updated_at = ? WHERE patient_id = ?", (now, now, patient_id))
    conn.commit()
    conn.close()
    
    logger.info(f"Soft-deleted patient: {patient_id}")
    return {"data": {"patient_id": patient_id, "deleted_at": now, "status": "soft_deleted"}, "error": None}

# -------------------------------------------------------------
# VOICE AGENT (VAPI / RETELL) TOOL INTEGRATION ENDPOINTS
# -------------------------------------------------------------

# Bonus Tool 1: Check if caller is already registered
@app.post("/api/voice/check-patient")
async def voice_check_patient(request: Request):
    body = await request.json()
    logger.info(f"Voice Agent checking caller: {body}")
    
    # Extract phone from Vapi tool call or direct JSON
    phone = body.get("phone_number") or body.get("message", {}).get("toolCalls", [{}])[0].get("function", {}).get("arguments", {}).get("phone_number", "")
    clean_phone = "".join(filter(str.isdigit, phone))
    
    if len(clean_phone) == 11 and clean_phone.startswith("1"):
        clean_phone = clean_phone[1:]
        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients WHERE phone_number = ? AND deleted_at IS NULL", (clean_phone,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        patient = dict(row)
        return {
            "found": True,
            "patient_id": patient["patient_id"],
            "first_name": patient["first_name"],
            "last_name": patient["last_name"],
            "message": f"Found existing record for {patient['first_name']} {patient['last_name']}."
        }
    return {"found": False, "message": "No existing record found."}

# Main Tool 2: Voice agent registers patient on call completion
@app.post("/api/voice/register-patient")
async def voice_register_patient(request: Request):
    import json
    body = await request.json()
    logger.info(f"Voice Agent register payload received: {body}")
    
    tool_call_id = None
    args = body
    
    # Check if this is wrapped in Vapi's standard tool-call structure
    if "message" in body and "toolCalls" in body["message"]:
        tool_call = body["message"]["toolCalls"][0]
        tool_call_id = tool_call.get("id")
        func_args = tool_call.get("function", {}).get("arguments", {})
        if isinstance(func_args, str):
            try:
                args = json.loads(func_args)
            except Exception:
                args = {}
        else:
            args = func_args
            
    # Sometimes Vapi passes nested arguments directly
    elif "toolCalls" in body:
        tool_call = body["toolCalls"][0]
        tool_call_id = tool_call.get("id")
        func_args = tool_call.get("function", {}).get("arguments", {})
        args = json.loads(func_args) if isinstance(func_args, str) else func_args
        
    try:
        # Smart normalization for field name variations
        if "full_legal_name" in args and "first_name" not in args:
            parts = args["full_legal_name"].strip().split(None, 1)
            args["first_name"] = parts[0]
            args["last_name"] = parts[1] if len(parts) > 1 else parts[0]
            
        if "address" in args and isinstance(args["address"], dict):
            addr = args["address"]
            args["address_line_1"] = addr.get("street") or addr.get("address_line_1", "100 Main St")
            args["city"] = addr.get("city", "New York")
            raw_state = addr.get("state_or_region") or addr.get("state", "NY")
            args["state"] = raw_state[:2].upper() if len(raw_state) >= 2 else "NY"
            args["zip_code"] = "".join(filter(str.isdigit, addr.get("postal_code") or addr.get("zip_code", "10001")))[:5]
            
        if "sex" not in args or not args["sex"]:
            args["sex"] = "Other"
            
        # Validate through our PatientCreate model
        patient_obj = PatientCreate(**args)
        result = create_patient(patient_obj)
        patient_id = result["data"]["patient_id"]
        success_msg = f"Patient {patient_obj.first_name} {patient_obj.last_name} registered successfully with ID {patient_id}."
        logger.info(success_msg)
        
        response = {
            "success": True,
            "patient_id": patient_id,
            "message": success_msg
        }
        
        if tool_call_id:
            response["results"] = [
                {
                    "toolCallId": tool_call_id,
                    "result": success_msg
                }
            ]
        return response
    except Exception as e:
        logger.error(f"Voice registration error: {str(e)}")
        err_msg = f"Failed to register patient: {str(e)}"
        response = {
            "success": False,
            "error": err_msg
        }
        if tool_call_id:
            response["results"] = [
                {
                    "toolCallId": tool_call_id,
                    "result": err_msg
                }
            ]
        return response

# -------------------------------------------------------------
# BONUS: LIVE WEB DASHBOARD
# -------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CareCloud Voice AI - Registered Patients</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>body { font-family: 'Outfit', sans-serif; }</style>
    </head>
    <body class="bg-slate-50 min-h-screen text-slate-800">
        <header class="bg-white border-b border-slate-200 sticky top-0 z-10 shadow-sm">
            <div class="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center text-white font-bold text-xl">AI</div>
                    <div>
                        <h1 class="font-bold text-xl text-slate-900 leading-tight">Patient Voice Agent Service</h1>
                        <p class="text-xs text-slate-500">Live Intake Dashboard & REST API</p>
                    </div>
                </div>
                <div class="flex gap-3">
                    <a href="/docs" target="_blank" class="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-sm font-semibold transition">Swagger API Docs</a>
                    <button onclick="fetchPatients()" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold transition">Refresh Data</button>
                </div>
            </div>
        </header>

        <main class="max-w-7xl mx-auto px-6 py-8">
            <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                <div class="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                    <div>
                        <h2 class="text-lg font-bold text-slate-900">Registered Patient Records</h2>
                        <p class="text-sm text-slate-500">Auto-synced from Phone Voice Agent intake</p>
                    </div>
                    <span id="patient-count" class="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-xs font-semibold">Loading...</span>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm text-slate-600">
                        <thead class="bg-slate-50 text-slate-500 font-semibold uppercase text-xs border-b border-slate-200">
                            <tr>
                                <th class="px-6 py-4">Patient Name</th>
                                <th class="px-6 py-4">DOB</th>
                                <th class="px-6 py-4">Phone</th>
                                <th class="px-6 py-4">Location</th>
                                <th class="px-6 py-4">Insurance</th>
                                <th class="px-6 py-4">Registered (UTC)</th>
                            </tr>
                        </thead>
                        <tbody id="patient-table-body" class="divide-y divide-slate-100">
                            <tr><td colspan="6" class="px-6 py-8 text-center text-slate-400">Loading patients...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </main>

        <script>
            async function fetchPatients() {
                try {
                    const res = await fetch('/patients');
                    const json = await res.json();
                    const patients = json.data;
                    document.getElementById('patient-count').innerText = `${patients.length} Patient(s)`;
                    const tbody = document.getElementById('patient-table-body');
                    if (patients.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-8 text-center text-slate-400">No patients registered yet. Dial the phone number to register!</td></tr>';
                        return;
                    }
                    tbody.innerHTML = patients.map(p => `
                        <tr class="hover:bg-slate-50/80 transition">
                            <td class="px-6 py-4 font-semibold text-slate-900">${p.first_name} ${p.last_name} <span class="text-xs font-normal text-slate-400 block">${p.sex}</span></td>
                            <td class="px-6 py-4">${p.date_of_birth}</td>
                            <td class="px-6 py-4 font-mono text-xs">${p.phone_number}</td>
                            <td class="px-6 py-4">${p.city}, ${p.state} ${p.zip_code}</td>
                            <td class="px-6 py-4">${p.insurance_provider ? p.insurance_provider : '<span class="text-slate-400 italic">None</span>'}</td>
                            <td class="px-6 py-4 text-xs text-slate-500">${new Date(p.created_at).toLocaleString()}</td>
                        </tr>
                    `).join('');
                } catch (err) {
                    console.error(err);
                }
            }
            fetchPatients();
            setInterval(fetchPatients, 5000); // Auto-refresh every 5s
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)