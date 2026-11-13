"""Native counterfactual check: battle entry depends on SKIP text, not its icon."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from maa.controller import CustomController
from maa.pipeline import JOCR
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--image', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
args = p.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
Toolkit.init_option(str(args.output))
resource = Resource()
resource.use_cpu()
assert resource.post_bundle(str(args.source / 'assets/resource/base')).wait().succeeded

class Offline(CustomController):
    def connect(self): return True
    def request_uuid(self): return 'lab-icon-contract'
    def screencap(self): return np.zeros((1280, 720, 3), np.uint8)
    def get_features(self): return 0
    def click(self, *args): raise AssertionError('Input forbidden')
    def swipe(self, *args): raise AssertionError('Input forbidden')

controller = Offline()
assert controller.post_connection().wait().succeeded
tasker = Tasker()
assert tasker.bind(resource, controller)
node = resource.get_node_data('ProduceRecognitionSkipRound')['recognition']
assert node['type'] == 'OCR', 'Battle entry still depends on changing icon artwork'
params = JOCR(**node['param'])
frame = np.asarray(Image.open(args.image).convert('RGB'))[:, :, ::-1].copy()
records = []
for mutation, roi, expected in [('erase-icon', (628, 746, 700, 783), True), ('erase-label', (628, 783, 700, 820), False)]:
    changed = frame.copy()
    x1, y1, x2, y2 = roi
    changed[y1:y2, x1:x2] = 240
    result = tasker.post_recognition('OCR', params, changed).wait().get().nodes[0].recognition
    assert bool(result.hit) == expected, mutation
    records.append({'mutation': mutation, 'expected': expected, 'actual': bool(result.hit),
                    'frameSha256': hashlib.sha256(changed.tobytes()).hexdigest()})
report = {'passed': True, 'synthetic': True, 'sourceImageSha256': hashlib.sha256(args.image.read_bytes()).hexdigest(),
          'pipelineSha256': hashlib.sha256((args.source / 'assets/resource/base/pipeline/ProduceUtils.json').read_bytes()).hexdigest(),
          'cases': records, 'input': 'disabled'}
(args.output / 'report.json').write_text(json.dumps(report, indent=2), 'utf-8')
print(json.dumps(report))
