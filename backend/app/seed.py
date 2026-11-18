import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KnowledgeDocument, Program, User
from app.rag import embed
from app.security import hash_password


DEMO_PROGRAMS = [
    {
        "code": "DEMO-IIT-LICENCE",
        "institution": "IIT",
        "title": "Licence programme (sample)",
        "level": "Licence",
        "summary": (
            "Sample record to demonstrate the orientation workflow. This is not an official "
            "programme description. Replace it with verified IIT information before use."
        ),
        "duration": "Not provided in the project brief",
        "prerequisites": "Not provided in the project brief",
        "subjects": ["informatique", "mathématiques"],
        "careers": ["Not specified in the project brief"],
    },
    {
        "code": "DEMO-IIT-PREPA",
        "institution": "IIT",
        "title": "Preparatory programme (sample)",
        "level": "Préparatoire",
        "summary": (
            "Sample record to demonstrate the orientation workflow. This is not an official "
            "programme description. Replace it with verified IIT information before use."
        ),
        "duration": "Not provided in the project brief",
        "prerequisites": "Not provided in the project brief",
        "subjects": ["mathématiques", "sciences"],
        "careers": ["Not specified in the project brief"],
    },
    {
        "code": "DEMO-IIT-INGENIERIE",
        "institution": "IIT",
        "title": "Engineering programme (sample)",
        "level": "Ingénierie",
        "summary": (
            "Sample record to demonstrate the orientation workflow. This is not an official "
            "programme description. Replace it with verified IIT information before use."
        ),
        "duration": "Not provided in the project brief",
        "prerequisites": "Not provided in the project brief",
        "subjects": ["informatique", "mathématiques", "ingénierie"],
        "careers": ["Not specified in the project brief"],
    },
    {
        "code": "DEMO-ISB-FORMATION",
        "institution": "ISB",
        "title": "ISB programme (sample)",
        "level": "Not specified",
        "summary": (
            "Sample record to demonstrate the orientation workflow. The project brief names ISB "
            "but provides no programme details. Replace it with verified ISB information."
        ),
        "duration": "Not provided in the project brief",
        "prerequisites": "Not provided in the project brief",
        "subjects": [],
        "careers": ["Not specified in the project brief"],
    },
]

DEMO_DOCUMENTS = [
    {
        "title": "Project brief: SmartCampus AI",
        "institution": "IIT",
        "content": (
            "The supplied 2026-2027 project brief describes IIT Licence, Preparatory, and "
            "Engineering pathways. It gives no official curriculum, admission criteria, tuition, "
            "duration, or career outcomes. Those must be checked with an academic adviser. "
            "This record is a project-brief excerpt, not a complete official catalogue."
        ),
    },
    {
        "title": "Project brief: ISB programme coverage",
        "institution": "ISB",
        "content": (
            "The supplied 2026-2027 project brief says that the platform should explain ISB "
            "programmes. It does not name any programme or provide curricula, admission criteria, "
            "tuition, duration, or career outcomes. Ask an ISB academic adviser for verified "
            "information. This is a sample reference, not an official catalogue."
        ),
    },
    {
        "title": "Project brief: human review requirements",
        "institution": "IIT",
        "content": (
            "The project brief requires a human academic decision for official recommendations. "
            "The assistant can present candidate interests and compare available source material, "
            "but must not make an official admission decision. An academic adviser verifies or "
            "adjusts an orientation recommendation; an interview coordinator handles interview "
            "scheduling and records interview observations."
        ),
    },
]

DEMO_ACCOUNTS = [
    ("demo.admin@smartcampus.example.com", "Platform administrator", "admin", None),
    ("demo.iit@smartcampus.example.com", "IIT academic adviser", "academic_iit", "IIT"),
    ("demo.isb@smartcampus.example.com", "ISB academic adviser", "academic_isb", "ISB"),
    ("demo.interviewer@smartcampus.example.com", "Interview coordinator", "interviewer", None),
    ("demo.director@smartcampus.example.com", "Admissions director", "director", None),
]


async def seed_demo_data(db: Session) -> None:
    if os.getenv("APP_ENV", "development") == "production":
        return
    if os.getenv("SEED_DEMO_DATA", "true").casefold() != "true":
        return

    for item in DEMO_PROGRAMS:
        if db.scalar(select(Program).where(Program.code == item["code"])) is None:
            db.add(Program(**item, is_sample=True, is_active=True))

    for item in DEMO_DOCUMENTS:
        if db.scalar(
            select(KnowledgeDocument).where(KnowledgeDocument.title == item["title"])
        ) is None:
            db.add(
                KnowledgeDocument(
                    **item,
                    is_sample=True,
                    embedding=await embed(f'{item["title"]} {item["content"]}'),
                )
            )

    demo_password = os.getenv("DEMO_PASSWORD", "CampusDemo2026!")
    for email, name, role, institution in DEMO_ACCOUNTS:
        if db.scalar(select(User).where(User.email == email)) is None:
            db.add(
                User(
                    name=name,
                    email=email,
                    role=role,
                    institution=institution,
                    password_hash=hash_password(demo_password),
                )
            )
    db.commit()
