import hashlib
from pathlib import Path

directory = Path(__file__).resolve().parent.parent / "dist"
lines: list[str] = []
for path in sorted(directory.iterdir()):
    if path.suffix not in {".zip", ".exe"}:
        continue
    with path.open("rb") as source:
        lines.append(
            f"{hashlib.file_digest(source, 'sha256').hexdigest()}  {path.name}"
        )
_ = (directory / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
