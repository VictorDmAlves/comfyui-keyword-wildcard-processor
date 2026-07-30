from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterable


PLACEHOLDER = "Select Wildcard"
KEYWORD_PATTERN = re.compile(r"<keyword>", re.IGNORECASE)
MAX_SEED = 0xFFFFFFFFFFFFFFFF


def _candidate_custom_nodes_dirs() -> list[Path]:
    """Return likely ComfyUI custom_nodes directories without assuming an install path."""
    candidates: list[Path] = []

    # This package is normally installed directly inside ComfyUI/custom_nodes.
    candidates.append(Path(__file__).resolve().parent.parent)

    try:
        import folder_paths  # type: ignore

        base_path = getattr(folder_paths, "base_path", None)
        if base_path:
            candidates.append(Path(base_path).resolve() / "custom_nodes")

        folder_paths_file = getattr(folder_paths, "__file__", None)
        if folder_paths_file:
            candidates.append(Path(folder_paths_file).resolve().parent / "custom_nodes")
    except Exception:
        pass

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            key = str(candidate.resolve()).casefold()
        except OSError:
            key = str(candidate).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _iter_impact_roots() -> Iterable[Path]:
    """Find the installed Impact Pack by its files, not by a fixed folder name."""
    seen: set[str] = set()

    for custom_nodes_dir in _candidate_custom_nodes_dirs():
        if not custom_nodes_dir.is_dir():
            continue

        try:
            children = list(custom_nodes_dir.iterdir())
        except OSError:
            continue

        for child in children:
            if not child.is_dir():
                continue

            impact_module = child / "modules" / "impact" / "wildcards.py"
            if not impact_module.is_file():
                continue

            try:
                key = str(child.resolve()).casefold()
            except OSError:
                key = str(child).casefold()
            if key in seen:
                continue

            seen.add(key)
            yield child


def _load_impact_wildcards() -> ModuleType:
    """Import Impact Pack's wildcard engine, with a path-based fallback."""
    try:
        return importlib.import_module("impact.wildcards")
    except ModuleNotFoundError:
        pass

    for impact_root in _iter_impact_roots():
        modules_dir = impact_root / "modules"
        modules_dir_text = str(modules_dir)
        if modules_dir_text not in sys.path:
            sys.path.insert(0, modules_dir_text)
        try:
            return importlib.import_module("impact.wildcards")
        except ModuleNotFoundError:
            continue

    raise RuntimeError(
        "ComfyUI-Impact-Pack was not found. Install or enable the Impact Pack "
        "before using the Keyword Wildcard Processor."
    )


def _configured_custom_wildcards_dir() -> Path | None:
    """Read Impact Pack's configured custom_wildcards directory when available."""
    try:
        impact_config = importlib.import_module("impact.config")
        configured = impact_config.get_config().get("custom_wildcards")
        if configured:
            path = Path(configured).expanduser()
            if path.is_dir():
                return path.resolve()
    except Exception:
        pass
    return None


def _custom_wildcard_dirs() -> list[Path]:
    """Return all valid Impact Pack custom_wildcards directories."""
    directories: list[Path] = []

    configured = _configured_custom_wildcards_dir()
    if configured is not None:
        directories.append(configured)

    for impact_root in _iter_impact_roots():
        candidate = impact_root / "custom_wildcards"
        if candidate.is_dir():
            directories.append(candidate.resolve())

    unique: list[Path] = []
    seen: set[str] = set()
    for directory in directories:
        key = str(directory).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(directory)
    return unique


def _normalize_wildcard_name(relative_path: Path) -> str:
    """Match Impact Pack's path normalization for TXT wildcard names."""
    without_suffix = relative_path.with_suffix("")
    normalized = without_suffix.as_posix().replace(" ", "-").lower()
    return f"__{normalized}__"


def list_custom_wildcards() -> list[str]:
    """List TXT wildcards from Impact Pack's custom_wildcards directory."""
    tokens: set[str] = set()

    for wildcard_dir in _custom_wildcard_dirs():
        try:
            files = wildcard_dir.rglob("*.txt")
            for file_path in files:
                if file_path.is_file():
                    relative = file_path.relative_to(wildcard_dir)
                    tokens.add(_normalize_wildcard_name(relative))
        except (OSError, ValueError):
            continue

    return [PLACEHOLDER, *sorted(tokens, key=str.casefold)]


class KeywordWildcardProcessor:
    """Impact-compatible wildcard processor with a replaceable <keyword> slot."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": False,
                        "tooltip": (
                            "Free-form prompt. May contain Wildcards in the format __name__. "
                            "It also works as a standard prompt, without Wildcards."
                        ),
                    },
                ),
                "processed_text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": False,
                        "tooltip": "Final result of the last execution.",
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": MAX_SEED,
                        "control_after_generate": True,
                        "tooltip": "Seed used by the same Wildcard engine as the Impact Pack.",
                    },
                ),
                "wildcard_selector": (
                    list_custom_wildcards(),
                    {
                        "default": PLACEHOLDER,
                        "tooltip": (
                            "Select a TXT file of custom_wildcards and insert it "
                            "automatically __file_name__ in the prompt field."
                        ),
                    },
                ),
                "keyword": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "dynamicPrompts": False,
                        "tooltip": (
                            "When filled, replaces all occurrences of "
                            "<keyword> after wildcard expansion. Empty = no substitution."
                        ),
                    },
                ),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("processed text",)
    FUNCTION = "process"
    CATEGORY = "Wildcards"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "It processes prompts using the same engine as the ImpactWildcardProcessor and then "
        "replaces <keyword> with the text provided in the keyword field."
    )

    def process(
        self,
        prompt: str,
        processed_text: str,
        seed: int,
        wildcard_selector: str,
        keyword: str,
    ):
        del processed_text, wildcard_selector

        impact_wildcards = _load_impact_wildcards()
        result = impact_wildcards.process(text=prompt, seed=seed)

        clean_keyword = keyword.strip()
        if clean_keyword:
            result = KEYWORD_PATTERN.sub(lambda _match: clean_keyword, result)

        return {
            "ui": {"text": [result]},
            "result": (result,),
        }
