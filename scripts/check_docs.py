"""Check local Markdown links and archived documentation hashes, without network I/O."""
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    errors = []
    checked = 0
    documents = [ROOT / name for name in ("README.md", "AGENTS.md", "log.md")]
    documents += sorted((ROOT / "docs").rglob("*.md"))
    documents += sorted((ROOT / "scripts").glob("*.md"))
    for path in documents:
        content = path.read_text(encoding="utf-8")
        # Keep line numbers stable while excluding fenced examples.
        content = re.sub(r"```.*?```", lambda m: "\n" * m.group().count("\n"), content, flags=re.S)
        for match in re.finditer(r"\[[^\]\n]+\]\((<[^>]+>|[^\s)]+)(?:\s+\"[^\"]*\")?\)", content):
            target = unquote(match[1].strip("<>").split("#", 1)[0])
            if not target or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            checked += 1
            if not (path.parent / target).exists():
                line = content[:match.start()].count("\n") + 1
                errors.append(f"{path.relative_to(ROOT)}:{line}: missing {target}")
    for path in sorted((ROOT / "docs/archive").glob("*.manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        archive = path.with_name(path.name.removesuffix(".manifest.json") + ".zip")
        if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["archive_sha256"]:
            errors.append(f"Archive hash mismatch: {archive.name}")
        with zipfile.ZipFile(archive) as contents:
            expected = {item["path"] for item in manifest["files"]} | {"manifest.json"}
            if set(contents.namelist()) != expected:
                errors.append(f"Archive inventory mismatch: {archive.name}")
            for item in manifest["files"]:
                data = contents.read(item["path"])
                if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                    errors.append(f"Archive member mismatch: {archive.name}/{item['path']}")
    for error in errors:
        print(error)
    print(f"Checked {len(documents)} documents, {checked} local links; {len(errors)} errors.")
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
