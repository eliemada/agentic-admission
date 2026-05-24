"""Tests for dossier and document models."""

from __future__ import annotations

from pathlib import PurePosixPath

from agentic_admission.models.document import DocumentType, DossierDocument, classify_document
from agentic_admission.models.dossier import Dossier, ProcessingStage
from agentic_admission.models.evaluation import AgentRole, AgentScorecard, Decision, PanelVerdict
from tests.conftest import make_justification, make_verdict_summary

# ---------------------------------------------------------------------------
# DocumentType classification
# ---------------------------------------------------------------------------


class TestClassifyDocument:
    """Tests for document type classification from filenames."""

    def test_synthese(self) -> None:
        name = "1 - Cand. Master Synthese de la candidature_B4295009779"
        assert classify_document(name) == DocumentType.APPLICATION_SUMMARY

    def test_motivation_letter(self) -> None:
        name = "2 - Cand. Master Lettre de motivation_F942803165"
        assert classify_document(name) == DocumentType.MOTIVATION_LETTER

    def test_recommendation_letter(self) -> None:
        name = "3 - Cand. Master Referent #1 Lettre de recommandation_F909725189"
        assert classify_document(name) == DocumentType.RECOMMENDATION_LETTER

    def test_referent_synthese(self) -> None:
        name = "4 - Cand. Master Referent #1 Synthese_B4295009779"
        assert classify_document(name) == DocumentType.REFERENT_SUMMARY

    def test_transcript(self) -> None:
        name = "9 - Cand. Master Releve de notes institution #1_F763062988"
        assert classify_document(name) == DocumentType.TRANSCRIPT

    def test_diploma(self) -> None:
        name = "8 - Cand. Master Diplome institution #1_F1613252838"
        assert classify_document(name) == DocumentType.DIPLOMA

    def test_cv(self) -> None:
        name = "11 - Cand. Master CV_F2036236076"
        assert classify_document(name) == DocumentType.CV

    def test_language_certificate(self) -> None:
        name = "12 - Cand. Master Certificat linguistique (TOEFL ou autres)_F256430106"
        assert classify_document(name) == DocumentType.LANGUAGE_CERTIFICATE

    def test_gre(self) -> None:
        name = "13 - Cand. Master Resultats GRE_F1116244394"
        assert classify_document(name) == DocumentType.GRE_RESULTS

    def test_other_documents(self) -> None:
        name = "13 - Cand. Master Autres documents_F1880641039"
        assert classify_document(name) == DocumentType.OTHER

    def test_unknown_fallback(self) -> None:
        name = "random_file_name.pdf"
        assert classify_document(name) == DocumentType.UNKNOWN


# ---------------------------------------------------------------------------
# DossierDocument
# ---------------------------------------------------------------------------


class TestDossierDocument:
    """Tests for the DossierDocument model."""

    def test_create_document(self) -> None:
        doc = DossierDocument(
            path=PurePosixPath(
                "2024-25-fall/akiki/2 - Cand. Master Lettre de motivation_F942803165"
            ),
            document_type=DocumentType.MOTIVATION_LETTER,
            number=2,
        )
        assert doc.document_type == DocumentType.MOTIVATION_LETTER
        assert doc.number == 2

    def test_immutable(self) -> None:
        doc = DossierDocument(
            path=PurePosixPath("some/path"), document_type=DocumentType.CV, number=11
        )
        # Pydantic frozen model — assignment should raise
        try:
            doc.number = 99  # type: ignore[misc]
        except Exception:
            pass
        assert doc.number == 11


# ---------------------------------------------------------------------------
# Dossier
# ---------------------------------------------------------------------------


