"""Game project directory scanner — extracts metadata from common game file structures."""
import os
import re
from pathlib import Path

_MAIN_PRIORITY = [
    "index.html", "index.htm", "game.html", "main.html",
    "main.py", "game.py", "app.py",
    "main.js", "game.js", "index.js",
    "main.cpp", "main.c", "main.lua", "main.gd",
]

_SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', '.DS_Store'}


def scan_game_path(path: str) -> dict:
    game_path = Path(path)
    if not game_path.exists():
        raise ValueError(f"Path not found: {path}")
    if not game_path.is_dir():
        raise ValueError(f"Not a directory: {path}")

    result = {
        "path": str(game_path.resolve()),
        "name": game_path.name,
        "description": "",
        "main_file": None,
        "all_files": [],
        "file_types": [],
        "size_bytes": 0,
    }

    type_counts: dict[str, int] = {}
    for root, dirs, files in os.walk(game_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith('.')]
        for fname in files:
            fpath = Path(root) / fname
            try:
                size = fpath.stat().st_size
                result["size_bytes"] += size
                rel = str(fpath.relative_to(game_path))
                result["all_files"].append(rel)
                ext = fpath.suffix.lower()
                if ext:
                    type_counts[ext] = type_counts.get(ext, 0) + 1
            except OSError:
                pass

    result["file_types"] = sorted(type_counts.keys())

    for candidate in _MAIN_PRIORITY:
        if (game_path / candidate).exists():
            result["main_file"] = candidate
            break

    _extract_metadata(game_path, result)
    return result


def _extract_metadata(game_path: Path, result: dict) -> None:
    for readme in ("README.md", "readme.md", "README.txt", "readme.txt"):
        rpath = game_path / readme
        if not rpath.exists():
            continue
        try:
            content = rpath.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"^#+\s*(.+)", content, re.MULTILINE)
            if m:
                result["name"] = m.group(1).strip()
            paras = [p.strip() for p in re.split(r"\n{2,}", content) if p.strip()]
            for para in paras[1:3]:
                cleaned = re.sub(r"[#*`\[\]()]", "", para).strip()
                if len(cleaned) > 30:
                    result["description"] = cleaned[:600]
                    break
            return
        except Exception:
            pass

    index = game_path / "index.html"
    if index.exists():
        try:
            content = index.read_text(encoding="utf-8", errors="ignore")[:8000]
            m = re.search(r"<title[^>]*>([^<]+)</title>", content, re.IGNORECASE)
            if m:
                result["name"] = m.group(1).strip()

            for pat in (
                r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
                r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
            ):
                m = re.search(pat, content, re.IGNORECASE)
                if m:
                    result["description"] = m.group(1).strip()
                    return

            for c in re.findall(r"<!--(.+?)-->", content, re.DOTALL):
                c = c.strip()
                if len(c) > 40 and not c.startswith("[") and "<" not in c:
                    result["description"] = c[:400].strip()
                    return
        except Exception:
            pass
        return

    main_py = game_path / "main.py"
    if main_py.exists():
        try:
            content = main_py.read_text(encoding="utf-8", errors="ignore")[:3000]
            m = re.search(r'"""(.+?)"""', content, re.DOTALL)
            if m:
                doc = m.group(1).strip()
                lines = [ln.strip() for ln in doc.split("\n") if ln.strip()]
                if lines:
                    result["name"] = lines[0]
                if len(lines) > 1:
                    result["description"] = " ".join(lines[1:])[:400]
        except Exception:
            pass
