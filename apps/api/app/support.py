"""Explicit publication of a user's message through the local GitHub CLI identity."""

import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from app.auth.service import Principal, rate_limit, require_user
from app.config import settings
from app.db import get_db
from app.errors import problem
from app.models import SupportSubmission

router = APIRouter(tags=["Support"])


class SupportMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)

    @field_validator("subject", "body")
    @classmethod
    def not_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Message must not be blank")
        return value


def github(arguments, payload=None):
    executable = shutil.which("gh")
    if not executable:
        problem(503, "GITHUB_UNAVAILABLE", "GitHub接続が未設定です。接続手順を確認してください。")
    # The local CLI manages credentials; tokens never enter the frontend or arguments.
    env = {**os.environ, "GH_PROMPT_DISABLED": "1", "GH_DEBUG": "", "NO_COLOR": "1"}
    return subprocess.run(
        [executable, "api", "--hostname", "github.com", *arguments],
        input=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def github_account():
    if not shutil.which("gh"):
        return None
    try:
        response = github(["user", "--method", "GET"])
        if response.returncode:
            return None
        account = json.loads(response.stdout).get("login", "")
        return account if re.fullmatch(r"[A-Za-z0-9-]{1,39}", account) else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def gateway_request(path, payload=None):
    with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
        url = settings.support_gateway_url.rstrip("/") + path
        return client.get(url) if payload is None else client.post(url, json=payload)


@router.get("/support")
def support(p: Principal = Depends(require_user)):
    repository = settings.support_github_repository
    ready = False
    if repository and settings.support_gateway_url:
        try:
            response = gateway_request("/status")
            data = response.json()
            ready = (
                response.status_code == 200
                and data.get("repository") == repository
                and data.get("can_submit") is True
            )
        except (httpx.HTTPError, ValueError):
            pass
    elif repository and settings.support_operator_delivery:
        ready = bool(github_account())
    return {
        "github_url": f"https://github.com/{repository}/issues" if repository else None,
        "repository": repository or None,
        "can_submit": ready,
        "local_only": False,
    }


@router.post("/support", status_code=201)
def submit(data: SupportMessage, p: Principal = Depends(require_user), db: DBSession = Depends(get_db)):
    repository = settings.support_github_repository
    if not repository:
        problem(503, "SUPPORT_DISABLED", "問い合わせ窓口が設定されていません。")
    key = str(data.request_id)
    fingerprint = hmac.new(
        settings.secret_key.encode(),
        json.dumps([repository, data.subject, data.body], ensure_ascii=False).encode(),
        hashlib.sha256,
    ).hexdigest()

    def existing_result(item):
        if item.payload_hash != fingerprint:
            problem(409, "SUPPORT_CONFLICT", "送信内容が変わっています。画面を開き直してください。")
        if item.state == "sent":
            return {"issue_url": item.issue_url, "issue_number": item.issue_number}
        problem(
            409,
            "SUPPORT_PENDING",
            "送信結果を確認中です。重複を避けるためGitHubのIssue一覧を確認してください。",
        )

    previous = db.scalar(
        select(SupportSubmission).where(
            SupportSubmission.user_id == p.user.id, SupportSubmission.request_id == key
        )
    )
    if previous:
        return existing_result(previous)
    rate_limit(f"support:{p.user.id}", 5, 3600)
    if not settings.support_gateway_url and not (settings.support_operator_delivery and github_account()):
        problem(503, "GITHUB_UNAVAILABLE", "問い合わせ窓口は準備中です。入力内容は残しています。")
    item = SupportSubmission(user_id=p.user.id, request_id=key, payload_hash=fingerprint, state="pending")
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return existing_result(
            db.scalar(
                select(SupportSubmission).where(
                    SupportSubmission.user_id == p.user.id, SupportSubmission.request_id == key
                )
            )
        )
    try:
        if settings.support_gateway_url:
            response = gateway_request(
                "/issues", {"request_id": key, "subject": data.subject, "body": data.body}
            )
            result = response.json()
            success = response.status_code == 201
        else:
            response = github(
                [f"repos/{repository}/issues", "--method", "POST", "--input", "-"],
                {"title": data.subject, "body": data.body},
            )
            result = json.loads(response.stdout) if response.stdout else {}
            result = {"issue_url": result.get("html_url"), "issue_number": result.get("number")}
            success = response.returncode == 0
        url, number = result.get("issue_url", ""), result.get("issue_number")
        if (
            success
            and isinstance(number, int)
            and number > 0
            and url == f"https://github.com/{repository}/issues/{number}"
        ):
            item.state, item.issue_url, item.issue_number = "sent", url, number
            db.commit()
            return {"issue_url": url, "issue_number": number}
    except (OSError, subprocess.TimeoutExpired, ValueError, httpx.HTTPError):
        pass
    # A timeout may follow a successful GitHub write. Do not automatically resend.
    item.state = "uncertain"
    db.commit()
    problem(
        502,
        "SUPPORT_UNCERTAIN",
        "送信結果を確認できませんでした。内容は残しています。再送の前にGitHubのIssue一覧を確認してください。",
    )
