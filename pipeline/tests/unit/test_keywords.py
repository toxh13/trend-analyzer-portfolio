import json
import re
from dataclasses import replace
from pathlib import Path

import kiwipiepy
import pytest

from trend_pipeline import keywords
from trend_pipeline.keywords import RuleSet, extract_keywords, load_rules


def write_rules(tmp_path: Path, body: str, name: str = "keyword_rules.yml") -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def valid_rules_body(**overrides: str) -> str:
    """검증을 통과하는 최소 규칙 YAML. overrides 로 줄 단위 값을 바꾼다."""
    lines = {
        "input_field": "title",
        "analyzer": "kiwi",
        "analyzer_version": kiwipiepy.__version__,
        "pos_tags": "[NNG, NNP]",
        "min_length": "2",
        "stopwords": "[]",
        "hanja_map": "[[中, 중국]]",
    }
    lines.update(overrides)
    return "".join(f"{key}: {value}\n" for key, value in lines.items())


# --- 추출 동작 (실제 Kiwi) ---


def test_hanja_abbreviations_expanded():
    kws = extract_keywords("美 관세 압박에 中企 수출 비상", load_rules())
    assert {"미국", "관세", "중소기업", "수출"} <= kws
    assert not kws & {"美", "中", "企", "中企"}


@pytest.mark.parametrize(
    ("title", "expected", "unexpected"),
    [
        ("中東 정세 불안에 유가 급등", {"중동", "유가"}, {"중국", "東"}),
        ("北美 시장 공략", {"북미", "시장"}, {"북한", "미국"}),
        ("南北 정상회담", {"남북"}, {"북한", "南"}),
        ("南美 순방", {"남미"}, {"미국", "南"}),
    ],
    ids=["middle-east", "north-america", "inter-korean", "south-america"],
)
def test_hanja_compounds_replaced_before_single_characters(title, expected, unexpected):
    # 두 글자 약어(中東·北美·南北·南美)를 한 글자(中·北·美)보다 먼저 바꿔야 뜻이 맞는다
    kws = extract_keywords(title, load_rules())
    assert expected <= kws
    assert not kws & unexpected


def test_surname_hanja_dropped():
    assert "尹" not in extract_keywords("[속보]尹 선거법 2심", load_rules())


def test_foreign_word_kept():
    assert "AI" in extract_keywords("AI 반도체 수출 증가", load_rules())


def test_notice_title_has_no_keywords():
    assert extract_keywords("[부고] 홍길동씨 별세", load_rules()) == frozenset()


def test_hanja_map_order_is_longest_first():
    rules = load_rules()
    # 긴 것(中企)이 먼저 치환되어야 중소기업이 된다
    kws = extract_keywords("中企 수출", rules)
    assert "중소기업" in kws
    assert "중국" not in kws

    # 순서를 뒤집으면 中이 먼저 중국으로 바뀌고 企만 남아 중소기업이 사라진다. 순서는 의미가 있다
    reversed_rules = replace(rules, hanja_map=tuple(reversed(rules.hanja_map)))
    reversed_kws = extract_keywords("中企 수출", reversed_rules)
    assert "중국" in reversed_kws
    assert "중소기업" not in reversed_kws
    assert reversed_rules.version != rules.version


def test_stopword_is_filtered_out():
    rules = load_rules()
    assert {"관세", "수출"} <= extract_keywords("관세 수출", rules)

    filtered = extract_keywords("관세 수출", replace(rules, stopwords=frozenset({"수출"})))
    assert "수출" not in filtered
    assert "관세" in filtered


def test_empty_cleaned_title_skips_kiwi(monkeypatch):
    def fail():
        raise AssertionError("빈 제목에서는 Kiwi를 만들거나 부르면 안 된다")

    monkeypatch.setattr(keywords, "_kiwi", fail)
    rules = load_rules()
    assert extract_keywords("[속보]", rules) == frozenset()
    assert extract_keywords("   ", rules) == frozenset()
    # 공지 태그도 Kiwi 이전에 끝난다
    assert extract_keywords("[인사] 임원 승진", rules) == frozenset()


def test_kiwi_instance_is_created_once():
    assert keywords._kiwi() is keywords._kiwi()


# --- 규칙 파일 읽기와 검증 ---


def test_packaged_rules_version_is_8_lowercase_hex():
    assert re.fullmatch(r"[0-9a-f]{8}", load_rules().version)


