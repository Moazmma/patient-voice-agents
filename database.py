import sqlite3
from datetime import datetime, timezone

DB_NAME = "patients.db"

def get_connection():
    """SQLite database connection banata hai."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Dict ki tarah access karne ke liye
    return conn

def init_db():
    """Table banata hai agar pehle se nahi bana hua."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        patient_id TEXT PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        date_of_birth TEXT NOT NULL,
        sex TEXT NOT NULL,
        phone_number TEXT NOT NULL,
        email TEXT,
        address_line_1 TEXT NOT NULL,
        address_line_2 TEXT,
        city TEXT NOT NULL,
        state TEXT NOT NULL,
        zip_code TEXT NOT NULL,
        insurance_provider TEXT,
        insurance_member_id TEXT,
        preferred_language TEXT DEFAULT 'English',
        emergency_contact_name TEXT,
        emergency_contact_phone TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT
    )
    """)
    
    # Check karein agar table khali hai to 1 sample patient (Seed Data) add karein
    cursor.execute("SELECT COUNT(*) FROM patients")
    count = cursor.fetchone()[0]
    
    if count == 0:
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
        INSERT INTO patients (
            patient_id, first_name, last_name, date_of_birth, sex,
            phone_number, email, address_line_1, address_line_2,
            city, state, zip_code, insurance_provider, insurance_member_id,
            preferred_language, emergency_contact_name, emergency_contact_phone,
            created_at, updated_at
        ) VALUES (
            'seed-001-uuid-example', 'John', 'Smith', '01/15/1985', 'Male',
            '2025550143', 'john.smith@example.com', '123 Main St', 'Apt 4B',
            'New York', 'NY', '10001', 'Blue Cross', 'BC123456789',
            'English', 'Mary Smith', '2025550199',
            ?, ?
        )
        """, (now, now))
        conn.commit()
        print("Sample seed patient added successfully!")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")