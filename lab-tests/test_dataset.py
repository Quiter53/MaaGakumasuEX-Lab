"""Data leakage and annotation failures must stop before expensive training."""
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from train import validate


class DatasetChecks(unittest.TestCase):
    def setUp(self):
        temporary_root = Path(__file__).resolve().parents[1] / "outputs/test-tmp"
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temporary_root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data.yaml"
        self.data.write_text(yaml.safe_dump(dict(train="images/train", val="images/val",
            names=["cards", "suggestions", "useless"])), "utf-8")
        for split, color in [("train", "red"), ("val", "green")]:
            image = self.root / "images" / split / "frame.png"
            label = self.root / "labels" / split / "frame.txt"
            image.parent.mkdir(parents=True)
            label.parent.mkdir(parents=True)
            Image.new("RGB", (720, 1280), color).save(image)
            label.write_text("0 0.5 0.5 0.2 0.2\n", "utf-8")

    def test_portable_yaml_is_independent_of_process_working_directory(self):
        self.assertEqual(1, validate(self.data)["splits"]["train"]["images"])

    def test_same_pixels_in_different_file_names_cannot_leak_between_splits(self):
        Image.new("RGB", (720, 1280), "red").save(self.root / "images/val/frame.png")
        with self.assertRaisesRegex(ValueError, "Duplicate frame"):
            validate(self.data)

    def test_missing_labels_are_not_silently_treated_as_negative_samples(self):
        (self.root / "labels/train/frame.txt").unlink()
        with self.assertRaisesRegex(ValueError, "Missing annotation"):
            validate(self.data)

    def test_wrong_class_order_and_nonfinite_coordinates_are_rejected(self):
        (self.root / "labels/train/frame.txt").write_text("1 nan 0.5 0.2 0.2", "utf-8")
        with self.assertRaisesRegex(ValueError, "normalized"):
            validate(self.data)
        self.data.write_text(yaml.safe_dump(dict(train="images/train", val="images/val",
            names=["suggestions", "cards", "useless"])), "utf-8")
        with self.assertRaisesRegex(ValueError, "class IDs"):
            validate(self.data)


if __name__ == "__main__":
    unittest.main()
