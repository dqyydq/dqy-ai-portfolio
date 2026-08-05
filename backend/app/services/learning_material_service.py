import re
from pathlib import Path


LEARNING_MATERIAL_PATH = (
    Path(__file__).resolve().parents[3] / "AI-Agent-Platform-Redis-Learning.md"
)
SUPPORTED_LEARNING_DAYS = frozenset(range(1, 8))


def load_learning_day_material(learning_day: int) -> str:
    if learning_day not in SUPPORTED_LEARNING_DAYS:
        raise ValueError(f"Unsupported learning day: {learning_day}")

    source = LEARNING_MATERIAL_PATH.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^## Day {learning_day}\s*$([\s\S]*?)(?=^## Day \d+\s*$|\Z)",
        re.MULTILINE,
    )
    match = pattern.search(source)
    if match is None:
        raise ValueError(f"Learning material for Day {learning_day} was not found")
    return match.group(0).strip()
