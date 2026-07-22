import os
import requests
from bs4 import BeautifulSoup
from crawlers.article_fields import parse_local_published_at
from crawlers.crawl_result import CrawlResult
from crawlers.http_retry import request_with_retry

# -----------------------------------------------------------------
# [수집량 조절]
# -----------------------------------------------------------------
# OCI 무료 서버 기준 3시간 배치당 약 50건을 목표로 합니다.
# RSS는 피드당 4건으로 줄이고, 네이버/다음 HTML 상세 크롤링은 카테고리당 7건까지 늘립니다.
# -----------------------------------------------------------------
MAX_ARTICLES_PER_CATEGORY = int(os.environ.get("MAX_ARTICLES_PER_CATEGORY", "7"))
MAX_DETAIL_ATTEMPTS_PER_CATEGORY = MAX_ARTICLES_PER_CATEGORY * 2
REQUEST_TIMEOUT = int(os.environ.get("CRAWLER_REQUEST_TIMEOUT", "10"))


def crawl_daum():
    # 1. 크롤링할 타깃 URL 설정
    urls = {
        "IT/과학": "https://news.daum.net/tech",
        "경제": "https://news.daum.net/economy"
    }

    # 2. 봇(Bot)으로 차단당하는 것을 방지하기 위해 브라우저 헤더 정보 추가
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    result = CrawlResult(channel="daum")

    for category, url in urls.items():
        discovered = 0
        valid = 0
        invalid = 0
        detail_attempts = 0
        outcome = "failure"
        try:
            # 3. 페이지 HTML 요청
            response = request_with_retry(
                requests.get,
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            response.encoding = 'utf-8'

            if response.status_code == 200:
                # 4. BeautifulSoup을 이용해 HTML 파싱
                soup = BeautifulSoup(response.text, "html.parser")

                # 5. 다음 뉴스 헤드라인 주요 뉴스 기사 제목 태그 추출
                headlines = soup.select("a.item_newsheadline2")
                discovered = len(headlines)
                if discovered == 0:
                    print(f"기사 선택자를 찾지 못했습니다. source=daum category={category}")
                    continue

                for link_tag in headlines:
                    if valid >= MAX_ARTICLES_PER_CATEGORY:
                        break

                    clean_title = link_tag.get_text().strip()
                    news_url = link_tag.get("href")

                    if clean_title and news_url:
                        if detail_attempts >= MAX_DETAIL_ATTEMPTS_PER_CATEGORY:
                            break
                        detail_attempts += 1
                        published_at = None
                        article_content = None

                        # 기사 상세 페이지(news_url)로 한 번 더 접속하여 본문 스크래핑
                        try:
                            detail_response = request_with_retry(
                                requests.get,
                                news_url,
                                headers=headers,
                                timeout=REQUEST_TIMEOUT,
                            )
                            detail_response.encoding = 'utf-8'

                            if detail_response.status_code == 200:
                                detail_soup = BeautifulSoup(detail_response.text, "html.parser")

                                published_area = detail_soup.select_one("span.num_date")
                                content_area = detail_soup.select_one("div.article_view")

                                if content_area:
                                    article_content = content_area.get_text(separator=" ", strip=True).replace("\xa0", " ")

                                if published_area:
                                    published_at_raw = published_area.get_text(separator=" ", strip=True)
                                    published_at = parse_local_published_at(
                                        published_at_raw,
                                        '%Y. %m. %d. %H:%M',
                                        '%Y-%m-%dT%H:%M:00',
                                    )
                        except Exception as e:
                            print(f"[{clean_title}] 본문 수집 중 에러 발생: {e}")

                        if not article_content:
                            reason = "content_missing"
                        elif not published_area:
                            reason = "published_at_missing"
                        elif not published_at:
                            reason = "published_at_parse_failed"
                        else:
                            reason = None
                        if reason:
                            invalid += 1
                            print(f"기사 제외: source=daum category={category} reason={reason}")
                            continue

                        # 2. 결과 리스트에 축적
                        result.articles.append({
                            "title": clean_title,
                            "content": article_content,
                            "sourceUrl": news_url,
                            "source": "다음 뉴스",
                            "category": category,
                            "publishedAt": published_at, # 👈 이제 한글 텍스트 대신 무조건 valid한 ISO 날짜 문자열이 보장됩니다!
                        })
                        valid += 1
                    else:
                        invalid += 1
                        print(f"기사 제목 또는 URL을 찾을 수 없습니다. 카테고리: {category}")
                if valid > 0:
                    outcome = "partial_failure" if invalid > 0 else "success"
                elif invalid > 0:
                    outcome = "partial_failure"
            else:
                print(f"페이지를 불러오지 못했습니다. 상태 코드: {response.status_code}")

        except Exception as e:
            print(f"크롤링 중 오류 발생: {e}")
        finally:
            result.record_unit(outcome, invalid)
            print(
                f"event=crawl_unit_completed channel=daum category={category} "
                f"outcome={outcome} discovered={discovered} detail_attempts={detail_attempts} "
                f"valid={valid} invalid={invalid}"
            )

    return result


if __name__ == "__main__":
    print("----- [단독 테스트 모드] daum_crawler.py -----")
    result = crawl_daum()
    print(f"수집 결과: {result.articles}")
    print("-----------------------------------------------")
