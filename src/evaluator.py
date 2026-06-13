"""
CVRadar
Candidate Evaluation Engine (LLM Tracks)
src/evaluator.py

v3 changes:
- Uses LLMProvider instead of direct Gemini SDK
- Works with Gemini / Claude / OpenAI transparently
- EvaluationResult schema includes primary_domain and filter flags
  (one call per CV, no separate filter call)
- On graceful failure (all retries exhausted): returns
  (None, None) so app.py can degrade to Track 1 local scoring
- Fixed import: from src.schemas
"""

from typing import Optional, Tuple
from pydantic import BaseModel, Field
from typing import List

from src.schemas import CandidateProfile, ScoreBreakdown
from src.filters import FilterFlags
from src.llm_provider import LLMProvider


# =====================================================
# RESPONSE SCHEMA
# One Gemini/Claude/OpenAI call extracts everything:
# candidate info + domain + filter flags
# =====================================================

class EvaluationResult(BaseModel):

    candidate_name: str = Field(
        description="The candidate's actual full name from the resume."
    )
    education_summary: str = Field(
        description="Highest degree earned, field of study, and institution."
    )
    experience_years: float = Field(
        description=(
            "Total professional workforce experience in years (not academic). "
            "Count only paid work history, not internships or projects."
        )
    )
    primary_domain: str = Field(
        description=(
            "The candidate's primary academic and professional stream. "
            "Examples: Remote Sensing, Civil Engineering, Data Science, "
            "Economics, Law, Agriculture, Computer Science. Be specific."
        )
    )
    domain_expertise: List[str] = Field(
        default_factory=list,
        description="List of domain/sector areas the candidate has worked in.",
    )
    technical_skills: List[str] = Field(
        default_factory=list,
        description="All technical tools, languages, frameworks, and methodologies found.",
    )
    certifications: List[str] = Field(
        default_factory=list,
        description="All certifications, licenses, and accreditations listed.",
    )
    projects: List[str] = Field(
        default_factory=list,
        description="Up to 5 key project titles or brief descriptions.",
    )
    matched_requirements: List[str] = Field(
        default_factory=list,
        description="JD must-have requirements clearly evidenced in the resume.",
    )
    missing_requirements: List[str] = Field(
        default_factory=list,
        description="JD must-have requirements not found in the resume.",
    )
    summary: str = Field(
        description=(
            "2-3 factual sentences summarising the candidate's profile "
            "relative to the JD. No opinion, only evidence from the CV."
        )
    )

    # --- Merged filter detection ---
    inclusion_matched: bool = Field(
        description=(
            "True ONLY if the candidate clearly exhibits at least one "
            "of the listed PRIORITY traits. False if no priority traits listed."
        )
    )
    exclusion_violated: bool = Field(
        description=(
            "True ONLY if the candidate clearly exhibits at least one "
            "of the listed NEGATIVE FILTER traits. False if none listed."
        )
    )
    filter_reason: str = Field(
        description=(
            "One sentence naming which trait triggered the flag, "
            "or 'No filter traits detected.'"
        )
    )


# =====================================================
# PROMPT BUILDER
# =====================================================

def build_prompt(
    resume_text: str,
    jd_text: str,
    jd_requirements,
    priority_traits: str,
    exclusion_traits: str,
) -> str:

    clean_inc = (
        priority_traits.strip()
        if priority_traits.strip()
        else "None — set inclusion_matched to false."
    )
    clean_exc = (
        exclusion_traits.strip()
        if exclusion_traits.strip()
        else "None — set exclusion_violated to false."
    )

    return f"""
You are an expert recruitment analyst. Your task is to extract
structured information from the candidate's resume and evaluate
it against the job description.

RULES:
- Do NOT generate scores. Scores are computed externally.
- Do NOT hallucinate. Only use evidence present in the resume.
- Be conservative with filter flags: clear evidence only.
- For experience_years: count ONLY professional paid work experience.
  Do not count academic years, internships, or project durations.

==========================================================
JOB DESCRIPTION
{jd_text}

==========================================================
STRUCTURED JD REQUIREMENTS
Must Have Skills: {jd_requirements.must_have_skills}
Nice To Have Skills: {jd_requirements.nice_to_have_skills}
Education: {jd_requirements.education}
Experience Required: {jd_requirements.experience}
Domain: {jd_requirements.domain}
Certifications: {jd_requirements.certifications}

==========================================================
PRIORITY TRAITS (set inclusion_matched=true if clearly present):
{clean_inc}

NEGATIVE FILTERS (set exclusion_violated=true if clearly present):
{clean_exc}

==========================================================
ANONYMIZED RESUME:
{resume_text}
"""


# =====================================================
# CANDIDATE EVALUATOR
# =====================================================

class CandidateEvaluator:

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def evaluate(
        self,
        resume_text: str,
        jd_text: str,
        jd_requirements,
        file_name: str,
        file_hash: str,
        priority_traits: str = "",
        exclusion_traits: str = "",
    ) -> Tuple[Optional[CandidateProfile], Optional[FilterFlags]]:
        """
        Returns (profile, filter_flags) on success.
        Returns (None, None) on graceful failure — caller degrades to Track 1.
        """
        prompt = build_prompt(
            resume_text=resume_text,
            jd_text=jd_text,
            jd_requirements=jd_requirements,
            priority_traits=priority_traits,
            exclusion_traits=exclusion_traits,
        )

        result_dict = self.provider.call(
            prompt=prompt,
            response_schema=EvaluationResult,
            graceful=True,
        )

        if result_dict is None:
            # Graceful degradation — caller handles Track 1 fallback
            return None, None

        try:
            result = EvaluationResult(**result_dict)
        except Exception:
            return None, None

        profile = CandidateProfile(
            candidate_name=result.candidate_name or "Unknown",
            education_summary=result.education_summary or "",
            experience_years=float(result.experience_years or 0),
            primary_domain=result.primary_domain or "",
            domain_expertise=result.domain_expertise or [],
            technical_skills=result.technical_skills or [],
            certifications=result.certifications or [],
            projects=result.projects or [],
            matched_requirements=result.matched_requirements or [],
            missing_requirements=result.missing_requirements or [],
            summary=result.summary or "",
            score_breakdown=ScoreBreakdown(),
            fit_category="",
            status="Success",
            processing_track=f"Track 2 ({self.provider.provider})",
            file_name=file_name,
            file_hash=file_hash,
            processing_notes="",
        )

        filters_active = bool(
            priority_traits.strip() or exclusion_traits.strip()
        )

        flags = None
        if filters_active:
            flags = FilterFlags(
                inclusion_matched=result.inclusion_matched,
                exclusion_violated=result.exclusion_violated,
                reason=result.filter_reason or "No filter traits detected.",
            )

        return profile, flags
