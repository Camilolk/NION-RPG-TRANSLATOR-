import unittest
from nion.repair import build_review

class RepairTests(unittest.TestCase):
    def test_only_severe(self):
        data = {
            "Goblin": "Goblin",
            "Hello there": "Hola",
            "N-No!!": "¡" * 100,
            "What is happening to me in this strange place?": "¿Qué?",
        }
        result = build_review(data)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(not row["aprobado"] and not row["propuesta"] for row in result))
    def test_no_mutation(self):
        memory = {"N-No!!": "¡" * 100}
        before = dict(memory)
        build_review(memory)
        self.assertEqual(memory, before)

if __name__ == "__main__":
    unittest.main()
