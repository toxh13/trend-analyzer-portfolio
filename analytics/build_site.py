"""원천 파일 → dbt build(테스트 포함) → 정적 JSON → 계약 검사를 한 번에 실행합니다.

    python analytics/build_site.py --raw-root fixtures/raw-root --seeds-dir fixtures/seeds \
        --as-of 2026-10-24T12:00:00 --out /tmp/site

종료 코드: dbt build(품질 테스트 포함) 실패 또는 contracts/site 위반이면 1, 성공이면 0.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ANALYTICS = Path(__file__).resolve().parent
REPO_ROOT = ANALYTICS.parent
SEOUL = ZoneInfo("Asia/Seoul")
AS_OF_FORMAT = "%Y-%m-%dT%H:%M:%S"

sys.path.insert(0, str(ANALYTICS))
import export_site  # noqa: E402


def parse_as_of(value: str | None) -> str:
    if value is None:
        return datetime.now(SEOUL).strftime(AS_OF_FORMAT)
    try:
        return datetime.strptime(value, AS_OF_FORMAT).strftime(AS_OF_FORMAT)
    except ValueError:
        raise argparse.ArgumentTypeError(f"--as-of 는 YYYY-MM-DDTHH:MM:SS 형식이어야 합니다: {value}")


def run_dbt(raw_root: Path, seeds_dir: Path, as_of: str, work_dir: Path, strict_freshness: bool) -> Path:
    """dbt build 를 실행하고 DuckDB 파일 경로를 돌려준다. 실패하면 RuntimeError."""
    from dbt.cli.main import dbtRunner

    duckdb_path = work_dir / "trend.duckdb"
    os.environ["RAW_DATA_DIR"] = str(raw_root.resolve())
    os.environ["SEEDS_DIR"] = str(seeds_dir.resolve())
    os.environ["DBT_DUCKDB_PATH"] = str(duckdb_path)
    dbt_vars = {"as_of": as_of, "strict_freshness": strict_freshness}
    result = dbtRunner().invoke([
        "build",
        "--project-dir", str(ANALYTICS),
        "--profiles-dir", str(ANALYTICS),
        "--target-path", str(work_dir / "target"),
        "--log-path", str(work_dir / "logs"),
        "--no-partial-parse",
        "--no-use-colors",
        "--vars", json.dumps(dbt_vars),
    ])
    if not result.success:
        raise RuntimeError(f"dbt build 실패: {result.exception or '품질 테스트 또는 모델 오류 (위 로그 참고)'}")
    return duckdb_path


def validate_contracts(site_dir: Path) -> list[str]:
    sys.path.insert(0, str(REPO_ROOT / "contracts"))
    import validate

    checked, errors = validate.validate_site(site_dir, validate.build_validators())
    if checked == 0:
        errors.append(f"{site_dir}: 검사할 정적 JSON이 없습니다")
    return errors


def build_site(
    raw_root: Path,
    out: Path,
    as_of: str,
    seeds_dir: Path,
    code_version: str,
    generated_at: str | None = None,
    work_dir: Path | None = None,
    strict_freshness: bool = False,
) -> dict[str, object]:
    """라이브러리 진입점 (테스트에서 사용). 실패하면 RuntimeError."""
    for path, label in ((raw_root, "--raw-root"), (seeds_dir, "--seeds-dir")):
        if not path.is_dir():
            raise RuntimeError(f"{label} 디렉터리가 없습니다: {path}")
    export_site.check_out_dir(out)

    with tempfile.TemporaryDirectory(prefix="trend-dbt-") as temp:
        work = work_dir or Path(temp)
        work.mkdir(parents=True, exist_ok=True)
        duckdb_path = run_dbt(raw_root, seeds_dir, as_of, work, strict_freshness)
        files = export_site.build_files(duckdb_path, generated_at or export_site.utc_now_text(), code_version)

    export_site.write_files(files, out)
    errors = validate_contracts(out)
    if errors:
        raise RuntimeError("계약 위반:\n" + "\n".join(errors))
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-root", type=Path, required=True, help="raw/ 를 포함한 디렉터리 (data 브랜치 체크아웃)")
    parser.add_argument("--out", type=Path, required=True, help="정적 JSON 출력 디렉터리")
    parser.add_argument("--as-of", type=parse_as_of, default=None, help="서울 로컬 YYYY-MM-DDTHH:MM:SS, 기본 현재")
    parser.add_argument("--seeds-dir", type=Path, default=ANALYTICS / "seeds")
    parser.add_argument("--code-version", default=os.environ.get("GITHUB_SHA", "local"))
    parser.add_argument("--work-dir", type=Path, default=None, help="dbt target·DuckDB 를 남길 디렉터리 (기본 임시)")
    parser.add_argument("--strict-freshness", action="store_true", help="마지막 성공 실행이 24시간을 넘으면 실패")
    args = parser.parse_args()

    as_of = args.as_of or parse_as_of(None)
    try:
        files = build_site(
            args.raw_root, args.out, as_of, args.seeds_dir, args.code_version,
            work_dir=args.work_dir, strict_freshness=args.strict_freshness,
        )
    except RuntimeError as error:
        print(f"build_site 실패: {error}", file=sys.stderr)
        return 1
    meta = files["meta.json"]
    print(
        f"wrote {len(files)} files to {args.out} "
        f"(asOf={meta['asOf']} freshness={meta['freshness']} articles30d={meta['counts']['articles30d']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
