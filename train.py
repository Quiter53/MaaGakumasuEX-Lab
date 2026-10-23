"""Validate a labelled dataset, train YOLO11, or export a candidate ONNX."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil

import yaml

from lab import ROOT, SOURCE, provenance


def validate(data):
    data = data.resolve()
    config = yaml.safe_load(data.read_text("utf-8"))
    names = config.get("names")
    if isinstance(names, dict):
        names = [names.get(i) for i in range(len(names))]
    if names != ["cards", "suggestions", "useless"]:
        raise ValueError("names must preserve class IDs: cards, suggestions, useless")
    base = (data.parent / config.get("path", ".")).resolve()
    hashes, counts = {}, {}
    for split in ("train", "val", "test"):
        if split not in config:
            if split == "test":
                continue
            raise ValueError(f"Missing {split} split")
        if not isinstance(config[split], str):
            raise ValueError("This entry point supports one image directory per split")
        images = (base / config[split]).resolve()
        if images.name != split or images.parent.name != "images":
            raise ValueError("Use images/train, images/val and images/test")
        found = sorted(p for p in images.rglob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
        if not found:
            raise ValueError(f"No images in {images}")
        classes = [0, 0, 0]
        for image in found:
            # Detect renamed/re-encoded copies by hashing decoded image pixels.
            from PIL import Image
            with Image.open(image) as im:
                if im.size != (720, 1280):
                    raise ValueError(f"Expected original 720x1280 frame: {image}")
                sha = hashlib.sha256(im.convert("RGB").tobytes()).hexdigest()
            if sha in hashes:
                raise ValueError(f"Duplicate frame: {image} and {hashes[sha]}; split by recording session")
            hashes[sha] = str(image)
            label = images.parent.parent / "labels" / split / image.relative_to(images).with_suffix(".txt")
            if not label.is_file():
                raise ValueError(f"Missing annotation (use empty txt for negative): {label}")
            for line in label.read_text("utf-8").splitlines():
                if not line.strip():
                    continue
                values = line.split()
                if len(values) != 5 or values[0] not in {"0", "1", "2"}:
                    raise ValueError(f"Invalid YOLO detection annotation: {label}: {line}")
                x, y, w, h = map(float, values[1:])
                if not all(math.isfinite(v) for v in (x, y, w, h)) or not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
                    raise ValueError(f"Coordinates must be normalized: {label}: {line}")
                if min(x-w/2, y-h/2) < -1e-6 or max(x+w/2, y+h/2) > 1+1e-6:
                    raise ValueError(f"Box extends outside frame: {label}: {line}")
                classes[int(values[0])] += 1
        counts[split] = dict(images=len(found), classes=classes)
    return dict(data=str(data), dataSha256=hashlib.sha256(data.read_bytes()).hexdigest(), splits=counts,
                frameHashes=hashes, datasetRoot=str(base), config=config)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--data", type=Path, required=True)
    train = sub.add_parser("train")
    train.add_argument("--data", type=Path, required=True)
    train.add_argument("--weights", type=Path, required=True, help="Local YOLO11 .pt, not the deployed ONNX")
    train.add_argument("--epochs", type=int, default=100)
    train.add_argument("--batch", type=int, default=8)
    train.add_argument("--imgsz", type=int, default=640)
    train.add_argument("--device", default="cpu", help="Use 0 for the first CUDA GPU")
    train.add_argument("--output", type=Path, required=True)
    export = sub.add_parser("export")
    export.add_argument("--weights", type=Path, required=True)
    export.add_argument("--imgsz", type=int, default=640)
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "check":
        report = validate(args.data)
        print(json.dumps(report["splits"], indent=2))
        return
    if not args.weights.is_file() or args.weights.suffix != ".pt":
        parser.error("Provide local .pt weights; original training weights are not bundled")
    output = args.output.resolve()
    if output.is_relative_to(SOURCE.resolve()):
        parser.error("Save candidates outside the source checkout")
    if args.imgsz <= 0 or args.imgsz % 32:
        parser.error("imgsz must be a positive multiple of 32")
    report = validate(args.data) if args.command == "train" else None
    from ultralytics import YOLO
    provenance(output)
    weights = output / "input.pt"
    shutil.copyfile(args.weights, weights)
    model = YOLO(str(weights))
    if args.command == "export":
        if list(model.names.values()) != ["cards", "suggestions", "useless"]:
            parser.error("Weights have a different class order")
        model.export(format="onnx", imgsz=args.imgsz, opset=17, dynamic=False, simplify=False, nms=False, device="cpu")
        weights.with_suffix(".onnx").rename(output / "candidate.onnx")
    else:
        # Absolute paths in the generated copy make Ultralytics independent of CWD.
        config = report.pop("config")
        config["path"] = report["datasetRoot"]
        dataset = output / "data.yaml"
        dataset.write_text(yaml.safe_dump(config, allow_unicode=True), "utf-8")
        (output / "dataset-manifest.json").write_text(json.dumps(report, indent=2), "utf-8")
        model.train(data=str(dataset), epochs=args.epochs, batch=args.batch, imgsz=args.imgsz,
                    device=args.device, project=str(output), name="detect", exist_ok=False,
                    seed=11011, deterministic=True, workers=0, patience=30, cos_lr=True)
        model.val(data=str(dataset), split="val", device=args.device, project=str(output), name="validation")


if __name__ == "__main__":
    main()
