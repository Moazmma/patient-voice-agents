import re
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator

class SexEnum(str, Enum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"
    DECLINE = "Decline to Answer"

# Valid 2-letter US State Codes
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", 
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", 
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", 
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"
}

class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: str  # MM/DD/YYYY
    sex: SexEnum
    phone_number: str
    email: Optional[EmailStr] = None
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    state: str
    zip_code: str
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = "English"
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    # Name validation (1-50 chars, letters, hyphens, apostrophes)
    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not (1 <= len(v) <= 50):
            raise ValueError("Name must be between 1 and 50 characters")
        if not re.match(r"^[a-zA-Z\s\-']+$", v):
            raise ValueError("Name can only contain alphabetic characters, hyphens, and apostrophes")
        return v.title()

    # Date of Birth validation (MM/DD/YYYY, not in future)
    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: str) -> str:
        v = v.strip()
        try:
            dob = datetime.strptime(v, "%m/%d/%Y")
        except ValueError:
            raise ValueError("Date of birth must be in valid MM/DD/YYYY format")
        if dob > datetime.now():
            raise ValueError("Date of birth cannot be in the future")
        return v

    # Phone number validation (10 digits)
    @field_validator("phone_number", "emergency_contact_phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        # Sirf digits extract karein
        digits = re.sub(r"\D", "", v)
        # Agar aagay 1 laga ho (US country code), remove karein
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) != 10:
            raise ValueError("Phone number must be a valid 10-digit U.S. number")
        return digits

    # State validation (2 letters US abbreviation)
    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in US_STATES:
            raise ValueError(f"State must be a valid 2-letter U.S. state abbreviation (e.g. NY, CA, TX)")
        return v

    # Zip code validation (5 digits or ZIP+4)
    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^\d{5}(-\d{4})?$", v):
            raise ValueError("ZIP code must be 5 digits (e.g. 90210) or ZIP+4 (e.g. 90210-1234)")
        return v

class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    sex: Optional[SexEnum] = None
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None