"""GPA extraction agent: reads transcript text and returns structured GPA info."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, Field, model_validator

from agentic_admission.agents.llm_client import ChatMessage, complete

if TYPE_CHECKING:
    import httpx


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class GpaExtraction(BaseModel, frozen=True):
    """Structured GPA information extracted from transcripts.

    Attributes
    ----------
    gpa_value
        Raw GPA or average as it appears on the transcript (e.g. ``"3.7"``).
    gpa_scale
        Maximum of the grading scale (e.g. ``"4.0"``, ``"20"``, ``"6.0"``).
    gpa_normalized
        GPA normalized to a 0-100 scale for cross-system comparison.
    grading_system
        Identified grading system (e.g. ``"US 4.0"``, ``"French /20"``).
    institution_name
        Primary institution extracted from the transcript.
    degree_name
        Degree title (e.g. ``"BSc Electrical Engineering"``).
    notable_courses
        Brief note on outstanding strengths or weaknesses in specific courses.
    trajectory
        Grade trajectory: ``"improving"``, ``"declining"``, ``"stable"``,
        or ``"mixed"``.
    confidence
        Extraction confidence from 0.0 (guessing) to 1.0 (unambiguous).
    """

    gpa_value: str = Field(description="Raw GPA value, e.g. '3.7', '14.5', '5.3'")
    gpa_scale: str = Field(description="Scale maximum, e.g. '4.0', '20', '6.0'")
    gpa_normalized: float = Field(description="GPA normalized to 0-100 scale")
    grading_system: str = Field(
        description="Identified grading system, e.g. 'US 4.0', 'French /20', 'Swiss /6'"
    )
    institution_name: str = Field(description="Primary institution name from transcript")
    degree_name: str = Field(description="Degree title, e.g. 'BSc Electrical Engineering'")
    notable_courses: str = Field(description="Brief note on course-level strengths or weaknesses")
    trajectory: str = Field(
        description="Grade trajectory: 'improving', 'declining', 'stable', or 'mixed'"
    )
    confidence: float = Field(
        description="Extraction confidence from 0.0 (guessing) to 1.0 (unambiguous)"
    )

    _MAX_NORMALIZED: float = 100.0
    _MAX_CONFIDENCE: float = 1.0

    @model_validator(mode="after")
    def _clamp_ranges(self) -> Self:
        """Ensure normalized GPA and confidence are within valid ranges."""
        if not (0.0 <= self.gpa_normalized <= self._MAX_NORMALIZED):
            msg = f"gpa_normalized must be 0-100, got {self.gpa_normalized}"
            raise ValueError(msg)
        if not (0.0 <= self.confidence <= self._MAX_CONFIDENCE):
            msg = f"confidence must be 0.0-1.0, got {self.confidence}"
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a GPA extraction specialist for the EPFL MTE admissions panel.

Your task is to read a candidate's transcript text and extract structured GPA
information. The transcript may come from any country and use any grading system.

## Instructions

1. **Identify the grading scale** from context clues: university name, country
   references, grade format, or explicit scale notation.

2. **Extract the overall GPA or cumulative average.** If no single GPA is stated,
   compute or estimate it from individual course grades.

3. **Normalize to a 0-100 scale** using these conversions:
   - **US 4.0 scale:** GPA * 25 (e.g. 4.0 -> 100, 3.0 -> 75)
   - **French /20:** score * 5 (e.g. 16/20 -> 80, 14/20 -> 70)
   - **Swiss /6:** (score - 1) * 20 (e.g. 5.0/6 -> 80, 4.0/6 -> 60)
   - **German 1-5 (1=best):** (5 - score) * 25 (e.g. 1.0 -> 100, 2.5 -> 62.5)
   - **Indian /10 (CGPA):** score * 10 (e.g. 8.5 -> 85)
   - **Percentage systems:** use value as-is (e.g. 85% -> 85)
   - **UK classifications:** First -> 80, 2:1 -> 65, 2:2 -> 55, Third -> 45

4. **Handle multiple transcripts:** If the candidate has transcripts from multiple
   institutions (e.g. bachelor + exchange semester), use the primary degree
   institution for the main GPA. Mention exchange grades in notable_courses.

5. **Handle missing or unreadable data:** If grades are pass/fail, the transcript
   is an image placeholder, or grades cannot be determined, set gpa_value to "N/A",
   gpa_normalized to 0.0, and confidence to a low value (0.1-0.3).

6. **Assess trajectory** by comparing early-year grades to later-year grades.

7. **Set confidence** based on how clear and unambiguous the extraction is:
   - 0.9-1.0: Explicit GPA stated with clear scale
   - 0.7-0.8: GPA computed from individual grades with known scale
   - 0.5-0.6: Scale inferred from context, some ambiguity
   - 0.1-0.4: Significant uncertainty, missing data, or image-only transcript

Respond with a JSON object matching the GpaExtraction schema.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def extract_gpa(
    transcript_text: str, *, model: str, base_url: str, client: httpx.AsyncClient | None = None
) -> GpaExtraction:
    """Extract structured GPA information from transcript text.

    Parameters
    ----------
    transcript_text
        Concatenated markdown text of all transcripts for a candidate.
    model
        LLM model identifier.
    base_url
        LLM endpoint base URL.
    client
        Optional shared ``httpx.AsyncClient``.

    Returns
    -------
    GpaExtraction
        Parsed GPA extraction with normalized score and metadata.
    """
    if not transcript_text.strip():
        return GpaExtraction(
            gpa_value="N/A",
            gpa_scale="N/A",
            gpa_normalized=0.0,
            grading_system="unknown",
            institution_name="unknown",
            degree_name="unknown",
            notable_courses="No transcript text available.",
            trajectory="stable",
            confidence=0.0,
        )

    messages = [
        ChatMessage(role="system", content=_SYSTEM_PROMPT),
        ChatMessage(
            role="user",
            content=f"Extract GPA information from this transcript:\n\n{transcript_text}",
        ),
    ]

    return await complete(
        messages=messages,
        response_model=GpaExtraction,
        model=model,
        base_url=base_url,
        client=client,
    )
