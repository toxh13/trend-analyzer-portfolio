#!/usr/bin/env bash
# 수집 1회: seen URL 생성 → batch_cli → 원천 파일 커밋·push. ingest.yml 과 CI 오프라인 e2e 가 같이 씁니다.
#
#   bash scripts/ops/ingest.sh <data-dir>
#
# 환경 변수
#   TRIGGER         schedule|workflow_dispatch|backfill|local (기본 local)
#   MAX_ARTICLES    비우면 batch_cli 기본값
#   CODE_VERSION    기본 $GITHUB_SHA 또는 local
#   SOURCE_FIXTURE  있으면 네트워크 대신 고정 기사 사용(--source-fixture)
#   BATCH_CLI       기본 <저장소>/crawling-python/batch_cli.py (테스트에서 stub 으로 바꿈)
#   PYTHON          기본 python3
#   SKIP_COMMIT=1   커밋·push 생략(로컬 확인용)
#
# 종료 코드: batch_cli 의 종료 코드(outcome == FAILURE 이면 1). FAILURE 여도 run JSON 은 커밋해 이력을 남깁니다.
# run JSON 을 찾지 못하거나 커밋·push 가 실패하면 1.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "사용법: $0 <data-dir>" >&2
  exit 2
fi
ops_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$ops_dir/../.." && pwd)"
data_dir="$(cd "$1" && pwd)"
python_bin="${PYTHON:-python3}"
batch_cli="${BATCH_CLI:-$repo_root/crawling-python/batch_cli.py}"

if [[ -n "${MAX_ARTICLES:-}" && ! "$MAX_ARTICLES" =~ ^[1-9][0-9]*$ ]]; then
  echo "::error::MAX_ARTICLES 는 1 이상의 정수여야 합니다: '$MAX_ARTICLES'"
  exit 2
fi

"$python_bin" "$ops_dir/build_seen_urls.py" --data-dir "$data_dir"

args=(--output-dir "$data_dir" --seen-urls "$data_dir/state/seen_urls.txt"
      --trigger "${TRIGGER:-local}" --code-version "${CODE_VERSION:-${GITHUB_SHA:-local}}")
[[ -n "${MAX_ARTICLES:-}" ]] && args+=(--max-articles "$MAX_ARTICLES")
[[ -n "${SOURCE_FIXTURE:-}" ]] && args+=(--source-fixture "$SOURCE_FIXTURE")

log="$(mktemp)"
trap 'rm -f "$log"' EXIT
set +e
"$python_bin" "$batch_cli" "${args[@]}" | tee "$log"
batch_code=${PIPESTATUS[0]}
set -e

# 인터페이스: 마지막 줄이 run JSON 경로
run_json="$(tail -n 1 "$log" | tr -d '\r')"
if [[ -n "$run_json" && "$run_json" != /* && ! -f "$run_json" ]]; then
  run_json="$data_dir/$run_json"
fi
if [[ -z "$run_json" || ! -f "$run_json" ]]; then
  echo "::error::batch_cli(종료 코드 $batch_code)가 run JSON 경로를 남기지 않았습니다"
  exit 1
fi

run_meta="$(
  "$python_bin" - "$run_json" <<'PY'
import json, sys
run = json.load(open(sys.argv[1], encoding="utf-8"))
print(run["runId"], run["outcome"], run["writtenCount"])
PY
)"
read -r run_id outcome written <<<"$run_meta"
echo "run=$run_id outcome=$outcome written=$written exit=$batch_code"
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  { echo "run_id=$run_id"; echo "outcome=$outcome"; echo "written=$written"; } >> "$GITHUB_OUTPUT"
fi
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  echo "수집 \`$run_id\`: **$outcome**, written=$written" >> "$GITHUB_STEP_SUMMARY"
fi
if [[ "$outcome" == "PARTIAL_FAILURE" ]]; then
  echo "::warning::일부 채널이 실패했습니다(PARTIAL_FAILURE). 수집분은 저장합니다"
fi

if [[ "${SKIP_COMMIT:-0}" != "1" ]]; then
  bash "$ops_dir/commit_raw.sh" "$data_dir" "$run_json"
fi

if [[ "$batch_code" -ne 0 ]]; then
  echo "::error::수집 실패: outcome=$outcome (batch_cli 종료 코드 $batch_code)"
fi
exit "$batch_code"
