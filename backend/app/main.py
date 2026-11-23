from __future__ import annotations

import logging
import hashlib
import os
import re
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from types import SimpleNamespace
from typing import Any
from typing_extensions import Annotated

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal, get_db, initialize_database
from app.models import (
    Appointment,
    CandidateProfile,
    Conversation,
    GuestSession,
    KnowledgeDocument,
    Message,
    Notification,
    PreRegistration,
    Program,
    Quiz,
    User,
    utc_now,
)
from app.rag import (
    ChunkHit,
    answer_with_hits,
    embed,
    ensure_document_chunks,
    reindex_documents,
    search_chunk_hits,
)
from app.schemas import (
    AppointmentInput,
    ConversationCreate,
    CreateUserRequest,
    DocumentInput,
    GuestMessageInput,
    LoginRequest,
    MessageInput,
    ProfileUpdate,
    ProgramInput,
    QuizSubmission,
    RegisterRequest,
    RegistrationInput,
    ReviewInput,
)
from app.security import hash_password, issue_token, read_token, verify_password
from app.seed import seed_demo_data


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)
app = FastAPI(
    title="SmartCampus AI API",
    description=(
        "Admissions-orientation demo API. Demo catalogue records are not official. "
        "An authorized human remains responsible for academic and admission decisions."
    ),
    version="0.1.0",
)
origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Guest-Token"],
)

bearer = HTTPBearer(auto_error=False)
Db = Annotated[Session, Depends(get_db)]
STAFF_ROLES = {"academic_iit", "academic_isb", "interviewer", "director", "admin"}
REVIEW_ROLES = {"academic_iit", "academic_isb", "admin"}


@app.on_event("startup")
async def startup() -> None:
    if os.getenv("APP_ENV", "development") == "production" and len(
        os.getenv("JWT_SECRET", "")
    ) < 32:
        raise RuntimeError("JWT_SECRET must be set to at least 32 characters in production.")
    initialize_database()
    with SessionLocal() as db:
        await seed_demo_data(db)


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Db,
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    try:
        payload = read_token(credentials.credentials)
        user = db.get(User, int(payload["sub"]))
    except (ValueError, KeyError, TypeError) as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="This account is unavailable.")
    return user


def require_roles(*roles: str):
    def dependency(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="You do not have permission for this action.")
        return user

    return dependency


def public_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "institution": user.institution,
        "created_at": user.created_at,
    }


def get_or_create_profile(db: Session, user_id: int) -> CandidateProfile:
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
    if profile is None:
        profile = CandidateProfile(user_id=user_id)
        db.add(profile)
        db.flush()
    return profile


def visible_preregistrations(db: Session, user: User) -> list[PreRegistration]:
    statement = select(PreRegistration).options(
        joinedload(PreRegistration.program),
    )
    if user.role == "candidate":
        statement = statement.where(PreRegistration.user_id == user.id)
    elif user.role == "academic_iit":
        statement = statement.join(Program).where(Program.institution == "IIT")
    elif user.role == "academic_isb":
        statement = statement.join(Program).where(Program.institution == "ISB")
    return list(db.scalars(statement.order_by(PreRegistration.created_at.desc())).unique())


def can_review_program(user: User, program: Program) -> bool:
    if user.role == "admin":
        return True
    return (user.role == "academic_iit" and program.institution == "IIT") or (
        user.role == "academic_isb" and program.institution == "ISB"
    )


def detect_language(content: str, fallback: str) -> str:
    if re.search(r"[\u0600-\u06FF]", content):
        return "Tunisian Arabic / Arabic script"
    folded = content.casefold()
    arabizi_markers = ("chnowa", "chneya", "nheb", "n7eb", "kifech", "ena", "famma")
    if any(marker in folded for marker in arabizi_markers):
        return "Arabizi"
    return fallback or "fr"


def extract_profile_hints(profile: CandidateProfile, content: str) -> None:
    folded = content.casefold()
    interest_words = {
        "informatique": ("informatique", "programming", "coding", "ordinateur", "computer"),
        "mathématiques": ("math", "mathématique", "رياضيات"),
        "sciences": ("science", "physique", "chimie"),
        "gestion": ("gestion", "management", "business"),
        "économie": ("économie", "economics", "finance"),
        "ingénierie": ("ingénierie", "engineering", "engineer"),
    }
    interests = list(profile.interests or [])
    for label, terms in interest_words.items():
        if label not in interests and any(term in folded for term in terms):
            interests.append(label)
    profile.interests = interests

    level_terms = {
        "Baccalauréat": ("bac", "baccalauréat", "lycée", "lycee", "terminale"),
        "Licence": ("licence",),
        "Préparatoire": ("prépa", "prepa", "preparatoire", "préparatoire"),
    }
    for level, terms in level_terms.items():
        if any(term in folded for term in terms):
            profile.current_level = level
            break
    if not profile.goals:
        goal_markers = ("devenir", "objectif", "career", "future", "nheb nkoun", "n7eb nkoun")
        if any(marker in folded for marker in goal_markers):
            profile.goals = content[:1000]
    profile.updated_at = utc_now()


def recommendation_rows(profile: CandidateProfile, programs: list[Program]) -> list[dict[str, Any]]:
    candidate_terms = {
        term.casefold()
        for term in [
            *(profile.interests or []),
            profile.current_level,
            profile.goals,
        ]
        if term
    }
    rows = []
    for program in programs:
        program_terms = {
            term.casefold()
            for term in [program.level, *(program.subjects or []), *(program.careers or [])]
            if term
        }
        matches = sorted(candidate_terms & program_terms)
        score = round(100 * len(matches) / max(1, len(candidate_terms | program_terms)))
        reason = (
            f"Interest overlap: {', '.join(matches)}."
            if matches
            else "Add interests and goals to see which listed topics may fit."
        )
        rows.append(
            {
                "program": program,
                "interest_overlap": score,
                "matched_interests": matches,
                "explanation": reason,
                "score_note": "Keyword overlap only. This is not an eligibility or admission score.",
                "requires_human_review": True,
            }
        )
    return sorted(rows, key=lambda row: row["interest_overlap"], reverse=True)


