"""crawling-python/batch_cli.py 의 고정 인터페이스만 흉내 내는 stub (WORKSTREAMS.md "고정 인터페이스").

환경 변수
  STUB_ARGS_FILE  받은 인자를 JSON 으로 기록
  STUB_URLS       쉼표로 구분한 후보 URL (기본 2개)
  STUB_OUTCOME    SUCCESS|PARTIAL_FAILURE|EMPTY|FAILURE (기본: 쓴 기사가 있으면 SUCCESS, 없으면 EMPTY)
  STUB_CRASH=1    run JSON 없이 비정상 종료
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

parser = argparse.ArgumentParser()
parser.add_argument("--output-dir", required=True)
parser.add_argument("--seen-urls")
parser.add_argument("--max-articles", type=int, default=50)
parser.add_argument("--trigger", default="local")
parser.add_argument("--code-version", default="local")
parser.add_argument("--source-fixture")
args = parser.parse_args()

if os.environ.get("STUB_ARGS_FILE"):
    Path(os.environ["STUB_ARGS_FILE"]).write_text(json.dumps(sys.argv[1:]))
print("stub: 수집 시작")
if os.environ.get("STUB_CRASH") == "1":
    print("Traceback: 예상하지 못한 오류", file=sys.stderr)
    sys.exit(1)

seen = set()
if args.seen_urls and Path(args.seen_urls).exists():
    seen = set(Path(args.seen_urls).read_text(encoding="utf-8").split())
candidates = os.environ.get("STUB_URLS", "https://news.example.com/a,https://news.example.com/b").split(",")
candidates = [url for url in candidates if url]
fresh = [url for url in candidates if url not in seen]
selected = fresh[: args.max_articles]
outcome = os.environ.get("STUB_OUTCOME") or ("SUCCESS" if selected else "EMPTY")
written = 0 if outcome == "FAILURE" else len(selected)

now = datetime.now(timezone.utc)
stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
dt = now.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
run_id = str(uuid.uuid4())
out = Path(args.output_dir)
if written:
    path = out / "raw" / "articles" / f"dt={dt}" / f"{run_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "schemaVersion": 1, "runId": run_id, "channel": "rss", "source": "Google News RSS - stub",
            "category": "IT/과학", "title": f"stub 기사 {i}", "sourceUrl": url,
            "publishedAt": "2026-10-24T09:00:00", "crawledAt": stamp, "summary": "stub 요약",
            "keywords": [{"keyword": "인공지능", "occurrenceCount": 1}],
        }
        for i, url in enumerate(selected[:written])
    ]
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

dropped = len(fresh) - len(selected)
failed_write = len(selected) - written
run = {
    "schemaVersion": 1, "runId": run_id, "startedAt": stamp, "completedAt": stamp, "outcome": outcome,
    "trigger": args.trigger, "crawlerOutputCount": len(candidates), "validationRejectedCount": 0,
    "duplicateUrlCount": 0, "previouslySeenCount": len(candidates) - len(fresh), "eligibleCount": len(fresh),
    "selectedCount": len(selected), "droppedByLimitCount": dropped, "preprocessingFailedCount": 0,
    "writtenCount": written, "writeFailedCount": failed_write, "reconciliationOk": True, "durationMs": 1,
    "channels": [
        {"channel": "rss", "outcome": outcome, "validatedArticleCount": len(candidates), "sourceInvalidCount": 0,
         "successfulUnits": 1, "partialUnits": 0, "emptyUnits": 0, "failedUnits": 0}
    ],
    "codeVersion": args.code_version,
}
run_path = out / "raw" / "runs" / f"dt={dt}" / f"{run_id}.json"
run_path.parent.mkdir(parents=True, exist_ok=True)
run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
print(run_path)
sys.exit(1 if outcome == "FAILURE" else 0)
