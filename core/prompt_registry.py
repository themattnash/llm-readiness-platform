from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import difflib


PROMPTS_DIR = Path("prompts")
PROMPT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{2,63}$")  # 3-64 chars, safe for paths


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_prompt_id(prompt_id: str) -> None:
    if not PROMPT_ID_RE.match(prompt_id):
        raise ValueError(
            "Invalid prompt_id. Use 3–64 chars: lowercase letters, numbers, '_' or '-'. "
            "Must start with a letter/number. Example: checkout_refusal_v1"
        )


def version_filename(version: int) -> str:
    return f"v{version:04d}.txt"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@dataclass(frozen=True)
class PromptVersion:
    version: int
    text_path: Path
    created_at: str
    note: Optional[str] = None


class PromptRegistry:
    """
    Prompt source control.

    Stores prompt versions as plain text files under:
      prompts/<prompt_id>/v0001.txt, v0002.txt, ...

    And a small meta.json index for timestamps and notes.
    """

    def __init__(self, root: Path = PROMPTS_DIR):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _prompt_dir(self, prompt_id: str) -> Path:
        validate_prompt_id(prompt_id)
        return self.root / prompt_id

    def _meta_path(self, prompt_id: str) -> Path:
        return self._prompt_dir(prompt_id) / "meta.json"

    def _load_meta(self, prompt_id: str) -> Dict:
        meta_path = self._meta_path(prompt_id)
        if not meta_path.exists():
            return {"prompt_id": prompt_id, "versions": []}
        return json.loads(meta_path.read_text(encoding="utf-8"))

    def _save_meta(self, prompt_id: str, meta: Dict) -> None:
        meta_path = self._meta_path(prompt_id)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(meta, indent=2, sort_keys=False), encoding="utf-8")

    def list_prompts(self) -> List[str]:
        if not self.root.exists():
            return []
        return sorted([p.name for p in self.root.iterdir() if p.is_dir()])

    def list_versions(self, prompt_id: str) -> List[PromptVersion]:
        meta = self._load_meta(prompt_id)
        out: List[PromptVersion] = []
        for v in meta.get("versions", []):
            version = int(v["version"])
            out.append(
                PromptVersion(
                    version=version,
                    text_path=self._prompt_dir(prompt_id) / version_filename(version),
                    created_at=v.get("created_at", ""),
                    note=v.get("note"),
                )
            )
        return out

    def latest_version(self, prompt_id: str) -> Optional[int]:
        versions = self.list_versions(prompt_id)
        return versions[-1].version if versions else None

    def get(self, prompt_id: str, version: Optional[int] = None) -> Tuple[int, str]:
        if version is None:
            version = self.latest_version(prompt_id)
            if version is None:
                raise FileNotFoundError(f"No versions found for prompt_id={prompt_id}")

        path = self._prompt_dir(prompt_id) / version_filename(version)
        if not path.exists():
            raise FileNotFoundError(f"Missing prompt file: {path}")
        return version, read_text(path)

    def add(self, prompt_id: str, text: str, note: Optional[str] = None) -> int:
        prompt_dir = self._prompt_dir(prompt_id)
        prompt_dir.mkdir(parents=True, exist_ok=True)

        meta = self._load_meta(prompt_id)
        versions = meta.get("versions", [])
        next_version = (int(versions[-1]["version"]) + 1) if versions else 1

        text_path = prompt_dir / version_filename(next_version)
        write_text(text_path, text.strip() + "\n")

        versions.append(
            {
                "version": next_version,
                "created_at": utc_now_iso(),
                "note": note,
            }
        )
        meta["versions"] = versions
        self._save_meta(prompt_id, meta)

        return next_version

    def diff(self, prompt_id: str, v1: int, v2: int) -> str:
        _, t1 = self.get(prompt_id, v1)
        _, t2 = self.get(prompt_id, v2)

        lines1 = t1.splitlines(keepends=False)
        lines2 = t2.splitlines(keepends=False)

        diff_iter = difflib.unified_diff(
            lines1,
            lines2,
            fromfile=f"{prompt_id}:{version_filename(v1)}",
            tofile=f"{prompt_id}:{version_filename(v2)}",
            lineterm="",
        )
        return "\n".join(diff_iter)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prompt registry (versioning + diff)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a new version of a prompt")
    p_add.add_argument("prompt_id")
    p_add.add_argument("--file", type=str, help="Path to a text file containing the prompt")
    p_add.add_argument("--text", type=str, help="Prompt text (if not using --file)")
    p_add.add_argument("--note", type=str, default=None, help="Optional note about this change")

    p_list = sub.add_parser("list", help="List prompt IDs in the registry")

    p_hist = sub.add_parser("history", help="List versions for a prompt_id")
    p_hist.add_argument("prompt_id")

    p_show = sub.add_parser("show", help="Print a prompt version (defaults to latest)")
    p_show.add_argument("prompt_id")
    p_show.add_argument("--version", type=int, default=None)

    p_diff = sub.add_parser("diff", help="Unified diff between two versions")
    p_diff.add_argument("prompt_id")
    p_diff.add_argument("v1", type=int)
    p_diff.add_argument("v2", type=int)

    args = parser.parse_args()
    reg = PromptRegistry()

    if args.cmd == "add":
        if args.file:
            text = read_text(Path(args.file))
        elif args.text:
            text = args.text
        else:
            raise SystemExit("Provide --file <path> or --text '<prompt text>'")
        v = reg.add(args.prompt_id, text=text, note=args.note)
        print(f"Added {args.prompt_id} version v{v:04d}")

    elif args.cmd == "list":
        for pid in reg.list_prompts():
            latest = reg.latest_version(pid)
            latest_str = f"v{latest:04d}" if latest else "-"
            print(f"{pid}\t{latest_str}")

    elif args.cmd == "history":
        versions = reg.list_versions(args.prompt_id)
        if not versions:
            print("No versions found.")
            return
        for pv in versions:
            note = f" — {pv.note}" if pv.note else ""
            print(f"v{pv.version:04d}\t{pv.created_at}{note}")

    elif args.cmd == "show":
        v, text = reg.get(args.prompt_id, args.version)
        print(f"# {args.prompt_id} v{v:04d}\n")
        print(text.rstrip())

    elif args.cmd == "diff":
        print(reg.diff(args.prompt_id, args.v1, args.v2))


if __name__ == "__main__":
    main()
