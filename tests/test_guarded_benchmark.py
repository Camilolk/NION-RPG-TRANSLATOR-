import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nion import guarded_benchmark


class BenchmarkTests(unittest.TestCase):
    def test_report_without_real_model(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "result.json"
            fake = [{"original": "Hello", "traduccion": "Hola",
                     "estado": "lista", "alertas": [], "reintento": False}]
            with patch.object(guarded_benchmark, "translate_guarded", return_value=fake):
                with patch.object(guarded_benchmark, "MarianEngine"):
                    self.assertEqual(guarded_benchmark.main(
                        ["--limit", "1", "--out", str(out)]), 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["total"], 1)
            self.assertEqual(data["estados"], {"lista": 1})

    def test_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "existing.json"
            out.write_text("untouched", encoding="utf-8")
            with self.assertRaises(SystemExit):
                guarded_benchmark.main(["--out", str(out)])
            self.assertEqual(out.read_text(encoding="utf-8"), "untouched")


if __name__ == "__main__":
    unittest.main()
