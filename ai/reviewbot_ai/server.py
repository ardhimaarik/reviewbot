# ai/reviewbot_ai/server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .llm_client import review_diff
from .static_analysis import run_linters
import time, logging

app = FastAPI()
logger = logging.getLogger(__name__)

class ReviewRequest(BaseModel):
    diff: str
    file_paths: list[str]
    repo_path: str
    model: str = "claude-haiku-4-5-20241022"

@app.post("/review")
def handle_review(req: ReviewRequest):
    start = time.time()
    try:
        # 1. Run linters (deterministic-first)
        linter_issues = run_linters(req.repo_path, req.file_paths)
        linter_json = [i.model_dump() for i in linter_issues]

        # 2. LLM review (judgment layer)
        result = review_diff(req.diff, str(linter_json), req.file_paths, req.model)

        return {
            "review": result.model_dump(),
            "linter_issues": linter_json,
            "latency_ms": int((time.time() - start) * 1000),
        }
    except Exception as e:
        logger.exception("Review failed")
        raise HTTPException(status_code=500, detail=str(e))
    