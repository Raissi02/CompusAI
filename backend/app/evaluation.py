from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session

from app.main import detect_language, extract_profile_hints
from app.rag import answer_with_sources, search_documents


CASES = [
    {
        "id": "french-iit",
        "language": "fr",
        "institution": "IIT",
        "expected_source": "Project brief: SmartCampus AI",
        "question": "Je veux comparer les parcours de Licence et d'ingénierie à l'IIT.",
    },
    {
        "id": "tunisian-arabic-script-isb",
        "language": "Tunisian Arabic / Arabic script",
        "institution": "ISB",
        "expected_source": "Project brief: ISB programme coverage",
        "question": "شنية المعلومات الرسمية على برامج ISB؟",
    },
    {
        "id": "arabizi-isb",
        "language": "Arabizi",
        "institution": "ISB",
        "expected_source": "Project brief: ISB programme coverage",
        "question": "nheb naaref les programmes ISB w chnowa les infos officielles",
    },
    {
        "id": "arabizi-iit",
        "language": "Arabizi",
        "institution": "IIT",
        "expected_source": "Project brief: SmartCampus AI",
        "question": "n7eb naaref parcours Licence w engineering mta3 IIT",
    },
    {
        "id": "tunisian-arabic-script-iit",
        "language": "Tunisian Arabic / Arabic script",
        "institution": "IIT",
        "expected_source": "Project brief: SmartCampus AI",
        "question": "شنية مسارات Licence والهندسة في IIT؟",
    },
    {
        "id": "french-human-review",
        "language": "fr",
        "institution": "IIT",
        "expected_source": "Project brief: human review requirements",
        "question": (
            "Un academic adviser vérifie la recommandation d’orientation IIT avant "
            "une décision officielle d’admission."
        ),
    },
]


async def evaluate_language_and_retrieval(db: Session) -> dict[str, Any]:
    results = []
    for case in CASES:
        started = time.perf_counter()
        detected = detect_language(case["question"], "fr")
        sources = await search_documents(db, case["question"])
        relevant = any(source.institution == case["institution"] for source in sources)
        expected_source_retrieved = any(
            source.title == case["expected_source"] for source in sources
        )
        profile = SimpleNamespace(interests=[], current_level="", goals="", updated_at=None)
        extract_profile_hints(profile, case["question"])
        results.append(
            {
                "id": case["id"],
                "expected_language": case["language"],
                "detected_language": detected,
                "language_match": detected == case["language"],
                "expected_institution": case["institution"],
                "retrieved_institution": relevant,
                "expected_source": case["expected_source"],
                "expected_source_retrieved": expected_source_retrieved,
                "source_titles": [source.title for source in sources],
                "profile_interests_extracted": profile.interests,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        )
    checks = [
        {
            "metric": "language_detection",
            "passed": all(result["language_match"] for result in results),
            "score": sum(result["language_match"] for result in results) / len(results),
        },
        {
            "metric": "institution_retrieval_recall",
            "passed": all(result["retrieved_institution"] for result in results),
            "score": sum(result["retrieved_institution"] for result in results) / len(results),
        },
        {
            "metric": "expected_source_recall",
            "passed": all(result["expected_source_retrieved"] for result in results),
            "score": sum(result["expected_source_retrieved"] for result in results)
            / len(results),
        },
    ]
    return {
        "suite": "smoke-tests, not an academic or model-quality benchmark",
        "cases": results,
        "checks": checks,
        "limitations": (
            "Six hand-written routing and retrieval cases do not establish answer quality, "
            "dialect coverage, admissions accuracy, or fairness. Load official source material "
            "and an academically reviewed evaluation set before using this for model selection."
        ),
    }


async def compare_configured_models(db: Session, models: list[str]) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for model in models[:3]:
        responses = []
        for case in CASES:
            sources = await search_documents(db, case["question"])
            start = time.perf_counter()
            answer = await answer_with_sources(
                case["question"],
                sources,
                case["language"],
                model_override=model,
            )
            responses.append(
                {
                    "case": case["id"],
                    "latency_ms": round((time.perf_counter() - start) * 1000, 1),
                    "cited_sources": "[1]" in answer or "[2]" in answer,
                    "answer_available": bool(answer.strip()),
                    "answer": answer,
                }
            )
        comparisons.append(
            {
                "model": model,
                "responses": responses,
                "summary": {
                    "average_latency_ms": round(
                        sum(response["latency_ms"] for response in responses)
                        / len(responses),
                        1,
                    ),
                    "citation_rate": sum(
                        response["cited_sources"] for response in responses
                    )
                    / len(responses),
                    "answer_availability": sum(
                        response["answer_available"] for response in responses
                    )
                    / len(responses),
                },
            }
        )
    return comparisons
