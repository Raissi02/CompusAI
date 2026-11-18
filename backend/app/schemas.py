from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


Role = Literal["candidate", "academic_iit", "academic_isb", "interviewer", "director", "admin"]


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class GuestMessageInput(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class CreateUserRequest(RegisterRequest):
    role: Role
    institution: Literal["IIT", "ISB"] | None = None


class ProfileUpdate(BaseModel):
    preferred_language: str | None = Field(default=None, max_length=32)
    current_level: str | None = Field(default=None, max_length=120)
    grades: dict[str, Any] | None = None
    interests: list[str] | None = Field(default=None, max_length=20)
    goals: str | None = Field(default=None, max_length=2000)
    constraints: str | None = Field(default=None, max_length=1000)


class ProgramInput(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    institution: Literal["IIT", "ISB"]
    title: str = Field(min_length=2, max_length=180)
    level: str = Field(min_length=2, max_length=80)
    summary: str = Field(default="", max_length=8000)
    duration: str = Field(default="", max_length=100)
    prerequisites: str = Field(default="", max_length=4000)
    tuition: str = Field(default="", max_length=1000)
    subjects: list[str] = Field(default_factory=list, max_length=40)
    careers: list[str] = Field(default_factory=list, max_length=40)
    source_url: str | None = Field(default=None, max_length=1000)
    is_sample: bool = True
    is_active: bool = True


class MessageInput(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class RegistrationInput(BaseModel):
    program_id: int
    consent: bool
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def require_consent(self) -> "RegistrationInput":
        if not self.consent:
            raise ValueError("Consent is required before creating a pre-registration.")
        return self


class QuizSubmission(BaseModel):
    answers: dict[str, Any]


class ReviewInput(BaseModel):
    status: Literal["needs_information", "approved", "rejected"]
    notes: str = Field(default="", max_length=2000)


class AppointmentInput(BaseModel):
    candidate_id: int
    starts_at: datetime
    duration_minutes: int = Field(default=30, ge=15, le=120)
    mode: Literal["online", "on_campus"] = "online"
    location: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=2000)


class ProgramResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    institution: str
    title: str
    level: str
    summary: str
    duration: str
    prerequisites: str
    subjects: list[str]
    careers: list[str]
    source_url: str | None
    is_sample: bool
    is_active: bool


class DocumentInput(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    institution: Literal["IIT", "ISB"]
    content: str = Field(min_length=40, max_length=30000)
    source_url: str | None = Field(default=None, max_length=1000)
    is_sample: bool = False


class ConversationCreate(BaseModel):
    language: str = Field(default="fr", max_length=32)
