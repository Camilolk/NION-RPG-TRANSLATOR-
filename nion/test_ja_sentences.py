"""Pruebas de segmentación japonesa sin descargar modelos."""
import unittest
from .ja_sentences import split_sentences_safe


class SentenceTests(unittest.TestCase):
    def test_preserves_punctuation(self):
        text = "Can you see me? You must be powerful. That's strange!"
        self.assertEqual(split_sentences_safe(text), [
            "Can you see me? ", "You must be powerful. ", "That's strange!"
        ])

    def test_roundtrip(self):
        samples = [
            "You really are, son! Make sure to keep her close. It'd be bad...",
            "A vest made of tanned hide.",
            "Wait!  Please stay.",
            "Mr. Smith is here. Hello!",
            "Woah... This is strange.",
            r"Hello \\V[1]! How are you?",
            "%1 is blinded! What now?",
            "One sentence.",
            "",
        ]
        for text in samples:
            with self.subTest(text=text):
                self.assertEqual("".join(split_sentences_safe(text)), text)

    def test_protect_rpg_codes(self):
        for text in (r"Hello \\V[1]! How are you?", "%1 is blinded! What now?"):
            self.assertEqual(split_sentences_safe(text), [text])

    def test_abbreviations(self):
        self.assertEqual(split_sentences_safe("Mr. Smith is here. Hello!"),
                         ["Mr. Smith is here. ", "Hello!"])


if __name__ == "__main__":
    unittest.main()
