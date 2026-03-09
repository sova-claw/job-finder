import hashlib
import json

from app.schemas.profile import CandidateProfile, Certification

PROFILE = CandidateProfile(
    name="Nazar Khimin",
    title="Senior SDET transitioning to AI Engineer",
    summary=(
        "Senior automation and platform engineer moving into AI/Python roles with strong backend, "
        "cloud, data, and delivery experience."
    ),
    location="Kyiv, Ukraine",
    english_level="B2+",
    years_experience={
        "python": 7,
        "cloud": 5,
        "docker": 6,
        "sql": 6,
        "etl": 4,
        "fastapi": 2,
        "llm": 1,
    },
    strong_skills=[
        "Python",
        "Docker",
        "SQL",
        "Pandas",
        "NumPy",
        "Kafka",
        "GCP",
        "AWS",
        "ETL",
        "Testing",
        "FastAPI",
    ],
    working_skills=[
        "LangChain",
        "Agents",
        "RAG",
        "pgvector",
        "Anthropic API",
        "OpenAI API",
        "MLOps",
    ],
    certifications=[
        Certification(name="Professional Cloud Developer", provider="Google Cloud"),
        Certification(name="AWS Certified Cloud Practitioner", provider="AWS"),
    ],
    current_projects=[
        "Career Intelligence System",
        "AI-assisted automation tooling",
    ],
    target_roles=[
        "Python AI Engineer",
        "ML Engineer",
        "AI Platform Engineer",
    ],
    preferred_domains=["FinTech", "HealthTech", "Developer Tools", "EdTech"],
    achievements=[
        "Built and maintained automation platforms used in production environments.",
        "Delivered large-scale test and backend systems for product teams.",
        "Shipping CIS as a self-hosted AI job intelligence platform.",
    ],
    learning_plan={
        "LLM APIs": 1,
        "LangChain / agents": 2,
        "RAG + Vector DB": 2,
        "FastAPI production": 1,
        "Production ML (1y+)": 4,
    },
)


def get_candidate_profile() -> CandidateProfile:
    return PROFILE


def get_profile_hash() -> str:
    payload = PROFILE.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True)
    return hashlib.md5(serialized.encode("utf-8"), usedforsecurity=False).hexdigest()
