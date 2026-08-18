# ai/reviewbot_ai/server.py
import os
import json
import time
import logging
from fastapi import FastAPI, HTTPException, HealthCheck
from fastapi.responses import JSONResponse
import uvicorn

from .schemas import ReviewRequest, ReviewResponse, ReviewOutput
from .llm_client import review_diff
from .static_analysis import run_linters

# Setup logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Reviewbot AI Service",
    version="0.1.0",
    description="AI layer for Go PR reviews",
)

# Health check endpoint
@app.get("/health")
def health():
    """Health check — minimal response."""
    return {"status": "ok"}

# Review endpoint
@app.post("/review", response_model=ReviewResponse)
def handle_review(req: ReviewRequest):
    """
    Review a PR diff.
    
    Input:
        - diff: unified diff
        - file_paths: changed files
        - repo_path: local repo path (for linters)
        - model: LLM model name (default qwen3.5:9b)
    
    Output:
        - review: ReviewOutput with issues
        - linter_issues: pre-caught issues (from golangci-lint)
        - latency_ms: end-to-end time
    """
    start = time.time()
    logger.info(f"Review request: {len(req.file_paths)} files, {len(req.diff)} bytes diff")
    
    try:
        # 1. Run linters (deterministic-first)
        linter_issues = run_linters(req.repo_path, req.file_paths)
        linter_json = json.dumps([i.model_dump() for i in linter_issues])
        logger.info(f"Linter found {len(linter_issues)} issues")

        # 2. LLM review (judgment layer)
        review_output = review_diff(
            req.diff,
            linter_json,
            req.file_paths,
            req.model,
        )

        latency_ms = int((time.time() - start) * 1000)
        logger.info(f"Review complete: {len(review_output.issues)} issues found, {latency_ms}ms")

        return ReviewResponse(
            review=review_output,
            linter_issues=[i.model_dump() for i in linter_issues],
            latency_ms=latency_ms,
        )

    except Exception as e:
        logger.exception("Review failed")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8081))
    uvicorn.run(app, host="0.0.0.0", port=port)