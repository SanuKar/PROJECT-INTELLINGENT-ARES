from pydantic import BaseModel
from typing import List


class CandidateProfile(BaseModel):
    candidate_id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    address: str
    skills: List[str]
    experience: List[str]
    education: List[str]
    certifications: List[str]
    projects: List[str]


class JobDescription(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    description: str
    required_skills: List[str]
    preferred_skills: List[str]
    required_qualifications: List[str]
    experience_required: str
    responsibilities: List[str]


class RetrievalResult(BaseModel):
    candidate_id: str
    job_id: str
    matched_skills: List[str]
    missing_skills: List[str]
    relevant_experience: List[str]
    relevant_projects: List[str]
    semantic_similarity: float
    retrieved_context: List[str]


class ScoringResult(BaseModel):
    user_score: float
    explanation: dict[str, float]
    confidence: float