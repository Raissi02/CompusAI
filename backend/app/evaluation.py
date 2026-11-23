from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session

from app.main import detect_language, extract_profile_hints
from app.rag import answer_with_hits, search_chunk_hits


CASES = [
    {
        "id": "french-iit-prepa",
        "language": "fr",
        "fallback": "fr",
        "institution": "IIT",
        "expected_source": "IIT — Cycle préparatoire",
        "question": "Quels sont les prérequis et les frais du cycle préparatoire à l'IIT ?",
    },
    {
        "id": "french-iit-admission",
        "language": "fr",
        "fallback": "fr",
        "institution": "IIT",
        "expected_source": "IIT — Procédure d'admission et entretien",
        "question": "Comment se déroule l'admission à l'IIT et quels documents faut-il ?",
    },
    {
        "id": "french-iit-fees",
        "language": "fr",
        "fallback": "fr",
        "institution": "IIT",
        "expected_source": "IIT — Frais de scolarité, paiement et remboursement",
        "question": "Combien coûte une année en génie informatique pour un étudiant tunisien ?",
    },
    {
        "id": "french-iit-scholarships",
        "language": "fr",
        "fallback": "fr",
        "institution": "IIT",
        "expected_source": "IIT — Bourses et aides financières",
        "question": "Existe-t-il des bourses à l'IIT et comment les demander ?",
    },
    {
        "id": "english-isb-licences",
        "language": "en",
        "fallback": "en",
        "institution": "ISB",
        "expected_source": "ISB — Licences et conditions d'admission",
        "question": "What are the admission requirements and duration of the Business Administration licence?",
    },
    {
        "id": "english-isb-masters",
        "language": "en",
        "fallback": "en",
        "institution": "ISB",
        "expected_source": "ISB — Masters, MBA et admission",
        "question": "Which master programmes does ISB offer?",
    },
]


async def evaluate_language_and_retrieval(db: Session) -> dict[str, Any]:
    results = []
    for case in CASES:
        started = time.perf_counter()
        detected = detect_language(case["question"], case.get("fallback", "fr"))
        hits = await search_chunk_hits(db, case["question"])
        relevant = any(hit.document.institution == case["institution"] for hit in hits)
        expected_source_retrieved = any(
            hit.document.title == case["expected_source"] for hit in hits
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
                "retrieved_chunks": [
                    {
                        "document": hit.document.title,
                        "institution": hit.document.institution,
                        "chunk_id": hit.chunk.id,
                        "score": hit.score,
                        "lexical_score": hit.lexical_score,
                        "vector_score": hit.vector_score,
                        "snippet": hit.chunk.content[:160],
                    }
                    for hit in hits
                ],
                "source_titles": [hit.document.title for hit in hits],
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
            hits = await search_chunk_hits(db, case["question"])
            start = time.perf_counter()
            answer = await answer_with_hits(
                case["question"],
                hits,
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
