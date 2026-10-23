"""Read-only export of original Unity Sprite / Texture2D images to PNG."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_name(name):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return value[:140] or "unnamed"


def export(source, output, *, unity_version="6000.0.77f1"):
    import UnityPy
    UnityPy.config.FALLBACK_UNITY_VERSION = unity_version
    source, output = Path(source).resolve(), Path(output).resolve()
    source_hash = sha(source)
    output.mkdir(parents=True, exist_ok=False)
    env = UnityPy.load(str(source))
    files, errors, skipped = [], [], []
    for obj in env.objects:
        kind = obj.type.name
        if kind not in {"Sprite", "Texture2D"}:
            continue
        name = obj.peek_name() or "unnamed"
        try:
            data = obj.read()
            if kind == "Texture2D" and (data.m_Width < 1 or data.m_Height < 1):
                skipped.append(dict(name=name, type=kind, pathId=obj.path_id,
                                    reason="Empty runtime texture; no stored pixels", size=[data.m_Width, data.m_Height]))
                continue
            image = data.image
            if image.width < 1 or image.height < 1:
                continue
            folder = "sprites" if kind == "Sprite" else "textures"
            identity = hashlib.sha256(obj.assets_file.name.encode()).hexdigest()[:8]
            relative = Path(folder) / f"{safe_name(name)}__{identity}__{obj.path_id}.png"
            target = output / relative
            target.parent.mkdir(exist_ok=True)
            if target.exists():
                raise FileExistsError(f"Export collision: {relative}")
            image.save(target, "PNG")
            files.append(dict(path=relative.as_posix(), name=name, type=kind,
                serializedFile=obj.assets_file.name, pathId=obj.path_id, size=list(image.size),
                mode=image.mode, bytes=target.stat().st_size, sha256=sha(target),
                rgbaSha256=hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest()))
            if len(files) % 200 == 0:
                print(f"Unity images exported: {len(files)}", flush=True)
        except Exception as error:
            errors.append(dict(name=name, type=kind, pathId=obj.path_id,
                               error=f"{type(error).__name__}: {error}"))
    if sha(source) != source_hash:
        raise RuntimeError("Source changed during export")
    report = dict(sourceName=source.name, sourceSha256=source_hash,
        unityFallbackVersion=unity_version, unityPyVersion=importlib.metadata.version("UnityPy"),
        processing="Native Sprite/Texture2D decoding to PNG; no resizing or artwork enhancement",
        files=files, errors=errors, skipped=skipped)
    (output / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", "utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, help="New directory; existing directories are not overwritten")
    parser.add_argument("--unity-version", default="6000.0.77f1")
    args = parser.parse_args()
    report = export(args.source, args.output, unity_version=args.unity_version)
    print(json.dumps(dict(exported=len(report["files"]), errors=len(report["errors"]))))
    if report["errors"]:
        raise SystemExit("Some assets could not be exported; inspect manifest.json")


if __name__ == "__main__":
    main()
