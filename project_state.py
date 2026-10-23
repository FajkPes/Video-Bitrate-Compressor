"""Portable, atomic project checkpoints (no Tk dependency)."""
import hashlib
import json
import os
import tempfile
from pathlib import Path


def atomic_json(path, data):
    path = Path(path)
    descriptor, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, default=str, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def fingerprint(path):
    try:
        stat = Path(path).stat()
        return [stat.st_size, stat.st_mtime_ns]
    except (OSError, TypeError):
        return None


def settings_key(settings):
    settings = {k: v for k, v in settings.items()
                if k not in ("lang", "in", "recurse", "ignore", "overwrite", "keep_partial")}
    return hashlib.sha256(json.dumps(settings, sort_keys=True, default=str).encode()).hexdigest()


def is_complete(info, key):
    return (info.get("job_state") == "done" and info.get("job_key") == key
            and bool(info.get("dst")) and info.get("source_stamp") is not None
            and info.get("output_stamp") is not None
            and fingerprint(info["path"]) == info["source_stamp"]
            and fingerprint(info["dst"]) == info["output_stamp"])


def read_project(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != "vbc-project" or data.get("version") != 1:
        raise ValueError("Neplatný nebo nepodporovaný projekt / Invalid project")
    if not isinstance(data.get("settings"), dict) or not isinstance(data.get("files"), list):
        raise ValueError("Projekt neobsahuje nastavení a seznam souborů / Missing project data")
    for item in data["files"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item.get("rel"):
            raise ValueError("Neplatná položka projektu / Invalid project item")
        if not Path(item["path"]).is_absolute():
            raise ValueError("Projekt vyžaduje absolutní cesty / Absolute paths required")
        rel = Path(item["rel"]) if isinstance(item["rel"], str) else None
        if rel is None or rel.is_absolute() or rel.drive or ".." in rel.parts:
            raise ValueError("Neplatná relativní cesta v projektu / Invalid relative project path")
        if item.get("dst") and (not isinstance(item["dst"], str) or not Path(item["dst"]).is_absolute()):
            raise ValueError("Neplatná cesta výstupu / Invalid output path")
    return data
