from bot_core.compat import STORY_PHRASE_MAX, STORY_PHRASE_MIN, story_phrase

S1 = "Вас связывает доверие и интерес друг к другу."
S2 = "Вам легко вместе начинать новое и поддерживать друг друга в трудный момент."
S3 = "Чтобы связь крепла, чаще говорите о своих ожиданиях вслух и бережно слушайте друг друга."


def test_phrase_collects_sentences_up_to_min():
    p = story_phrase(f"{S1} {S2} {S3}")
    assert p.startswith(S1) and S2 in p
    assert len(p) <= STORY_PHRASE_MAX


def test_phrase_never_exceeds_max():
    long_one = "Очень " * 60 + "длинное предложение."
    p = story_phrase(long_one)
    assert len(p) <= STORY_PHRASE_MAX and p.endswith("…")


def test_short_summary_kept_whole():
    assert story_phrase(S1) == S1
    assert STORY_PHRASE_MIN <= STORY_PHRASE_MAX
