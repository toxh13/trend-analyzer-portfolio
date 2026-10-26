#!/usr/bin/env bash
# orphan `data` 브랜치를 README 와 빈 raw/, state/ 로 만들어 push 합니다.
#
#   bash scripts/ops/init_data_branch.sh [--dry-run]
#
# - 원격에 이미 브랜치가 있으면 아무것도 하지 않고 0 으로 끝납니다(여러 번 실행해도 안전).
# - 작업 트리·인덱스·현재 브랜치를 건드리지 않습니다. 임시 인덱스로 트리를 만들고 commit-tree 로 부모 없는 커밋을 만듭니다.
# - 환경 변수: DATA_BRANCH(기본 data), DATA_REMOTE(기본 origin)
set -euo pipefail

branch="${DATA_BRANCH:-data}"
remote="${DATA_REMOTE:-origin}"
dry_run=false
if [[ "${1:-}" == "--dry-run" ]]; then
  dry_run=true
fi

if git ls-remote --exit-code --heads "$remote" "$branch" >/dev/null 2>&1; then
  echo "이미 있음: $remote/$branch — 아무것도 하지 않습니다"
  exit 0
fi

readme="$(cat <<'MD'
# data 브랜치

Trend Analyzer v2 의 **원천 데이터 저장소**입니다. `main` 과 히스토리를 공유하지 않습니다(orphan).

- `raw/articles/dt=YYYY-MM-DD/<runId>.jsonl` — 기사 1건 = 1줄 (`contracts/raw/article.schema.json`)
- `raw/runs/dt=YYYY-MM-DD/<runId>.json` — 수집 1회 = 1파일 (`contracts/raw/run.schema.json`)
- `state/seen_urls.txt` — 최근 7일 수집 URL. 매 실행 다시 만듭니다.

`ingest.yml` 워크플로만 이 브랜치에 커밋합니다. 파일은 추가만 하고 수정하지 않습니다.
설계: `docs/v2/DESIGN.md` 3절 (main 브랜치), 운영: `docs/v2/RUNBOOK.md`
MD
)"

tmp_index="$(mktemp)"
trap 'rm -f "$tmp_index"' EXIT
rm -f "$tmp_index"  # 빈 인덱스로 시작

add_blob() {  # <경로> <내용>
  local blob
  blob="$(printf '%s' "$2" | git hash-object -w --stdin)"
  GIT_INDEX_FILE="$tmp_index" git update-index --add --cacheinfo "100644,$blob,$1"
}

add_blob README.md "$readme"$'\n'
add_blob raw/articles/.gitkeep ""
add_blob raw/runs/.gitkeep ""
add_blob state/.gitkeep ""
tree="$(GIT_INDEX_FILE="$tmp_index" git write-tree)"

commit="$(
  GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-github-actions[bot]}" \
  GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}" \
  GIT_COMMITTER_NAME="${GIT_COMMITTER_NAME:-github-actions[bot]}" \
  GIT_COMMITTER_EMAIL="${GIT_COMMITTER_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}" \
  git commit-tree "$tree" -m "data: 브랜치 초기화"
)"

if $dry_run; then
  echo "[dry-run] $remote/$branch 를 만들 커밋: $commit (tree $tree)"
  git ls-tree -r --name-only "$commit"
  exit 0
fi

git push "$remote" "$commit:refs/heads/$branch"
echo "생성: $remote/$branch ($commit)"
