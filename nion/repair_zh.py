"""Reparación puntual y reversible de 32 textos chinos; por defecto solo vista previa."""
import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from nion.codes import CODE_RE
from nion.extract import protected_names
from nion.glossary import load_glossary
from nion.memory import Memory
from nion.pipeline import pending_texts, scan

TRANSLATIONS = json.loads(r'''{
  "E\\|...\\|li....\\|o...\\|-k...un!": "E\\|...\\|li....\\|o...\\|-君！",
  "your power without much trouble. And from there, I'll help you strengthen it.": "你的力量应该不会遇到太大困难。之后，我会帮你进一步增强它。",
  "Fuck. I gotta jerk off now. My mind is going wild, but I need some patience.": "该死。我现在真想自慰。脑子里全是乱七八糟的念头，但我得忍耐一下。",
  "(Eheheh...\\| I might do it with him soon... I can't believe it. After so long.": "（嘿嘿……\\| 我可能很快就会和他做那件事……真不敢相信，过了这么久。）",
  "\\|*pat* \\|*pat*.": "\\|*轻拍* \\|*轻拍*。",
  "Grrrrrr.....": "Grrrrrr.....",
  "MMmm... *Chu* ": "唔嗯……*啾* ",
  "Wait for me outside!": "在外面等我！",
  "Woah, so you can see me? You must be a really powerful mage. That's quite a difficult": "哇，你竟然能看见我？你一定是个非常强大的魔法师。这可是相当困难的",
  "*ahem*.": "*清嗓子*。",
  "Ahhh! What?! I don't want to get in trouble, no no no...!": "啊啊！什么？！我可不想惹麻烦，不不不……！",
  "Weird Man": "奇怪的男人",
  "*Huff... Huff...*": "*呼……呼……*",
  "C-C...an.... yo-... h-..r.. e....? E..-lio!": "你……你能……听……见……吗？艾……利奥！",
  "\\|...*shrug*.": "\\|……*耸肩*。",
  "E\\|...\\|li....\\|o...\\|-k...un....?": "E\\|...\\|li....\\|o...\\|-君……？",
  "You really are, son! Make sure to keep her close. It'd be bad if someone took her away...": "你可真是啊，儿子！一定要把她留在身边。要是被别人抢走就不好了……",
  "ha.... ah... ha....": "哈……啊……哈……",
  "*squish...\\| shlick...*\\!": "*噗叽……\\| 啪唧……*\\!",
  "Haah... hngggg....aahh...": "哈啊……嗯呃……啊啊……",
  "Nnnm... mlmm... Sllrp... mmm...": "嗯唔……唔嗯……啧啧……嗯……",
  "Heeh. Haaah... Huh.. huhh.....!": "嘿……哈啊……呼……呼……！",
  "*yawns...*": "*打哈欠……*",
  "*Huff... huff...* Not too shabby.": "*呼……呼……* 还不赖。",
  "Ngh... hah...": "嗯呃……哈……",
  "I wanna go home...": "我想回家……",
  "your reasons.": "你的理由。",
  "\\}Ghlkgklh... hghnn.... *puaah*": "\\}咕噜咕噜……嗯呃……*噗哈*",
  "\\}Ahhnn... mnmmnn.... Slurp... schlk... slurp...": "\\}啊嗯……唔嗯……啧啧……啪唧……啧啧……",
  "\\}Really now? But you're looking pretty worked up yourself!": "\\}是吗？可你自己看起来也相当兴奋啊！",
  "%1 is blinded!": "%1失明了！",
  "%1 %2 received!": "%1获得了%2！"
}''')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", help="Ruta de data_ingles")
    parser.add_argument("--memory", required=True, help="Memoria china JSON")
    parser.add_argument("--commit", action="store_true", help="Guardar tras validar y respaldar")
    args = parser.parse_args()
    path = Path(args.memory)
    if not path.is_file():
        parser.error("No se encontró la memoria: " + str(path))
    data_dir, entries = scan(args.game)
    glossary = load_glossary()
    names = protected_names(data_dir, glossary)
    memory = Memory(str(path))
    pending = pending_texts(entries, memory, names, glossary)
    unknown = [s for s in pending if s not in TRANSLATIONS]
    if unknown:
        print("Se encontraron textos pendientes no contemplados:")
        for s in unknown[:10]:
            print(repr(s))
        parser.error("La lista cambió. No se modificó la memoria.")
    issues = []
    for src in pending:
        dst = TRANSLATIONS[src]
        if CODE_RE.findall(src) != CODE_RE.findall(dst):
            issues.append((src, "códigos RPG Maker diferentes"))
        if sorted(__import__("re").findall(r"%[1-9]\\d*", src)) != sorted(__import__("re").findall(r"%[1-9]\\d*", dst)):
            issues.append((src, "variables %n diferentes"))
    if issues:
        for src, why in issues:
            print(why, repr(src))
        parser.error("Validación fallida. No se modificó la memoria.")
    print("Pendientes actuales:", len(pending), "| Propuestas válidas:", len(pending))
    for i, src in enumerate(pending, 1):
        print(f"{i:02d} EN: {src!r}")
        print(f"   ZH: {TRANSLATIONS[src]!r}")
    if not args.commit:
        print("VISTA PREVIA: memoria sin modificar. Usa --commit si apruebas las traducciones.")
        return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(path.name + ".before-zh-repair-" + stamp + ".bak")
    shutil.copy2(path, backup)
    for src in pending:
        memory.set(src, TRANSLATIONS[src])
    memory.save()
    remaining = pending_texts(entries, memory, names, glossary)
    print("RESPALDO:", backup)
    print("GUARDADO:", path, "| Pendientes restantes:", len(remaining))
    if remaining:
        print("Algunos textos aún necesitan revisión:", len(remaining))

if __name__ == "__main__":
    main()