def notification_for(
    db: Session, user: User, subject: str, body: str
) -> Notification:
    notification = Notification(user_id=user.id, subject=subject, body=body)
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    if not host or not sender:
        notification.delivery_status = "not_configured"
        notification.error = "SMTP_HOST and SMTP_FROM are required to send email."
        db.add(notification)
        logger.info("Email notification queued but SMTP is not configured for user %s.", user.id)
        return notification

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = user.email
    message.set_content(body)
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as smtp:
            if os.getenv("SMTP_USE_TLS", "true").casefold() == "true":
                smtp.starttls()
            username = os.getenv("SMTP_USERNAME")
            password = os.getenv("SMTP_PASSWORD")
            if username:
                smtp.login(username, password or "")
            smtp.send_message(message)
        notification.delivery_status = "sent"
    except (OSError, smtplib.SMTPException, ValueError) as error:
        logger.exception("Could not send email notification to user %s.", user.id)
        notification.delivery_status = "failed"
        notification.error = str(error)[:1000]
    db.add(notification)
    return notification


def serialize_preregistration(item: PreRegistration) -> dict[str, Any]:
    return {
        "id": item.id,
        "candidate_id": item.user_id,
        "program": serialize_program(item.program),
        "status": item.status,
        "notes": item.notes,
        "created_at": item.created_at,
        "reviewed_at": item.reviewed_at,
    }


def serialize_program(program: Program) -> dict[str, Any]:
    return {
        "id": program.id,
        "code": program.code,
        "institution": program.institution,
        "title": program.title,
        "level": program.level,
        "summary": program.summary,
        "duration": program.duration,
        "prerequisites": program.prerequisites,
        "tuition": program.tuition,
        "subjects": program.subjects or [],
        "careers": program.careers or [],
        "source_url": program.source_url,
        "is_sample": program.is_sample,
        "is_active": program.is_active,
        "updated_at": program.updated_at,
    }


def serialize_profile(profile: CandidateProfile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "user_id": profile.user_id,
        "preferred_language": profile.preferred_language,
        "current_level": profile.current_level,
        "grades": profile.grades or {},
        "interests": profile.interests or [],
        "goals": profile.goals,
        "constraints": profile.constraints,
        "consent_at": profile.consent_at,
        "updated_at": profile.updated_at,
    }


def serialize_message(message: Message) -> dict[str, Any]:
    return {
        "id": message.id,
        "sender": message.sender,
        "content": message.content,
        "citations": message.citations or [],
        "created_at": message.created_at,
    }


def serialize_citations(hits: list[ChunkHit]) -> list[dict[str, Any]]:
    return [
        {
            "title": hit.document.title,
            "institution": hit.document.institution,
            "is_sample": hit.document.is_sample,
            "source_url": hit.document.source_url or "",
            "snippet": hit.chunk.content[:280].strip(),
            "chunk_id": hit.chunk.id,
        }
        for hit in hits
    ]


def serialize_appointment(appointment: Appointment) -> dict[str, Any]:
    return {
        "id": appointment.id,
        "user_id": appointment.user_id,
        "starts_at": appointment.starts_at,
        "duration_minutes": appointment.duration_minutes,
        "mode": appointment.mode,
        "location": appointment.location,
        "status": appointment.status,
        "notes": appointment.notes,
        "created_at": appointment.created_at,
    }


def serialize_notification(notification: Notification) -> dict[str, Any]:
    return {
        "id": notification.id,
        "subject": notification.subject,
        "body": notification.body,
        "channel": notification.channel,
        "delivery_status": notification.delivery_status,
        "error": notification.error,
        "created_at": notification.created_at,
    }


def _guest_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _active_guest_session(session_id: str, token: str | None, db: Session) -> GuestSession:
    if not token or len(token) > 200:
        raise HTTPException(status_code=401, detail="A valid guest-session token is required.")
    guest = db.scalar(
        select(GuestSession).where(
            GuestSession.id == session_id,
            GuestSession.token_hash == _guest_token_hash(token),
        )
    )
    if guest is None:
        raise HTTPException(status_code=401, detail="Guest session not found.")
    if guest.user_id is not None:
        raise HTTPException(status_code=409, detail="This guest session is linked to an account. Sign in to continue.")
    expiry = guest.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= utc_now():
        raise HTTPException(status_code=410, detail="This guest session expired. Start a new conversation.")
    return guest


def _link_guest_session(db: Session, token: str | None, user: User) -> bool:
    if not token:
        return False
    guest = db.scalar(
        select(GuestSession).where(
            GuestSession.token_hash == _guest_token_hash(token),
        )
    )
    if guest is None:
        raise HTTPException(status_code=401, detail="Guest session could not be linked. Sign in again.")
    if guest.user_id is not None:
        if guest.user_id == user.id:
            return False
        raise HTTPException(status_code=409, detail="This guest session is already linked to another account.")
    expiry = guest.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= utc_now():
        raise HTTPException(status_code=410, detail="This guest session expired and cannot be linked.")

    profile = get_or_create_profile(db, user.id)
    memory = guest.memory or {}
    profile.interests = list(dict.fromkeys([*(profile.interests or []), *memory.get("interests", [])]))
    profile.current_level = profile.current_level or memory.get("current_level", "")
    profile.goals = profile.goals or memory.get("goals", "")
    for conversation in guest.conversations:
        conversation.user_id = user.id
        conversation.guest_session_id = None
    guest.user_id = user.id
    return True


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    db: Db,
    guest_token: Annotated[str | None, Header(alias="X-Guest-Token")] = None,
) -> dict[str, Any]:
    email = str(payload.email).casefold()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role="candidate",
    )
    db.add(user)
    db.flush()
    get_or_create_profile(db, user.id)
    guest_linked = _link_guest_session(db, guest_token, user)
    db.commit()
    db.refresh(user)
    return {
        "access_token": issue_token(user.id),
        "token_type": "bearer",
        "user": public_user(user),
        "guest_session_linked": guest_linked,
    }


