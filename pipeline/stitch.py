import subprocess
import sys
from pathlib import Path

from pipeline import config


class StitchError(Exception):
    pass


def _write_concat_file(clips: list[Path]) -> Path:
    concat_path = config.WORK_DIR / "concat.txt"
    lines = [f"file '{clip.resolve()}'" for clip in clips]
    concat_path.write_text("\n".join(lines) + "\n")
    return concat_path


def _run_ffmpeg(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["ffmpeg", *args], capture_output=True, text=True)


def stitch(clips: list[Path], out_path: Path) -> Path:
    concat_path = _write_concat_file(clips)

    result = _run_ffmpeg(
        ["-y", "-f", "concat", "-safe", "0", "-i", str(concat_path), "-c", "copy", str(out_path)]
    )
    if result.returncode == 0:
        return out_path

    print(
        "[stitch] -c copy failed (clips likely differ in resolution/framerate/codec), "
        "falling back to a re-encode with libx264",
        file=sys.stderr,
    )
    result = _run_ffmpeg(
        [
            "-y", "-f", "concat", "-safe", "0", "-i", str(concat_path),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path),
        ]
    )
    if result.returncode == 0:
        return out_path

    raise StitchError(f"ffmpeg failed to stitch clips into {out_path}: {result.stderr.strip()}")
