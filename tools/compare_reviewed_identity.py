"""Compare fixed identity readers on existing reviewed boxes, without detection/input."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image

from evaluate_badge_matching import ROOT, prepare
from evaluate_reviewed_frames import key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'source')
    parser.add_argument('--reference', default='b06e998e76a35e8c5b801bba8d15f652aee34954')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a new output path')
    _, _, _, _, candidate, reference = prepare(args.source.resolve(), ROOT, args.reference)
    dataset = ROOT / 'datasets/video-eval-20261025'
    duplicates = {f['sha256'] for f in json.loads((dataset/'curation.json').read_text())['frames'] if f['duplicateOf']}
    inputs = []
    for group in ('first', 'second'):
        for row in json.loads((dataset/f'{group}_labels.json').read_text('utf-8'))['labels']:
            if row['sha256'] not in duplicates:
                inputs.append((group, dataset/row['file'], row['boxes'], row['names'], row['sha256']))
    for row in json.loads((args.source/'tests/fixtures/hand_identity_labels.json').read_text('utf-8'))['frames']:
        inputs.append(('historical', ROOT/'fixtures/hand'/row['file'], [[x,884,189,249] for x in row['xs']], row['names'], None))
    stats, records, changes = {}, [], []
    for group, path, boxes, truth, expected_hash in inputs:
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected_hash and sha != expected_hash:
            raise ValueError(f'Reviewed image changed: {path}')
        with Image.open(path) as image:
            bgr = np.asarray(image.convert('RGB'))[:, :, ::-1].copy()
        for slot, (box, expected) in enumerate(zip(boxes, truth)):
            row = dict(group=group, file=path.relative_to(ROOT).as_posix(), sha256=sha, slot=slot, box=box, expected=expected)
            for tag, reader in [('reference', reference), ('candidate', candidate)]:
                result = reader.read(bgr, box, boxes)
                row[tag] = asdict(result) if result else None
                name = result.name if result else None
                outcome = 'unknown' if name is None else 'correct' if key(name) == key(expected) else 'wrong'
                stats.setdefault(group, {}).setdefault(tag, Counter()).update(total=1, **{outcome: 1})
            records.append(row)
            old, new = row['reference'], row['candidate']
            if (old is None) != (new is None) or (old and any(new[k] != v for k, v in old.items())):
                changes.append(row)
    result = dict(scope='Existing reviewed identity boxes; Codex visual labels, not independent human audit or live cultivation',
                  reference=args.reference, sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=args.source,text=True).strip(),
                  identitySha256=hashlib.sha256((args.source/'agent/custom/hand_identity.py').read_bytes()).hexdigest(),
                  stats=stats, changes=changes, records=records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps(dict(stats=stats, changed=len(changes)), ensure_ascii=False))
    if changes:
        raise SystemExit('Reviewed identity results changed; inspect the report')


if __name__ == '__main__':
    main()