@app.post("/api/auth/login")
def login(
    payload: LoginRequest,
    db: Db,
    guest_token: Annotated[str | None, Header(alias="X-Guest-Token")] = None,
) -> dict[str, Any]:
    user = db.scalar(select(User).where(User.email == str(payload.email).casefold()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been disabled.")
    guest_linked = _link_guest_session(db, guest_token, user)
    db.commit()
    return {
        "access_token": issue_token(user.id),
        "token_type": "bearer",
        "user": public_user(user),
        "guest_session_linked": guest_linked,
    }


@app.get("/api/auth/me")
def me(user: Annotated[User, Depends(current_user)]) -> dict[str, Any]:
    return public_user(user)


@app.get("/api/programs")
def list_programs(
    db: Db, user: Annotated[User, Depends(current_user)]
) -> list[dict[str, Any]]:
    statement = select(Program)
    if user.role == "candidate":
        statement = statement.where(Program.is_active.is_(True))
    if user.role == "academic_iit":
        statement = statement.where(Program.institution == "IIT")
    if user.role == "academic_isb":
        statement = statement.where(Program.institution == "ISB")
    return [
        serialize_program(program)
        for program in db.scalars(statement.order_by(Program.institution, Program.title))
    ]


@app.post("/api/programs", status_code=status.HTTP_201_CREATED)
def create_program(
    payload: ProgramInput,
    db: Db,
    admin: Annotated[User, Depends(require_roles("admin"))],
) -> dict[str, Any]:
    del admin
    if db.scalar(select(Program).where(Program.code == payload.code)):
        raise HTTPException(status_code=409, detail="A programme with this code already exists.")
    program = Program(**payload.model_dump(), updated_at=utc_now())
    db.add(program)
    db.commit()
    db.refresh(program)
    return serialize_program(program)


@app.put("/api/programs/{program_id}")
def update_program(
    program_id: int,
    payload: ProgramInput,
    db: Db,
    admin: Annotated[User, Depends(require_roles("admin"))],
) -> dict[str, Any]:
    del admin
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(status_code=404, detail="Programme not found.")
    code_owner = db.scalar(
        select(Program).where(Program.code == payload.code, Program.id != program.id)
    )
    if code_owner:
        raise HTTPException(status_code=409, detail="A programme with this code already exists.")
    for key, value in payload.model_dump().items():
        setattr(program, key, value)
    program.updated_at = utc_now()
    db.commit()
    db.refresh(program)
    return serialize_program(program)


@app.get("/api/profile")
def get_profile(db: Db, user: Annotated[User, Depends(current_user)]) -> dict[str, Any]:
    profile = get_or_create_profile(db, user.id)
    db.commit()
    return {"user": public_user(user), "profile": serialize_profile(profile)}


@app.put("/api/profile")
def update_profile(
    payload: ProfileUpdate, db: Db, user: Annotated[User, Depends(current_user)]
) -> dict[str, Any]:
    if user.role != "candidate":
        raise HTTPException(status_code=403, detail="Only candidates can edit their own profile.")
    profile = get_or_create_profile(db, user.id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(profile, key, value)
    profile.updated_at = utc_now()
    db.commit()
    db.refresh(profile)
    return serialize_profile(profile)


@app.post("/api/recommendations")
def get_recommendations(
    db: Db, user: Annotated[User, Depends(current_user)]
) -> dict[str, Any]:
    if user.role != "candidate":
        raise HTTPException(status_code=403, detail="Recommendations are available in candidate accounts.")
    profile = get_or_create_profile(db, user.id)
    programs = list(
        db.scalars(select(Program).where(Program.is_active.is_(True)).order_by(Program.title))
    )
    rows = recommendation_rows(profile, programs)
    db.commit()
    return {
        "recommendations": [
            {**row, "program": serialize_program(row["program"])} for row in rows
        ],
        "method": "transparent keyword overlap over the profile and listed programme topics",
        "disclaimer": (
            "Suggestions are exploratory, not eligibility checks or official academic advice. "
            "Sample records are not official programme information. An academic adviser must "
            "verify an orientation recommendation."
        ),
    }


@app.post("/api/conversations", status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate, db: Db, user: Annotated[User, Depends(current_user)]
) -> dict[str, Any]:
    if user.role != "candidate":
        raise HTTPException(status_code=403, detail="Only candidates can start a conversation.")
    conversation = Conversation(user_id=user.id, language=payload.language)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return {"id": conversation.id, "language": conversation.language, "messages": []}


@app.post("/api/guest/sessions", status_code=status.HTTP_201_CREATED)
def create_guest_session(db: Db) -> dict[str, Any]:
    now = utc_now()
    expired = db.scalars(
        select(GuestSession).where(
            GuestSession.user_id.is_(None),
            GuestSession.expires_at <= now,
        )
    )
    for session in expired:
        db.delete(session)

    session_id = secrets.token_urlsafe(18)
    token = secrets.token_urlsafe(32)
    guest = GuestSession(
        id=session_id,
        token_hash=_guest_token_hash(token),
        memory={},
        created_at=now,
        last_active_at=now,
        expires_at=now + timedelta(days=30),
    )
    db.add(guest)
    db.flush()
    conversation = Conversation(
        guest_session_id=guest.id,
        language="fr",
        status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return {
        "id": guest.id,
        "token": token,
        "conversation_id": conversation.id,
        "expires_at": guest.expires_at,
        "retention_days": 30,
    }


@app.get("/api/guest/sessions/{session_id}")
def get_guest_session(
    session_id: str,
    db: Db,
    guest_token: Annotated[str | None, Header(alias="X-Guest-Token")] = None,
) -> dict[str, Any]:
    guest = _active_guest_session(session_id, guest_token, db)
    conversation = db.scalar(
        select(Conversation)
        .options(joinedload(Conversation.messages))
        .where(Conversation.guest_session_id == guest.id)
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Guest conversation not found.")
    return {
        "id": guest.id,
        "conversation_id": conversation.id,
        "language": conversation.language,
        "memory": guest.memory or {},
        "messages": [serialize_message(message) for message in conversation.messages],
        "expires_at": guest.expires_at,
    }


@app.post("/api/guest/sessions/{session_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_guest_message(
    session_id: str,
    payload: GuestMessageInput,
    db: Db,
    guest_token: Annotated[str | None, Header(alias="X-Guest-Token")] = None,
) -> dict[str, Any]:
    guest = _active_guest_session(session_id, guest_token, db)
    now = utc_now()
    window_start = guest.window_started_at
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=timezone.utc)
    if (now - window_start).total_seconds() >= 60:
        guest.window_started_at = now
        guest.window_count = 0
    if guest.window_count >= 20:
        raise HTTPException(
            status_code=429,
            detail="This guest session has reached its message limit. Please wait a minute or sign in.",
        )
    guest.window_count += 1
    guest.last_active_at = now

    conversation = db.scalar(
        select(Conversation)
        .options(joinedload(Conversation.messages))
        .where(Conversation.guest_session_id == guest.id)
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Guest conversation not found.")
    conversation.language = detect_language(payload.content, conversation.language)
    memory = guest.memory or {}
    guest_profile = SimpleNamespace(
        interests=list(memory.get("interests", [])),
        current_level=memory.get("current_level", ""),
        goals=memory.get("goals", ""),
        updated_at=now,
    )
    extract_profile_hints(guest_profile, payload.content)
    guest.memory = {
        "interests": guest_profile.interests,
        "current_level": guest_profile.current_level,
        "goals": guest_profile.goals,
    }
    candidate_message = Message(
        conversation_id=conversation.id,
        sender="candidate",
        content=payload.content,
    )
    db.add(candidate_message)
    conversation.updated_at = now
    db.flush()
    history = [
        {
            "role": "assistant" if message.sender == "assistant" else "user",
            "content": message.content,
        }
        for message in conversation.messages[-8:]
    ]
    memory_text = " ".join(
        [*guest.memory.get("interests", []), guest.memory.get("current_level", ""), guest.memory.get("goals", "")]
    )
    try:
        hits = await search_chunk_hits(db, f"{payload.content}\n{memory_text}")
        reply = await answer_with_hits(
            payload.content,
            hits,
            conversation.language,
            memory=guest.memory,
            history=history,
        )
        citations = serialize_citations(hits)
    except (httpx.HTTPError, RuntimeError, ValueError) as error:
        logger.exception("Could not produce a grounded guest reply.")
        db.commit()
        raise HTTPException(
            status_code=502,
            detail=f"The assistant could not complete this reply: {error}",
        ) from error
    assistant_message = Message(
        conversation_id=conversation.id,
        sender="assistant",
        content=reply,
        citations=citations,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(candidate_message)
    db.refresh(assistant_message)
    return {
        "candidate_message": serialize_message(candidate_message),
        "assistant_message": serialize_message(assistant_message),
        "detected_language": conversation.language,
        "memory": guest.memory,
    }


@app.get("/api/conversations")
def list_conversations(db: Db, user: Annotated[User, Depends(current_user)]) -> list[dict[str, Any]]:
    if user.role != "candidate":
        raise HTTPException(status_code=403, detail="Only candidates can view these conversations.")
    conversations = db.scalars(
        select(Conversation)
        .options(joinedload(Conversation.messages))
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    ).unique()
    return [
        {
            "id": conversation.id,
            "language": conversation.language,
            "created_at": conversation.created_at,
            "messages": [serialize_message(message) for message in conversation.messages],
        }
        for conversation in conversations
    ]


@app.post("/api/conversations/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: int,
    payload: MessageInput,
    db: Db,
    user: Annotated[User, Depends(current_user)],
) -> dict[str, Any]:
    conversation = db.scalar(
        select(Conversation)
        .options(joinedload(Conversation.messages))
        .where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    profile = get_or_create_profile(db, user.id)
    conversation.language = detect_language(payload.content, conversation.language)
    extract_profile_hints(profile, payload.content)
    candidate_message = Message(
        conversation_id=conversation.id, sender="candidate", content=payload.content
    )
    db.add(candidate_message)
    conversation.updated_at = utc_now()
    db.flush()

    try:
        memory = {
            "interests": profile.interests or [],
            "current_level": profile.current_level,
            "goals": profile.goals,
            "constraints": profile.constraints,
        }
        memory_text = " ".join(
            [
                *memory["interests"],
                memory["current_level"],
                memory["goals"],
                memory["constraints"],
            ]
        )
        history = [
            {
                "role": "assistant" if message.sender == "assistant" else "user",
                "content": message.content,
            }
            for message in conversation.messages[-8:]
        ]
        sources = await search_chunk_hits(db, f"{payload.content}\n{memory_text}")
        reply = await answer_with_hits(
            payload.content, sources, conversation.language, memory=memory, history=history
        )
        citations = serialize_citations(sources)
    except (httpx.HTTPError, RuntimeError, ValueError) as error:
        logger.exception("Could not produce a grounded assistant reply.")
        db.commit()
        raise HTTPException(
            status_code=502,
            detail=f"The assistant could not complete this reply: {error}",
        ) from error

    assistant_message = Message(
        conversation_id=conversation.id,
        sender="assistant",
        content=reply,
        citations=citations,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(candidate_message)
    db.refresh(assistant_message)
    return {
        "candidate_message": serialize_message(candidate_message),
        "assistant_message": serialize_message(assistant_message),
        "detected_language": conversation.language,
    }


@app.post("/api/preregistrations", status_code=status.HTTP_201_CREATED)
def create_preregistration(
    payload: RegistrationInput,
    db: Db,
    user: Annotated[User, Depends(current_user)],
) -> dict[str, Any]:
    if user.role != "candidate":
        raise HTTPException(status_code=403, detail="Only candidates can pre-register.")
    program = db.get(Program, payload.program_id)
    if program is None or not program.is_active:
        raise HTTPException(status_code=404, detail="This programme is unavailable.")
    existing = db.scalar(
        select(PreRegistration).where(
            PreRegistration.user_id == user.id,
            PreRegistration.program_id == program.id,
            PreRegistration.status.not_in(["withdrawn", "rejected"]),
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="You already have an active application for this programme.")

    consent_at = utc_now()
    profile = get_or_create_profile(db, user.id)
    profile.consent_at = consent_at
    registration = PreRegistration(
        user_id=user.id,
        program_id=program.id,
        status="pending_review",
        consent_at=consent_at,
        notes=payload.notes,
    )
    db.add(registration)
    db.flush()
    notification = notification_for(
        db,
        user,
        "Pre-registration received",
        f"We recorded your pre-registration request for {program.title}. "
        "An admissions adviser will review it. This message is not an admission decision.",
    )
    db.commit()
    db.refresh(registration)
    db.refresh(notification)
    return {
        "registration": serialize_preregistration(registration),
        "notification": {
            "delivery_status": notification.delivery_status,
            "message": notification.error,
        },
    }


@app.get("/api/preregistrations")
def list_preregistrations(
    db: Db, user: Annotated[User, Depends(current_user)]
) -> list[dict[str, Any]]:
    return [serialize_preregistration(item) for item in visible_preregistrations(db, user)]


@app.patch("/api/preregistrations/{registration_id}")
def review_preregistration(
    registration_id: int,
    payload: ReviewInput,
    db: Db,
    reviewer: Annotated[User, Depends(require_roles(*REVIEW_ROLES))],
) -> dict[str, Any]:
    registration = db.scalar(
        select(PreRegistration)
        .options(joinedload(PreRegistration.program))
        .where(PreRegistration.id == registration_id)
    )
    if registration is None:
        raise HTTPException(status_code=404, detail="Pre-registration not found.")
    if not can_review_program(reviewer, registration.program):
        raise HTTPException(status_code=403, detail="This programme belongs to another academic team.")
    registration.status = payload.status
    registration.notes = payload.notes
    registration.reviewer_id = reviewer.id
    registration.reviewed_at = utc_now()
    notification = notification_for(
        db,
        db.get(User, registration.user_id),
        "An update to your pre-registration",
        f"Your pre-registration for {registration.program.title} has an update: "
        f"{payload.status.replace('_', ' ')}. "
        "Please contact the admissions team for the official next steps.",
    )
    db.commit()
    db.refresh(registration)
    db.refresh(notification)
    return {
        "registration": serialize_preregistration(registration),
        "notification": {"delivery_status": notification.delivery_status, "message": notification.error},
    }


def make_quiz_questions(program: Program, profile: CandidateProfile) -> list[dict[str, Any]]:
    subjects = (program.subjects or [])[:5] or [
        "the subjects you enjoy",
        "a topic you want to explore",
    ]
    questions: list[dict[str, Any]] = [
        {
            "id": "interests",
            "category": "interests",
            "type": "multi",
            "question": "Which areas would you like to explore in this programme?",
            "options": subjects,
        },
        {
            "id": "experience",
            "category": "self_assessment",
            "type": "single",
            "question": "How would you describe your previous experience with these topics?",
            "options": ["New to them", "A little experience", "Some experience", "I would like to discuss this"],
        },
        {
            "id": "motivation",
            "category": "motivation",
            "type": "text",
            "question": "What interests you about this programme or its subject areas?",
        },
        {
            "id": "support",
            "category": "support_needs",
            "type": "text",
            "question": "What would you like an adviser to explain during your interview?",
        },
    ]
    if profile.current_level or profile.goals:
        questions.append(
            {
                "id": "next_step",
                "category": "goals",
                "type": "text",
                "question": (
                    f"How does this programme relate to your current level "
                    f"({profile.current_level or 'not yet shared'}) and your next goal?"
                ),
            }
        )
    return questions


@app.post("/api/quizzes", status_code=status.HTTP_201_CREATED)
def create_quiz(
    program_id: int, db: Db, user: Annotated[User, Depends(current_user)]
) -> dict[str, Any]:
    if user.role != "candidate":
        raise HTTPException(status_code=403, detail="Only candidates can take a questionnaire.")
    program = db.get(Program, program_id)
    if program is None or not program.is_active:
        raise HTTPException(status_code=404, detail="This programme is unavailable.")
    profile = get_or_create_profile(db, user.id)
    quiz = Quiz(
        user_id=user.id,
        program_id=program.id,
        questions=make_quiz_questions(program, profile),
        answers={},
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return {
        "id": quiz.id,
        "program": serialize_program(program),
        "questions": quiz.questions,
        "interpretation": "Exploratory questionnaire for an adviser. It is not an admission test or decision.",
    }


@app.post("/api/quizzes/{quiz_id}/submit")
def submit_quiz(
    quiz_id: int,
    payload: QuizSubmission,
    db: Db,
    user: Annotated[User, Depends(current_user)],
) -> dict[str, Any]:
    quiz = db.get(Quiz, quiz_id)
    if quiz is None or quiz.user_id != user.id:
        raise HTTPException(status_code=404, detail="Questionnaire not found.")
    if quiz.submitted_at is not None:
        raise HTTPException(status_code=409, detail="This questionnaire has already been submitted.")
    valid_ids = {question["id"] for question in quiz.questions}
    if set(payload.answers) - valid_ids:
        raise HTTPException(status_code=422, detail="Answers contain an unknown question.")
    quiz.answers = payload.answers
    answered = sum(
        1 for value in payload.answers.values() if value is not None and str(value).strip()
    )
    quiz.completion_score = round(100 * answered / len(valid_ids)) if valid_ids else 0
    quiz.submitted_at = utc_now()
    profile = get_or_create_profile(db, user.id)
    profile.updated_at = utc_now()
    response_summary = ", ".join(
        question["category"].replace("_", " ")
        for question in quiz.questions
        if question["id"] in payload.answers and str(payload.answers[question["id"]]).strip()
    )
    quiz.summary = (
        f"Responses shared in: {response_summary or 'no categories yet'}. "
        "Completion reflects answered questions only; it is not a knowledge or admission score. "
        "An interviewer should discuss the candidate's responses and record their own assessment."
    )
    db.commit()
    db.refresh(quiz)
    return {
        "id": quiz.id,
        "completion_score": quiz.completion_score,
        "summary": quiz.summary,
        "answers": quiz.answers,
        "submitted_at": quiz.submitted_at,
    }


@app.get("/api/quizzes")
def list_quizzes(db: Db, user: Annotated[User, Depends(current_user)]) -> list[dict[str, Any]]:
    statement = select(Quiz).options(joinedload(Quiz.program))
    if user.role == "candidate":
        statement = statement.where(Quiz.user_id == user.id)
    elif user.role == "academic_iit":
        statement = statement.join(Program).where(Program.institution == "IIT")
    elif user.role == "academic_isb":
        statement = statement.join(Program).where(Program.institution == "ISB")
    elif user.role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="You do not have permission to view questionnaires.")
    return [
        {
            "id": quiz.id,
            "candidate_id": quiz.user_id,
            "program": serialize_program(quiz.program),
            "questions": quiz.questions,
            "answers": quiz.answers,
            "completion_score": quiz.completion_score,
            "summary": quiz.summary,
            "submitted_at": quiz.submitted_at,
        }
        for quiz in db.scalars(statement.order_by(Quiz.created_at.desc())).unique()
    ]


@app.post("/api/appointments", status_code=status.HTTP_201_CREATED)
def propose_appointment(
    payload: AppointmentInput,
    db: Db,
    coordinator: Annotated[User, Depends(require_roles("interviewer", "admin"))],
) -> dict[str, Any]:
    candidate = db.get(User, payload.candidate_id)
    if candidate is None or candidate.role != "candidate":
        raise HTTPException(status_code=404, detail="Candidate not found.")
    starts_at = payload.starts_at
    if starts_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="Appointment time must include a timezone.")
    starts_at = starts_at.astimezone(timezone.utc)
    if starts_at <= utc_now():
        raise HTTPException(status_code=422, detail="Choose a future appointment time.")
    overlap = db.scalar(
        select(Appointment).where(
            Appointment.starts_at == starts_at,
            Appointment.status.in_(["proposed", "confirmed"]),
        )
    )
    if overlap:
        raise HTTPException(status_code=409, detail="This time is already reserved.")
    appointment = Appointment(
        user_id=candidate.id,
        starts_at=starts_at,
        duration_minutes=payload.duration_minutes,
        mode=payload.mode,
        location=payload.location,
        notes=payload.notes,
        created_by=coordinator.id,
        status="proposed",
    )
    db.add(appointment)
    notification = notification_for(
        db,
        candidate,
        "Interview time proposed",
        f"An interview has been proposed for {starts_at.isoformat()}. "
        "Please sign in to confirm or decline this proposed time.",
    )
    db.commit()
    db.refresh(appointment)
    db.refresh(notification)
    return {
        "appointment": serialize_appointment(appointment),
        "notification": {"delivery_status": notification.delivery_status, "message": notification.error},
    }


@app.get("/api/appointments")
def list_appointments(
    db: Db, user: Annotated[User, Depends(current_user)]
) -> list[dict[str, Any]]:
    statement = select(Appointment)
    if user.role == "candidate":
        statement = statement.where(Appointment.user_id == user.id)
    elif user.role in {"academic_iit", "academic_isb"}:
        institution = "IIT" if user.role == "academic_iit" else "ISB"
        scoped_candidates = (
            select(PreRegistration.user_id)
            .join(Program, Program.id == PreRegistration.program_id)
            .where(Program.institution == institution)
        )
        statement = statement.where(Appointment.user_id.in_(scoped_candidates))
    elif user.role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="You do not have permission to view appointments.")
    return [
        serialize_appointment(appointment)
        for appointment in db.scalars(statement.order_by(Appointment.starts_at))
    ]


@app.patch("/api/appointments/{appointment_id}")
def respond_to_appointment(
    appointment_id: int,
    action: str,
    db: Db,
    user: Annotated[User, Depends(current_user)],
) -> dict[str, Any]:
    if action not in {"confirm", "decline"}:
        raise HTTPException(status_code=422, detail="Action must be confirm or decline.")
    appointment = db.get(Appointment, appointment_id)
    if appointment is None or appointment.user_id != user.id or user.role != "candidate":
        raise HTTPException(status_code=404, detail="Appointment not found.")
    if appointment.status != "proposed":
        raise HTTPException(status_code=409, detail="This appointment is no longer awaiting a response.")
    appointment.status = "confirmed" if action == "confirm" else "declined"
    db.commit()
    db.refresh(appointment)
    return serialize_appointment(appointment)


@app.get("/api/staff/candidates")
def staff_candidates(
    db: Db, staff: Annotated[User, Depends(require_roles(*STAFF_ROLES))]
) -> list[dict[str, Any]]:
    statement = select(User).options(joinedload(User.profile)).where(User.role == "candidate")
    if staff.role == "academic_iit":
        statement = statement.join(PreRegistration, PreRegistration.user_id == User.id).join(
            Program, Program.id == PreRegistration.program_id
        ).where(Program.institution == "IIT")
    elif staff.role == "academic_isb":
        statement = statement.join(PreRegistration, PreRegistration.user_id == User.id).join(
            Program, Program.id == PreRegistration.program_id
        ).where(Program.institution == "ISB")
    users = db.scalars(statement.order_by(User.created_at.desc())).unique()
    return [
        {
            "user": public_user(candidate),
            "profile": serialize_profile(candidate.profile),
            "preregistrations": [
                serialize_preregistration(item)
                for item in visible_preregistrations(db, staff)
                if item.user_id == candidate.id
            ],
        }
        for candidate in users
    ]


@app.get("/api/staff/conversations/{candidate_id}")
def candidate_conversations(
    candidate_id: int,
    db: Db,
    staff: Annotated[User, Depends(require_roles(*STAFF_ROLES))],
) -> list[dict[str, Any]]:
    candidate = db.get(User, candidate_id)
    if candidate is None or candidate.role != "candidate":
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if staff.role in {"academic_iit", "academic_isb"}:
        allowed = {item.user_id for item in visible_preregistrations(db, staff)}
        if candidate_id not in allowed:
            raise HTTPException(status_code=403, detail="This candidate is outside your academic team.")
    conversations = db.scalars(
        select(Conversation)
        .options(joinedload(Conversation.messages))
        .where(Conversation.user_id == candidate_id)
        .order_by(Conversation.created_at)
    ).unique()
    return [
        {
            "id": conversation.id,
            "language": conversation.language,
            "messages": [serialize_message(message) for message in conversation.messages],
        }
        for conversation in conversations
    ]


@app.get("/api/stats")
def get_stats(
    db: Db, user: Annotated[User, Depends(require_roles(*STAFF_ROLES))]
) -> dict[str, Any]:
    registration_query = select(PreRegistration)
    if user.role == "academic_iit":
        registration_query = registration_query.join(Program).where(Program.institution == "IIT")
    elif user.role == "academic_isb":
        registration_query = registration_query.join(Program).where(Program.institution == "ISB")

    registrations = list(db.scalars(registration_query))
    scoped_candidates = select(PreRegistration.user_id)
    if user.role in {"academic_iit", "academic_isb"}:
        institution = "IIT" if user.role == "academic_iit" else "ISB"
        scoped_candidates = scoped_candidates.join(
            Program, Program.id == PreRegistration.program_id
        ).where(Program.institution == institution)
    candidate_filter = (
        User.id.in_(scoped_candidates)
        if user.role in {"academic_iit", "academic_isb"}
        else User.role == "candidate"
    )
    candidate_count = db.scalar(select(func.count(User.id)).where(candidate_filter)) or 0
    conversation_filter = (
        Conversation.user_id.in_(scoped_candidates)
        if user.role in {"academic_iit", "academic_isb"}
        else True
    )
    appointment_filter = (
        Appointment.user_id.in_(scoped_candidates)
        if user.role in {"academic_iit", "academic_isb"}
        else True
    )
    conversation_count = db.scalar(
        select(func.count(Conversation.id)).where(conversation_filter)
    ) or 0
    appointment_count = db.scalar(
        select(func.count(Appointment.id)).where(appointment_filter)
    ) or 0
    counts_by_status: dict[str, int] = {}
    for registration in registrations:
        counts_by_status[registration.status] = counts_by_status.get(registration.status, 0) + 1
    program_counts_query = (
        select(Program.institution, func.count(PreRegistration.id))
        .outerjoin(PreRegistration, PreRegistration.program_id == Program.id)
    )
    if user.role in {"academic_iit", "academic_isb"}:
        institution = "IIT" if user.role == "academic_iit" else "ISB"
        program_counts_query = program_counts_query.where(Program.institution == institution)
    program_counts = db.execute(program_counts_query.group_by(Program.institution)).all()
    return {
        "candidates": candidate_count,
        "conversations": conversation_count,
        "preregistrations": len(registrations),
        "appointments": appointment_count,
        "registrations_by_status": counts_by_status,
        "preregistrations_by_institution": {institution: count for institution, count in program_counts},
        "data_note": "Counts reflect records currently stored in this database; no projections are used.",
    }


@app.get("/api/notifications")
def list_notifications(
    db: Db, user: Annotated[User, Depends(current_user)]
) -> list[dict[str, Any]]:
    if user.role != "candidate":
        raise HTTPException(status_code=403, detail="Candidate notifications are private.")
    notifications = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
    )
    return [serialize_notification(notification) for notification in notifications]


@app.get("/api/admin/users")
def admin_users(
    db: Db, admin: Annotated[User, Depends(require_roles("admin"))]
) -> list[dict[str, Any]]:
    del admin
    return [public_user(user) for user in db.scalars(select(User).order_by(User.created_at.desc()))]


@app.post("/api/admin/users", status_code=status.HTTP_201_CREATED)
def create_staff_user(
    payload: CreateUserRequest,
    db: Db,
    admin: Annotated[User, Depends(require_roles("admin"))],
) -> dict[str, Any]:
    email = str(payload.email).casefold()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    if payload.role == "academic_iit" and payload.institution != "IIT":
        raise HTTPException(status_code=422, detail="IIT academic accounts must be assigned to IIT.")
    if payload.role == "academic_isb" and payload.institution != "ISB":
        raise HTTPException(status_code=422, detail="ISB academic accounts must be assigned to ISB.")
    user = User(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        institution=payload.institution,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Administrator %s created account %s with role %s.", admin.id, user.id, user.role)
    return public_user(user)


@app.get("/api/admin/documents")
def admin_documents(
    db: Db, admin: Annotated[User, Depends(require_roles("admin"))]
) -> list[dict[str, Any]]:
    del admin
    documents = db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.updated_at.desc()))
    return [
        {
            "id": document.id,
            "title": document.title,
            "institution": document.institution,
            "content": document.content,
            "source_url": document.source_url,
            "is_sample": document.is_sample,
            "chunks": len(document.chunks),
            "updated_at": document.updated_at,
        }
        for document in documents
    ]


@app.post("/api/admin/documents/reindex")
async def reindex_knowledge_documents(
    db: Db, admin: Annotated[User, Depends(require_roles("admin"))]
) -> dict[str, Any]:
    try:
        result = await reindex_documents(db)
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        logger.exception("Could not reindex knowledge documents.")
        raise HTTPException(status_code=502, detail=f"Could not reindex documents: {error}") from error
    logger.info(
        "Administrator %s reindexed %s documents into %s chunks.",
        admin.id,
        result["documents"],
        result["chunks"],
    )
    return {
        **result,
        "note": (
            "Chunks were rebuilt with the currently configured embedding model. "
            "Re-index after changing EMBEDDING_MODEL or EMBEDDING_DIMENSIONS."
        ),
    }


@app.delete("/api/admin/documents/{document_id}")
def delete_knowledge_document(
    document_id: int,
    db: Db,
    admin: Annotated[User, Depends(require_roles("admin"))],
) -> dict[str, Any]:
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    db.delete(document)
    db.commit()
    logger.info("Administrator %s deleted knowledge document %s.", admin.id, document_id)
    return {"deleted": document_id}


@app.post("/api/admin/documents", status_code=status.HTTP_201_CREATED)
async def add_knowledge_document(
    payload: DocumentInput,
    db: Db,
    admin: Annotated[User, Depends(require_roles("admin"))],
) -> dict[str, Any]:
    try:
        vector = await embed(f"{payload.title}\n{payload.content}")
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        logger.exception("Could not embed knowledge document.")
        raise HTTPException(status_code=502, detail=f"Could not index document: {error}") from error
    document = KnowledgeDocument(
        **payload.model_dump(),
        embedding=vector,
        updated_at=utc_now(),
    )
    db.add(document)
    db.flush()
    try:
        await ensure_document_chunks(db, document)
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        logger.exception("Could not chunk knowledge document.")
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Could not index document: {error}") from error
    db.commit()
    db.refresh(document)
    logger.info("Administrator %s indexed knowledge document %s.", admin.id, document.id)
    return {
        "id": document.id,
        "title": document.title,
        "institution": document.institution,
        "is_sample": document.is_sample,
        "chunks": len(document.chunks),
    }


@app.post("/api/admin/evaluations")
async def run_model_evaluation(
    db: Db,
    admin: Annotated[User, Depends(require_roles("admin"))],
) -> dict[str, Any]:
    from app.evaluation import compare_configured_models, evaluate_language_and_retrieval

    try:
        smoke_test = await evaluate_language_and_retrieval(db)
        configured_models = list(
            dict.fromkeys(
                item.strip()
                for item in os.getenv("EVALUATION_MODELS", "").split(",")
                if item.strip()
            )
        )
        comparisons = (
            await compare_configured_models(db, configured_models)
            if configured_models and os.getenv("OPENAI_API_KEY")
            else []
        )
    except (httpx.HTTPError, RuntimeError, ValueError, KeyError) as error:
        logger.exception("Model evaluation failed for administrator %s.", admin.id)
        raise HTTPException(status_code=502, detail=f"Model evaluation failed: {error}") from error
    return {
        **smoke_test,
        "provider_comparison": comparisons,
        "provider_note": (
            "Provider calls run three fixed test prompts per model and may incur API charges."
            if comparisons
            else "No provider comparison ran. Configure OPENAI_API_KEY and EVALUATION_MODELS."
        ),
    }


@app.post("/api/audio/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    user: User = Depends(current_user),
) -> dict[str, str]:
    del user
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="Speech transcription is not configured. Set an OpenAI-compatible API key and endpoint.",
        )
    filename = audio.filename or "audio.webm"
    allowed_extensions = {".webm", ".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".mpeg"}
    extension = os.path.splitext(filename)[1].casefold()
    if extension not in allowed_extensions:
        raise HTTPException(status_code=415, detail="Use a supported audio file: webm, wav, mp3, m4a, mp4, ogg.")
    content = await audio.read(12 * 1024 * 1024 + 1)
    if len(content) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio files must be no larger than 12 MB.")
    if not content:
        raise HTTPException(status_code=422, detail="The uploaded audio file is empty.")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                data={"model": os.getenv("TRANSCRIPTION_MODEL", "whisper-1")},
                files={"file": (filename, content, audio.content_type or "application/octet-stream")},
            )
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, KeyError) as error:
        logger.exception("Audio transcription provider failed.")
        raise HTTPException(status_code=502, detail=f"Transcription failed: {error}") from error
    text = result.get("text")
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(status_code=502, detail="The transcription provider returned no text.")
    return {"text": text.strip()}


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "SmartCampus AI API", "docs": "/docs", "health": "/api/health"}
