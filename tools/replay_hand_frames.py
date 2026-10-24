"""Read-only native detection and paired identity replay of extracted video frames.

Predictions are provisional. Human-reviewed labels are required before reporting
accuracy; the contact sheets deliberately omit predicted names.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image, ImageDraw

from evaluate_badge_matching import BASELINE, prepare, ROOT


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=ROOT/'source')
    p.add_argument('--baseline', default=BASELINE)
    p.add_argument('--frames', type=Path, required=True)
    p.add_argument('--stride', type=int, default=1)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        p.error('Use a new output directory')
    args.output.mkdir(parents=True)
    _, _, _, _, candidate, baseline = prepare(args.source, ROOT, args.baseline)
    from custom.hand_identity import hand_boxes
    from maa.toolkit import Toolkit
    from maa.resource import Resource
    from maa.pipeline import JNeuralNetworkDetect
    from maa.controller import CustomController
    from maa.tasker import Tasker
    Toolkit.init_option(str(args.output.resolve()))

    class ReadOnly(CustomController):
        def connect(self): return True
        def request_uuid(self): return 'video-offline-evaluation'
        def screencap(self): return np.zeros((1280,720,3),np.uint8)
        def get_features(self): return 0
        def click(self,*args): raise RuntimeError('Game input is disabled')
        def swipe(self,*args): raise RuntimeError('Game input is disabled')
    resource = Resource()
    resource.use_cpu()
    assert resource.post_bundle(str(args.source/'assets/resource/base')).wait().succeeded
    controller = ReadOnly()
    assert controller.post_connection().wait().succeeded
    tasker = Tasker()
    assert tasker.bind(resource,controller)
    params = JNeuralNetworkDetect(**resource.get_node_data('ProduceRecognitionCards')['recognition']['param'])
    records = []
    files = sorted(args.frames.rglob('*.png'))[::args.stride]
    for n, path in enumerate(files):
        with Image.open(path) as img:
            rgb = np.asarray(img.convert('RGB'))
        assert rgb.shape == (1280,720,3)
        bgr = rgb[:,:,::-1].copy()
        detail = tasker.post_recognition('NeuralNetworkDetect',params,bgr).wait().get()
        rows = detail.nodes[0].recognition.all_results
        boxes = hand_boxes(rows)
        record = dict(index=n, file=str(path.resolve()), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                      labelsVerified=False, boxes=boxes, detector=[dict(label=r.label,box=list(r.box),score=r.score) for r in rows],
                      baseline=[],candidate=[],timingMs={})
        for tag,reader in [('baseline',baseline),('candidate',candidate)]:
            start=time.perf_counter()
            for box in boxes:
                result=reader.read(bgr,box,boxes)
                record[tag].append(asdict(result) if result else None)
            record['timingMs'][tag]=(time.perf_counter()-start)*1000
        records.append(record)
        if n%10==0:print(f'Replayed {n+1}/{len(files)} frames',flush=True)
    (args.output/'predictions.json').write_text(json.dumps({'scope':__doc__,'records':records},ensure_ascii=False,indent=2),'utf-8')
    selected=[r for r in records if r['boxes']]
    for page in range((len(selected)+9)//10):
        sheet=Image.new('RGB',(1440,5*380),'#dddddd');draw=ImageDraw.Draw(sheet)
        for cell,row in enumerate(selected[page*10:page*10+10]):
            x,y=(cell%2)*720,(cell//2)*380
            with Image.open(row['file']) as im:
                sheet.paste(im.crop((0,810,720,1160)),(x,y+28))
            draw.text((x+5,y+5),f"frame {row['index']} | {Path(row['file']).parent.name}/{Path(row['file']).name} | {len(row['boxes'])} boxes",fill='black')
        sheet.save(args.output/f'review-{page:02d}.jpg',quality=95)
    print(json.dumps({'frames':len(records),'framesWithHand':len(selected),'cards':sum(len(r['boxes']) for r in records),
                      'badgeRecoveries':sum(bool(v and v.get('badge_recovered')) for r in records for v in r['candidate']),
                      'labelsVerified':False}),flush=True)


if __name__=='__main__':
    main()
