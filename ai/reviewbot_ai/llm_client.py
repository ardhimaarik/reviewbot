# ai/reviewbot_ai/llm_client.py
import os
import json
import logging
from openai import OpenAI
from .schemas import ReviewOutput
from .prompts import SYSTEM_PROMPT, build_prompt

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

def _get_client() -> OpenAI:
    """Get OpenAI-compatible client (Ollama local)."""
    return OpenAI(base_url=f"{OLLAMA_HOST}/v1", api_key="ollama")

def review_diff(
    diff: str,
    linter_json: str,
    file_paths: list[str],
    model: str = "qwen3.5:9b",
) -> ReviewOutput:
    """
    Review a diff using LLM.
    
    Args:
        diff: Unified diff
        linter_json: JSON string of linter issues (already caught)
        file_paths: List of changed files
        model: Model name (default qwen3.5:9b local)
    
    Returns:
        ReviewOutput with issues + summary
    
    Raises:
        ValueError: If LLM output cannot be parsed as valid JSON
    """
    client = _get_client()
    prompt = build_prompt(diff, linter_json, file_paths)

    logger.info(f"Reviewing with model={model}, files={len(file_paths)}, diff_lines={len(diff.splitlines())}")

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=2048,
            temperature=0.2,  # reproducibility for eval
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        raw_text = response.choices[0].message.content
        logger.debug(f"LLM response: {raw_text[:200]}...")

    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise

    # Parse + validate via Pydantic
    try:
        return ReviewOutput.model_validate_json(raw_text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}\nRaw: {raw_text}")
        raise ValueError(f"LLM output not valid JSON: {e}")
    except Exception as e:
        logger.warning(f"First parse failed, retrying with stricter temp...")
        
        # Retry with temperature=0 for deterministic output
        try:
            retry_response = client.chat.completions.create(
                model=model,
                max_tokens=2048,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": raw_text},
                    {
                        "role": "user",
                        "content": "Your previous response was invalid JSON. Return ONLY valid JSON matching the schema. No markdown, no explanation."
                    },
                ],
            )
            retry_text = retry_response.choices[0].message.content
            return ReviewOutput.model_validate_json(retry_text)
        except Exception as retry_err:
            logger.error(f"Retry also failed: {retry_err}")
            raise ValueError(f"LLM output cannot be parsed after retry: {retry_err}")