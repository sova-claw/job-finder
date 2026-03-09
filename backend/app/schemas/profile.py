from pydantic import BaseModel, Field


class Certification(BaseModel):
    name: str
    provider: str


class CandidateProfile(BaseModel):
    name: str
    title: str
    summary: str
    location: str
    english_level: str
    years_experience: dict[str, int]
    strong_skills: list[str]
    working_skills: list[str]
    certifications: list[Certification]
    current_projects: list[str]
    target_roles: list[str]
    preferred_domains: list[str]
    achievements: list[str]
    learning_plan: dict[str, int] = Field(
        description="Estimated weeks to become credible for a given skill.",
    )
