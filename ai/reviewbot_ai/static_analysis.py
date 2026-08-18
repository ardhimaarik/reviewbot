# ai/reviewbot_ai/static_analysis.py
import subprocess
import json
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class LinterIssue(BaseModel):
    """Single linter issue."""
    linter: str
    file: str
    line: int
    severity: str
    message: str

def run_linters(repo_path: str, changed_files: list[str]) -> list[LinterIssue]:
    """
    Run golangci-lint and parse output JSON.
    Filter to only changed files.
    
    Args:
        repo_path: Local repo path
        changed_files: List of files to check
    
    Returns:
        List of LinterIssue objects (or empty if linter fails)
    """
    if not changed_files:
        return []

    changed_set = set(changed_files)
    issues = []

    try:
        logger.info(f"Running golangci-lint on {len(changed_files)} files in {repo_path}")
        
        result = subprocess.run(
            [
                "golangci-lint", "run",
                "--out-format=json",
                "--timeout=2m",
                "--new-from-rev=HEAD~1",
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=180,
        )
        
        # golangci-lint exit code 1 = issues found (not an error)
        if result.stdout:
            raw = json.loads(result.stdout)
        else:
            logger.warning("golangci-lint returned empty output")
            return []

    except subprocess.TimeoutExpired:
        logger.error("golangci-lint timed out")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse golangci-lint JSON: {e}")
        return []
    except FileNotFoundError:
        logger.error("golangci-lint not found in PATH — make sure it's installed")
        return []
    except Exception as e:
        logger.error(f"Unexpected error running linter: {e}")
        return []

    # Parse issues, filter to changed files
    for item in raw.get("Issues", []):
        filepath = item.get("Pos", {}).get("Filename", "")
        
        # Skip if not in changed files
        if filepath not in changed_set:
            continue
        
        try:
            issue = LinterIssue(
                linter=item.get("FromLinter", "unknown"),
                file=filepath,
                line=item.get("Pos", {}).get("Line", 0),
                severity=item.get("Severity", "warning").lower(),
                message=item.get("Text", ""),
            )
            issues.append(issue)
        except Exception as e:
            logger.warning(f"Failed to parse linter issue: {e}")
            continue

    logger.info(f"Found {len(issues)} linter issues in changed files")
    return issues