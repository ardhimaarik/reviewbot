# ai/reviewbot_ai/schemas.py
from pydantic import BaseModel, Field
from typing import Optional

class ReviewIssue(BaseModel):
    """Single issue found in code review."""
    severity: str = Field(
        description="blocker | major | minor | nit",
        pattern="^(blocker|major|minor|nit)$"
    )
    category: str = Field(
        description="bug | perf | style | security | clarity | test",
        pattern="^(bug|perf|style|security|clarity|test)$"
    )
    file: str = Field(description="Filepath relative to repo root")
    line: int = Field(description="Line number (1-indexed)", ge=1)
    message: str = Field(description="Human-readable issue description")
    suggestion: str = Field(description="Concrete fix or improvement suggestion")
    confidence: float = Field(
        description="Confidence score 0-1 that this issue is real",
        ge=0.0,
        le=1.0
    )

class ReviewOutput(BaseModel):
    """Complete review result from LLM."""
    summary: str = Field(description="Brief summary of review (1-2 sentences)")
    issues: list[ReviewIssue] = Field(
        default_factory=list,
        description="List of issues found (empty if none)"
    )

class ReviewRequest(BaseModel):
    """Request to review a pull request diff."""
    diff: str = Field(description="Unified diff from git")
    file_paths: list[str] = Field(description="List of changed files")
    repo_path: str = Field(default=".", description="Local repo path for linter")
    model: str = Field(
        default="qwen3.5:9b",
        description="Model to use for review"
    )

class ReviewResponse(BaseModel):
    """Response with review results + metadata."""
    review: ReviewOutput
    linter_issues: list[dict] = Field(default_factory=list)
    latency_ms: int = Field(description="End-to-end latency in milliseconds")
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    cost_usd: Optional[float] = None