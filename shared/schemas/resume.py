#Resume Document Schema for parsed resumes
from pydantic import BaseModel

class ResumeDocument(BaseModel):
    Resume_Id: str
    file_name: str
    file_type: str
    raw_text: str
    cleaned_text: str


