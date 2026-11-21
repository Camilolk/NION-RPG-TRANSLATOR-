import unittest
from nion.repair_propose import propose

class FakeEngine:
    def __init__(self):
        self.calls = []
    def translate_batch(self, texts, src, tgt):
        self.calls.extend(texts)
        return ["¡No!" for _ in texts]

class ProposalTests(unittest.TestCase):
    def test_limit_and_original_unchanged(self):
        rows = [
            {"original": "N-No!!", "traduccion_actual": "¡" * 100, "propuesta": "", "aprobado": False},
            {"original": "Stop!!!", "traduccion_actual": "¡" * 100, "propuesta": "", "aprobado": False},
        ]
        engine = FakeEngine()
        result = propose(rows, engine, limit=1)
        self.assertEqual(len(engine.calls), 1)
        self.assertEqual(rows[0]["propuesta"], "")
        self.assertEqual(result[0]["propuesta"], "¡No!")
        self.assertFalse(result[0]["aprobado"])
        self.assertEqual(result[1]["propuesta"], "")

if __name__ == "__main__":
    unittest.main()
