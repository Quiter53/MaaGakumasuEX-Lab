"""Portable EX regression, screenshot replay and calibration entry points."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"


def run(command, cwd=SOURCE, env=None):
    print("+", subprocess.list2cmdline(list(map(str, command))), flush=True)
    subprocess.run(list(map(str, command)), cwd=cwd, check=True,
                   env={**os.environ, "PYTHONUTF8": "1", **(env or {})})


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare():
    manifest = json.loads((ROOT / "fixtures/manifest.json").read_text("utf-8"))
    # Validate the complete overlay before copying anything; never replace edits.
    pairs = []
    for item in manifest["files"]:
        src = ROOT / "fixtures" / item["path"]
        dst = SOURCE / "tests/fixtures" / item["path"]
        assert src.resolve().is_relative_to((ROOT / "fixtures").resolve())
        assert dst.resolve().is_relative_to((SOURCE / "tests/fixtures").resolve())
        if digest(src) != item["sha256"]:
            raise RuntimeError(f"Fixture checksum differs: {src}")
        if dst.exists() and digest(dst) != item["sha256"]:
            raise RuntimeError(f"Existing fixture differs; review manually: {dst}")
        pairs.append((src, dst))
    for src, dst in pairs:
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
    print(f"Verified/restored {len(pairs)} replay fixtures.")


def provenance(output):
    output.mkdir(parents=True, exist_ok=False)
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=SOURCE).decode("utf-8").strip()
    data = dict(sourceCommit=git("rev-parse", "HEAD"),
                sourceChanges=git("status", "--porcelain"), python=sys.version,
                command=sys.argv, fixtureManifest=digest(ROOT / "fixtures/manifest.json"))
    data["packages"] = subprocess.check_output([sys.executable, "-m", "pip", "freeze"]).decode("utf-8").splitlines()
    (output / "environment.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare", help="Restore private fixtures into the pinned source checkout")
    test = sub.add_parser("test", help="Run all existing Python regressions")
    test.add_argument("--output", type=Path, default=ROOT / "outputs/test")
    test.add_argument("--vectors", type=Path, help="native-policy-vectors.json from CardRulesUi")
    test.add_argument("pytest_args", nargs=argparse.REMAINDER)
    calibrate = sub.add_parser("calibrate", help="Synthetic metric threshold fitting, not YOLO training")
    calibrate.add_argument("--per-mode", type=int, default=400)
    calibrate.add_argument("--output", type=Path, default=ROOT / "outputs/calibration")
    evaluate = sub.add_parser("evaluate-hand", help="Evaluate historical labelled frames with manual card boxes")
    evaluate.add_argument("--output", type=Path, default=ROOT / "outputs/hand-evaluation")
    ui = sub.add_parser("ui", help="Run a native .NET 10 regression harness")
    ui.add_argument("suite", choices=["CardRulesUi", "CardListUi", "DrinkUi", "FocusImages", "native_task_watchdog"])
    ui.add_argument("--dotnet", default="dotnet", help=".NET 10 SDK dotnet executable")
    ui.add_argument("--output", type=Path, default=ROOT / "outputs/ui")
    ui.add_argument("--combo-only", action="store_true")
    check = sub.add_parser("model-check", help="Replay the original native detector on a saved image")
    check.add_argument("--image", type=Path, required=True)
    check.add_argument("extra", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not (SOURCE / "agent").is_dir():
        parser.error("Run git submodule update --init --recursive first")
    if args.command == "prepare":
        prepare()
    elif args.command == "test":
        prepare()
        output = args.output.resolve()
        provenance(output)
        extra = args.pytest_args
        if extra[:1] == ["--"]:
            extra = extra[1:]
        env = {"CARD_RULE_VECTORS": str(args.vectors.resolve())} if args.vectors else {}
        if args.vectors and not args.vectors.is_file():
            parser.error("Native policy vectors file does not exist")
        run([sys.executable, "-m", "pytest", "-q", "tests", f"--junitxml={output / 'junit.xml'}", *extra], env=env)
    elif args.command == "calibrate":
        output = args.output.resolve()
        provenance(output)
        run([sys.executable, SOURCE / "tools/train_hand_identity.py", "--per-mode", args.per_mode,
             "--output", output / "calibration.json", "--report", output / "report.json"])
    elif args.command == "evaluate-hand":
        output = args.output.resolve()
        provenance(output)
        run([sys.executable, SOURCE / "tools/evaluate_hand_identity.py", ROOT / "fixtures/hand",
             "--output", output / "report.json"])
    elif args.command == "ui":
        if args.combo_only and args.suite != "CardRulesUi":
            parser.error("--combo-only is only supported by CardRulesUi")
        output = args.output.resolve()
        provenance(output)
        staging = output / "fixture"
        staging.mkdir()
        shutil.copytree(SOURCE / "assets/config", staging / "config")
        shutil.copytree(SOURCE / "assets/card_library", staging / "card_library")
        for name in ("data", "lang", "tasks"):
            shutil.copytree(SOURCE / "assets" / name, staging / name)
        shutil.copyfile(SOURCE / "assets/interface.json", staging / "interface.json")
        if args.suite == "CardRulesUi":
            # The legacy harness explicitly expects the built-in policy fixture,
            # whose active preset differs from the public portable defaults.
            shutil.copyfile(SOURCE / "agent/custom/card_rules.defaults.json", staging / "config/card_rules.json")
        command = [args.dotnet, "run", "--project", SOURCE / "tests" / args.suite, "-c", "Release", "--"]
        if args.suite == "CardRulesUi":
            command += [staging, output]
            if args.combo_only:
                command += ["--combo-only"]
        elif args.suite == "CardListUi":
            command += [staging]
        elif args.suite == "DrinkUi":
            command += [SOURCE, staging]
        run(command)
    elif args.command == "model-check":
        extra = args.extra[1:] if args.extra[:1] == ["--"] else args.extra
        run([sys.executable, SOURCE / "tools/check_cards_model.py", SOURCE / "assets/resource/base",
             "--image", args.image.resolve(), *extra])


if __name__ == "__main__":
    main()
