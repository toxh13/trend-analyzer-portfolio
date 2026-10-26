#!/usr/bin/env bash
# 원천 파일 → 정적 JSON → React static 빌드 → Pages 배포 디렉터리. publish.yml 과 CI 오프라인 e2e 가 같이 씁니다.
#
#   bash scripts/ops/build_pages.sh <raw-root> <out-dir>
#
# 환경 변수
#   SEEDS_DIR     build_site --seeds-dir (기본: build_site 기본값 analytics/seeds)
#   AS_OF         build_site --as-of (기본: 현재)
#   CODE_VERSION  기본 $GITHUB_SHA 또는 local
#   PUBLIC_URL    기본 /trend-analyzer-portfolio
#   PYTHON        기본 python3
#   BUILD_SITE    기본 <저장소>/analytics/build_site.py (테스트에서 stub 으로 바꿈)
#   FRONTEND_DIR  기본 <저장소>/frontend-react
#
# frontend-react 의 npm 의존성은 미리 설치돼 있어야 합니다(npm ci).
# build_site 가 실패(dbt 테스트·계약 위반)하면 여기서 멈추므로, 호출한 워크플로는 배포하지 않습니다.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "사용법: $0 <raw-root> <out-dir>" >&2
  exit 2
fi
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
raw_root="$(cd "$1" && pwd)"
out_dir="$2"
python_bin="${PYTHON:-python3}"
build_site="${BUILD_SITE:-$repo_root/analytics/build_site.py}"
frontend_dir="${FRONTEND_DIR:-$repo_root/frontend-react}"

site_data="$(mktemp -d)"
trap 'rm -rf "$site_data"' EXIT

args=(--raw-root "$raw_root" --out "$site_data" --code-version "${CODE_VERSION:-${GITHUB_SHA:-local}}")
[[ -n "${SEEDS_DIR:-}" ]] && args+=(--seeds-dir "$SEEDS_DIR")
[[ -n "${AS_OF:-}" ]] && args+=(--as-of "$AS_OF")
"$python_bin" "$build_site" "${args[@]}"
"$python_bin" "$repo_root/contracts/validate.py" --site-dir "$site_data"

(
  cd "$frontend_dir"
  REACT_APP_DATA_MODE=static PUBLIC_URL="${PUBLIC_URL:-/trend-analyzer-portfolio}" npm run build
)

rm -rf "$out_dir"
mkdir -p "$out_dir"
cp -R "$frontend_dir/build/." "$out_dir/"
rm -rf "$out_dir/data"
cp -R "$site_data" "$out_dir/data"
echo "배포 디렉터리: $out_dir (정적 JSON $(find "$out_dir/data" -name '*.json' | wc -l)개)"
