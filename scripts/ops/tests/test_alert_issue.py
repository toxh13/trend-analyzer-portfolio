from __future__ import annotations

import io
import json
import urllib.error
from typing import Any

import pytest

import alert_issue
from alert_issue import LABEL, Alerter, ApiError, issue_title

REPO = "owner/repo"
RUN_URL = "https://github.com/owner/repo/actions/runs/1"


class FakeGitHub:
    """GitHub REST API 중 이 스크립트가 쓰는 부분만 흉내 낸다."""

    def __init__(self, issues: list[dict[str, Any]] | None = None, label_exists: bool = False):
        self.issues = issues or []
        self.label_exists = label_exists
        self.calls: list[tuple[str, str, Any]] = []
        self.comments: dict[int, list[str]] = {}

    @property
    def writes(self) -> list[tuple[str, str]]:
        return [(method, path) for method, path, _ in self.calls if method != "GET"]

    def __call__(self, method: str, path: str, body: Any) -> Any:
        self.calls.append((method, path, body))
        if method == "GET" and path.startswith(f"/repos/{REPO}/issues?"):
            assert f"labels={LABEL}" in path and "state=open" in path
            page = int(path.rsplit("page=", 1)[1])
            open_issues = [i for i in self.issues if i.get("state", "open") == "open"]
            return open_issues[(page - 1) * 100 : page * 100]
        if method == "POST" and path == f"/repos/{REPO}/labels":
            if self.label_exists:
                raise ApiError(422, "already_exists")
            self.label_exists = True
            return {"name": body["name"]}
        if method == "POST" and path == f"/repos/{REPO}/issues":
            issue = {"number": 100 + len(self.issues), "title": body["title"], "state": "open", "body": body["body"]}
            self.issues.append(issue)
            return issue
        if method == "POST" and path.endswith("/comments"):
            number = int(path.split("/")[-2])
            self.comments.setdefault(number, []).append(body["body"])
            return {"id": 1}
        if method == "PATCH":
            number = int(path.split("/")[-1])
            issue = next(i for i in self.issues if i["number"] == number)
            issue.update(body)
            return issue
        raise AssertionError(f"예상하지 못한 요청: {method} {path}")


def open_issue(number: int, workflow: str = "ingest", **extra) -> dict[str, Any]:
    return {"number": number, "title": issue_title(workflow), "state": "open", **extra}


def test_실패_첫번째면_라벨과_Issue_생성():
    github = FakeGitHub()
    result = Alerter(github, REPO).report_failure("ingest", RUN_URL, "outcome=FAILURE")

    assert result == "opened #100"
    assert github.writes == [("POST", f"/repos/{REPO}/labels"), ("POST", f"/repos/{REPO}/issues")]
    created = github.issues[0]
    assert created["title"] == "[pipeline-failure] ingest"
    assert RUN_URL in created["body"] and "outcome=FAILURE" in created["body"]
    assert github.calls[-1][2]["labels"] == [LABEL]


def test_라벨이_이미_있으면_422를_무시하고_생성():
    github = FakeGitHub(label_exists=True)
    assert Alerter(github, REPO).report_failure("publish", RUN_URL, "") == "opened #100"
    assert github.issues[0]["title"] == "[pipeline-failure] publish"


def test_라벨_생성이_다른_이유로_실패하면_전파():
    def broken(method, path, body):
        if method == "GET":
            return []
        raise ApiError(403, "forbidden")

    with pytest.raises(ApiError):
        Alerter(broken, REPO).report_failure("ingest", RUN_URL, "")


def test_연속_실패는_열린_Issue_하나에_댓글로_누적():
    github = FakeGitHub()
    alerter = Alerter(github, REPO)
    alerter.report_failure("ingest", RUN_URL, "1")
    assert alerter.report_failure("ingest", RUN_URL + "2", "2") == "commented #100"
    assert alerter.report_failure("ingest", RUN_URL + "3", "3") == "commented #100"

    assert len(github.issues) == 1
    assert len(github.comments[100]) == 2
    assert RUN_URL + "3" in github.comments[100][1]


def test_워크플로별로_Issue를_따로_관리():
    github = FakeGitHub(issues=[open_issue(7, "publish")])
    assert Alerter(github, REPO).report_failure("ingest", RUN_URL, "") == "opened #101"
    assert 7 not in github.comments


