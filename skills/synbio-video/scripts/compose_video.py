#!/usr/bin/env python3
"""Compose local video clips without uploading or overwriting user files.

Python 3.9+ standard library only. External dependency: a suitable FFmpeg build.
All source audio is discarded. Output audio is silence or one replacement track.
"""

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


class CompositionError(Exception):
    pass


def object_keys(value, allowed, label):
    if not isinstance(value, dict):
        raise CompositionError(f"{label} must be a JSON object")
    unknown = set(value) - allowed
    if unknown:
        raise CompositionError(f"Unknown {label} fields: {', '.join(sorted(unknown))}")


def number(value, label, minimum, maximum, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CompositionError(f"{label} must be numeric")
    # Range-check Python integers before conversion inside isfinite (huge ints can overflow).
    if not minimum <= value <= maximum or not math.isfinite(value):
        raise CompositionError(f"{label} must be between {minimum} and {maximum}")
    if integer and not isinstance(value, int):
        raise CompositionError(f"{label} must be an integer")
    return value


def local_path(value, base, label, existing=False):
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise CompositionError(f"{label} must be a nonempty local path")
    if "://" in value:
        raise CompositionError(f"{label} accepts local files only")
    path = Path(value).expanduser()
    path = (base / path).resolve() if not path.is_absolute() else path.resolve()
    if existing and not path.is_file():
        raise CompositionError(f"{label} does not exist: {path}")
    return path


def load_plan(manifest):
    with manifest.open("r", encoding="utf-8-sig") as handle:
        raw = json.load(handle)
    object_keys(raw, {"schema_version", "output", "width", "height", "fps", "clips",
                      "soundtrack", "soundtrack_volume"}, "manifest")
    if type(raw.get("schema_version")) is not int or raw["schema_version"] != 1:
        raise CompositionError("schema_version must be integer 1")
    width = number(raw.get("width", 1280), "width", 16, 7680, True)
    height = number(raw.get("height", 720), "height", 16, 7680, True)
    fps = number(raw.get("fps", 25), "fps", 1, 60, True)
    if width % 2 or height % 2:
        raise CompositionError("width and height must be even")
    output = local_path(raw.get("output"), manifest.parent, "output")
    if output.suffix.lower() != ".mp4":
        raise CompositionError("output must end in .mp4")
    items = raw.get("clips")
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise CompositionError("clips must contain 1 to 100 entries")
    clips, warnings = [], []
    frame_cursor = 0
    for i, item in enumerate(items):
        label = f"clips[{i}]"
        object_keys(item, {"path", "start", "duration", "caption", "visual_type", "source_note"}, label)
        path = local_path(item.get("path"), manifest.parent, label + ".path", True)
        start = number(item.get("start", 0), label + ".start", 0, 1e9)
        duration = number(item.get("duration"), label + ".duration", 1e-9, 3600)
        frames = max(1, int(math.floor(duration * fps + 0.5)))
        caption = item.get("caption", "")
        note = item.get("source_note", "")
        if not isinstance(caption, str) or not isinstance(note, str):
            raise CompositionError(label + ".caption and .source_note must be strings")
        caption = caption.replace("\r\n", "\n").replace("\r", "\n").strip()
        if "\n\n" in caption or "\x00" in caption:
            raise CompositionError(label + ".caption contains an empty line or NUL")
        visual_type = item.get("visual_type", "unspecified")
        if visual_type not in ("live", "data", "illustration", "ai-illustration", "unspecified"):
            raise CompositionError(label + ".visual_type is unsupported")
        if visual_type == "ai-illustration" and not ("AI" in caption or "示意" in caption):
            warnings.append(f"Clip {i + 1}: confirm a visible AI illustration label before publishing")
        clips.append({"path": str(path), "start": start, "requested_duration": duration,
                      "frames": frames, "duration": frames / fps, "start_frame": frame_cursor,
                      "caption": caption, "visual_type": visual_type, "source_note": note})
        frame_cursor += frames
    soundtrack = raw.get("soundtrack")
    if soundtrack is not None:
        soundtrack = str(local_path(soundtrack, manifest.parent, "soundtrack", True))
    volume = number(raw.get("soundtrack_volume", 0.25), "soundtrack_volume", 0, 1)
    report = output.with_suffix(".report.json")
    srt = output.with_suffix(".srt") if any(x["caption"] for x in clips) else None
    targets = [output, report] + ([srt] if srt else [])
    sources = {manifest.resolve()} | {Path(x["path"]) for x in clips}
    if soundtrack:
        sources.add(Path(soundtrack))
    for target in targets:
        if target in sources:
            raise CompositionError(f"Output would replace an input file: {target}")
        if os.path.lexists(target):
            raise CompositionError(f"Refusing to overwrite existing path: {target}")
    return {"schema_version": 1, "width": width, "height": height, "fps": fps,
            "total_frames": frame_cursor, "duration_seconds": frame_cursor / fps,
            "clips": clips, "soundtrack": soundtrack, "soundtrack_volume": volume,
            "output": str(output), "report": str(report), "srt": str(srt) if srt else None,
            "audio_mode": "replacement-soundtrack" if soundtrack else "silence",
            "original_audio_preserved": False, "subtitles_burned_in": False,
            "warnings": warnings}


def resolve_ffmpeg(requested, dry_run=False):
    result = shutil.which(requested)
    if result:
        return str(Path(result).resolve())
    path = Path(requested).expanduser()
    if path.is_file():
        return str(path.resolve())
    if dry_run:
        return requested
    raise CompositionError("FFmpeg not found; provide --ffmpeg /path/to/ffmpeg")


def run(command, capture=False):
    result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, shell=False)
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace")[-5000:]
        raise CompositionError(f"FFmpeg failed ({result.returncode}):\n{detail}")
    return result.stdout if capture else None


