from pydantic import BaseModel
from typing import List

class Candidate_profile(BaseModel):
    candidate_id: str
    first_name: str
    last_name: str
    email: str
    phone_number: str
    address: str
    skills: List[str]
    experience: List[str]
    education: List[str]
    certifications: List[str]
    projects: List[str]

class Job_description(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    description: str
    required_skills: List[str]
    preferred_skills: List[str]
    required_qualifications: List[str]
    experience_required: List[str]
    responsibilities: List[str]

class Retreival_result(BaseModel):
    candidate_id: str
    job_id: str
    match_skills:list[str]
    missing_skills:list[str]
    relevant_experience:list[str]
    relevant_project:list[str]
    semantic_similarity: float
    retreived_context: str


class ScoringResult(BaseModel):
    score: float
    Explanation:dict[str, float]
    confidence: float