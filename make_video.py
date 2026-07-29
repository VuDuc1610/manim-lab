import argparse
import shutil
import sys
import time

from pipeline import config
from pipeline.codegen import generate_all_scenes, generate_scene_code
from pipeline.planner import PlanError, make_plan
from pipeline.renderer import RenderError, render_all, render_scene
from pipeline.stitch import StitchError, stitch

QUALITY_FLAGS = {"ql": "-ql", "qm": "-qm", "qh": "-qh"}


def _print_timing(timings: dict) -> None:
    print()
    for name, (elapsed, note) in timings.items():
        note_str = f"   ({note})" if note else ""
        print(f"{name:<12}{elapsed:>6.1f}s{note_str}")
    print("─" * 17)
    total = sum(elapsed for elapsed, _ in timings.values())
    print(f"{'total':<12}{total:>6.1f}s")


def _clean_work_dir() -> None:
    shutil.rmtree(config.WORK_DIR, ignore_errors=True)
    config.WORK_DIR.mkdir(parents=True, exist_ok=True)


def run(
    prompt: str,
    quality: str = "qm",
    scenes_hint: int | None = None,
    keep_work: bool = False,
    strict: bool = False,
    sequential: bool = False,
):
    quality_flag = QUALITY_FLAGS[quality]
    mode = "sequential" if sequential else "parallel"
    timings = {}

    try:
        full_prompt = prompt if scenes_hint is None else f"{prompt} (aim for about {scenes_hint} scenes)"

        t0 = time.perf_counter()
        plan = make_plan(full_prompt)
        timings["plan"] = (time.perf_counter() - t0, "")

        n_scenes = len(plan["scenes"])

        t0 = time.perf_counter()
        if sequential:
            sources = {scene["id"]: generate_scene_code(plan, scene) for scene in plan["scenes"]}
        else:
            sources = generate_all_scenes(plan)
        timings["codegen"] = (time.perf_counter() - t0, f"{n_scenes} scenes, {mode}")

        t0 = time.perf_counter()
        if sequential:
            results = {}
            for scene_id, code in sources.items():
                try:
                    results[scene_id] = render_scene(code, scene_id, quality_flag)
                except RenderError as e:
                    if strict:
                        raise
                    print(f"[scene {scene_id}] dropped after exhausting retries: {e}", file=sys.stderr)
        else:
            results = render_all(sources, quality_flag, strict=strict)
        if not results:
            raise RenderError("all scenes failed to render; nothing to stitch")
        timings["render"] = (time.perf_counter() - t0, f"{len(results)}/{n_scenes} scenes, {mode}")

        t0 = time.perf_counter()
        clips = [results[scene_id] for scene_id in sorted(results)]
        out_path = config.OUT_DIR / f"{plan['slug']}.mp4"
        stitch(clips, out_path)
        timings["stitch"] = (time.perf_counter() - t0, "")

        _print_timing(timings)
        return out_path
    except Exception:
        _print_timing(timings)
        raise
    finally:
        if not keep_work:
            _clean_work_dir()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Turn a text prompt into an explainer video.")
    parser.add_argument("prompt")
    parser.add_argument("--quality", choices=["ql", "qm", "qh"], default="qm")
    parser.add_argument("--scenes", type=int, default=None, dest="scenes_hint")
    parser.add_argument("--keep-work", action="store_true", dest="keep_work")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--sequential", action="store_true", help="debug: disable parallelism")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        out_path = run(
            args.prompt,
            quality=args.quality,
            scenes_hint=args.scenes_hint,
            keep_work=args.keep_work,
            strict=args.strict,
            sequential=args.sequential,
        )
    except (PlanError, RenderError, StitchError) as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"\n{out_path}")


if __name__ == "__main__":
    main()