def test_같은_제목의_PR은_Issue로_보지_않음():
    github = FakeGitHub(issues=[open_issue(5, pull_request={"url": "x"})])
    assert Alerter(github, REPO).report_failure("ingest", RUN_URL, "") == "opened #101"


def test_성공하면_댓글_남기고_닫음():
    github = FakeGitHub(issues=[open_issue(9)])
    assert Alerter(github, REPO).report_success("ingest", RUN_URL) == "closed #9"

    assert github.writes == [
        ("POST", f"/repos/{REPO}/issues/9/comments"),
        ("PATCH", f"/repos/{REPO}/issues/9"),
    ]
    assert github.calls[-1][2] == {"state": "closed", "state_reason": "completed"}
    assert "복구" in github.comments[9][0]


def test_성공인데_열린_Issue가_없으면_쓰기_없음():
    github = FakeGitHub(issues=[open_issue(3, "publish")])
    assert Alerter(github, REPO).report_success("ingest", RUN_URL) == "nothing to close"
    assert github.writes == []


def test_실패_성공_실패면_새_Issue():
    github = FakeGitHub()
    alerter = Alerter(github, REPO)
    alerter.report_failure("ingest", RUN_URL, "")
    alerter.report_success("ingest", RUN_URL)
    assert alerter.report_failure("ingest", RUN_URL, "") == "opened #101"
    assert [i["state"] for i in github.issues] == ["closed", "open"]


def test_열린_Issue가_100개를_넘으면_다음_페이지까지_찾음():
    others = [open_issue(i, f"other-{i}") for i in range(1, 101)]
    github = FakeGitHub(issues=[*others, open_issue(500)])
    assert Alerter(github, REPO).report_success("ingest", RUN_URL) == "closed #500"
    assert [path for method, path, _ in github.calls if method == "GET"][-1].endswith("page=2")


def test_dry_run은_조회만_하고_쓰지_않음(capsys):
    github = FakeGitHub(issues=[open_issue(9)])
    alerter = Alerter(github, REPO, dry_run=True)
    assert alerter.report_success("ingest", RUN_URL) == "closed #9"
    assert alerter.report_failure("publish", RUN_URL, "") == "opened (dry-run)"
    assert github.writes == []
    assert github.issues[0]["state"] == "open"
    assert capsys.readouterr().out.count("[dry-run]") == 4


def test_main_토큰이_없으면_2(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert alert_issue.main(["failure", "--workflow", "ingest", "--run-url", RUN_URL, "--repo", REPO]) == 2


def test_main_dry_run에서_토큰이_없으면_건너뜀(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    code = alert_issue.main(["success", "--workflow", "ingest", "--run-url", RUN_URL, "--repo", REPO, "--dry-run"])
    assert code == 0
    assert "건너뜁니다" in capsys.readouterr().out


def test_main_저장소는_GITHUB_REPOSITORY에서(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO)
    github = FakeGitHub()
    assert alert_issue.main(["failure", "--workflow", "ingest", "--run-url", RUN_URL], transport=github) == 0
    assert "opened #100" in capsys.readouterr().out


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_urllib_transport_요청_형식(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["method"] = request.get_method()
        seen["headers"] = dict(request.header_items())
        seen["body"] = json.loads(request.data)
        return FakeResponse(b'{"number": 1}')

    monkeypatch.setattr(alert_issue.urllib.request, "urlopen", fake_urlopen)
    send = alert_issue.urllib_transport("https://api.example.com/", "tok")
    assert send("POST", "/repos/o/r/issues", {"title": "t"}) == {"number": 1}

    assert seen["url"] == "https://api.example.com/repos/o/r/issues"
    assert seen["method"] == "POST"
    assert seen["headers"]["Authorization"] == "Bearer tok"
    assert seen["headers"]["Content-type"] == "application/json"
    assert seen["body"] == {"title": "t"}


def test_urllib_transport_HTTP_오류는_ApiError(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 422, "Unprocessable", {}, io.BytesIO(b"already_exists"))

    monkeypatch.setattr(alert_issue.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ApiError) as error:
        alert_issue.urllib_transport("https://api.example.com", "tok")("POST", "/x", {})
    assert error.value.status == 422


def test_urllib_transport_빈_응답은_None(monkeypatch):
    monkeypatch.setattr(alert_issue.urllib.request, "urlopen", lambda request, timeout: FakeResponse(b""))
    assert alert_issue.urllib_transport("https://api.example.com", "tok")("PATCH", "/x", {}) is None
