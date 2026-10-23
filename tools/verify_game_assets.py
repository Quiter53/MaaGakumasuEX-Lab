"""Verify original reference PNGs against their export manifests."""
import hashlib
import json
from pathlib import Path

from PIL import Image


def verify(root):
    root = Path(root).resolve()
    total, size = 0, 0
    expected = set()
    for report_path, base in [(root / "card-drink-manifest.json", root),
                              (root / "ui/manifest.json", root / "ui")]:
        report = json.loads(report_path.read_text("utf-8"))
        if report["errors"]:
            raise RuntimeError(f"Unresolved export errors in {report_path}")
        for item in report["files"]:
            path = (base / item["path"]).resolve()
            if not path.is_relative_to(root):
                raise ValueError(f"Path escapes asset directory: {item['path']}")
            expected.add(path)
            with path.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != item["sha256"] or path.stat().st_size != item["bytes"]:
                raise ValueError(f"File checksum differs: {path}")
            with Image.open(path) as image:
                image.load()
                pixels = hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest()
                if list(image.size) != item["size"] or pixels != item["rgbaSha256"]:
                    raise ValueError(f"Decoded pixels differ: {path}")
            total += 1
            size += item["bytes"]
    actual = set(root.rglob("*.png"))
    if actual != expected:
        raise ValueError(f"Manifest coverage differs: {len(actual)} files, {len(expected)} entries")
    return dict(images=total, bytes=size, sha256Verified=True, decodedPixelsVerified=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1] / "game-assets")
    args = parser.parse_args()
    print(json.dumps(verify(args.root)))
