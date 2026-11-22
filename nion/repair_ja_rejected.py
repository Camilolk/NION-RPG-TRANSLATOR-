"""Reparación manual de los 38 rechazos japoneses, con respaldo y comprobaciones.

Vista previa por defecto. --commit aplica solo las coincidencias exactas.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil

from .codes import CODE_RE
from .memory import Memory

PAIRS = [
("Fuck them. Especially those  girls in", "あいつらなんかくそくらえだ。特に、あそこにいるあの女の子たちは"),
("This brought enormous change. The Kingdom quickly adapted and", "これによって大きな変化がもたらされた。王国はすぐに適応し、"),
("(Ughh... Good... Yeah... Let me flip the page...)", "（うぅ……いいぞ……そうだ……ページをめくろう……）"),
("Fuck off with your crap! I don't care about this bullshit,", "くだらないことを言うな！ そんなたわ言はどうでもいい、"),
("That's e-enough... it's t-too much... I've... already... too many... nghhhhh....!!!", "も、もう十分……や、やりすぎだ……もう……すでに……多すぎる……んぐぅぅ……！！！"),
("Woah, nee-san! You have really huge boobies! Can I rub them? Pleaaaase?", "うわあ、お姉さん！ すっごく胸が大きいね！ 触ってもいい？ お願いだよぉ！"),
("What the hell is it that you want?! You want some too like the other guy?!", "いったい何が望みなの？！ あんたもあの男みたいに欲しいっていうの？！"),
("(Uhmm... I've been thinking about it too often... maybe there's something wrong", "（うーん……最近そのことばかり考えてる……もしかして何かおかしいのかも"),
("O-Of course not. I just want you to relax. It's not weird to want that,", "も、もちろん違うよ。ただリラックスしてほしいだけだ。それを望むのは変なことじゃないし、"),
("What...!?! H-How dare you!!?! You took of my... bra...nnghh...!", "なっ……！？ よ、よくもそんなことを！！ 私の……ブラを外したなんて……んんっ……！"),
("(Huh... he actually did stop...)", "（あれ……本当にやめてくれた……）"),
("A-Ahah... I accidentally consumed it the first time I used the Arca Purger... I'm sorry,", "あ、あはは……初めてアルカ・パージャーを使ったとき、うっかり使い切っちゃって……ごめんなさい、"),
("Heheheh! Hell yeaah! Take your boobs out! Come on! I'll throw some gold in!", "へへへ！ いいぞぉ！ 胸を出してみろよ！ ほら！ 金貨も投げてやるぜ！"),
("He will! I'm sure of it! He just needs a little more time to get to know you.", "きっとそうするよ！ 間違いない！ 君のことをもっと知る時間が少し必要なだけだ。"),
("(Heh, finally. Let's see how far this goes.)", "（へっ、やっとだ。どこまで進むか見てみよう。）"),
("(F-Fuck. It's too good. I'm... cumming!)", "（く、くそっ。気持ちよすぎる。い、イク……！）"),
("Hmm.. hmmmm ♫ Of course you wouldn't. I'm too good, you know?", "ふん……ふふーん♫ 当然そんなことできないよね。私ってすごいんだから。"),
("Hmmm? My, my. You're something else. Just you two managed to achieve this by", "んん？ あらあら、あなたたちは大したものね。たった二人でここまで成し遂げるなんて"),
("Ahh. Ahhhnnn...~! So good! T-That spot right there...! Yes!", "ああっ……あぁん……っ！ 気持ちいい！ そ、そこ……！ そうっ！"),
("B-Besides, I really want to try and get on your dad’s good side before anything", "そ、それに、何より先に君のお父さんに気に入ってもらいたいんだ"),
("Ahahahah!! Eat that, you dumb mutts!", "あはははっ！！ ざまあみろ、この間抜けな犬ども！"),
("(Woah. I've never seen him going all out like this.)", "（うわあ。あいつがここまで本気を出すところ、初めて見た。）"),
("Just your boobs! I mean... I've already touched them, and they're already out.", "胸だけだよ！ だって……もう触ったし、今だって出てるじゃないか。"),
("(Heh... she's barely putting up a fight anymore. Look at how red she is.", "（へへ……もうほとんど抵抗してないな。あんなに顔を赤くしてる。"),
("*Whisper* Y-Yeah... I have to keep him on track after all... *Whisper*", "＊小声＊ う、うん……やっぱり彼が道を踏み外さないようにしないと……＊小声＊"),
("Aaah.... aaa... nnnmh....!", "ああっ……あぁ……んんっ……！"),
("Erika!!!!!!!!", "エリカ!!!!!!!!"),
("Aaaaaaaaaaaaghhhh!!", "ああああああああっ！！"),
("Uuuaaaaaaaggghhhhhh!!", "うわああああああっ！！"),
("(Heheh, this might be my chance to take upon that offer from earlier...)", "（へへっ、さっきの申し出を受けるチャンスかもしれない……）"),
("What... what do you even want now? The blowjob thing? I... that's too much, I don't think", "な……今度は何が望みなの？ フェラのこと？ わ、私には無理よ、そんなの……"),
("How about just the tip, then? A blowjob means taking the whole thing.", "じゃあ、先っぽだけならどう？ フェラっていうのは全部くわえることだから。"),
("(Ngh... so disgusting... some of the liquid leaking from the tip is coating my tongue...", "（んぐっ……気持ち悪い……先端から漏れた液体が舌にまとわりついてる……"),
("(Nghh... I better get this taken care of already...", "（んんっ……もうさっさと片づけたほうがいい……"),
("Aahhhnn... (H-He's touching my...!)", "あぁん……（か、彼が私の……に触ってる……！）"),
("Hey, hey, hey... just relax and take it. You're frustrated.", "おいおいおい……落ち着いて受け入れろよ。欲求不満なんだろ。"),
("Y-You mean... you want to give me a blowjob?", "つ、つまり……私にフェラをしてくれるってこと？"),
("Ehehehe! Of course you couldn't! Gob smell you all over! Eheheh!", "えへへへ！ そりゃ無理だよ！ ゴブにはお前の匂いがぷんぷんするもん！ えへへ！"),
]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--memory", required=True)
    p.add_argument("--commit", action="store_true")
    args = p.parse_args()
    path = Path(args.memory)
    if path.name != "nion_memory_en_ja_nllb.json" or not path.is_file():
        p.error("Se requiere la memoria japonesa NLLB existente (no la antigua).")
    rejected_path = Path(str(path) + ".rejected.json")
    if not rejected_path.is_file():
        p.error("Falta el registro de rechazos.")
    with rejected_path.open(encoding="utf-8") as f:
        rejected = json.load(f)
    translations = dict(PAIRS)
    if len(PAIRS) != 38 or len(translations) != 38 or set(rejected) != set(translations):
        p.error("Los 38 rechazos no coinciden exactamente con esta reparación; no se cambió nada.")
    memory = Memory(str(path))
    if any(source in memory for source in translations):
        p.error("Hay textos ya traducidos en memoria; no se sobrescribirá nada.")
    for source, target in PAIRS:
        if CODE_RE.findall(source) != CODE_RE.findall(target):
            p.error("Código RPG Maker no preservado: " + repr(source))
        print("EN:", repr(source))
        print("JA:", repr(target))
    if not args.commit:
        print("VISTA PREVIA: usa --commit para guardar con respaldo.")
        return
    suffix = ".before-ja-repair-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".bak"
    backup_memory = Path(str(path) + suffix)
    backup_rejected = Path(str(rejected_path) + suffix)
    shutil.copy2(path, backup_memory)
    shutil.copy2(rejected_path, backup_rejected)
    for source, target in PAIRS:
        memory.set(source, target)
        rejected.pop(source)
    memory.save()
    tmp = Path(str(rejected_path) + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(rejected, f, ensure_ascii=False, indent=2)
    tmp.replace(rejected_path)
    print("RESPALDO MEMORIA:", backup_memory)
    print("RESPALDO RECHAZOS:", backup_rejected)
    print("Rechazos restantes:", len(rejected))


if __name__ == "__main__":
    main()