def test_packaged_rules_match_first_version_values():
    rules = load_rules()
    assert rules.input_field == "title"
    assert rules.analyzer == "kiwi"
    assert rules.analyzer_version == kiwipiepy.__version__
    assert rules.pos_tags == ("NNG", "NNP", "SL", "SH")
    assert rules.min_length == 2
    assert rules.stopwords == frozenset()
    assert rules.hanja_map == (
        ("中企", "중소기업"), ("中東", "중동"), ("北美", "북미"), ("南美", "남미"), ("南北", "남북"),
        ("美", "미국"), ("中", "중국"), ("日", "일본"), ("北", "북한"), ("韓", "한국"),
        ("英", "영국"), ("伊", "이탈리아"), ("與", "여당"), ("野", "야당"), ("靑", "청와대"),
    )  # fmt: skip


def test_analyzer_version_mismatch_raises_runtime_error(tmp_path):
    path = write_rules(tmp_path, valid_rules_body(analyzer_version="0.0.0"))
    with pytest.raises(RuntimeError) as excinfo:
        load_rules(path)
    # 기대 버전과 설치된 버전이 둘 다 보여야 원인을 바로 안다
    assert "0.0.0" in str(excinfo.value)
    assert kiwipiepy.__version__ in str(excinfo.value)


@pytest.mark.parametrize(
    "override",
    [
        {"input_field": "summary"},
        {"analyzer": "okt"},
        {"min_length": "0"},
        {"min_length": "-1"},
        {"min_length": "two"},
        {"pos_tags": "[]"},
    ],
)
def test_invalid_rules_raise_value_error(tmp_path, override):
    path = write_rules(tmp_path, valid_rules_body(**override))
    with pytest.raises(ValueError):
        load_rules(path)


def test_valid_minimal_rules_load(tmp_path):
    rules = load_rules(write_rules(tmp_path, valid_rules_body()))
    assert rules.pos_tags == ("NNG", "NNP")
    assert rules.hanja_map == (("中", "중국"),)


# --- version / JSON ---


def test_version_ignores_yaml_formatting(tmp_path):
    # 같은 내용, 다른 들여쓰기·표기·키 순서·불용어 순서 → 같은 version
    block = f"""\
# 주석은 version에 영향이 없다
input_field: title
analyzer: kiwi
analyzer_version: {kiwipiepy.__version__}
pos_tags:
  - NNG
  - NNP
min_length: 2
stopwords:
  - 기자
  - 뉴스
hanja_map:
  - [中企, 중소기업]
  - [中, 중국]
"""
    flow = f"""\
hanja_map: [ [ 中企, "중소기업" ], [ "中", 중국 ] ]
stopwords: [뉴스,   기자]
min_length: 2
pos_tags: [NNG,
           NNP]
analyzer_version: "{kiwipiepy.__version__}"
analyzer: 'kiwi'
input_field: title
"""
    a = load_rules(write_rules(tmp_path, block, "block.yml"))
    b = load_rules(write_rules(tmp_path, flow, "flow.yml"))
    assert a == b
    assert a.version == b.version


def test_version_changes_when_stopword_added():
    rules = load_rules()
    with_stopword = replace(rules, stopwords=rules.stopwords | {"기자"})
    assert with_stopword.version != rules.version


def test_json_round_trip():
    r = load_rules()
    assert RuleSet.from_json(r.to_json()) == r


def test_json_round_trip_restores_types():
    r = replace(load_rules(), stopwords=frozenset({"기자", "뉴스"}))
    restored = RuleSet.from_json(r.to_json())
    assert restored == r
    assert isinstance(restored.pos_tags, tuple)
    assert isinstance(restored.stopwords, frozenset)
    assert isinstance(restored.hanja_map, tuple)
    assert all(isinstance(pair, tuple) for pair in restored.hanja_map)
    assert restored.version == r.version


def test_to_json_is_canonical():
    r = replace(load_rules(), stopwords=frozenset({"뉴스", "기자"}))
    text = r.to_json()
    # 공백 없는 압축형, 한글은 그대로, 키는 정렬, 불용어는 정렬된 목록
    assert " " not in text
    assert "중소기업" in text
    data = json.loads(text)
    assert list(data) == sorted(data)
    assert data["stopwords"] == ["기자", "뉴스"]
    # pos_tags와 hanja_map은 주어진 순서를 지킨다
    assert data["pos_tags"] == ["NNG", "NNP", "SL", "SH"]
    assert data["hanja_map"][0] == ["中企", "중소기업"]
