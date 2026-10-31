import json, os, re, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nion.codes import (compose_from_segments, mask, names_preserved, needs_translation, unmask)
from nion.engine import Engine, EchoEngine, EngineError
from nion.extract import find_data_dir, iter_entries, protected_names
from nion.memory import Memory
from nion.glossary import load_glossary, normalize_names
from nion.pipeline import apply_translations, pending_texts, scan, translate_pending


def read(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def make_game(root, mv=False):
    d = os.path.join(root, "www", "data") if mv else os.path.join(root, "data")
    write(d + "/Actors.json", [None, {"name": "Grant", "nickname": "The Hero", "profile": "A brave hero."}])
    write(d + "/System.json", {"currencyUnit": "Gold", "skillTypes": ["", "Magic"],
          "terms": {"basic": ["Level"], "commands": ["Fight", None], "params": ["Max HP"],
                    "messages": {"victory": "%1 is victorious!"}}})
    write(d + "/Items.json", [None, {"name": "Potion", "description": "Heals HP."}])
    write(d + "/Map001.json", {"displayName": "Old Town", "events": [None, {"name": "Village Elder", "pages": [{"list": [
        {"code": 101, "indent": 0, "parameters": ["", 0, 0, 2, "Elio"]},
        {"code": 401, "indent": 0, "parameters": ["\\C[2]Grant says hello\\C[0] world, \\N[1]!"]},
        {"code": 102, "indent": 0, "parameters": [["Yes", "No"], 1]},
        {"code": 402, "indent": 0, "parameters": [0, "Yes"]},
        {"code": 108, "indent": 0, "parameters": ["comment, do not translate"]},
        {"code": 0, "indent": 0, "parameters": []}]}]}]})
    write(d + "/MapInfos.json", [None, {"name": "editor only"}])
    return d


class BreakingEngine(Engine):
    """Falla en el segundo lote para probar la reanudación."""
    name = "breaking"
    max_batch = 2
    calls = 0

    def translate_batch(self, texts, src, tgt):
        BreakingEngine.calls += 1
        if BreakingEngine.calls == 2:
            raise EngineError("sin conexión")
        return ["T:" + t for t in texts]


class LossyEngine(Engine):
    """Pierde los marcadores -> debe activarse la traducción por trozos."""
    name = "lossy"

    def translate_batch(self, texts, src, tgt):
        return ["X:" + re.sub(r"\\[\\[NION_TOKEN_\\d+\\]\\]", "", t) for t in texts]


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_mask_keeps_colon_after_protected_speaker_name(self):
        masked, tokens = mask("Elio: We should hurry.", protected_terms=["Elio"])
        self.assertEqual(tokens, ["Elio:"])
        self.assertEqual(unmask(masked.replace("We should hurry.", "Debemos apresurarnos."),
                                tokens), "Elio: Debemos apresurarnos.")


    def test_code_only_mask_keeps_proper_names_visible(self):
        original = r"\\C[22]Elio: We need to find Shiori before sunset. \\V[1]"
        masked, tokens = mask(original, protected_terms=())
        self.assertEqual(tokens, [r"\\C[22]", r"\\V[1]"])
        self.assertIn("Elio", masked)
        self.assertIn("Shiori", masked)
        translated = masked.replace("We need to find", "Necesitamos encontrar a")
        restored = unmask(translated, tokens)
        self.assertTrue(names_preserved(original, restored, ["Elio", "Shiori"]))
        self.assertIn(r"\\C[22]Elio", restored)
        self.assertIn(r"Shiori antes", restored)

    def test_names_preserved_rejects_missing_name(self):
        self.assertFalse(names_preserved("Elio habló con Shiori.", "Elio habló.", ["Elio", "Shiori"]))

    def test_mask_roundtrip(self):
        t = "\\C[2]Hola\\C[0] %1 <WordWrap> \\{grande\\}"
        masked, tokens = mask(t)
        self.assertNotIn("\\C", masked)
        self.assertEqual(unmask(masked, tokens), t)
        self.assertIsNone(unmask(masked.replace("[[NION_TOKEN_0]]", ""), tokens))
        self.assertIsNone(unmask(masked + " [[NION_TOKEN_99]]", tokens))
        self.assertIsNone(unmask(masked.replace("[[NION_TOKEN_0]]", "[[NION_TOKEN_7]]"), tokens))

    def test_proper_names_are_masked_and_restored(self):
        terms = ["Grant", "Elio", "Village Elder"]
        original = "Grant habló con Elio en Village Elder."
        masked, tokens = mask(original, protected_terms=terms)
        self.assertEqual(tokens, ["Grant", "Elio", "Village Elder"])
        self.assertEqual(unmask(masked, tokens), original)
        self.assertEqual(compose_from_segments(
            original, {"habló con": "spoke with", "en": "at", ".": "."}, terms
        ), "Grant spoke with Elio at Village Elder.")

    def test_rpg_codes_and_cyrillic_roundtrip(self):
        original = r"\C[2]Привет \V[1] \N[1] \I[64] \G \{текст\} %1 %2 <WordWrap><br> \n<Grant>"
        masked, tokens = mask(original, protected_terms=["Grant"])
        self.assertEqual(unmask(masked, tokens), original)
        self.assertIn("Привет", masked)
        self.assertNotIn("\\V[1]", masked)
        self.assertTrue(needs_translation(original))

    def test_needs_translation(self):
        self.assertFalse(needs_translation("\\C[2]  %1 <br> 123"))
        self.assertTrue(needs_translation("\\C[2]Hi"))

    def test_extract_mz_and_mv(self):
        for mv in (False, True):
            with self.subTest(mv=mv):
                root = os.path.join(self.root, "mv" if mv else "mz")
                make_game(root, mv)
                data_dir = find_data_dir(root)
                texts = [entry.text for entry in iter_entries(data_dir)]
                for expected in ("Potion", "Heals HP.", "Old Town", "Yes", "No",
                                 "Gold", "Magic", "Level", "Fight", "Max HP",
                                 "%1 is victorious!", "The Hero", "A brave hero."):
                    self.assertIn(expected, texts)
                self.assertNotIn("Grant", texts)
                self.assertIn("Elio", texts)  # nombre visible del hablante
                self.assertNotIn("Village Elder", texts)  # identificador interno
                self.assertNotIn("comment, do not translate", texts)
                self.assertNotIn("editor only", texts)

    def test_names_survive_translation_and_apply(self):
        root = os.path.join(self.root, "named-game")
        data_dir = make_game(root)
        names = protected_names(data_dir)
        self.assertIn("Grant", names)
        self.assertIn("Elio", names)
        self.assertNotIn("Village Elder", names)

        memory = Memory(os.path.join(self.root, "names-memory.json"))
        _, entries = scan(root)
        translate_pending(entries, memory, EchoEngine(), "en", "es",
                          log=lambda *_: None, protected_terms=names)
        out = os.path.join(self.root, "named-out")
        apply_translations(root, out, memory)
        output = read(out + "/Map001.json")
        line = output["events"][1]["pages"][0]["list"][1]["parameters"][0]
        self.assertIn("Grant", line)
        self.assertNotIn("Elio", line)  # Elio está representado por \N[1] y su nombre no se traduce
        self.assertIn("\\C[2]", line)
        self.assertIn("\\C[0]", line)
        self.assertIn("\\N[1]", line)
        self.assertEqual(read(out + "/Actors.json")[1]["name"], "Grant")
        self.assertEqual(output["events"][1]["pages"][0]["list"][0]["parameters"][4], "Elio")

    def test_glossary_normalizes_names_and_preserves_rpg_codes(self):
        glossary = load_glossary()
        self.assertEqual(
            normalize_names(r"\C[22]Грант habló con Элио", glossary),
            r"\C[22]Grant habló con Elio",
        )
        self.assertEqual(normalize_names("Охранник", glossary), "Охранник")

    def test_russian_actor_names_and_descriptive_speakers(self):
        root = os.path.join(self.root, "russian-game")
        data_dir = make_game(root)
        actors_path = os.path.join(data_dir, "Actors.json")
        actors = read(actors_path)
        actors[1]["name"] = "Грант"
        write(actors_path, actors)

        map_path = os.path.join(data_dir, "Map001.json")
        game_map = read(map_path)
        commands = game_map["events"][1]["pages"][0]["list"]
        commands[0]["parameters"][4] = r"\C[22]Элио"
        commands.insert(1, {"code": 101, "indent": 0,
                            "parameters": ["", 0, 0, 2, "Охранник"]})
        commands.insert(2, {"code": 401, "indent": 0,
                            "parameters": ["Грант встретил Элио."]})
        write(map_path, game_map)

        glossary = load_glossary()
        names = protected_names(data_dir, glossary)
        entries = list(iter_entries(data_dir))
        self.assertIn("Охранник", [entry.text for entry in entries])
        self.assertNotIn("Охранник", names)

        memory = Memory(os.path.join(self.root, "russian-memory.json"))
        translate_pending(entries, memory, EchoEngine(), "ru", "es",
                          log=lambda *_: None, protected_terms=names, glossary=glossary)
        out = os.path.join(self.root, "russian-out")
        apply_translations(root, out, memory, glossary=glossary)

        output_actors = read(os.path.join(out, "Actors.json"))
        self.assertEqual(output_actors[1]["name"], "Grant")
        output_map = read(os.path.join(out, "Map001.json"))
        output_commands = output_map["events"][1]["pages"][0]["list"]
        self.assertEqual(output_commands[0]["parameters"][4], r"\C[22]Elio")
        self.assertEqual(output_commands[1]["parameters"][4], "[ES] Охранник")
        self.assertIn("Grant", output_commands[2]["parameters"][0])
        self.assertIn("Elio", output_commands[2]["parameters"][0])
    def test_apply_never_touches_original(self):
        root = os.path.join(self.root, "g")
        d = make_game(root)
        before = open(d + "/Items.json", encoding="utf-8").read()
        mem = Memory(os.path.join(self.root, "m.json"))
        _, entries = scan(root)
        translate_pending(entries, mem, EchoEngine(), "en", "es", log=lambda *_: None,
                          protected_terms=protected_names(d))
        out = os.path.join(self.root, "out")
        applied, missing = apply_translations(root, out, mem, log=lambda *_: None)
        self.assertEqual(open(d + "/Items.json", encoding="utf-8").read(), before)
        self.assertEqual(read(out + "/Items.json")[1]["name"], "[ES] Potion")
        self.assertEqual(read(out + "/MapInfos.json")[1]["name"], "editor only")
        self.assertGreater(applied, 5)
        with self.assertRaises(EngineError):
            apply_translations(root, d, mem, log=lambda *_: None)

    def test_codes_survive(self):
        root = os.path.join(self.root, "g")
        make_game(root)
        mem = Memory(os.path.join(self.root, "m.json"))
        _, entries = scan(root)
        translate_pending(entries, mem, EchoEngine(), "en", "es", log=lambda *_: None,
                          protected_terms=protected_names(root + "/data"))
        out = os.path.join(self.root, "out")
        apply_translations(root, out, mem, log=lambda *_: None)
        line = read(out + "/Map001.json")["events"][1]["pages"][0]["list"][1]["parameters"][0]
        self.assertIn("\\C[2]", line)
        self.assertIn("\\C[0]", line)
        self.assertIn("\\N[1]", line)

    def test_fallback_when_engine_loses_placeholders(self):
        root = os.path.join(self.root, "g")
        make_game(root)
        mem = Memory(os.path.join(self.root, "m.json"))
        _, entries = scan(root)
        translate_pending(entries, mem, LossyEngine(), "en", "es", log=lambda *_: None,
                          protected_terms=protected_names(root + "/data"))
        out = os.path.join(self.root, "out")
        apply_translations(root, out, mem, log=lambda *_: None)
        line = read(out + "/Map001.json")["events"][1]["pages"][0]["list"][1]["parameters"][0]
        self.assertTrue(line.startswith("\\C[2]Grant"), line)
        self.assertIn("X:says hello", line)
        self.assertIn("\\N[1]", line)

    def test_resume_after_failure(self):
        root = os.path.join(self.root, "g")
        make_game(root)
        path = os.path.join(self.root, "m.json")
        data_dir, entries = scan(root)
        names = protected_names(data_dir)
        BreakingEngine.calls = 0
        with self.assertRaises(EngineError):
            translate_pending(entries, Memory(path), BreakingEngine(), "en", "es", log=lambda *_: None,
                              protected_terms=names)
        saved = len(Memory(path))
        self.assertGreater(saved, 0)
        mem = Memory(path)
        before = len(pending_texts(entries, mem, names))
        BreakingEngine.calls = 10
        translate_pending(entries, mem, BreakingEngine(), "en", "es", log=lambda *_: None,
                          protected_terms=names)
        self.assertEqual(len(pending_texts(entries, mem, names)), 0)
        self.assertGreater(before, 0)

    def test_old_segment_cache_is_reused(self):
        mem = Memory(os.path.join(self.root, "m.json"))
        mem.set("Hello", "Hola")
        mem.set("world,", "mundo,")
        self.assertEqual(compose_from_segments(
            "\\C[2]Hello\\C[0] world, \\N[1]!", mem
        ), "\\C[2]Hola\\C[0] mundo, \\N[1]!")
        self.assertIsNone(compose_from_segments("Unknown", mem))


if __name__ == "__main__":
    unittest.main()
