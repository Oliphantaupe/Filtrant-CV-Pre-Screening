from pydantic import BaseModel, Field
from typing import Optional


class PersonalInfo(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class Education(BaseModel):
    degree: Optional[str] = None
    field: Optional[str] = None
    institution: Optional[str] = None
    year: Optional[int] = None
    level_score: int = Field(default=1, ge=1, le=5)
    # 1=high school, 2=associate, 3=bachelor, 4=master, 5=phd


class Experience(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    start: Optional[str] = None   # "YYYY-MM"
    end: Optional[str] = None     # "YYYY-MM" or "present"
    duration_months: Optional[int] = None


class Skills(BaseModel):
    technical: list[str] = []
    methods: list[str] = []
    management: list[str] = []


class Language(BaseModel):
    language: str
    level: Optional[str] = None   # CEFR: A1..C2
    level_score: int = Field(default=1, ge=1, le=6)
    # 1=A1, 2=A2, 3=B1, 4=B2, 5=C1, 6=C2


class Certification(BaseModel):
    name: str
    year: Optional[int] = None


class CVSchema(BaseModel):
    personal: PersonalInfo = PersonalInfo()
    target_role: Optional[str] = None
    summary: Optional[str] = None
    education: list[Education] = []
    experience: list[Experience] = []
    skills: Skills = Skills()
    languages: list[Language] = []
    certifications: list[Certification] = []
    parse_quality: str = "partial"   # "complete" | "partial" | "poor"
    missing_fields: list[str] = []
