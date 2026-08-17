# ai/reviewbot_ai/llm_client.py
import json
import anthropic
from .schemas import ReviewOutput
from .prompts import SYSTEM_PROMPT, build_prompt

client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY env var
# Untuk LiteLLM: ganti ke openai.OpenAI(base_url="http://litellm:4000/v1")

def review_diff(
    diff: str,
    linter_json: str,
    file_paths: list[str],
    model: str = "claude-haiku-4-5-20241022",
) -> ReviewOutput:
    prompt = build_prompt(diff, linter_json, file_paths)

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        temperature=0.2,  # reproducibility untuk eval
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.content[0].text

    # parse + validate via Pydantic — kalau gagal, retry sekali
    try:
        return ReviewOutput.model_validate_json(raw_text)
    except Exception:
        retry_response = client.messages.create(
            model=model,
            max_tokens=2048,
            temperature=0.0,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": raw_text},
                {"role": "user", "content": "Your previous response was invalid JSON. Return ONLY valid JSON matching the schema. No markdown, no explanation."},
            ],
        )
        return ReviewOutput.model_validate_json(retry_response.content[0].text)