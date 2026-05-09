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
    per_subject_averages: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Optional per-subject averages on the transcript's native scale, "
            "keyed by lowercased subject family (e.g. 'analysis', 'algebra', "
            "'physics', 'mathematics'). Especially useful for EPFL-internal "
            "candidates whose admission threshold is the algebra+analysis "
            "average rather than overall GPA. Empty dict when not extractable."
        ),
    )
    section_switch_detected: bool = Field(
        default=False,
        description=(
            "True when the transcript shows the candidate switching bachelor "
            "section (mise à niveau / change of major). Lowers the weight of "
            "early-section grades in downstream scoring."
        ),
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

1. **Identify the PRIMARY transcript first.** When the dossier contains
   multiple transcripts (e.g. main bachelor + minor + exchange semester
   + visiting program), pick exactly one as primary and treat the rest
   as secondary context:
   - **Primary** is the longest-program degree (typically a 3-4 year
     BSc/BEng/BA/MSc) where the candidate is being awarded the diploma
     they list as their main qualification.
   - **Secondary** transcripts are minors, exchange/visiting semesters,
     and certificate programs. Their grades go in ``notable_courses``,
     never in ``gpa_value`` or ``per_subject_averages``.
   - In the rare case where two transcripts could plausibly be primary
     (e.g. dual degree), pick the one whose institution awards the
     diploma the candidate is presenting and lower ``confidence``.

2. **Numerical-average rule.** When the primary transcript lists
   per-module marks, you MUST compute and report the numerical average
   as ``gpa_value`` (e.g. ``"66.27"`` on a /100 scale). Categorical
   classifications such as "First Class", "Distinction", "Cum Laude"
   belong in ``notable_courses`` only — never as ``gpa_value``.
   Categorical-only ``gpa_value`` (e.g. ``"First Class"``) is allowed
   ONLY when the transcript provides no per-module marks at all.

3. **Identify the grading scale** from context clues: university name,
   country references, grade format, or explicit scale notation.

4. **Normalize to a 0-100 scale** using these conversions:
   - **US 4.0 scale:** GPA * 25 (e.g. 4.0 -> 100, 3.0 -> 75)
   - **French /20:** score * 5 (e.g. 16/20 -> 80, 14/20 -> 70)
   - **Swiss /6:** (score - 1) * 20 (e.g. 5.0/6 -> 80, 4.0/6 -> 60)
   - **German 1-5 (1=best):** (5 - score) * 25 (e.g. 1.0 -> 100, 2.5 -> 62.5)
   - **Indian /10 (CGPA):** score * 10 (e.g. 8.5 -> 85)
   - **Italian /30:** (score - 18) / 12 * 100 (e.g. 28/30 -> 83, 30/30 -> 100)
   - **Percentage systems:** use value as-is (e.g. 85% -> 85)
   - **UK numeric (0-100):** use value as-is (e.g. 66 average -> 66)
   - **UK classifications (when no marks given):** First -> 75, 2:1 -> 65,
     2:2 -> 55, Third -> 45. PREFER computing from numeric marks when present.

4. **Italian transcripts (special rules):**
   - The 18-30 scale is standard. ``30 e lode`` / ``30L`` / ``30 cum laude`` is
     a distinction above 30 — record gpa_value as ``"30 e lode"`` verbatim
     (the gate parser knows what to do with it).
   - Italians can retake exams to improve grades, which inflates averages.
     This is why the SPE threshold for Italian schools is high (28-29). Do
     NOT try to deflate the average yourself; just extract honestly.
   - The thesis grade (often ``"110/110"`` or ``"110 e lode"``) is NOT the
     course average. Do not use it as the GPA.

5. **Per-subject averages (per_subject_averages):**
   Compute averages keyed by lowercased subject family when there are at
   least two courses in that family on the **primary** transcript. Use
   these keys: ``"analysis"``, ``"algebra"``, ``"mathematics"`` (catch-
   all when calc/algebra are not separable), ``"physics"``,
   ``"mechanics"``, ``"computer_science"``, ``"chemistry"``,
   ``"biology"``, ``"economics"``, ``"electrical"``.

   **Hard rules for this field:**
   - All values MUST be on the **same scale** as ``gpa_value``. If
     ``gpa_value`` is ``"66.27"`` on a /100 scale, every entry here is
     /100. Do NOT mix scales (no ``{"math": 86, "cs": 3.95}``).
   - Compute ONLY from primary-transcript courses. Do NOT include
     courses from minors, exchanges, or secondary transcripts — those
     belong in ``notable_courses``.
   - Single-course buckets are allowed (e.g. ``"mathematics": 86`` from
     a single Engineering Mathematics course). Skip a bucket only when
     no relevant course exists.
   - Do NOT invent buckets. If the candidate has no computer-science
     courses, the dict has no ``"computer_science"`` key.

   **EPFL-internal transcripts:** This field is decisive — the committee
   evaluates internals on the algebra+analysis average. ALWAYS populate
   ``"analysis"`` and ``"algebra"`` keys when courses are present
   (Analyse I/II, Algèbre linéaire, Algèbre I/II, ...). Include advanced
   variants (Analyse avancée I/II) under the same ``"analysis"`` key.

6. **Section switches (section_switch_detected):**
   Set ``true`` when the transcript shows the candidate enrolled in one
   bachelor section early (e.g. mathematics, physics) and a different
   section later (e.g. micro-engineering). EPFL term: "mise à niveau".
   Indicators: change in section/department on the transcript, repeated
   first-year courses, gaps in semester numbering.

7. **Handle multiple transcripts:** Apply the primary-vs-secondary rule
   from instruction (1). Secondary transcripts (minors, exchanges,
   visiting programs) appear in ``notable_courses`` only. Never let a
   secondary transcript's high GPA leak into ``gpa_value`` — even if
   the primary's GPA is much weaker, the gate compares against the
   primary degree's threshold.

8. **Handle missing or unreadable data:** If grades are pass/fail, the transcript
   is an image placeholder, or grades cannot be determined, set gpa_value to "N/A",
   gpa_normalized to 0.0, and confidence to a low value (0.1-0.3).

9. **Assess trajectory** by comparing early-year grades to later-year grades.
   For section-switchers, base trajectory on the post-switch section only.

10. **Set confidence** based on how clear and unambiguous the extraction is:
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
