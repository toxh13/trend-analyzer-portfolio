import os
from functools import lru_cache

# 키워드 병합 추천 모듈입니다.
# 후보 키워드와 기존 대표 키워드를 같은 임베딩 공간에 올린 뒤,
# 코사인 유사도가 기준값 이상인 경우 병합 후보로 추천합니다.

# 기본 모델은 한국어/영어가 섞인 키워드에도 비교적 안정적인 다국어 SentenceTransformer입니다.
# 운영 중 모델을 바꾸거나 버전을 명시해야 하면 환경변수로 덮어씁니다.
DEFAULT_MODEL_NAME = os.environ.get(
    "KEYWORD_RECOMMENDER_MODEL",
    "dragonkue/multilingual-e5-small-ko",
)
MODEL_VERSION = os.environ.get("KEYWORD_RECOMMENDER_MODEL_VERSION", DEFAULT_MODEL_NAME)


@lru_cache(maxsize=1)
def _load_model():
    """무거운 임베딩 모델은 프로세스당 한 번만 로딩해 이후 요청에서 재사용합니다."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is not installed. Install requirements.txt before running recommendations."
        ) from exc

    return SentenceTransformer(DEFAULT_MODEL_NAME)


def recommend_keyword_merges(candidate_keywords, selected_target_group, threshold=0.85, top_k=3):
    """후보 키워드 중 선택된 대표 키워드와 유사한 항목만 추천 목록으로 만듭니다."""
    if not candidate_keywords or not selected_target_group:
        return {
            "modelName": DEFAULT_MODEL_NAME,
            "modelVersion": MODEL_VERSION,
            "suggestions": [],
        }

    model = _load_model()

    # Spring 백엔드에서 넘어온 DTO 중 비교에 사용할 실제 키워드 문자열만 분리합니다.
    candidate_texts = [item["keyword"] for item in candidate_keywords]
    target_text = selected_target_group["canonicalKeyword"]

    # normalize_embeddings=True를 사용하면 내적 연산이 곧 코사인 유사도 계산이 됩니다.
    candidate_embeddings = model.encode(candidate_texts, normalize_embeddings=True)
    target_embedding = model.encode([target_text], normalize_embeddings=True)[0]

    suggestions = []
    for candidate_index, candidate in enumerate(candidate_keywords):
        # 프론트엔드에서 사용자가 선택한 대표 키워드 1개와만 비교합니다.
        score = float(candidate_embeddings[candidate_index] @ target_embedding)
        if score >= threshold:
            suggestions.append({
                "sourceKeyword": candidate["keyword"],
                "normalizedSourceKeyword": candidate["normalizedKeyword"],
                "targetGroupId": selected_target_group["id"],
                "targetKeyword": selected_target_group["canonicalKeyword"],
                "similarityScore": round(score, 4),
                "reason": (
                    f'Embedding similarity {score:.4f} is above the {threshold:.2f} threshold '
                    f'for "{selected_target_group["canonicalKeyword"]}".'
                ),
                "modelName": DEFAULT_MODEL_NAME,
                "modelVersion": MODEL_VERSION,
            })

    suggestions.sort(key=lambda item: item["similarityScore"], reverse=True)
    suggestions = suggestions[:top_k]

    return {
        "modelName": DEFAULT_MODEL_NAME,
        "modelVersion": MODEL_VERSION,
        "suggestions": suggestions,
    }
