import pathlib

PROMPT_ROOT = pathlib.Path(__file__).parent / "prompts"

def load_prompt_template(name: str) -> str:
    """
    Load a prompt file from llm/prompts directory.
    Example: load_prompt_template("analysis_agent.txt")
    """
    p = PROMPT_ROOT / name
    if not p.exists():
        raise FileNotFoundError(f"Prompt {name} not found at {p}")
    return p.read_text(encoding="utf-8")
