"""analytics/build_site.py 의 고정 인터페이스만 흉내 내는 stub: 공용 정답 JSON 을 --out 에 복사합니다.

STUB_FAIL=1 이면 dbt 테스트 실패처럼 종료 코드 1, STUB_BREAK_CONTRACT=1 이면 계약 위반 파일을 남깁니다.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]

parser = argparse.ArgumentParser()
parser.add_argument("--raw-root", required=True)
parser.add_argument("--out", required=True)
parser.add_argument("--as-of")
parser.add_argument("--seeds-dir")
parser.add_argument("--code-version")
args = parser.parse_args()

if os.environ.get("STUB_ARGS_FILE"):
    Path(os.environ["STUB_ARGS_FILE"]).write_text(json.dumps(sys.argv[1:]))
if os.environ.get("STUB_FAIL") == "1":
    print("dbt build 실패", file=sys.stderr)
    sys.exit(1)
shutil.copytree(REPO_ROOT / "fixtures" / "site" / "data", args.out, dirs_exist_ok=True)
if os.environ.get("STUB_BREAK_CONTRACT") == "1":
    (Path(args.out) / "meta.json").write_text('{"freshness": "unknown"}')
