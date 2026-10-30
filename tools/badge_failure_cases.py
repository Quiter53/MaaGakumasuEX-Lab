"""Lossless, per-frame evidence for synthetic negative acceptance (RGB on disk)."""
from dataclasses import asdict
import hashlib
import html
import json
from pathlib import Path

import numpy as np
from PIL import Image


def pixel_hash(image):
    return hashlib.sha256(np.ascontiguousarray(image).tobytes()).hexdigest()


def tuple_state(value):
    return tuple(tuple_state(v) for v in value) if isinstance(value, list) else value


def negative_frame(synth, frames, cat, names, rng, patch, seed, index, hard, add_badge):
    """Keep the historical RNG calls/order exactly; return replacement evidence."""
    image, boxes, _ = synth.compose(frames, cat, names, rng, 3, hard=hard)
    replacements = []
    for box in boxes:
        x, y, w, h = box
        art_h = round(h * .865)
        noise_seed = seed + index + x
        noise = np.random.default_rng(noise_seed)
        kind = 'noise' if index % 2 else 'solid'
        pixels = noise.integers(0, 256, (art_h, w, 3) if index % 2 else 3, dtype=np.uint8)
        image[y:y+art_h, x:x+w] = pixels
        replacements.append(dict(kind=kind, seed=noise_seed, rect=[x, y, w, art_h],
                                 color=pixels.tolist() if kind == 'solid' else None))
        add_badge(image, box, boxes, patch, rng)
    return image, boxes, replacements


def result_dict(result):
    return asdict(result) if result is not None else None


def save_negative_frame(directory, case_id, image, boxes, context, rows):
    """Record every negative prediction, independently of change caps or equality."""
    record = dict(id=case_id, expected=None, boxes=boxes, imageShape=list(image.shape),
                  imageSha256=pixel_hash(image), **context, cards=rows)
    failures = [row['slot'] for row in rows if any(
        row[tag] is not None and row[tag]['name'] is not None for tag in ('baseline', 'candidate'))]
    record['failureSlots'] = failures
    if failures:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        name = case_id + '.png'
        temporary = directory / (name + '.tmp')
        Image.fromarray(image).save(temporary, format='PNG')
        with Image.open(temporary) as saved:
            if pixel_hash(np.asarray(saved.convert('RGB'))) != record['imageSha256']:
                raise ValueError(f'Saved PNG differs from the evaluated frame: {case_id}')
        temporary.replace(directory / name)
        record['image'] = name
        (directory / (case_id + '.json')).write_text(json.dumps(record, ensure_ascii=False, indent=2), 'utf-8')
    return record


def write_index(directory, records):
    cards = []
    for record in records:
        if record['failureSlots']:
            details = json.dumps({k: v for k, v in record.items() if k != 'rngState'}, ensure_ascii=False, indent=2)
            height, width = record['imageShape'][:2]
            rectangles = ''.join(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
                                 f'fill="none" stroke="red" stroke-width="2"><title>slot {i}</title></rect>'
                                 for i, (x, y, w, h) in enumerate(record['boxes']))
            cards.append(f'<article><h2>{html.escape(record["id"])}</h2>'
                         f'<svg width="360" viewBox="0 0 {width} {height}">'
                         f'<image width="{width}" height="{height}" href="{html.escape(record["image"], quote=True)}"/>'
                         f'{rectangles}</svg>'
                         f'<pre>{html.escape(details)}</pre></article>')
    Path(directory, 'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>合成负样本错误接受</title>'
        '<style>body{font:16px sans-serif}article{display:flex;gap:20px;flex-wrap:wrap;'
        'border-bottom:1px solid #aaa}pre{white-space:pre-wrap;max-width:900px}</style>'
        '<h1>合成负样本错误接受</h1><p>框为合成输入框；分数是相似度，非概率。'
        '所有基线或候选接受的负样本均列出，不代表实机错误率。</p>' + ''.join(cards), 'utf-8')
