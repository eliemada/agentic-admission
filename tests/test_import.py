"""Smoke tests verifying that core packages are importable."""

from __future__ import annotations

import agentic_admission
import agentic_admission.agents
import agentic_admission.anonymizer
import agentic_admission.config
import agentic_admission.extraction
import agentic_admission.models


def test_package_imports() -> None:
    """Verify the top-level package can be imported."""
    assert agentic_admission.__doc__ is not None


def test_submodule_imports() -> None:
    """Verify all submodules can be imported."""
    assert agentic_admission.agents.__doc__ is not None
    assert agentic_admission.anonymizer.__doc__ is not None
    assert agentic_admission.config.__doc__ is not None
    assert agentic_admission.extraction.__doc__ is not None
    assert agentic_admission.models.__doc__ is not None
