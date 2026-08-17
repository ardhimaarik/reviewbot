# ai/reviewbot_ai/schemas.py
from pydantic import BaseModel, Field

class ReviewIssue(BaseModel):
    severity: str = Field(description="blocker | major | minor | nit")
    category: str = Field(description="bug | perf | style | security | clarity")
    file: str
    line: int
    message: str
    suggestion: str
    confidence: float = Field(ge=0.0, le=1.0)

class ReviewOutput(BaseModel):
    summary: str
    issues: list[ReviewIssue] = []