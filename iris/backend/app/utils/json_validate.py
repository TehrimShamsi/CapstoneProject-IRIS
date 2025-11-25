import json
from jsonschema import validate, ValidationError

from ..llm.prompt_loader import PROMPT_ROOT  # not used; keep for import path
import pathlib

SCHEMA_DIR = pathlib.Path(__file__).parent.parent / "schemas"

def load_schema(name: str):
    p = SCHEMA_DIR / f"{name}.json"
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

ANALYSIS_SCHEMA = load_schema("analysis_schema")
SYNTHESIS_SCHEMA = load_schema("synthesis_schema")

def validate_json(raw_text: str, schema_name: str):
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        # attempt naive repair: find first { ... } block
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        data = json.loads(raw_text[start:end])
    schema = ANALYSIS_SCHEMA if schema_name=="analysis" else SYNTHESIS_SCHEMA
    try:
        validate(instance=data, schema=schema)
    except ValidationError as e:
        raise ValueError(f"JSON did not validate against schema {schema_name}: {e}")
    return data
