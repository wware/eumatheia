"""Pydantic models for exhibits and sessions."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class PaneType(str, Enum):
    """Types of panes that can be displayed."""

    TERMINAL = "terminal"
    IFRAME = "iframe"
    MARKDOWN = "markdown"


class Pane(BaseModel):
    """Configuration for a UI pane."""

    type: PaneType = Field(description="Type of pane to display")
    label: str = Field(description="Label shown in the pane tab")
    path: str | None = Field(
        default=None, description="Path for iframe panes (e.g., /dashboard/)"
    )


class VerifyManual(BaseModel):
    """Manual verification - user clicks Continue."""

    type: Literal["manual"] = "manual"


class VerifyShell(BaseModel):
    """Scripted shell verification."""

    type: Literal["shell"] = "shell"
    command: str = Field(description="Shell command to run for verification")
    expect_contains: str = Field(description="String that must appear in output")


Verify = VerifyManual | VerifyShell


class AncillaryFiles(BaseModel):
    """Ancillary files for a step (Dockerfiles, compose files, scripts, etc.)."""

    dockerfile: str | None = Field(
        default=None, description="Path to Dockerfile relative to exhibit directory"
    )
    compose: str | None = Field(
        default=None,
        description="Path to docker-compose.yml relative to exhibit directory",
    )
    scripts: list[str] = Field(
        default_factory=list,
        description="Paths to scripts relative to exhibit directory",
    )


class NavButton(BaseModel):
    """Custom navigation button for non-linear navigation."""

    label: str = Field(description="Button label text")
    target: str = Field(
        description="Target step ID (or 'previous' for back navigation)"
    )


class Step(BaseModel):
    """A single step in an exhibit."""

    id: str = Field(description="Unique identifier for this step")
    narrative: str = Field(description="Path to markdown file with step narrative")
    panes: list[Pane] = Field(description="Panes visible for this step")
    verify: Verify = Field(description="Verification method for this step")
    next: str | None = Field(description="ID of next step, or null if end of exhibit")
    ancillary: AncillaryFiles | None = Field(
        default=None, description="Optional ancillary files for this step"
    )
    nav: list[NavButton] | None = Field(
        default=None,
        description="Optional custom navigation buttons (overrides next/previous)",
    )


class SetupManifest(BaseModel):
    """Kubernetes manifest to apply during setup."""

    manifest: str = Field(description="Path to Kubernetes manifest file")


class Exhibit(BaseModel):
    """An exhibit - a sequence of learning steps."""

    exhibit: str = Field(description="Unique identifier for this exhibit")
    title: str = Field(description="Human-readable title")
    setup: list[SetupManifest] = Field(
        default_factory=list, description="Manifests to apply at exhibit start"
    )
    steps: list[Step] = Field(description="Ordered list of steps")

    def get_step(self, step_id: str) -> Step | None:
        """Get a step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    @property
    def first_step(self) -> Step | None:
        """Get the first step in the exhibit."""
        return self.steps[0] if self.steps else None


class Session(BaseModel):
    """A learner session."""

    session_id: str = Field(description="Unique session identifier (namespace name)")
    exhibit_id: str = Field(description="ID of the exhibit being followed")
    current_step: str = Field(description="ID of the current step")
    created_at: float = Field(description="Unix timestamp when session was created")
    last_activity: float = Field(description="Unix timestamp of last activity")

    model_config = {"frozen": True}
