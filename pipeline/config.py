from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = PROJECT_ROOT / "work"
OUT_DIR = PROJECT_ROOT / "out"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

PLANNER_MODEL = "gemini-2.5-flash"
CODEGEN_MODEL = "gemini-2.5-flash"
REPAIR_MODEL = "gemini-2.5-flash"

DEFAULT_QUALITY = "-qm"

MAX_RENDER_ATTEMPTS = 3
RENDER_TIMEOUT_SEC = 180

MIN_SCENES = 3
MAX_SCENES = 6

MIN_SCENE_SEC = 5
MAX_SCENE_SEC = 10

WORK_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)