class TestDossier:
    """Tests for the Dossier model."""

    def test_create_minimal(self) -> None:
        dossier = Dossier(folder_name="akiki", semester="2024-25-fall", documents=[])
        assert dossier.folder_name == "akiki"
        assert dossier.semester == "2024-25-fall"
        assert dossier.candidate is None
        assert dossier.stage == ProcessingStage.RAW

    def test_with_documents(self) -> None:
        docs = [
            DossierDocument(path=PurePosixPath("a"), document_type=DocumentType.CV, number=11),
            DossierDocument(
                path=PurePosixPath("b"), document_type=DocumentType.MOTIVATION_LETTER, number=2
            ),
        ]
        dossier = Dossier(folder_name="akiki", semester="2024-25-fall", documents=docs)
        assert len(dossier.documents) == 2

    def test_has_document_type(self) -> None:
        docs = [DossierDocument(path=PurePosixPath("a"), document_type=DocumentType.CV, number=11)]
        dossier = Dossier(folder_name="akiki", semester="2024-25-fall", documents=docs)
        assert dossier.has_document(DocumentType.CV)
        assert not dossier.has_document(DocumentType.MOTIVATION_LETTER)

    def test_documents_by_type(self) -> None:
        docs = [
            DossierDocument(
                path=PurePosixPath("a"), document_type=DocumentType.RECOMMENDATION_LETTER, number=3
            ),
            DossierDocument(
                path=PurePosixPath("b"), document_type=DocumentType.RECOMMENDATION_LETTER, number=5
            ),
            DossierDocument(path=PurePosixPath("c"), document_type=DocumentType.CV, number=11),
        ]
        dossier = Dossier(folder_name="akiki", semester="2024-25-fall", documents=docs)
        recs = dossier.documents_by_type(DocumentType.RECOMMENDATION_LETTER)
        assert len(recs) == 2

    def test_processing_stage_progression(self) -> None:
        """Stages have a logical ordering."""
        assert ProcessingStage.RAW.value < ProcessingStage.NORMALIZED.value
        assert ProcessingStage.NORMALIZED.value < ProcessingStage.EXTRACTED.value
        assert ProcessingStage.EXTRACTED.value < ProcessingStage.ANONYMIZED.value
        assert ProcessingStage.ANONYMIZED.value < ProcessingStage.EVALUATED.value


# ---------------------------------------------------------------------------
# Evaluation models
# ---------------------------------------------------------------------------


class TestAgentEvaluation:
    """Tests for AgentScorecard and PanelVerdict models."""

    def test_create_scorecard(self) -> None:
        card = AgentScorecard(
            role=AgentRole.ACADEMIC,
            scores={"academic_strength": 8, "institution_quality": 7},
            justifications={
                "academic_strength": make_justification(pros=("Strong GPA from top-tier school.",)),
                "institution_quality": make_justification(pros=("Priority tier.",)),
            },
        )
        assert card.role == AgentRole.ACADEMIC
        assert card.scores["academic_strength"] == 8

    def test_panel_verdict(self) -> None:
        cards = (
            AgentScorecard(
                role=AgentRole.ACADEMIC,
                scores={"academic_strength": 3},
                justifications={"academic_strength": make_justification(cons=("Weak GPA.",))},
            ),
            AgentScorecard(
                role=AgentRole.MOTIVATION,
                scores={"motivation_clarity": 8},
                justifications={
                    "motivation_clarity": make_justification(pros=("Strong motivation letter.",))
                },
            ),
        )
        verdict = PanelVerdict(
            candidate_id="2024-25_round1_10",
            scorecards=cards,
            debates=(),
            final_scores={"academic_strength": 3, "motivation_clarity": 8},
            composite_score=5.5,
            decision=Decision.WAITLIST,
            justification=make_verdict_summary(
                pros=("Strong motivation",), cons=("Panel split, sending to committee.",)
            ),
        )
        assert verdict.decision == Decision.WAITLIST
        assert len(verdict.scorecards) == 2

    def test_agent_roles(self) -> None:
        roles = {r.value for r in AgentRole}
        assert "academic" in roles
        assert "reference" in roles
        assert "motivation" in roles
        assert "devils_advocate" in roles
        assert "chair" in roles
