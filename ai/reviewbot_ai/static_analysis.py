# ai/reviewbot_ai/static_analysis.py
import subprocess
import json
from pydantic import BaseModel

class LinterIssue(BaseModel):
    linter: str
    file: str
    line: int
    severity: str
    message: str

def run_linters(repo_path: str, changed_files: list[str]) -> list[LinterIssue]:
    """Run golangci-lint dan parse output JSON.
    Filter hanya file yang changed — jangan report noise dari file lain."""
    try:
        result = subprocess.run(
            ["golangci-lint", "run", "--out-format=json",
             "--timeout=2m", "--new-from-rev=HEAD~1"],
            cwd=repo_path,
            capture_output=True, text=True, timeout=180,
        )
        # golangci-lint exit code 1 = ada issues (bukan error)
        raw = json.loads(result.stdout) if result.stdout else {"Issues": []}
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return []

    issues = []
    changed_set = set(changed_files)
    for item in raw.get("Issues", []):
        filepath = item.get("Pos", {}).get("Filename", "")
        if filepath not in changed_set:
            continue
        issues.append(LinterIssue(
            linter=item.get("FromLinter", "unknown"),
            file=filepath,
            line=item.get("Pos", {}).get("Line", 0),
            severity=item.get("Severity", "warning"),
            message=item.get("Text", ""),
        ))
    return issues