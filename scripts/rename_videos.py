#!/usr/bin/env python3
import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

if sys.platform == "win32":
    import winreg

DEFAULT_DURATION_PATTERN = r"(?P<minutes>\d+)m(?P<seconds>\d+)s"
DEFAULT_OPENAI_MODEL = "gpt-5.4-nano"
QUALITY_OPENAI_MODEL = "gpt-5.4-mini"
INVALID_FILENAME_CHARS = r'<>:"/\|?*'
HANDLE_PATTERN = r"[a-z0-9._-]{2,40}"
SITE_PREFIX_RE = re.compile(
    r"(?:"
    r"only\s*fans|fans\s*ly|fansly|many\s*vids|manyvids|"
    r"chaturbate|pornhub|loyal\s*fans|loyalfans|fan\s*centro|fancentro|"
    r"strip\s*chat|stripchat"
    r")\s*(?:[.,]?\s*(?:com|ly|net|io|me|tv|cc))?\s*[/\\|:._@\-\s]*(?P<handle>"
    + HANDLE_PATTERN
    + r")",
    re.IGNORECASE,
)
GENERIC_DOMAIN_RE = re.compile(
    r"(?:[a-z0-9][a-z0-9.-]*\.)+(?:com|ly|net|io|me|tv|cc)\s*[/\\|:._@\-\s]*(?P<handle>"
    + HANDLE_PATTERN
    + r")",
    re.IGNORECASE,
)
OCR_JUNK_TOKENS = {
    "com",
    "www",
    "http",
    "https",
    "onlyfans",
    "onlyfanscom",
    "fansly",
    "fanslycom",
    "manyvids",
    "manyvidscom",
    "chaturbate",
    "chaturbatecom",
    "pornhub",
    "pornhubcom",
    "loyalfans",
    "loyalfanscom",
    "fancentro",
    "fancentrocom",
    "stripchat",
    "stripchatcom",
}


def safe_name_part(value: str) -> str:
    cleaned = value.strip()
    for char in INVALID_FILENAME_CHARS:
        cleaned = cleaned.replace(char, "_")
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("_") or "unknown"


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"{name} was not found on PATH.")
    return path


def run_capture(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise RuntimeError(message)
    return result.stdout.strip()


def get_media_duration(file_path: Path) -> tuple[int, int, int]:
    ffprobe = require_tool("ffprobe")
    output = run_capture(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(file_path),
        ]
    )
    total_seconds = round(float(output))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return minutes, seconds, total_seconds


def get_video_orientation(file_path: Path) -> str:
    ffprobe = require_tool("ffprobe")
    output = run_capture(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=s=x:p=0",
            str(file_path),
        ]
    )
    width_text, height_text = output.split("x", 1)
    width = int(width_text)
    height = int(height_text)
    return "v" if height > width else "h"


def get_duration_from_name(
    file_path: Path, pattern: re.Pattern[str]
) -> tuple[int, int, int] | None:
    match = pattern.search(file_path.stem)
    if not match:
        return None
    if "minutes" not in match.groupdict() or "seconds" not in match.groupdict():
        raise RuntimeError(
            "Duration pattern must include named groups: minutes and seconds."
        )
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    return minutes, seconds, (minutes * 60) + seconds


def extract_scene_frames(
    file_path: Path, total_seconds: int, temp_dir: Path
) -> list[Path]:
    ffmpeg = require_tool("ffmpeg")
    positions = sorted(
        set(max(0, int(total_seconds * fraction)) for fraction in (0.25, 0.50, 0.75))
    )
    frames = []
    for index, position in enumerate(positions):
        frame_path = temp_dir / f"frame_{index}.jpg"
        result = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(position),
                "-i",
                str(file_path),
                "-frames:v",
                "1",
                "-vf",
                "scale=768:-2",
                "-q:v",
                "3",
                str(frame_path),
                "-y",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not frame_path.exists():
            message = (
                result.stderr.strip()
                or f"Could not extract scene frame at {position}s."
            )
            raise RuntimeError(message)
        frames.append(frame_path)
    return frames


def get_openai_api_key() -> str | None:
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key

    if sys.platform != "win32":
        return None

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as environment_key:
            value, _ = winreg.QueryValueEx(environment_key, "OPENAI_API_KEY")
            return value
    except OSError:
        return None


