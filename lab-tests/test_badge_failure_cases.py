"""Unchanged false accepts must remain visible, lossless and independently replayable."""
import json
from pathlib import Path
import random
import sys

import numpy as np
from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from badge_failure_cases import negative_frame, pixel_hash, save_negative_frame, tuple_state, write_index
from evaluate_badge_matching import BASELINE, add_badge, one_worker, prepare
from replay_badge_failures import matches_recorded, replay


def test_equal_false_accepts_are_uncapped_and_save_lossless_evidence(tmp_path):
    image = np.random.default_rng(4).integers(0, 256, (20, 30, 3), dtype=np.uint8)
    result = dict(name='same wrong card', candidate='same wrong card', score=.5, margin=.2)
    rows = [dict(slot=0, box=[0, 0, 10, 20], baseline=result, candidate=result)]
    records = [save_negative_frame(tmp_path, f'case-{i}', image, [[0, 0, 10, 20]], {'workerSeed': i}, rows)
               for i in range(65)]
    assert len(list(tmp_path.glob('*.png'))) == 65
    assert all(f['failureSlots'] == [0] for f in records)
    with Image.open(tmp_path / records[-1]['image']) as saved:
        assert pixel_hash(np.asarray(saved)) == pixel_hash(image)
    assert json.loads((tmp_path / 'case-64.json').read_text())['cards'] == rows
    write_index(tmp_path, records)
    assert 'case-64' in (tmp_path / 'index.html').read_text('utf-8')


@pytest.mark.parametrize('tags', [('baseline',), ('candidate',), ('baseline', 'candidate'), ()])
def test_either_acceptance_is_a_failure_but_joint_rejection_is_not(tmp_path, tags):
    row = dict(slot=0, box=[0, 0, 2, 2], **{tag: dict(name='wrong' if tag in tags else None) for tag in ('baseline', 'candidate')})
    record = save_negative_frame(tmp_path, 'case', np.zeros((2, 2, 3), np.uint8), [[0, 0, 2, 2]], {}, [row])
    assert bool(record['failureSlots']) == bool(tags)
    assert ('image' in record) == bool(tags)


def test_rng_snapshot_replays_without_preceding_hands_and_detects_tampering(tmp_path):
    synth, cat, frames, patch, candidate, baseline = prepare(ROOT / 'source', ROOT, BASELINE)
    rng = random.Random(92471)
    # An arbitrary stream position demonstrates that the seed alone is not needed.
    for _ in range(37):
        rng.random()
    state = json.loads(json.dumps(rng.getstate()))
    image, boxes, replacements = negative_frame(synth, frames, cat, sorted(cat), rng, patch, 92471, 2, True, add_badge)
    restored = random.Random()
    restored.setstate(tuple_state(state))
    other, other_boxes, other_replacements = negative_frame(synth, frames, cat, sorted(cat), restored, patch, 92471, 2, True, add_badge)
    assert np.array_equal(other, image) and boxes == other_boxes and replacements == other_replacements
    record = dict(id='sample', boxes=boxes, imageShape=list(image.shape), imageSha256=pixel_hash(image),
                  rngState=state, workerSeed=92471, sampleIndex=2, hard=True, replacements=replacements,
                  failureSlots=[0], cards=[])
    report = tmp_path / 'report.json'
    report.write_text(json.dumps(dict(baseline=BASELINE, negativeFrames=[record])))
    assert replay(report, ROOT / 'source', regenerate=True)['frames'] == 1
    record['imageSha256'] = 'invalid'
    report.write_text(json.dumps(dict(baseline=BASELINE, negativeFrames=[record])))
    with pytest.raises(ValueError, match='Pixel hash mismatch'):
        replay(report, ROOT / 'source', regenerate=True)


def test_negative_only_keeps_the_historical_random_stream(tmp_path):
    job = (str(ROOT / 'source'), str(ROOT), BASELINE, 1031, 1, True, True)
    scored = one_worker((*job, str(tmp_path / 'scored'), False))
    skipped = one_worker((*job, str(tmp_path / 'skipped'), True))
    assert scored['negativeFrames'] == skipped['negativeFrames']
    assert scored['stats']['negative-badge'] == skipped['stats']['negative-badge']


def test_replay_comparison_checks_names_and_scores():
    row = dict(recorded={'candidate': dict(name='card', score=.5)}, current={'candidate': dict(name='card', score=.5+1e-9)})
    assert matches_recorded([row])
    row['current']['candidate']['score'] = .6
    assert not matches_recorded([row])
    row['current']['candidate'] = None
    assert not matches_recorded([row])
