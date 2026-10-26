#!/usr/bin/env bash
# 수집 결과(raw/, state/)를 data 브랜치에 커밋하고 push 합니다.
#
#   bash scripts/ops/commit_raw.sh <data-dir> <run-json>
#
# - 커밋 메시지: `data: <runId> <outcome> written=<n>` (run JSON 에서 읽음)
# - push 가 거부되면(non-fast-forward 등) fetch → rebase 후 다시 push, 최대 COMMIT_RAW_RETRIES(기본 3)회 재시도.
#   raw/ 파일은 runId 별 새 파일이라 충돌하지 않습니다. 매번 다시 만드는 state/seen_urls.txt 만 겹칠 수 있어
#   rebase 는 `-X theirs`(= 지금 올리는 쪽)로 풉니다. 다음 실행에서 어차피 다시 만듭니다.
# - 바뀐 파일이 없으면 커밋하지 않고 0 으로 끝납니다.
# - 환경 변수: DATA_BRANCH(기본 data), DATA_REMOTE(기본 origin), COMMIT_RAW_RETRIES, COMMIT_RAW_BACKOFF(초, 기본 2)
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "사용법: $0 <data-dir> <run-json>" >&2
  exit 2
fi
data_dir="$1"
run_json="$2"
branch="${DATA_BRANCH:-data}"
remote="${DATA_REMOTE:-origin}"
retries="${COMMIT_RAW_RETRIES:-3}"
backoff="${COMMIT_RAW_BACKOFF:-2}"

run_meta="$(
  python3 - "$run_json" <<'PY'
import json, sys
run = json.load(open(sys.argv[1], encoding="utf-8"))
print(run["runId"], run["outcome"], run["writtenCount"])
PY
)"
read -r run_id outcome written <<<"$run_meta"
message="data: ${run_id} ${outcome} written=${written}"

cd "$data_dir"
git config user.name >/dev/null || git config user.name "github-actions[bot]"
git config user.email >/dev/null || git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

paths=()
for path in raw state; do
  [[ -e "$path" ]] && paths+=("$path")
done
if [[ ${#paths[@]} -eq 0 ]]; then
  echo "커밋할 raw/·state/ 가 없습니다" >&2
  exit 1
fi
git add -A -- "${paths[@]}"
if git diff --cached --quiet; then
  echo "바뀐 파일 없음: 커밋하지 않습니다"
  exit 0
fi
git commit -q -m "$message"
echo "커밋: $message"

attempt=0
until git push "$remote" "HEAD:refs/heads/$branch"; do
  if (( attempt >= retries )); then
    echo "push 실패: ${retries}회 재시도 후 포기합니다" >&2
    exit 1
  fi
  attempt=$((attempt + 1))
  echo "push 거부됨, rebase 후 재시도 ${attempt}/${retries}" >&2
  sleep $(( backoff * attempt ))
  git fetch -q "$remote" "$branch"
  if ! git rebase -q -X theirs FETCH_HEAD; then
    git rebase --abort || true
    echo "rebase 실패" >&2
    exit 1
  fi
done
echo "push 완료: $remote/$branch $(git rev-parse --short HEAD)"