def openai_scene_title(file_path: Path, total_seconds: int, model: str) -> str:
    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    with tempfile.TemporaryDirectory() as temp_name:
        frames = extract_scene_frames(file_path, total_seconds, Path(temp_name))
        content = [
            {
                "type": "input_text",
                "text": (
                    "Create a short filename-safe scene label.\n"
                    "Format: describe the explicit scene in a single line.\n"
                    "use action verbs to differentiate similar scenes.\n"
                    "example: busty girl fingering herself on the bed\n"
                    "dont do boring titles like man fondling woman on bed\n"
                    "dont use the proper terms like oral sex\n"
                    "if there is sex with a man then add bg to the title, if its lesbian sex add gg\n"
                    "Use 3 to 8 words total.\n"
                    "Do not include names, dates, punctuation, quotes, or extra explanation.\n"
                    "case does not matter. just return the most descriptive words that differentiate this scene from others in the same video."
                ),
            }
        ]
        for frame in frames:
            encoded = base64.b64encode(frame.read_bytes()).decode("ascii")
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{encoded}",
                    "detail": "low",
                }
            )

        payload = {
            "model": model,
            "input": [{"role": "user", "content": content}],
            "max_output_tokens": 40,
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI request failed: {exc.code} {body}") from exc

    raw_title = response_data.get("output_text", "")
    if not raw_title:
        parts = []
        for item in response_data.get("output", []):
            for part in item.get("content", []):
                text = part.get("text")
                if text:
                    parts.append(text)
        raw_title = " ".join(parts)

    cleaned = re.sub(r"[^a-z0-9]+", " ", raw_title.lower()).strip()
    words = [word for word in cleaned.split() if word]
    return " ".join(words[:8]) or "untitled scene"


def extract_corner_frames(
    file_path: Path, total_seconds: int, temp_dir: Path, position: str
) -> list[Path]:
    ffmpeg = require_tool("ffmpeg")
    positions = sorted(
        set(max(0, int(total_seconds * fraction)) for fraction in (0.20, 0.50, 0.80))
    )
    crop_filters = {
        "bottom-right": "crop=iw*0.50:ih*0.28:iw-iw*0.50:ih-ih*0.28,scale=1024:-2",
        "bottom-left": "crop=iw*0.50:ih*0.28:0:ih-ih*0.28,scale=1024:-2",
        "bottom": "crop=iw:ih*0.28:0:ih-ih*0.28,scale=1280:-2",
    }
    frames = []
    for index, video_position in enumerate(positions):
        frame_path = temp_dir / f"ocr_{index}.jpg"
        result = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(video_position),
                "-i",
                str(file_path),
                "-frames:v",
                "1",
                "-vf",
                crop_filters[position],
                "-q:v",
                "2",
                str(frame_path),
                "-y",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not frame_path.exists():
            message = (
                result.stderr.strip()
                or f"Could not extract OCR crop at {video_position}s."
            )
            raise RuntimeError(message)
        frames.append(frame_path)
    return frames


def openai_corner_ocr(
    file_path: Path, total_seconds: int, model: str, position: str
) -> str:
    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    with tempfile.TemporaryDirectory() as temp_name:
        frames = extract_corner_frames(
            file_path, total_seconds, Path(temp_name), position
        )
        content = [
            {
                "type": "input_text",
                "text": (
                    "Read the visible text or watermark in these cropped video corner images.\n"
                    "Return only the clearest repeated text, username, URL, or handle.\n"
                    "If no readable text appears, return no_text.\n"
                    "Do not describe the scene. Do not add extra words."
                ),
            }
        ]
        for frame in frames:
            encoded = base64.b64encode(frame.read_bytes()).decode("ascii")
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{encoded}",
                    "detail": "low",
                }
            )

        payload = {
            "model": model,
            "input": [{"role": "user", "content": content}],
            "max_output_tokens": 40,
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI OCR request failed: {exc.code} {body}") from exc

    raw_text = response_data.get("output_text", "")
    if not raw_text:
        parts = []
        for item in response_data.get("output", []):
            for part in item.get("content", []):
                text = part.get("text")
                if text:
                    parts.append(text)
        raw_text = " ".join(parts)

    return clean_ocr_text(raw_text) or ""


def clean_ocr_text(text: str) -> str | None:
    cleaned = text.strip().lower()
    if cleaned in {"", "no_text", "none", "not_readable", "unreadable"}:
        return None
    text_without_scheme = re.sub(r"https?://", "", cleaned)
    for pattern in (SITE_PREFIX_RE, GENERIC_DOMAIN_RE):
        match = pattern.search(text_without_scheme)
        if match:
            candidate = match.group("handle")
            candidate = re.sub(r"[^a-z0-9._-]+", "", candidate).strip("_.-")
            if candidate and candidate not in OCR_JUNK_TOKENS and not candidate.isdigit():
                return candidate[:80]

    cleaned = re.sub(r"[^a-z0-9._/@-]+", "_", text_without_scheme)
    cleaned = cleaned.replace("/", "_").replace("@", "")
    parts = [
        part
        for part in re.split(r"[_\s]+", cleaned)
        if part and part not in OCR_JUNK_TOKENS
    ]
    cleaned = "_".join(parts)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_.-")
    return cleaned[:80] or None


def iter_files(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise RuntimeError(f"Path does not exist: {path}")
    pattern = "**/*" if recursive else "*"
    return sorted(p for p in path.glob(pattern) if p.is_file())


def build_base_name(
    file_path: Path,
    duration_pattern: re.Pattern[str],
    scene_title: bool,
    model: str,
) -> tuple[str, int]:
    duration = get_duration_from_name(file_path, duration_pattern)
    if duration is None:
        duration = get_media_duration(file_path)
    minutes, seconds, total_seconds = duration

    parent = file_path.parent
    grandparent = parent.parent.name if parent.parent else parent.name
    orientation = get_video_orientation(file_path)
    title_part = ""
    if scene_title:
        title_part = "_" + openai_scene_title(file_path, total_seconds, model)

    return (
        f"{safe_name_part(grandparent)}_"
        f"{minutes}m{seconds:02d}s_"
        f"{title_part.lstrip('_') + '_' if title_part else ''}"
        f"{orientation}"
    ), total_seconds


def make_collision_safe_destination(
    folder: Path, base_name: str, suffix: str, source: Path
) -> Path:
    destination = folder / f"{base_name}{suffix}"
    collision_number = 2
    orientation_match = re.search(r"_(?P<orientation>[hv])$", base_name)
    while destination.exists() and destination.resolve() != source.resolve():
        if orientation_match:
            stem = base_name[: orientation_match.start()]
            orientation = orientation_match.group("orientation")
            destination = (
                folder / f"{stem}_duplicate{collision_number}_{orientation}{suffix}"
            )
        else:
            destination = folder / f"{base_name}_duplicate{collision_number}{suffix}"
        collision_number += 1
    return destination


def rename_files(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser().resolve()
    files = iter_files(path, args.recursive)
    duration_pattern = re.compile(args.pattern, re.IGNORECASE)

    for file_path in files:
        folder = file_path.parent
        base_name, total_seconds = build_base_name(
            file_path,
            duration_pattern,
            args.scene_title,
            args.openai_model,
        )
        ocr_text = ""
        if args.ocr_corner:
            ocr_text = openai_corner_ocr(
                file_path, total_seconds, args.openai_model, args.ocr_corner_position
            )
        destination = make_collision_safe_destination(
            folder, base_name, file_path.suffix, file_path
        )

        if args.apply:
            file_path.rename(destination)
            print(f"Renamed: {file_path} -> {destination}")
        else:
            print(f"Dry run: {file_path} -> {destination}")
        if args.ocr_corner:
            print(f"OCR: {file_path} -> {ocr_text or 'no_text'}")

    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rename videos to grandparent_duration_scene_orientation."
    )
    parser.add_argument("path", help="File or folder to process.")
    parser.add_argument(
        "--pattern",
        default=DEFAULT_DURATION_PATTERN,
        help="Regex with named groups minutes and seconds.",
    )
    parser.add_argument(
        "--scene-title",
        action="store_true",
        help="Use OpenAI vision to add body attributes plus action.",
    )
    parser.add_argument(
        "--ocr-corner",
        action="store_true",
        help="Use OpenAI vision to OCR text or watermark in a bottom corner.",
    )
    parser.add_argument(
        "--ocr-corner-position",
        choices=("bottom-right", "bottom-left", "bottom"),
        default="bottom-right",
        help="Video area to crop for OCR. Default: bottom-right.",
    )
    parser.add_argument(
        "--openai-model",
        default=DEFAULT_OPENAI_MODEL,
        help=(
            f"OpenAI model for scene titles. Default: {DEFAULT_OPENAI_MODEL}. "
            f"Use {QUALITY_OPENAI_MODEL} for better titles."
        ),
    )
    parser.add_argument("--recursive", action="store_true", help="Process subfolders.")
    parser.add_argument(
        "--apply", action="store_true", help="Rename files. Without this, dry run only."
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    try:
        return rename_files(parse_args(argv))
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
