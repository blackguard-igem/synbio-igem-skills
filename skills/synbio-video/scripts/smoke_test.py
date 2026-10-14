#!/usr/bin/env python3
"""Offline media smoke test; creates files only in a NEW --workdir.

Requires the same Python/FFmpeg as compose_video.py. No test framework needed.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
from compose_video import resolve_ffmpeg


def call(command, expected=0):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    if result.returncode != expected:
        raise RuntimeError(result.stderr.decode("utf-8", "replace"))
    return result.stdout


def write_json(path, data):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", required=True, type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    ffmpeg = resolve_ffmpeg(args.ffmpeg)
    directory = args.workdir.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    script = Path(__file__).with_name("compose_video.py")
    base = [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-n"]
    # Two dimensions, two frame rates, one clip without audio and one with audio.
    call(base + ["-f", "lavfi", "-i", "color=c=red:s=320x240:r=24:d=0.6",
                 "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(directory / "red silent.mp4")])
    call(base + ["-f", "lavfi", "-i", "color=c=blue:s=180x320:r=30:d=0.8",
                 "-f", "lavfi", "-i", "sine=frequency=440:duration=0.8", "-shortest",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(directory / "blue-audio.mp4")])
    call(base + ["-f", "lavfi", "-i", "sine=frequency=220:duration=0.3", str(directory / "music.wav")])
    data = {"schema_version": 1, "output": "results/silent.mp4", "width": 320, "height": 180, "fps": 25,
            "clips": [{"path": "red silent.mp4", "duration": 0.91, "caption": "教学示意"},
                      {"path": "blue-audio.mp4", "duration": 1.08, "caption": "AI 生成示意，非实验结果",
                       "visual_type": "ai-illustration"}]}
    manifest = directory / "manifest.json"
    write_json(manifest, data)
    command = [sys.executable, str(script), str(manifest), "--ffmpeg", ffmpeg]
    before = {str(path.relative_to(directory)) for path in directory.rglob("*")}
    preview = json.loads(call(command + ["--dry-run"]))
    assert before == {str(path.relative_to(directory)) for path in directory.rglob("*")}, "dry-run wrote files"
    assert abs(preview["duration_seconds"] - 2.0) < 1e-6
    call(command)
    output = directory / "results/silent.mp4"
    # The expected 50 RGB frames confirm both normalized geometry and duration.
    pixels = call([ffmpeg, "-v", "error", "-i", str(output), "-map", "0:v:0", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"])
    frame_size = 320 * 180 * 3
    assert len(pixels) == 50 * frame_size, "Unexpected frame count or dimensions"
    def center(frame):
        offset = frame * frame_size + (90 * 320 + 160) * 3
        return pixels[offset:offset + 3]
    assert center(5)[0] > 200 and center(40)[2] > 200, "Clip order/colors incorrect"
    silence = call([ffmpeg, "-v", "error", "-i", str(output), "-map", "0:a:0", "-f", "s16le", "pipe:1"])
    assert silence and not any(silence), "Original audio leaked into silent output"
    saved = output.read_bytes()
    call(command, expected=2)
    assert output.read_bytes() == saved, "Existing output was modified"
    srt = output.with_suffix(".srt").read_text(encoding="utf-8")
    assert "00:00:00,920 --> 00:00:02,000" in srt, "Subtitle quantization mismatch"
    music_data = dict(data, output="results/music.mp4", soundtrack="music.wav", soundtrack_volume=0.3)
    music_manifest = directory / "music-manifest.json"
    write_json(music_manifest, music_data)
    call([sys.executable, str(script), str(music_manifest), "--ffmpeg", ffmpeg])
    music_audio = call([ffmpeg, "-v", "error", "-i", str(directory / "results/music.mp4"),
                       "-map", "0:a:0", "-f", "s16le", "pipe:1"])
    assert any(music_audio), "Replacement music is silent"
    bad_manifest = directory / "bad-manifest.json"
    write_json(bad_manifest, dict(data, output="results/bad.mp4", unsupported_option=True))
    call([sys.executable, str(script), str(bad_manifest), "--ffmpeg", ffmpeg], expected=2)
    assert not (directory / "results/bad.mp4").exists()
    single_manifest = directory / "single-manifest.json"
    write_json(single_manifest, dict(data, output="results/single.mp4", clips=[
        {"path": "blue-audio.mp4", "start": 0.2, "duration": 0.2}]))
    call([sys.executable, str(script), str(single_manifest), "--ffmpeg", ffmpeg])
    assert not (directory / "results/single.srt").exists(), "Empty subtitles unexpectedly created"
    single_frames = call([ffmpeg, "-v", "error", "-i", str(directory / "results/single.mp4"),
                          "-map", "0:v:0", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"])
    assert len(single_frames) == 5 * frame_size, "Single clip trim produced incorrect length"
    empty_manifest = directory / "empty-seek.json"
    write_json(empty_manifest, dict(data, output="results/empty.mp4", clips=[
        {"path": "blue-audio.mp4", "start": 500, "duration": 0.2}]))
    call([sys.executable, str(script), str(empty_manifest), "--ffmpeg", ffmpeg], expected=2)
    assert not (directory / "results/empty.mp4").exists(), "Empty seek published output"
    huge_manifest = directory / "huge-number.json"
    write_json(huge_manifest, dict(data, output="results/huge.mp4", width=10 ** 400))
    huge_result = subprocess.run([sys.executable, str(script), str(huge_manifest), "--ffmpeg", ffmpeg],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    assert huge_result.returncode == 2 and b"Traceback" not in huge_result.stderr
    assert not (directory / "results/huge.mp4").exists(), "Invalid size published output"
    summary = {"status": "passed", "ffmpeg": ffmpeg,
               "checks": ["dry-run does not write", "mixed source geometry and frame rates", "no-audio source",
                          "short clips frozen to target length", "50 frames at 320x180", "correct clip order",
                          "original audio discarded", "SRT frame-aligned timing", "no-overwrite",
                          "replacement soundtrack", "unknown manifest fields rejected",
                          "single-clip seek/trim", "no empty SRT", "out-of-range seek rejected",
                          "huge numeric input rejected without traceback"],
               "human_visual_review": "not performed by this test"}
    write_json(directory / "test-results.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main()
