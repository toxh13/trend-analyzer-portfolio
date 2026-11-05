"""버전이 붙는 키워드 추출 규칙(keyword_rules.yml)과 제목 전용 Kiwi 명사 추출."""

import hashlib
import json
from dataclasses import dataclass, fields
from functools import cache
from importlib import resources
from pathlib import Path

import kiwipiepy
import yaml

from trend_pipeline.text_clean import clean_title


@dataclass(frozen=True)
class RuleSet:
    input_field: str
    analyzer: str
    analyzer_version: str
    pos_tags: tuple[str, ...]  # 주어진 순서를 지킨다
    min_length: int
    stopwords: frozenset[str]
    hanja_map: tuple[tuple[str, str], ...]  # 순서가 의미다: 앞에서부터 치환하므로 긴 것이 먼저

    def to_json(self) -> str:
        """정규화 JSON. 키는 정렬, 불용어는 정렬된 목록, 공백 없음, 한글은 그대로 둔다."""
        payload = {
            "input_field": self.input_field,
            "analyzer": self.analyzer,
            "analyzer_version": self.analyzer_version,
            "pos_tags": list(self.pos_tags),
            "min_length": self.min_length,
            "stopwords": sorted(self.stopwords),
            "hanja_map": [list(pair) for pair in self.hanja_map],
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json(cls, s: str) -> "RuleSet":
        data = json.loads(s)
        return cls(
            input_field=data["input_field"],
            analyzer=data["analyzer"],
            analyzer_version=data["analyzer_version"],
            pos_tags=tuple(data["pos_tags"]),
            min_length=data["min_length"],
            stopwords=frozenset(data["stopwords"]),
            hanja_map=tuple((hanja, word) for hanja, word in data["hanja_map"]),
        )

    @property
    def version(self) -> str:
        """정규화 JSON의 sha256 앞 8자리. YAML 표기(들여쓰기·주석·키 순서)와 무관하다."""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()[:8]


def load_rules(path: Path | None = None) -> RuleSet:
    """규칙 파일을 읽고 검증한다. path가 없으면 패키지 리소스를 읽는다.

    형식이나 값이 잘못되면 ValueError, 설치된 kiwipiepy 버전이 규칙의 analyzer_version과 다르면 RuntimeError.
    """
    if path is None:
        text = resources.files("trend_pipeline").joinpath("resources/keyword_rules.yml").read_text(encoding="utf-8")
    else:
        text = Path(path).read_text(encoding="utf-8")

    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("keyword_rules.yml 최상위는 매핑이어야 한다")
    names = [field.name for field in fields(RuleSet)]
    missing = [name for name in names if name not in data]
    unknown = sorted(str(key) for key in data if key not in names)
    if missing:
        raise ValueError(f"keyword_rules.yml: 필수 키 누락 {missing}")
    if unknown:
        raise ValueError(f"keyword_rules.yml: 알 수 없는 키 {unknown}")

    rules = RuleSet(
        input_field=_string(data, "input_field"),
        analyzer=_string(data, "analyzer"),
        analyzer_version=_string(data, "analyzer_version"),
        pos_tags=tuple(_string_list(data, "pos_tags")),
        min_length=data["min_length"],
        stopwords=frozenset(_string_list(data, "stopwords")),
        hanja_map=_hanja_pairs(data["hanja_map"]),
    )

    if rules.input_field != "title":
        raise ValueError(f"input_field는 'title'이어야 한다 (받은 값: {rules.input_field!r})")
    if rules.analyzer != "kiwi":
        raise ValueError(f"analyzer는 'kiwi'여야 한다 (받은 값: {rules.analyzer!r})")
    if isinstance(rules.min_length, bool) or not isinstance(rules.min_length, int) or rules.min_length < 1:
        raise ValueError(f"min_length는 양의 정수여야 한다 (받은 값: {rules.min_length!r})")
    if not rules.pos_tags:
        raise ValueError("pos_tags는 비어 있으면 안 된다")
    require_runnable(rules)
    return rules


def require_runnable(rules: RuleSet) -> None:
    """이 설치가 그 규칙으로 같은 키워드를 뽑을 수 있는지 확인한다. 아니면 RuntimeError.

    load_rules를 거치지 않은 규칙(DB의 rule_json에서 복원한 규칙 등)에도 같은 기준을 쓴다.
    """
    if rules.input_field != "title" or rules.analyzer != "kiwi":
        raise RuntimeError(
            f"규칙 {rules.version}: 이 코드는 input_field 'title'·analyzer 'kiwi' 규칙만 실행한다"
            f" (규칙: input_field {rules.input_field!r}, analyzer {rules.analyzer!r})"
        )
    # 형태소 분석기 버전이 달라지면 같은 제목도 다른 키워드가 나올 수 있어, 조용히 넘어가지 않고 멈춘다
    if rules.analyzer_version != kiwipiepy.__version__:
        raise RuntimeError(
            f"규칙 {rules.version}: kiwipiepy 버전 불일치: 규칙은 {rules.analyzer_version},"
            f" 설치된 버전은 {kiwipiepy.__version__}"
        )


def _string(data: dict, key: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise ValueError(f"{key}는 문자열이어야 한다 (받은 값: {value!r})")
    return value


def _string_list(data: dict, key: str) -> list[str]:
    value = data[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key}는 문자열 목록이어야 한다 (받은 값: {value!r})")
    return value


def _hanja_pairs(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        raise ValueError(f"hanja_map은 [한자, 단어] 쌍의 목록이어야 한다 (받은 값: {value!r})")
    pairs: list[tuple[str, str]] = []
    for index, item in enumerate(value):
        valid = isinstance(item, list) and len(item) == 2 and all(isinstance(part, str) and part for part in item)
        if not valid:
            raise ValueError(f"hanja_map[{index}]: 비어 있지 않은 문자열 두 개의 목록이어야 한다 (받은 값: {item!r})")
        pairs.append((item[0], item[1]))
    return tuple(pairs)


@cache
def _kiwi() -> kiwipiepy.Kiwi:
    """프로세스당 한 번만 만든다. 모델 적재가 무거우므로 import 때가 아니라 처음 쓸 때 만든다."""
    return kiwipiepy.Kiwi()


def extract_keywords(title: str, rules: RuleSet) -> frozenset[str]:
    """제목에서 키워드 집합을 뽑는다. 공지 제목이나 빈 제목은 Kiwi를 부르지 않고 빈 집합을 돌려준다."""
    cleaned = clean_title(title)
    if cleaned.excluded or not cleaned.text:
        return frozenset()

    # 한자 약어는 Kiwi가 한 글자 SH로만 읽으므로 먼저 한글 단어로 바꾼다. 앞뒤 공백으로 이웃 글자와 분리한다
    text = cleaned.text
    for hanja, word in rules.hanja_map:
        text = text.replace(hanja, f" {word} ")

    return frozenset(
        token.form
        for token in _kiwi().tokenize(text)
        if token.tag in rules.pos_tags and len(token.form) >= rules.min_length and token.form not in rules.stopwords
    )
