import os
import shutil
import json
import stat
from pathlib import Path


def _is_entry_line(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#")


def _template_name_from_index_line(line: str) -> str:
    return line.split(",", 1)[0].strip()


def _file_fingerprint(path: Path) -> str:
    if not path.exists():
        return "missing"
    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def _build_manifest(upstream_dir: Path, custom_dir: Path) -> dict:
    custom_templates = sorted([path.name for path in custom_dir.glob("*.textfsm")])
    custom_template_fingerprints = {
        name: _file_fingerprint(custom_dir / name) for name in custom_templates
    }
    return {
        "upstream_index": _file_fingerprint(upstream_dir / "index"),
        "custom_index": _file_fingerprint(custom_dir / "index"),
        "custom_templates": custom_templates,
        "custom_template_fingerprints": custom_template_fingerprints,
    }


def _read_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_manifest(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _merge_index(runtime_index: Path, custom_index: Path) -> None:
    if not custom_index.exists():
        return

    runtime_lines = runtime_index.read_text(encoding="utf-8").splitlines()
    custom_lines = custom_index.read_text(encoding="utf-8").splitlines()
    custom_entry_lines = [line for line in custom_lines if _is_entry_line(line)]
    custom_template_names = {_template_name_from_index_line(line) for line in custom_entry_lines}

    filtered_runtime_lines = []
    for line in runtime_lines:
        if _is_entry_line(line):
            if _template_name_from_index_line(line) in custom_template_names:
                continue
        filtered_runtime_lines.append(line)

    merged_lines = filtered_runtime_lines + custom_entry_lines
    runtime_index.write_text("\n".join(merged_lines) + "\n", encoding="utf-8")


def _on_rm_error(func, path, _exc_info):
    """Best-effort Windows handler for read-only/locked file attributes."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        # Keep original failure behavior if still not removable.
        raise


def _clear_directory(path: Path) -> None:
    """Remove directory contents without removing the directory itself."""
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return

    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child, onerror=_on_rm_error)
        else:
            try:
                os.chmod(child, stat.S_IWRITE)
            except OSError:
                pass
            child.unlink()


def _full_rebuild(upstream_dir: Path, custom_dir: Path, runtime_dir: Path) -> None:
    _clear_directory(runtime_dir)
    shutil.copytree(upstream_dir, runtime_dir, dirs_exist_ok=True)

    for custom_file in custom_dir.glob("*.textfsm"):
        shutil.copy2(custom_file, runtime_dir / custom_file.name)

    _merge_index(runtime_dir / "index", custom_dir / "index")


def _incremental_update(
    upstream_dir: Path,
    custom_dir: Path,
    runtime_dir: Path,
    old_manifest: dict,
    new_manifest: dict,
) -> None:
    old_templates = set(old_manifest.get("custom_templates", []))
    new_templates = set(new_manifest.get("custom_templates", []))

    removed_templates = old_templates - new_templates
    for template_name in removed_templates:
        upstream_template = upstream_dir / template_name
        runtime_template = runtime_dir / template_name
        if upstream_template.exists():
            shutil.copy2(upstream_template, runtime_template)
        elif runtime_template.exists():
            runtime_template.unlink()

    for template_name in sorted(new_templates):
        old_fp = old_manifest.get("custom_template_fingerprints", {}).get(template_name)
        new_fp = new_manifest.get("custom_template_fingerprints", {}).get(template_name)
        if old_fp != new_fp:
            shutil.copy2(custom_dir / template_name, runtime_dir / template_name)

    if old_manifest.get("custom_index") != new_manifest.get("custom_index") or removed_templates:
        _merge_index(runtime_dir / "index", custom_dir / "index")


def build_ntc_templates_runtime(project_root: Path | None = None) -> str:
    """
    Build runtime TextFSM templates directory by overlaying local custom templates
    on top of upstream ntc-templates.
    """
    root = project_root or Path(__file__).resolve().parent.parent
    upstream_dir = root / "dep" / "ntc-templates" / "ntc_templates" / "templates"
    custom_dir = root / "ntc-templates-custom" / "templates"
    runtime_dir = root / "ntc-templates-custom" / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = runtime_dir / ".manifest.json"
    old_manifest = _read_manifest(manifest_path)
    new_manifest = _build_manifest(upstream_dir, custom_dir)

    runtime_index = runtime_dir / "index"
    runtime_exists = runtime_index.exists()
    upstream_changed = old_manifest.get("upstream_index") != new_manifest.get("upstream_index")

    if not runtime_exists or upstream_changed:
        _full_rebuild(upstream_dir, custom_dir, runtime_dir)
    elif old_manifest != new_manifest:
        _incremental_update(upstream_dir, custom_dir, runtime_dir, old_manifest, new_manifest)

    _write_manifest(manifest_path, new_manifest)

    os.environ["NTC_TEMPLATES_DIR"] = str(runtime_dir.resolve())
    return os.environ["NTC_TEMPLATES_DIR"]
