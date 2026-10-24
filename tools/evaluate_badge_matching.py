"""Compare badge recovery with a Git baseline on identical synthetic hands.

Synthetic artwork is related to the reference gallery. This measures robustness
and regressions, not independent real-game accuracy. No game input is possible.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys
import time
import types

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '1b3d1f7e7b9f06624fac747775820e20a39efcc9'  # Published v2.1.3; works without fetched tag refs.


def prepare(source, lab, ref):
    sys.path.insert(0, str(source / 'agent'))
    package = types.ModuleType('custom')
    package.__path__ = [str(source / 'agent/custom')]
    sys.modules.setdefault('custom', package)
    from custom.hand_identity import HandIdentityReader
    baseline_name = 'custom._badge_baseline'
    module = types.ModuleType(baseline_name)
    module.__file__ = str(source / 'agent/custom/hand_identity.py')
    sys.modules[baseline_name] = module
    code = subprocess.check_output(['git', 'show', ref + ':agent/custom/hand_identity.py'], cwd=source)
    exec(compile(code, '<git-baseline-hand-identity>', 'exec'), module.__dict__)
    spec = importlib.util.spec_from_file_location('hand_synthetic', source / 'tools/evaluate_hand_synthetic.py')
    synth = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(synth)
    synth.LAB = lab
    cat = synth.catalog()
    frames = synth.build_frames(cat, synth.real_hand_boxes(lab))
    # Avoid the diagnosed badge-bearing source in our base UI plates. Add the
    # known overlay explicitly, with a known mask, after each hand is composed.
    frames = [f for f in frames if f['file'] != '20260813-215954-231-battle.png']
    with Image.open(lab / 'fixtures/hand/20260813-215954-231-battle.png') as image:
        badge = image.convert('RGB').crop((180, 932, 236, 991))
    baseline = module.HandIdentityReader()
    baseline.gates = json.loads(subprocess.check_output(
        ['git', 'show', ref + ':agent/custom/hand_identity_calibration.json'], cwd=source))['gates']
    return synth, cat, frames, np.asarray(badge), HandIdentityReader(), baseline


def add_badge(image, box, boxes, patch, rng):
    x, y, w, h = box
    bw, bh = round(w * 56 / 189), round(h * 59 / 249)
    patch = Image.fromarray(patch).resize((bw, bh), Image.Resampling.BILINEAR)
    mask = Image.new('L', (bw, bh))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, bw - 1, bh - 1), radius=round(bw * .18), fill=255)
    alpha = np.asarray(mask, np.float32) / 255
    px, py = x + round(w * 132 / 189) + rng.randint(-1, 1), y + round(h * 48 / 249) + rng.randint(-1, 1)
    right = min([b[0] for b in boxes if x < b[0] < x + w] or [x + w])
    visible_w = max(0, min(bw, right - px, image.shape[1] - px))
    if visible_w:
        a = alpha[:, :visible_w, None]
        region = image[py:py+bh, px:px+visible_w].astype(np.float32)
        image[py:py+bh, px:px+visible_w] = np.uint8(region * (1-a) + np.asarray(patch)[:, :visible_w] * a)


def one_worker(job):
    source, lab, ref, seed, count, hard, stacked = job
    synth, cat, frames, patch, candidate, baseline = prepare(Path(source), Path(lab), ref)
    names, rng = sorted(cat), random.Random(seed)
    stats, changes, timings = {}, [], {'baseline': [], 'candidate': []}
    def evaluate(image, boxes, truth, group):
        bgr = image[:, :, ::-1].copy()
        for box, expected in zip(boxes, truth):
            results = {}
            row = stats.setdefault(group, {'baseline': Counter(), 'candidate': Counter()})
            for tag, reader in [('baseline', baseline), ('candidate', candidate)]:
                start = time.perf_counter()
                result = reader.read(bgr, box, boxes)
                timings[tag].append((time.perf_counter() - start) * 1000)
                predicted = result.name if result else None
                outcome = 'unknown' if predicted is None else 'correct' if expected == synth.normalize_card_name(predicted).rstrip('+') else 'wrong'
                row[tag].update(total=1, **{outcome: 1})
                results[tag] = (predicted, result)
            if results['candidate'][0] != results['baseline'][0]:
                if len(changes) < 60:
                    changes.append({'group': group, 'expected': expected, 'box': box,
                                    **{tag: asdict(result) if result else None for tag, (_, result) in results.items()}})
                row['candidate']['changed'] += 1
                if results['candidate'][0] is not None and (expected is None or synth.normalize_card_name(results['candidate'][0]).rstrip('+') != expected):
                    row['candidate']['new_wrong'] += 1
    for k in range(1, 6):
        for _ in range(count):
            image, boxes, truth = synth.compose(frames, cat, names, rng, k, hard=hard)
            evaluate(image, boxes, truth, f'{k}-clean')
            image = image.copy()
            for box in boxes:
                add_badge(image, box, boxes, patch, rng)
                if stacked:
                    # Shift the same confirmed overlay down by half a badge.
                    for level in range(1, rng.randint(1,3)):
                        shifted = [box[0], box[1] + round(box[3]*.865*.14*level), box[2], box[3]]
                        add_badge(image, shifted, boxes, patch, rng)
            evaluate(image, boxes, truth, f'{k}-badge')
    # Explicit unknowns exercise accidental agreement on uninformative inputs.
    for i in range(count):
        image, boxes, _ = synth.compose(frames, cat, names, rng, 3, hard=hard)
        for box in boxes:
            x, y, w, h = box
            art_h = round(h * .865)
            noise = np.random.default_rng(seed + i + x)
            if i % 2:
                image[y:y+art_h, x:x+w] = noise.integers(0, 256, (art_h, w, 3), dtype=np.uint8)
            else:
                image[y:y+art_h, x:x+w] = noise.integers(0, 256, 3, dtype=np.uint8)
            add_badge(image, box, boxes, patch, rng)
        evaluate(image, boxes, [None]*len(boxes), 'negative-badge')
    return {'stats': {g: {k: dict(v) for k, v in row.items()} for g, row in stats.items()},
            'changes': changes, 'timings': timings}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=ROOT / 'source')
    p.add_argument('--baseline', default=BASELINE)
    p.add_argument('--per-k', type=int, default=100)
    p.add_argument('--seed', type=int, default=1031)
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--hard', action='store_true')
    p.add_argument('--stacked', action='store_true', help='Exercise 1-3 vertically stacked thumbnail badges')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        p.error('Use a new output path')
    jobs = [(str(args.source.resolve()), str(ROOT), args.baseline, args.seed + i*7919,
             args.per_k // args.workers + int(i < args.per_k % args.workers), args.hard, args.stacked)
            for i in range(min(args.workers, args.per_k))]
    total, changes, times = {}, [], {'baseline': [], 'candidate': []}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for report in pool.map(one_worker, jobs):
            for group, row in report['stats'].items():
                dest = total.setdefault(group, {'baseline': Counter(), 'candidate': Counter()})
                for tag, values in row.items():
                    dest[tag].update(values)
            changes += report['changes']
            for tag in times:
                times[tag] += report['timings'][tag]
    result = {'scope': __doc__, 'baseline': args.baseline,
              'sourceCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.source, text=True).strip(),
              'sourceChanges': subprocess.check_output(['git', 'status', '--porcelain'], cwd=args.source, text=True).strip(),
              'sourceHashes': {str(f.relative_to(args.source)): hashlib.sha256(f.read_bytes()).hexdigest()
                               for f in [args.source/'agent/custom/hand_identity.py', args.source/'agent/custom/hand_badge.py',
                                         args.source/'agent/custom/hand_identity_calibration.json']},
              'seed': args.seed, 'perK': args.per_k, 'hard': args.hard, 'stacked': args.stacked, 'workers': args.workers,
              'stats': {g: {k: dict(v) for k, v in row.items()} for g, row in total.items()},
              'changes': changes, 'timingMs': {k: dict(zip(['median','p95'], np.percentile(v,[50,95]).tolist())) for k,v in times.items()}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps({k: v for k,v in result.items() if k in ['stats','timingMs']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