def check_capabilities(ffmpeg, plan):
    filters = run([ffmpeg, "-hide_banner", "-filters"], True).decode("utf-8", "replace")
    encoders = run([ffmpeg, "-hide_banner", "-encoders"], True).decode("utf-8", "replace")
    filter_names = {parts[1] for line in filters.splitlines() if len(parts := line.split()) >= 2}
    encoder_names = {parts[1] for line in encoders.splitlines() if len(parts := line.split()) >= 2}
    required = {"scale", "pad", "setsar", "setpts", "tpad", "trim", "fps", "format", "concat", "volume"}
    if not plan["soundtrack"]:
        required.add("anullsrc")
    missing = sorted(required - filter_names) + sorted({"libx264", "aac"} - encoder_names)
    if missing:
        raise CompositionError("FFmpeg build lacks required filters/encoders: " + ", ".join(missing))


def build_command(ffmpeg, plan, output):
    command = [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-n"]
    for clip in plan["clips"]:
        command.extend(["-ss", str(clip["start"]), "-i", clip["path"]])
    if plan["soundtrack"]:
        command.extend(["-stream_loop", "-1", "-i", plan["soundtrack"]])
    else:
        command.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"])
    graph = []
    width, height, fps = plan["width"], plan["height"], plan["fps"]
    for i, clip in enumerate(plan["clips"]):
        graph.append(
            f"[{i}:v:0]fps={fps},scale=iw*sar:ih,setsar=1,"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,"
            f"tpad=stop_mode=clone:stop_duration={clip['duration']},"
            f"trim=end_frame={clip['frames']},setpts=N/({fps}*TB),format=yuv420p[v{i}]"
        )
    graph.append("".join(f"[v{i}]" for i in range(len(plan["clips"]))) +
                 f"concat=n={len(plan['clips'])}:v=1:a=0[vout]")
    volume = plan["soundtrack_volume"] if plan["soundtrack"] else 1
    command.extend(["-filter_complex_threads", "1", "-filter_complex", ";".join(graph),
                    "-map", "[vout]", "-map", f"{len(plan['clips'])}:a:0", "-af", f"volume={volume}",
                    "-t", str(plan["duration_seconds"]), "-r", str(fps),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
                    "-map_metadata", "-1", "-movflags", "+faststart", str(output)])
    return command


def srt_timestamp(frame, fps):
    milliseconds = int(math.floor(frame * 1000 / fps + 0.5))
    hours, remainder = divmod(milliseconds, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def render_srt(plan):
    entries = []
    for clip in plan["clips"]:
        if clip["caption"]:
            begin = srt_timestamp(clip["start_frame"], plan["fps"])
            end = srt_timestamp(clip["start_frame"] + clip["frames"], plan["fps"])
            entries.append(f"{len(entries) + 1}\n{begin} --> {end}\n{clip['caption']}\n")
    return "\n".join(entries)


def publish_new(source, destination, created):
    # Exclusive creation prevents a race from silently overwriting a new user file.
    with Path(destination).open("xb") as target:
        created.append(Path(destination))
        with Path(source).open("rb") as handle:
            shutil.copyfileobj(handle, target)


def compose(plan, ffmpeg):
    check_capabilities(ffmpeg, plan)
    # Check a decodable frame after each seek, including clips without audio.
    for i, clip in enumerate(plan["clips"]):
        frame = run([ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
                     "-ss", str(clip["start"]), "-i", clip["path"], "-map", "0:v:0",
                     "-frames:v", "1", "-vf", "scale=2:2", "-pix_fmt", "rgb24",
                     "-f", "rawvideo", "pipe:1"], True)
        if len(frame) != 12:
            raise CompositionError(f"Clip {i + 1} has no decodable frame at its start time")
    output = Path(plan["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        with tempfile.TemporaryDirectory(prefix=".synbio-video-", dir=output.parent) as directory:
            temporary = Path(directory)
            movie = temporary / "composed.mp4"
            run(build_command(ffmpeg, plan, movie))
            if not movie.is_file() or movie.stat().st_size == 0:
                raise CompositionError("FFmpeg did not produce a nonempty MP4")
            report_data = dict(plan, status="composed-awaiting-human-playback-review", ffmpeg=ffmpeg)
            report = temporary / "report.json"
            report.write_text(json.dumps(report_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            publish_new(movie, output, created)
            if plan["srt"]:
                srt = temporary / "subtitles.srt"
                srt.write_text(render_srt(plan), encoding="utf-8")
                publish_new(srt, plan["srt"], created)
            publish_new(report, plan["report"], created)
    except BaseException:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="UTF-8 JSON manifest; relative paths use its directory")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="FFmpeg executable name or full path")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and print a plan without writing files")
    args = parser.parse_args()
    try:
        plan = load_plan(args.manifest.resolve())
        ffmpeg = resolve_ffmpeg(args.ffmpeg, args.dry_run)
        if args.dry_run:
            result = dict(plan, status="dry-run-no-files-written", command_array=build_command(ffmpeg, plan, plan["output"]))
        else:
            compose(plan, ffmpeg)
            result = {"status": "composed-awaiting-human-playback-review", "output": plan["output"],
                      "report": plan["report"], "srt": plan["srt"], "duration_seconds": plan["duration_seconds"],
                      "audio_mode": plan["audio_mode"], "warnings": plan["warnings"]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (CompositionError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    # JSON is UTF-8 even when a Windows console has a legacy code page.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
