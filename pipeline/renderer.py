import glob
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pipeline import config
from pipeline.codegen import SanitizeError, sanitize
from pipeline.llm import generate, strip_code_fences


class RenderError(Exception):
    pass


def _write_scene_file(code: str, scene_id: int) -> Path:
    path = config.WORK_DIR / f"scene_{scene_id}.py"
    path.write_text(code)
    return path


def _run_docker_render(scene_id: int, quality: str):
    """Returns (success, error_excerpt)."""
    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{config.PROJECT_ROOT}:/manim",
                "manimcommunity/manim",
                "manim", quality, f"work/scene_{scene_id}.py", f"Scene{scene_id}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=config.RENDER_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        return False, (
            f"Render exceeded {config.RENDER_TIMEOUT_SEC}s — "
            "the scene is too complex, simplify it drastically"
        )

    if result.returncode == 0:
        return True, ""

    stderr_lines = result.stderr.strip().splitlines()
    return False, "\n".join(stderr_lines[-30:])


def _locate_output(scene_id: int) -> Path:
    pattern = str(
        config.PROJECT_ROOT / "media" / "videos" / f"scene_{scene_id}" / "**" / f"Scene{scene_id}.mp4"
    )
    matches = glob.glob(pattern, recursive=True)
    if not matches:
        raise RenderError(f"scene {scene_id}: no output file found matching {pattern}")
    return Path(max(matches, key=lambda p: Path(p).stat().st_mtime))


_REPAIR_SYSTEM = (
    "You are fixing a broken Manim Community Edition scene. Return the complete "
    "corrected file. Change as little as possible. Do not explain."
)


def _repair(code: str, scene_id: int, error_excerpt: str) -> str:
    user = (
        f"This Manim source for Scene{scene_id} failed to render:\n\n{code}\n\n"
        f"Error (last lines of stderr):\n{error_excerpt}\n\n"
        "Return the complete corrected Python source only. No markdown fences, no explanation."
    )
    raw = generate(_REPAIR_SYSTEM, user, config.REPAIR_MODEL)
    return sanitize(strip_code_fences(raw), scene_id)


def render_scene(code: str, scene_id: int, quality: str) -> Path:
    """Writes source, renders, repairs and retries on failure. Returns MP4 path."""
    for attempt in range(1, config.MAX_RENDER_ATTEMPTS + 1):
        _write_scene_file(code, scene_id)
        success, error_excerpt = _run_docker_render(scene_id, quality)
        if success:
            return _locate_output(scene_id)

        error_summary = error_excerpt.splitlines()[-1] if error_excerpt else "unknown error"
        print(
            f"[scene {scene_id}] attempt {attempt}/{config.MAX_RENDER_ATTEMPTS} — {error_summary}",
            file=sys.stderr,
        )

        if attempt >= config.MAX_RENDER_ATTEMPTS:
            raise RenderError(
                f"scene {scene_id}: failed to render after "
                f"{config.MAX_RENDER_ATTEMPTS} attempts: {error_summary}"
            )

        try:
            code = _repair(code, scene_id, error_excerpt)
        except SanitizeError as e:
            print(f"[scene {scene_id}] repair output failed sanitize: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[scene {scene_id}] repair call failed: {e}", file=sys.stderr)

    raise AssertionError("unreachable")


def render_all(sources: dict[int, str], quality: str, strict: bool = False) -> dict[int, Path]:
    """Renders every scene concurrently."""
    max_workers = min(len(sources), 4)
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(render_scene, code, scene_id, quality): scene_id
            for scene_id, code in sources.items()
        }
        for future, scene_id in futures.items():
            try:
                results[scene_id] = future.result()
            except RenderError:
                if strict:
                    raise
                print(f"[scene {scene_id}] dropped after exhausting retries", file=sys.stderr)
    return results
