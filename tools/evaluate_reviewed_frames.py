"""Score paired frame predictions against separately reviewed card names."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import unicodedata


def key(name):
    return ''.join(unicodedata.normalize('NFKC',name).strip().rstrip('+').split()) if name else None


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--predictions',type=Path,required=True)
    p.add_argument('--labels',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--curation',type=Path,help='Exclude reviewed near-duplicate hand views')
    args=p.parse_args()
    predictions={r['sha256']:r for r in json.loads(args.predictions.read_text('utf-8'))['records']}
    labels=json.loads(args.labels.read_text('utf-8'))
    duplicates=set()
    if args.curation:
        duplicates={r['sha256'] for r in json.loads(args.curation.read_text('utf-8'))['frames'] if r['duplicateOf']}
    stats=defaultdict(lambda:{'baseline':Counter(),'candidate':Counter()})
    failures=[]
    for label in labels['labels']:
        if label['sha256'] in duplicates:continue
        row=predictions[label['sha256']]
        assert row['sha256']==label['sha256'], 'Frame changed since review'
        assert len(label['names'])==len(row['boxes'])
        for tag in ['baseline','candidate']:
            all_correct=True
            for slot,(expected,value) in enumerate(zip(label['names'],row[tag])):
                got=value['name'] if value else None
                outcome='unknown' if got is None else 'correct' if key(got)==key(expected) else 'wrong'
                all_correct &= outcome=='correct'
                for group in ['all',label['state'],'badge' if slot in label['visibleBadgeSlots'] else 'no-badge']:
                    stats[group][tag].update(total=1,**{outcome:1})
                if outcome!='correct':
                    failures.append({'index':label['index'],'slot':slot,'state':label['state'],'tag':tag,
                                     'expected':expected,'result':value})
            stats[label['state']][tag].update(frames=1,wholeFrameCorrect=int(all_correct))
    report={'scope':labels['scope'],'sourceUrl':labels['sourceUrl'],'split':labels['split'],
            'recordingGroup':labels['recordingGroup'],'deduplicated':bool(args.curation),
            'stats':{k:{t:dict(c) for t,c in v.items()} for k,v in stats.items()},
            'failures':failures,'labelsFile':str(args.labels),'predictionsFile':str(args.predictions)}
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(report['stats'],ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
