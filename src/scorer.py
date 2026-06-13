"""
Nexus v2
Deterministic Candidate Scoring Engine
"""

from config import (
    SCORING_WEIGHTS,
    FIT_CATEGORIES
)

from src.schemas import (
    CandidateProfile,
    ScoreBreakdown,
    JDRequirements
)


class CandidateScorer:

    def __init__(self):

        self.weights = SCORING_WEIGHTS

    # ==================================================
    # FIT CATEGORY
    # ==================================================

    def fit_category(
        self,
        final_score
    ):

        for category, (
            low,
            high
        ) in FIT_CATEGORIES.items():

            if low <= final_score <= high:

                return category

        return "Low Fit"

    # ==================================================
    # SKILLS SCORE
    # ==================================================

    def score_skills(

        self,

        profile,

        jd

    ):

        required = set(

            x.lower()

            for x in
            jd.must_have_skills
        )

        candidate = set(

            x.lower()

            for x in
            profile.technical_skills
        )

        if not required:

            return self.weights[
                "skills"
            ]

        matched = len(
            required.intersection(
                candidate
            )
        )

        return round(

            (
                matched
                /
                len(required)
            )

            *
            self.weights[
                "skills"
            ]
        )

    # ==================================================
    # EXPERIENCE SCORE
    # ==================================================

    def score_experience(

        self,

        profile,

        jd

    ):

        try:

            required_years = float(

                "".join(

                    c

                    for c in
                    jd.experience

                    if c.isdigit()
                    or c == "."
                )
            )

        except Exception:

            required_years = 0

        candidate_years = (
            profile.experience_years
        )

        if required_years == 0:

            return self.weights[
                "experience"
            ]

        ratio = min(

            candidate_years
            /
            required_years,

            1.0
        )

        return round(

            ratio

            *
            self.weights[
                "experience"
            ]
        )

    # ==================================================
    # EDUCATION SCORE
    # ==================================================

    def score_education(

        self,

        profile,

        jd

    ):

        required = (
            jd.education.lower()
        )

        candidate = (
            profile.education_summary
            .lower()
        )

        if not required:

            return self.weights[
                "education"
            ]

        if required in candidate:

            return self.weights[
                "education"
            ]

        return round(

            self.weights[
                "education"
            ] * 0.5
        )

    # ==================================================
    # PROJECT SCORE
    # ==================================================

    def score_projects(

        self,

        profile

    ):

        count = len(
            profile.projects
        )

        if count >= 5:

            return self.weights[
                "projects"
            ]

        return round(

            (
                count
                /
                5
            )

            *
            self.weights[
                "projects"
            ]
        )

    # ==================================================
    # DOMAIN SCORE
    # ==================================================

    def score_domain(

        self,

        profile,

        jd

    ):

        required = (
            jd.domain
            .lower()
        )

        if not required:

            return self.weights[
                "domain"
            ]

        for domain in (
            profile.domain_expertise
        ):

            if required in (
                domain.lower()
            ):

                return self.weights[
                    "domain"
                ]

        return 0

    # ==================================================
    # CERTIFICATION SCORE
    # ==================================================

    def score_certifications(

        self,

        profile,

        jd

    ):

        required = set(

            x.lower()

            for x in
            jd.certifications
        )

        candidate = set(

            x.lower()

            for x in
            profile.certifications
        )

        if not required:

            return self.weights[
                "certifications"
            ]

        matched = len(
            required.intersection(
                candidate
            )
        )

        return round(

            (
                matched
                /
                len(required)
            )

            *
            self.weights[
                "certifications"
            ]
        )

    # ==================================================
    # BUILD SCORE BREAKDOWN
    # ==================================================

    def build_breakdown(

        self,

        profile,

        jd

    ):

        breakdown = ScoreBreakdown()

        breakdown.skills_score = (
            self.score_skills(
                profile,
                jd
            )
        )

        breakdown.experience_score = (
            self.score_experience(
                profile,
                jd
            )
        )

        breakdown.education_score = (
            self.score_education(
                profile,
                jd
            )
        )

        breakdown.project_score = (
            self.score_projects(
                profile
            )
        )

        breakdown.domain_score = (
            self.score_domain(
                profile,
                jd
            )
        )

        breakdown.certification_score = (
            self.score_certifications(
                profile,
                jd
            )
        )

        breakdown.final_score = (

            breakdown.skills_score +

            breakdown.experience_score +

            breakdown.education_score +

            breakdown.project_score +

            breakdown.domain_score +

            breakdown.certification_score
        )

        return breakdown

    # ==================================================
    # EXPLANATION
    # ==================================================

    def explanation(
        self,
        breakdown
    ):

        return f"""
Skills Score:
{breakdown.skills_score}/{self.weights['skills']}

Experience Score:
{breakdown.experience_score}/{self.weights['experience']}

Education Score:
{breakdown.education_score}/{self.weights['education']}

Project Score:
{breakdown.project_score}/{self.weights['projects']}

Domain Score:
{breakdown.domain_score}/{self.weights['domain']}

Certification Score:
{breakdown.certification_score}/{self.weights['certifications']}

Final Score:
{breakdown.final_score}/100
"""

    # ==================================================
    # MAIN ENTRY
    # ==================================================

    def score_candidate(

        self,

        profile:
        CandidateProfile,

        jd:
        JDRequirements

    ):

        breakdown = (
            self.build_breakdown(
                profile,
                jd
            )
        )

        profile.score_breakdown = (
            breakdown
        )

        profile.fit_category = (
            self.fit_category(
                breakdown.final_score
            )
        )

        explanation = (
            self.explanation(
                breakdown
            )
        )

        return (
            profile,
            explanation
        )

    # ==================================================
    # RANKING
    # ==================================================

    def rank_profiles(
        self,
        profiles
    ):

        return sorted(

            profiles,

            key=lambda p:
            p.score_breakdown.final_score,

            reverse=True
        )