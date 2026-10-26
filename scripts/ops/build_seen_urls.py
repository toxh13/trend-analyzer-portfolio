"""data 브랜치 체크아웃에서 최근 기사 URL을 모아 state/seen_urls.txt 를 만듭니다.

    python scripts/ops/build_seen_urls.py --data-dir data [--days 7] [--today YYYY-MM-DD]

- 기준 날짜는 경로의 `dt=` (배치 시작 시각의 서울 날짜)입니다. `today - days` 이후(포함) 파티션만 읽습니다.
  예약 실행이 자정을 넘겨 지연되는 경우를 생각해 경계 하루를 더 포함합니다(제외가 과한 쪽이 안전).
- 결과는 중복 없이 정렬해서 한 줄에 URL 하나로 씁니다. 파일이 없어도 빈 파일을 만듭니다.
- 깨진 줄은 경고만 남기고 건너뜁니다. seen URL은 최적화일 뿐이고, 중복은 dbt 단계에서 다시 제거됩니다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")
DT_PATTERN = re.compile(r"^dt=(\d{4}-\d{2}-\d{2})$")


def seoul_today() -> date:
    return datetime.now(SEOUL).date()


def recent_partitions(data_dir: Path, today: date, days: int) -> list[Path]:
    cutoff = today - timedelta(days=days)
    partitions = []
    for path in sorted((data_dir / "raw" / "articles").glob("dt=*")):
        match = DT_PATTERN.match(path.name)
        if not match or not path.is_dir():
            continue
        try:
            partition_date = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if cutoff <= partition_date <= today:
            partitions.append(path)
    return partitions


def collect_urls(partitions: list[Path]) -> tuple[set[str], int]:
    urls: set[str] = set()
    skipped = 0
    for partition in partitions:
        for path in sorted(partition.glob("*.jsonl")):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    url = json.loads(line).get("sourceUrl")
                except (json.JSONDecodeError, AttributeError):
                    url = None
                if not isinstance(url, str) or not url.strip():
                    skipped += 1
                    print(f"경고: {path}:{line_no}: sourceUrl 을 읽을 수 없어 건너뜁니다", file=sys.stderr)
                    continue
                urls.add(url.strip())
    return urls, skipped


def write_atomic(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, required=True, help="data 브랜치 체크아웃 (raw/ 를 포함)")
    parser.add_argument("--output", type=Path, help="기본 <data-dir>/state/seen_urls.txt")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--today", type=date.fromisoformat, help="서울 날짜 YYYY-MM-DD, 기본 오늘")
    args = parser.parse_args(argv)
    if args.days < 0:
        parser.error("--days 는 0 이상이어야 합니다")

    today = args.today or seoul_today()
    partitions = recent_partitions(args.data_dir, today, args.days)
    urls, skipped = collect_urls(partitions)
    output = args.output or args.data_dir / "state" / "seen_urls.txt"
    write_atomic(output, sorted(urls))
    print(f"partitions={len(partitions)} urls={len(urls)} skipped={skipped} output={output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
