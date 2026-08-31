"""Agent nodes, and the `.md` instructions that drive them.

Instructions are loaded from disk at runtime rather than embedded in Python:
they are a deliverable a judge reads, and a prompt buried in a string literal
is neither reviewable nor diffable.
"""

from pathlib import Path

INSTRUCTIONS_DIR = Path(__file__).resolve().parent / "instructions"


def load_instruction(name: str) -> str:
    """Reads `agents/instructions/<name>.md`."""
    path = INSTRUCTIONS_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"no instruction named {name!r} at {path}")
    return path.read_text()
