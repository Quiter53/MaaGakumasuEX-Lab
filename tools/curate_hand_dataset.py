"""Mark repeated hand views within the same recording and reviewed state.

The matching input is the visible artwork, with score/effect regions excluded.
Animated backgrounds and changing damage numbers do not define a new example.
Labels and states must already have been reviewed before running this command.
"""
import argparse
import json
from pathlib import Path
import sys
import types

import numpy as np
from PIL import Image


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--max-difference',type=float,default=6.0,help='Mean absolute RGB difference, 0..255')
    args=p.parse_args()
    if args.output.exists():p.error('Use a new output path')
    sys.path.insert(0,str(args.source/'agent'))
    package=types.ModuleType('custom');package.__path__=[str(args.source/'agent/custom')]
    sys.modules.setdefault('custom',package)
    from custom.hand_identity import art_box,visible_mask
    from custom.card_visual import _resize_rgb_bilinear
    manifest=json.loads((args.dataset/'manifest.json').read_text('utf-8'))
    output=[]
    for source in manifest['sources']:
        labels=json.loads((args.dataset/source['labelsFile']).read_text('utf-8'))['labels']
        kept=[]
        for row in labels:
            image=np.asarray(Image.open(args.dataset/row['file']).convert('RGB'))[:,:,::-1].copy()
            features=[]
            for box in row['boxes']:
                x,y,w,h=art_box(box)
                features.append((_resize_rgb_bilinear(image[y:y+h,x:x+w],32),visible_mask(box,row['boxes'])))
            duplicate=None
            for previous,other in kept:
                if previous['state']!=row['state'] or previous['names']!=row['names']:continue
                if not all(max(abs(a-b) for a,b in zip(x,y))<=8 for x,y in zip(row['boxes'],previous['boxes'])):continue
                differences=[]
                for (a,m),(b,n) in zip(features,other):
                    common=m&n
                    differences.append(float(np.abs(a[common]-b[common]).mean()*255) if common.sum()>=120 else float('inf'))
                if max(differences)<=args.max_difference:
                    duplicate=previous['sha256'];break
            output.append({'sha256':row['sha256'],'file':row['file'],'recordingGroup':source['videoId'],
                           'state':row['state'],'duplicateOf':duplicate})
            if duplicate is None:kept.append((row,features))
    report={'description':__doc__,'maxRgbDifference':args.max_difference,
            'total':len(output),'distinctHands':sum(r['duplicateOf'] is None for r in output),'frames':output}
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='frames'},ensure_ascii=False))


if __name__=='__main__':main()
