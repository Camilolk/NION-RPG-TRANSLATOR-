import unittest

from nion.segment_recovery import split_dialogue
from nion.guarded_translate import translate_guarded


class SegmentRecoveryTests(unittest.TestCase):
    def test_splits_simple_multisentence_dialogue(self):
        source = "I get you, don't worry! Did it work out? And what about the device?"
        self.assertEqual(split_dialogue(source), [
            "I get you, don't worry!", "Did it work out?", "And what about the device?"
        ])

    def test_does_not_split_rpg_codes_or_stuttering(self):
        self.assertEqual(split_dialogue(r"\\C[2]Hello! How are you?"), [])
        self.assertEqual(split_dialogue("N-No!! What happened?"), [])

    def test_recovers_omitted_sentences(self):
        class Engine:
            max_batch = 1
            def translate_batch(self, texts, src, tgt):
                return ["¿Funcionó?"]
            def translate_repair(self, text, src, tgt):
                return {
                    "I get you, don't worry!": "Entiendo, no te preocupes!",
                    "Did it work out?": "¿Salió bien?",
                    "And what about the device?": "¿Y el dispositivo?",
                }.get(text, "¿Funcionó?")
        rows = translate_guarded(
            ["I get you, don't worry! Did it work out? And what about the device?"],
            Engine(),
        )
        self.assertTrue(rows[0]["recuperacion_segmentada"])
        self.assertEqual(rows[0]["estado"], "reparada")
        self.assertEqual(rows[0]["traduccion"].count("?"), 2)

    def test_invalid_segments_stay_quarantined(self):
        class Engine:
            max_batch = 1
            def translate_batch(self, texts, src, tgt):
                return ["¿Funcionó?"]
            def translate_repair(self, text, src, tgt):
                return "¡" * 50
        rows = translate_guarded(
            ["I get you, don't worry! Did it work out? And what about the device?"],
            Engine(),
        )
        self.assertEqual(rows[0]["estado"], "cuarentena")
        self.assertFalse(rows[0]["recuperacion_segmentada"])


if __name__ == "__main__":
    unittest.main()
