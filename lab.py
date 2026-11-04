"""Portable EX regression, screenshot replay and calibration entry points."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"


def run(command, cwd=SOURCE, env=None, output=None):
    command = list(map(str, command))
    print("+", subprocess.list2cmdline(command), flush=True)
    environment = {**os.environ, "PYTHONUTF8": "1", **(env or {})}
    if output is None:
        subprocess.run(command, cwd=cwd, check=True, env=environment)
        return
    result_path = output / "result.json"
    result = json.loads(result_path.read_text("utf-8")) if result_path.exists() else {"commands": []}
    record = {"command": command, "cwd": str(cwd), "status": "running"}
    result["commands"].append(record)
    result["status"] = "running"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    started = time.monotonic()
    try:
        with (output / "run.log").open("a", encoding="utf-8") as log:
            log.write("+ " + subprocess.list2cmdline(command) + "\n")
            with subprocess.Popen(command, cwd=cwd, env=environment, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace") as process:
                for line in process.stdout:
                    print(line, end="", flush=True)
                    log.write(line)
                    log.flush()
                record["exitCode"] = process.wait()
        if record["exitCode"]:
            raise subprocess.CalledProcessError(record["exitCode"], command)
        record["status"] = "passed"
    except BaseException as error:
        record["status"] = "failed"
        record["error"] = str(error)
        raise
    finally:
        record["seconds"] = round(time.monotonic() - started, 3)
        result["status"] = "failed" if record["status"] == "failed" else "running"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(source=SOURCE):
    manifest = json.loads((ROOT / "fixtures/manifest.json").read_text("utf-8"))
    # Validate the complete overlay before copying anything; never replace edits.
    pairs = []
    for item in manifest["files"]:
        src = ROOT / "fixtures" / item["path"]
        dst = source / "tests/fixtures" / item["path"]
        if not src.resolve().is_relative_to((ROOT / "fixtures").resolve()):
            raise ValueError(f"Fixture path escapes fixtures: {src}")
        if not dst.resolve().is_relative_to((source / "tests/fixtures").resolve()):
            raise ValueError(f"Fixture destination escapes source fixtures: {dst}")
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


def provenance(output, source=SOURCE):
    output.mkdir(parents=True, exist_ok=False)
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=source).decode("utf-8").strip()
    data = dict(sourcePath=str(source), sourceCommit=git("rev-parse", "HEAD"),
                sourceChanges=git("status", "--porcelain"), python=sys.version,
                command=sys.argv, fixtureManifest=digest(ROOT / "fixtures/manifest.json"))
    data["sourceDiffSha256"] = hashlib.sha256(
        subprocess.check_output(["git", "diff", "--binary", "HEAD"], cwd=source)).hexdigest()
    data["packages"] = subprocess.check_output([sys.executable, "-m", "pip", "freeze"]).decode("utf-8").splitlines()
    (output / "environment.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


def ui_fixture(source, staging, suite):
    """Public defaults only; all test-generated state stays under its output."""
    staging.mkdir(parents=True)
    if suite == "NativeShots":
        shutil.copytree(source / "assets", staging, dirs_exist_ok=True)
    else:
        for name in ("config", "card_library", "data", "lang", "tasks"):
            shutil.copytree(source / "assets" / name, staging / name)
        shutil.copyfile(source / "assets/interface.json", staging / "interface.json")
    if suite == "CardRulesUi":
        shutil.copyfile(source / "agent/custom/card_rules.defaults.json", staging / "config/card_rules.json")
    if suite == "NativeShots":
        custom = staging / "agent/custom"
        custom.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / "agent/custom/drink_catalog.json", custom / "drink_catalog.json")
        config = {"UI.HasCompletedFirstUseTutorial": True, "EnableAutoUpdateResource": False,
                  "EnableAutoUpdateMFA": False, "EnableCheckVersion": False, "AutoConnectAfterRefresh": False,
                  "AutoDetectOnConnectionFailed": False, "BeforeTask": "None"}
        (staging / "config/config.json").write_text(json.dumps(config, indent=2), "utf-8")
        global_config = {"AnnouncementInfo.DoNotShowAgain": "True", "Changelog.DoNotShowAgain": "True", "NoAutoStart": "True"}
        (staging / "appsettings.json").write_text(json.dumps(global_config, indent=2), "utf-8")


def run_ui(args, source, output):
    project = next((source / "tests" / args.suite).glob("*.csproj"))
    runtime = output / "runtime"
    run([args.dotnet, "--info"], cwd=source, output=output)
    run([args.dotnet, "build", project, "-c", "Release", "-o", runtime], cwd=source, output=output)
    assembly = runtime / (project.stem + ".dll")
    command = [args.dotnet, assembly]
    if args.suite == "PortableLayout":
        portable = args.runtime.resolve()
        shutil.copytree(portable / "libs", runtime / "libs")
        for name in ("MFAAvalonia.runtimeconfig.json", "MFAAvalonia.deps.json", "libloader.dll"):
            shutil.copyfile(portable / name, runtime / name)
        evidence = {"path": str(portable), "files": {
            name: digest(portable / name) for name in (
                "libs/MFAAvalonia.Core.dll", "MFAAvalonia.runtimeconfig.json", "MFAAvalonia.deps.json", "libloader.dll")}}
        if (portable / "PORTABLE_BUILD.json").is_file():
            evidence["build"] = json.loads((portable / "PORTABLE_BUILD.json").read_text("utf-8"))
        (output / "portable-input.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), "utf-8")
        command = [args.dotnet, "exec", "--runtimeconfig", runtime / "MFAAvalonia.runtimeconfig.json",
                   "--depsfile", runtime / "MFAAvalonia.deps.json", assembly,
                   source / "native-ui/MFAAvalonia/Assets/Localization"]
    elif args.suite in ("CardRulesUi", "CardListUi", "DrinkUi", "NativeShots"):
        staging = output / "fixture"
        ui_fixture(source, staging, args.suite)
        if args.suite == "CardRulesUi":
            command += [staging, output]
            if args.combo_only:
                command += ["--combo-only"]
        elif args.suite == "CardListUi":
            command += [staging]
        elif args.suite == "DrinkUi":
            command += [source, staging]
        elif args.suite == "NativeShots":
            # AppPaths uses AppContext.BaseDirectory, so put defaults beside the test DLL.
            shutil.copytree(staging, runtime, dirs_exist_ok=True)
            command += [runtime, output, args.script]
    if args.suite == "native_archive_policy":
        command += [output / "archive-policy"]
    run(command, cwd=runtime, output=output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE,
                        help="Source checkout to test (default: pinned source submodule)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare", help="Restore verified replay fixtures into the selected source checkout")
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
    ui.add_argument("suite", choices=["CardRulesUi", "CardListUi", "DrinkUi", "FocusImages", "native_task_watchdog",
                                     "LiquidBoardTests", "ConfigSaveTests", "native_release_policy", "native_archive_policy",
                                     "NativeShots", "PortableLayout"])
    ui.add_argument("--dotnet", default="dotnet", help=".NET 10 SDK dotnet executable")
    ui.add_argument("--output", type=Path, default=ROOT / "outputs/ui")
    ui.add_argument("--combo-only", action="store_true")
    ui.add_argument("--runtime", type=Path, help="Portable package directory for PortableLayout (read-only input)")
    ui.add_argument("--script", choices=["basic", "all", "sizes", "small", "taskopts", "round4", "round5", "audit", "tutorial",
                                         "probe", "lang:zh-CN", "lang:zh-Hant", "lang:en-US", "lang:ja-JP"],
                    default="basic", help="NativeShots headless test or rendering script")
    check = sub.add_parser("model-check", help="Replay the original native detector on a saved image")
    check.add_argument("--image", type=Path, required=True)
    check.add_argument("--output", type=Path, default=ROOT / "outputs/model-check")
    check.add_argument("extra", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    source = args.source.resolve()
    if not (source / "agent").is_dir():
        parser.error("Source checkout is missing agent; select --source or initialize the source submodule")
    if args.command == "prepare":
        prepare(source)
    elif args.command == "test":
        if args.vectors and not args.vectors.is_file():
            parser.error("Native policy vectors file does not exist")
        prepare(source)
        output = args.output.resolve()
        provenance(output, source)
        extra = args.pytest_args
        if extra[:1] == ["--"]:
            extra = extra[1:]
        env = {"CARD_RULE_VECTORS": str(args.vectors.resolve())} if args.vectors else {}
        run([sys.executable, "-m", "pytest", "-q", "tests", f"--junitxml={output / 'junit.xml'}",
             f"--basetemp={output / 'pytest-tmp'}", "-o", f"cache_dir={output / 'pytest-cache'}", *extra],
            cwd=source, env=env, output=output)
    elif args.command == "calibrate":
        output = args.output.resolve()
        provenance(output, source)
        run([sys.executable, source / "tools/train_hand_identity.py", "--per-mode", args.per_mode,
             "--output", output / "calibration.json", "--report", output / "report.json"], cwd=source, output=output)
    elif args.command == "evaluate-hand":
        output = args.output.resolve()
        provenance(output, source)
        run([sys.executable, source / "tools/evaluate_hand_identity.py", ROOT / "fixtures/hand",
             "--output", output / "report.json"], cwd=source, output=output)
    elif args.command == "ui":
        if args.combo_only and args.suite != "CardRulesUi":
            parser.error("--combo-only is only supported by CardRulesUi")
        if args.script != "basic" and args.suite != "NativeShots":
            parser.error("--script is only supported by NativeShots")
        if args.suite == "PortableLayout" and (not args.runtime or not (args.runtime / "libs/MFAAvalonia.Core.dll").is_file()):
            parser.error("PortableLayout requires --runtime with a built portable package")
        if args.runtime and args.suite != "PortableLayout":
            parser.error("--runtime is only supported by PortableLayout")
        if len(list((source / "tests" / args.suite).glob("*.csproj"))) != 1:
            parser.error(f"The selected source does not provide the {args.suite} test project")
        output = args.output.resolve()
        provenance(output, source)
        run_ui(args, source, output)
    elif args.command == "model-check":
        extra = args.extra[1:] if args.extra[:1] == ["--"] else args.extra
        output = args.output.resolve()
        provenance(output, source)
        # Toolkit.init_option(".") owns native configuration and logs in its working directory.
        run([sys.executable, source / "tools/check_cards_model.py", source / "assets/resource/base",
             "--image", args.image.resolve(), *extra], cwd=output, output=output)
    if args.command != "prepare":
        result_path = output / "result.json"
        result = json.loads(result_path.read_text("utf-8"))
        result["status"] = "passed"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")


if __name__ == "__main__":
    main()
