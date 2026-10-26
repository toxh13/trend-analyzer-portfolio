"""파이프라인 실패를 `pipeline-failure` 라벨 Issue 하나에 누적하고, 성공하면 닫습니다.

    python scripts/ops/alert_issue.py failure --workflow ingest --run-url <url> [--summary <text>]
    python scripts/ops/alert_issue.py success --workflow ingest --run-url <url>

- 워크플로마다 열린 Issue는 하나입니다. 제목 `[pipeline-failure] <workflow>` 로 찾습니다.
- failure: 열린 Issue가 있으면 댓글, 없으면 라벨을 만들고(이미 있으면 무시) Issue를 엽니다.
- success: 열린 Issue가 있으면 복구 댓글을 남기고 닫습니다(state_reason=completed). 없으면 아무것도 안 합니다.
- 환경 변수: GITHUB_TOKEN(필수, issues: write), GITHUB_REPOSITORY(owner/repo), GITHUB_API_URL(기본 https://api.github.com).
- --dry-run 이면 조회만 하고 쓰기 요청은 출력만 합니다. 토큰이 없으면 조회도 건너뜁니다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

LABEL = "pipeline-failure"
LABEL_COLOR = "d73a4a"
LABEL_DESCRIPTION = "v2 파이프라인(ingest·publish) 실패 알림. 성공하면 자동으로 닫힘"


class ApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"GitHub API {status}: {message}")
        self.status = status


# (method, path, body) -> 응답 JSON. 테스트에서는 이 함수를 바꿔 끼운다.
Transport = Callable[[str, str, "dict[str, Any] | None"], Any]


def urllib_transport(api_url: str, token: str) -> Transport:
    def send(method: str, path: str, body: dict[str, Any] | None) -> Any:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            f"{api_url.rstrip('/')}{path}",
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "trend-analyzer-ops",
                **({"Content-Type": "application/json"} if data is not None else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            raise ApiError(error.code, error.read().decode("utf-8", "replace")[:500]) from error
        return json.loads(raw) if raw else None

    return send


def issue_title(workflow: str) -> str:
    return f"[{LABEL}] {workflow}"


@dataclass
class Alerter:
    transport: Transport
    repo: str
    dry_run: bool = False
    actions: list[str] = field(default_factory=list)

    def _write(self, method: str, path: str, body: dict[str, Any]) -> Any:
        self.actions.append(f"{method} {path}")
        if self.dry_run:
            print(f"[dry-run] {method} {path} {json.dumps(body, ensure_ascii=False)}")
            return None
        return self.transport(method, path, body)

    def find_open_issue(self, workflow: str) -> dict[str, Any] | None:
        title = issue_title(workflow)
        page = 1
        while True:
            issues = self.transport(
                "GET", f"/repos/{self.repo}/issues?state=open&labels={LABEL}&per_page=100&page={page}", None
            ) or []
            for issue in issues:
                # issues API 는 PR 도 돌려준다
                if "pull_request" not in issue and issue.get("title") == title:
                    return issue
            if len(issues) < 100:
                return None
            page += 1

    def ensure_label(self) -> None:
        try:
            self._write(
                "POST",
                f"/repos/{self.repo}/labels",
                {"name": LABEL, "color": LABEL_COLOR, "description": LABEL_DESCRIPTION},
            )
        except ApiError as error:
            if error.status != 422:  # 이미 있음
                raise

    def report_failure(self, workflow: str, run_url: str, summary: str) -> str:
        body = f"❌ `{workflow}` 실패\n\n- 실행: {run_url}\n" + (f"- 요약: {summary}\n" if summary else "")
        issue = self.find_open_issue(workflow)
        if issue:
            self._write("POST", f"/repos/{self.repo}/issues/{issue['number']}/comments", {"body": body})
            return f"commented #{issue['number']}"
        self.ensure_label()
        created = self._write(
            "POST",
            f"/repos/{self.repo}/issues",
            {
                "title": issue_title(workflow),
                "labels": [LABEL],
                "body": body
                + "\n같은 워크플로가 다시 실패하면 이 Issue에 댓글이 쌓이고, 다음 성공 시 자동으로 닫힙니다."
                + "\n대응 절차: `docs/v2/RUNBOOK.md`",
            },
        )
        return f"opened #{created['number']}" if created else "opened (dry-run)"

    def report_success(self, workflow: str, run_url: str) -> str:
        issue = self.find_open_issue(workflow)
        if not issue:
            return "nothing to close"
        number = issue["number"]
        self._write(
            "POST",
            f"/repos/{self.repo}/issues/{number}/comments",
            {"body": f"✅ `{workflow}` 복구: {run_url}\n\n성공 실행을 확인해 자동으로 닫습니다."},
        )
        self._write(
            "PATCH", f"/repos/{self.repo}/issues/{number}", {"state": "closed", "state_reason": "completed"}
        )
        return f"closed #{number}"


def main(argv: list[str] | None = None, transport: Transport | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("status", choices=["failure", "success"])
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.repo:
        parser.error("--repo 또는 GITHUB_REPOSITORY 가 필요합니다")

    if transport is None:
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            if args.dry_run:
                print(f"[dry-run] GITHUB_TOKEN 없음: {args.status} 알림을 건너뜁니다 ({args.workflow})")
                return 0
            print("GITHUB_TOKEN 이 필요합니다", file=sys.stderr)
            return 2
        transport = urllib_transport(os.environ.get("GITHUB_API_URL", "https://api.github.com"), token)

    alerter = Alerter(transport=transport, repo=args.repo, dry_run=args.dry_run)
    if args.status == "failure":
        result = alerter.report_failure(args.workflow, args.run_url, args.summary)
    else:
        result = alerter.report_success(args.workflow, args.run_url)
    print(f"{args.status} {args.workflow}: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
