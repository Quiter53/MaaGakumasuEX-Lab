"""Replay saved negative failures without game input or the preceding RNG stream."""
import argparse
import json
from pathlib import Path
import random
import hashlib
import subprocess
import platform
import sys

import numpy as np
import PIL
from PIL import Image

from badge_failure_cases import negative_frame, pixel_hash, result_dict, tuple_state, write_index
from evaluate_badge_matching import ROOT, add_badge, prepare


def replay(report_path, source, regenerate=False, case_id=None, all_negative=False, export_cases=None):
    report = json.loads(report_path.read_text('utf-8'))
    synth, cat, frames, patch, candidate, baseline = prepare(source, ROOT, report['baseline'])
    records = [f for f in report['negativeFrames'] if
               (f['id'] == case_id if case_id else all_negative or f['failureSlots'])]
    if not records:
        raise ValueError('No matching recorded cases')
    if export_cases is not None:
        export_cases.mkdir(parents=True, exist_ok=False)
    exported = []
    rows = []
    for frame in records:
        if regenerate or 'image' not in frame:
            rng = random.Random()
            rng.setstate(tuple_state(frame['rngState']))
            image, boxes, replacements = negative_frame(synth, frames, cat, sorted(cat), rng, patch,
                frame['workerSeed'], frame['sampleIndex'], frame['hard'], add_badge)
            if boxes != frame['boxes'] or replacements != frame['replacements']:
                raise ValueError(f'Generation metadata mismatch: {frame["id"]}')
        else:
            directory = (report_path.parent / report['caseDirectory']).resolve()
            path = (directory / frame['image']).resolve()
            if not path.is_relative_to(directory):
                raise ValueError('Case image is outside the report directory')
            with Image.open(path) as picture:
                image = np.asarray(picture.convert('RGB'))
            boxes = frame['boxes']
        if list(image.shape) != frame['imageShape'] or pixel_hash(image) != frame['imageSha256']:
            raise ValueError(f'Pixel hash mismatch: {frame["id"]}')
        if export_cases is not None:
            # File names derive from position, never untrusted case IDs.
            name = f'frame-{len(exported):04d}.png'
            Image.fromarray(image).save(export_cases / name)
            exported.append({**frame, 'image': name})
        bgr = image[:, :, ::-1].copy()
        for old in frame['cards']:
            current = {tag: result_dict(reader.read(bgr, old['box'], boxes))
                       for tag, reader in [('baseline', baseline), ('candidate', candidate)]}
            rows.append(dict(id=frame['id'], slot=old['slot'], box=old['box'],
                             recorded={tag: old[tag] for tag in current}, current=current))
    if export_cases is not None:
        write_index(export_cases, exported)
    return dict(scope='Synthetic negative identity matching; not real-game accuracy', cards=rows,
                sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip(),
                identitySha256=hashlib.sha256((source/'agent/custom/hand_identity.py').read_bytes()).hexdigest(),
                environment=dict(python=sys.version, platform=platform.platform(), numpy=np.__version__, pillow=PIL.__version__),
                reportSha256=hashlib.sha256(report_path.read_bytes()).hexdigest(),
                frames=len(records), regenerated=regenerate,
                accepted={tag: sum(r['current'][tag] is not None and r['current'][tag]['name'] is not None
                                  for r in rows) for tag in ('baseline', 'candidate')})


def matches_recorded(rows):
    for row in rows:
        for tag, actual in row['current'].items():
            expected = row['recorded'][tag]
            if actual is None or expected is None:
                if actual != expected:
                    return False
                continue
            if actual.keys() != expected.keys():
                return False
            for key, value in actual.items():
                other = expected[key]
                if isinstance(value, float):
                    if not np.isclose(value, other, rtol=1e-6, atol=1e-7):
                        return False
                elif value != other:
                    return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--source', type=Path, default=ROOT / 'source')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--regenerate', action='store_true', help='Restore RNG state and verify exact pixels')
    parser.add_argument('--all-negative', action='store_true', help='Replay rejected negatives too')
    parser.add_argument('--case', help='Frame ID, e.g. w92471-n0000')
    parser.add_argument('--export-cases', type=Path, help='New directory for verified full PNGs and an HTML index')
    parser.add_argument('--check-recorded', action='store_true', help='Fail on changed results/scores')
    parser.add_argument('--expect-no-candidate-accepts', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a new output path')
    if args.export_cases and args.export_cases.exists():
        parser.error('Use a new export directory')
    result = replay(args.report.resolve(), args.source.resolve(), args.regenerate, args.case, args.all_negative, args.export_cases)
    result['matchesRecorded'] = matches_recorded(result['cards'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'cards'}))
    if args.check_recorded and not result['matchesRecorded']:
        raise SystemExit('Recorded predictions differ; inspect the output')
    if args.expect_no_candidate_accepts and result['accepted']['candidate']:
        raise SystemExit('Candidate still accepts negative samples')


if __name__ == '__main__':
    main()
