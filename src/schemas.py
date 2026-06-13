"""
CVRadar
Data Schemas
src/schemas.py

Changes vs v2:
- CandidateProfile: added primary_domain (stream detection)
- CandidateProfile: added processing_track ("Track 1 Local" /
  "Track 2 LLM" / "Hybrid-Culled" / "Degraded to Local")
- processing_notes kept for internal audit but not in Excel output
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class ScoreBreakdown(BaseModel):
    skills_score: int = 0
    experience_score: int = 0
    education_score: int = 0
    project_score: int = 0
    domain_score: int = 0
    certification_score: int = 0
    final_score: int = 0


class JDRequirements(BaseModel):
    must_have_skills: List[str] = Field(default_factory=list)
    nice_to_have_skills: List[str] = Field(default_factory=list)
    education: str = ""
    experience: str = ""
    domain: str = ""
    certifications: List[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    candidate_name: str
    education_summary: str
    experience_years: float
    primary_domain: str = ""            # stream from taxonomy / LLM
    domain_expertise: List[str] = Field(default_factory=list)
    technical_skills: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)
    matched_requirements: List[str] = Field(default_factory=list)
    missing_requirements: List[str] = Field(default_factory=list)
    summary: str
    score_breakdown: ScoreBreakdown
    fit_category: str
    status: str
    processing_track: str = "Track 1 Local"
    file_name: str
    file_hash: str
    processing_notes: str = ""
