"""Regression tests for TextFit v2 event pagination."""
import unittest

from nion.textfit import fit_commands, visible_width


class TextFitPaginationTests(unittest.TestCase):
    def test_latos_paginated_and_preserves_next_event(self):
        header = {"code": 101, "indent": 0, "parameters": ["", 0, 0, 2, r"\C[28]Latos"]}
        original = [
            "Así que lo que estamos viendo ahora es probablemente una combinación de los efectos de",
            "y la corrupción que se propaga por el aire.",
            "Mana está en todas partes, incluso en el aire que respiramos, y la Corrupción lo está afectando.",
        ]
        commands = [header] + [
            {"code": 401, "indent": 0, "parameters": [line]} for line in original
        ] + [{"code": 213, "indent": 0, "parameters": [73, 7, True]}]
        fixed, skipped = fit_commands(commands, max_width=48)
        self.assertEqual((fixed, skipped), (1, 0))
        self.assertEqual(commands[-1]["code"], 213)
        headers = [c for c in commands if c["code"] == 101]
        self.assertGreater(len(headers), 1)
        self.assertTrue(all(h["parameters"] == header["parameters"] for h in headers))
        self.assertTrue(all(visible_width(c["parameters"][0]) <= 48
                            for c in commands if c["code"] == 401))
        for idx, cmd in enumerate(commands):
            if cmd["code"] == 101:
                count = 0
                for following in commands[idx + 1:]:
                    if following["code"] != 401:
                        break
                    count += 1
                self.assertLessEqual(count, 4)
        self.assertEqual(
            " ".join(c["parameters"][0] for c in commands if c["code"] == 401),
            " ".join(original),
        )

    def test_codes_skipped(self):
        commands = [
            {"code": 101, "indent": 0, "parameters": ["", 0, 0, 2]},
            {"code": 401, "indent": 0, "parameters": [r"\V[1] " + "hello " * 20]},
        ]
        before = repr(commands)
        self.assertEqual(fit_commands(commands, 48), (0, 1))
        self.assertEqual(repr(commands), before)

    def test_short_message_unchanged(self):
        commands = [
            {"code": 101, "indent": 0, "parameters": ["", 0, 0, 2]},
            {"code": 401, "indent": 0, "parameters": ["Hola."]},
        ]
        before = repr(commands)
        self.assertEqual(fit_commands(commands, 48), (0, 0))
        self.assertEqual(repr(commands), before)


if __name__ == "__main__":
    unittest.main()
