import hashlib
import json

from app.schemas.profile import CandidateProfile, Certification

ROLE_FOCUS_KEYWORDS = (
    "qa automation",
    "automation qa",
    "test automation",
    "sdet",
    "software engineer in test",
    "qa engineer",
    "quality engineer",
    "automation engineer",
    "aqa",
)

PYTHON_QA_STACK_KEYWORDS = (
    "python",
    "pytest",
    "playwright",
    "selenium",
    "webdriver",
    "api testing",
    "postman",
    "requests",
    "rest api",
)

FOREIGN_LOCATION_KEYWORDS = (
    "europe",
    "poland",
    "usa",
    "germany",
    "netherlands",
    "cyprus",
    "moldova",
    "slovakia",
    "slovenia",
    "united kingdom",
    "romania",
    "czech",
)

LOCAL_LOCATION_KEYWORDS = (
    "ukraine",
    "kyiv",
    "kyiv region",
    "київ",
    "львів",
    "lviv",
    "kharkiv",
    "харків",
    "odesa",
    "одеса",
    "dnipro",
    "дніпро",
    "poltava",
    "рівне",
    "rivne",
)

PROFILE = CandidateProfile(
    name="Nazar Khimin",
    title="Senior QA Automation Engineer (Python)",
    summary=(
        "Senior QA automation engineer focused on Python-based test platforms, API quality, "
        "CI/CD quality gates, scalable automation for product teams, and remote or abroad "
        "opportunities."
    ),
    location="Kyiv, Ukraine",
    english_level="B2+",
    years_experience={
        "python": 7,
        "cloud": 5,
        "docker": 6,
        "sql": 6,
        "api_testing": 6,
        "ui_automation": 5,
        "ci_cd": 6,
        "playwright": 2,
    },
    strong_skills=[
        "Python",
        "Pytest",
        "API Testing",
        "Test Automation",
        "Selenium",
        "Playwright",
        "CI/CD",
        "Docker",
        "SQL",
        "GCP",
        "AWS",
    ],
    working_skills=[
        "Performance Testing",
        "k6",
        "Contract Testing",
        "GitHub Actions",
        "Allure",
    ],
    certifications=[
        Certification(name="Professional Cloud Developer", provider="Google Cloud"),
        Certification(name="AWS Certified Cloud Practitioner", provider="AWS"),
    ],
    current_projects=[
        "Career Intelligence System",
        "Python QA automation accelerators",
    ],
    target_roles=[
        "Senior QA Automation Engineer",
        "Python QA Engineer",
        "SDET",
        "Test Automation Engineer",
    ],
    preferred_domains=["FinTech", "HealthTech", "Developer Tools", "EdTech"],
    achievements=[
        "Built and maintained Python automation platforms used in production delivery pipelines.",
        "Delivered API, UI, and integration test systems for product engineering teams.",
        "Shipping CIS as a self-hosted QA-focused job intelligence platform.",
    ],
    learning_plan={
        "Playwright at scale": 1,
        "Performance testing (k6)": 2,
        "Contract testing": 2,
        "Advanced CI quality gates": 1,
        "Security testing depth": 3,
    },
)


def get_candidate_profile() -> CandidateProfile:
    return PROFILE


def get_profile_hash() -> str:
    payload = PROFILE.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True)
    return hashlib.md5(serialized.encode("utf-8"), usedforsecurity=False).hexdigest()


def has_role_focus_signal(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in ROLE_FOCUS_KEYWORDS)


def has_python_qa_stack_signal(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in PYTHON_QA_STACK_KEYWORDS)


def matches_focus_role(title: str, raw_text: str = "") -> bool:
    title_text = title.lower()
    body_text = raw_text.lower()
    return has_role_focus_signal(title_text) and (
        has_python_qa_stack_signal(title_text) or has_python_qa_stack_signal(body_text)
    )


def matches_abroad_remote_preference(
    *,
    title: str,
    location: str | None = None,
    raw_text: str = "",
    remote: bool | None = None,
) -> bool:
    header_excerpt = "\n".join(raw_text.splitlines()[:24])
    searchable = "\n".join(filter(None, (title, location or "", header_excerpt))).lower()

    has_foreign_location = any(keyword in searchable for keyword in FOREIGN_LOCATION_KEYWORDS)
    has_local_location = any(keyword in searchable for keyword in LOCAL_LOCATION_KEYWORDS)

    if has_foreign_location:
        return True
    if remote and not has_local_location:
        return True
    return False
