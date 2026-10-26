from collections import Counter

# 기사 본문에서 자주 등장하지만 트렌드 키워드로 보기 어려운 일반 명사입니다.
# 운영하면서 불필요한 단어가 보이면 이 목록에 추가합니다.
STOPWORDS = {
    "이번", "입력", "평가", "기자", "오늘", "내일", "관련", "대해", "위해",
    "통해", "최근", "지난", "경우", "가능", "크게", "다른", "또한", "역시",
    "진행", "예정", "기반", "발표", "시간", "정도", "현재", "우리", "기업",
    "시장", "분야", "사업", "지원", "제공", "사용", "문제", "결과", "내용",
}



class _LazyOkt:
    """Okt를 처음 명사 추출할 때 한 번만 생성하고 이후 재사용합니다.

    Okt는 내부적으로 JVM/JPype 자원을 사용하므로 매 기사마다 새로 만들면 비용이 큽니다.
    또 모듈 import 시점에 만들면 Java가 없는 환경(stub 추출기를 쓰는 테스트)에서도
    JVM을 띄우려 하므로, KoNLPy import까지 실제 사용 시점으로 미룹니다.
    """

    def __init__(self):
        self._okt = None

    def nouns(self, text):
        if self._okt is None:
            from konlpy.tag import Okt
            self._okt = Okt()
        return self._okt.nouns(text)


OKT = _LazyOkt()


def keyword_extractor(content, top_n=5):
    """
    기사 본문에서 불용어를 제외한 상위 명사 키워드를 추출합니다.

    :param content: 기사 본문 텍스트
    :param top_n: 반환할 키워드 개수
    :return: 빈도순 상위 키워드와 기사 내 출현 횟수 목록
    """
    if not content:
        return []

    # Okt 명사 추출 결과는 기사 본문의 핵심 후보 단어로 사용합니다.
    raw_nouns = OKT.nouns(content)

    # 한 글자 단어와 일반적인 불용어는 트렌드 키워드 품질을 떨어뜨리므로 제외합니다.
    filtered_nouns = [
        noun for noun in raw_nouns
        if len(noun) > 1 and noun not in STOPWORDS
    ]

    counter = Counter(filtered_nouns)

    return [
        {"keyword": word, "occurrenceCount": count}
        for word, count in counter.most_common(top_n)
    ]
