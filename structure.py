"""
Structuring stage with an Ollama compatibility fallback.

It first tries Ollama's JSON mode. If that produces an empty response, it retries
without JSON mode and asks for a JSON-only answer. Raw diagnostics are printed.
"""
import json
import requests
import re
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:1.7b"
OUT = Path("structured.json")

PROMPT = """
Extract only information explicitly stated in the user's procurement text.
Return exactly one JSON object with these keys:
{
  "material": string or null,
  "process": string or null,
  "quantity": number or null,
  "unit": string or null,
  "clinker_tonnes": number or null,
  "fuel_name": string or null,
  "fuel_quantity": number or null,
  "fuel_unit": string or null,
  "emission_factor": number or null,
  "emission_factor_unit": string or null,
  "factor_source": string or null,
  "factor_year": number or null,
  "geography": string or null,
  "calculation_method": string or null,
  "boundary": string or null,
  "notes": string
}
Rules:
- Never invent missing values or emission factors.
- If clinker quantity is explicitly given in tonnes, set clinker_tonnes to that number.
- Extract a factor only if a numeric factor is explicitly stated.
- Use null for absent values.
- Return JSON only; no markdown and no explanation.
"""

def parse_object(raw):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("The model response text is empty.")
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        first, last = cleaned.find("{"), cleaned.rfind("}")
        if first == -1 or last <= first:
            raise ValueError(f"No JSON object in model text: {raw[:500]!r}")
        obj = json.loads(cleaned[first:last + 1])
    if not isinstance(obj, dict):
        raise ValueError("The JSON response is not an object.")
    return obj

def call_ollama(text, json_mode):
    payload = {
        "model": MODEL,
        "prompt": PROMPT + "\n\nUSER INPUT:\n" + text + "\n\nReturn the JSON object now.",
        "think" : False,
        "stream": False,
        "options": {"temperature": 0, "num_predict": 500, "num_ctx": 2048},
        "keep_alive": "5m",
    }
    if json_mode:
        payload["format"] = "json"
    resp = requests.post(OLLAMA_URL, json=payload, timeout=300)
    if not resp.ok:
        raise RuntimeError(f"Ollama HTTP {resp.status_code}: {resp.text[:800]}")
    try:
        data = resp.json()
    except ValueError as e:
        raise RuntimeError(f"Ollama API did not return JSON: {resp.text[:500]!r}") from e

    # Ollama's API envelope is JSON, but the generated model text is data["response"].
    generated = data.get("response")
    print(
        f"Debug: json_mode={json_mode}, done={data.get('done')}, "
        f"done_reason={data.get('done_reason')}, "
        f"response_type={type(generated).__name__}, "
        f"response_length={len(generated) if isinstance(generated, str) else 'n/a'}"
    )
    if data.get("error"):
        raise RuntimeError(f"Ollama reported an error: {data['error']}")
    if not isinstance(generated, str) or not generated.strip():
        raise ValueError("Ollama returned an empty generated-text field.")
    return generated

def main():
    OUT.unlink(missing_ok=True)
    print("STRUCTURING STEP")
    print("Paste text; finish with END on its own line:")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().upper() == "END":
            break
        lines.append(line)
    raw_text = "\n".join(lines).strip()
    if not raw_text:
        print("No input provided.")
        return

    try:
        # Attempt structured output first.
        try:
            generated = call_ollama(raw_text, json_mode=True)
            extracted = parse_object(generated)
        except (ValueError, json.JSONDecodeError) as first_error:
            print(f"JSON-mode attempt failed: {first_error}")
            print("Retrying once without Ollama JSON mode...")
            generated = call_ollama(raw_text, json_mode=False)
            extracted = parse_object(generated)

        extracted["_raw_input"] = raw_text
        OUT.write_text(json.dumps(extracted, indent=2, ensure_ascii=False), encoding="utf-8")
        print("\nSTRUCTURED VALUES:")
        print(json.dumps(extracted, indent=2, ensure_ascii=False))
        print("\nSaved structured.json")
    except requests.exceptions.ConnectionError:
        print("Cannot connect to Ollama. Start Ollama and check `ollama list`.")
    except requests.exceptions.Timeout:
        print("Ollama timed out. Close other applications and try again.")
    except (requests.HTTPError, RuntimeError, ValueError, json.JSONDecodeError) as e:
        print(f"Structuring failed: {e}")

if __name__ == "__main__":
    main()
