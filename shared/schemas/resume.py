# Resume Document Schema for parsed resumes

from pydantic import BaseModel


class ResumeDocument(BaseModel):
    resume_id: str
    filename: str
    file_type: str
    raw_text: str
    cleaned_text: str