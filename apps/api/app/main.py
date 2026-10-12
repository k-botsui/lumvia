import asyncio
import json
import logging
import time
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.analysis.routes import router as analysis_router
from app.auth.routes import router as auth_router
from app.auth.service import Principal, rate_limit, require_user
from app.cells.clips import router as clips_router
from app.cells.routes import router as cells_router
from app.collections.routes import router as collections_router
from app.config import settings
from app.context import request_id as current_request_id
from app.db import SessionLocal, get_db
from app.errors import problem
from app.jobs.routes import router as jobs_router
from app.link_shares import router as link_shares_router
from app.media.batch import router as batch_router
from app.media.covers import router as covers_router
from app.media.routes import router as media_router
from app.models import Asset, Media, Source
from app.search.routes import router as search_router
from app.sources.previews import router as previews_router
from app.sources.routes import router as sources_router
from app.storage.service import LocalStorage, storage
from app.support import router as support_router

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("lumvia.api")
upload_slots = asyncio.Semaphore(2)
app = FastAPI(
    title="Lumvia API",
    version="0.1.0",
    docs_url="/api/docs" if settings.environment != "production" else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.environment != "production" else None,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="lumvia_oidc",
    same_site="lax",
    https_only=settings.environment == "production",
    max_age=600,
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[urlparse(settings.app_url).hostname, "127.0.0.1", "localhost", "testserver", "api"],
)


class UploadLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = settings.max_upload_bytes + 1024 * 1024
        if scope["path"].startswith("/api/v1/link-shares"):
            limit = 2 * 1024 * 1024
        if scope["path"].endswith("/cover"):
            limit = 3 * 1024 * 1024
        headers = dict(scope["headers"])
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            length = limit + 1
        if length > limit:
            return await JSONResponse(
                {
                    "error": {
                        "code": "UPLOAD_TOO_LARGE",
                        "message": "画像は2 MB以下で選んでください。"
                        if limit == 3 * 1024 * 1024
                        else f"動画は{settings.max_upload_bytes // 1024**2} MB以下で追加してください。",
                    }
                },
                status_code=413,
            )(scope, receive, send)
        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > limit:
                raise HTTPException(
                    413,
                    detail={
                        "code": "UPLOAD_TOO_LARGE",
                        "message": "画像は2 MB以下で選んでください。"
                        if limit == 3 * 1024 * 1024
                        else f"動画は{settings.max_upload_bytes // 1024**2} MB以下で追加してください。",
                    },
                )
            return message

        return await self.app(scope, limited_receive, send)


app.add_middleware(UploadLimitMiddleware)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    current_request_id.set(request.state.request_id)
    started = time.monotonic()
    try:
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin != settings.app_url:
                problem(403, "ORIGIN_INVALID", "このリクエストは許可されていません。")
        if request.method == "POST" and request.url.path == "/api/v1/media":

            def guard_upload():
                with SessionLocal() as db:
                    principal = require_user(request, db)
                    rate_limit(f"upload-body:{principal.user.id}", 60, 60)

            await run_in_threadpool(guard_upload)
            if upload_slots.locked():
                problem(429, "UPLOAD_BUSY", "追加中の動画が完了してから、もう一度お試しください。")
            async with upload_slots:
                response = await call_next(request)
        else:
            response = await call_next(request)
    except HTTPException as exc:
        detail = (
            exc.detail
            if isinstance(exc.detail, dict)
            else {"code": "REQUEST_FAILED", "message": "リクエストを処理できません。"}
        )
        response = JSONResponse(
            {"error": detail, "request_id": request.state.request_id}, status_code=exc.status_code
        )
    except Exception:
        logger.error(json.dumps({"event": "request_failed", "request_id": request.state.request_id}))
        response = JSONResponse(
            {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "処理を完了できませんでした。しばらく待ってからお試しください。",
                },
                "request_id": request.state.request_id,
            },
            status_code=500,
        )
    response.headers.update(
        {
            "X-Request-ID": request.state.request_id,
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "same-origin",
            "X-Frame-Options": "DENY",
            "Cache-Control": "no-store",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }
    )
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    route = request.scope.get("route")
    logger.info(
        json.dumps(
            {
                "event": "request",
                "request_id": request.state.request_id,
                "method": request.method,
                "route": getattr(route, "path", "unmatched"),
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000),
            }
        )
    )
    return response


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    detail = (
        exc.detail
        if isinstance(exc.detail, dict)
        else {"code": "REQUEST_FAILED", "message": "リクエストを処理できません。"}
    )
    return JSONResponse(
        {"error": detail, "request_id": getattr(request.state, "request_id", None)},
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(
        {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "入力内容を確認してください。",
                "fields": [".".join(map(str, e["loc"][1:])) for e in exc.errors()],
            },
            "request_id": request.state.request_id,
        },
        status_code=422,
    )


@app.exception_handler(IntegrityError)
async def conflict_error(request, exc):
    return JSONResponse(
        {
            "error": {"code": "CONFLICT", "message": "同じ名前の項目があるか、別の操作が進行中です。"},
            "request_id": request.state.request_id,
        },
        status_code=409,
    )


api = APIRouter(prefix="/api/v1")
for router in [
    auth_router,
    media_router,
    covers_router,
    batch_router,
    cells_router,
    clips_router,
    collections_router,
    jobs_router,
    analysis_router,
    search_router,
    sources_router,
    previews_router,
    support_router,
]:
    api.include_router(router)


@api.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "version": "0.1.0"}


@api.get("/assets/{asset_id}")
def get_asset(
    asset_id: str, download: bool = False, p: Principal = Depends(require_user), db: Session = Depends(get_db)
):
    asset = db.scalar(select(Asset).join(Media).where(Asset.id == asset_id, Media.library_id == p.library.id))
    if not asset:
        problem(404, "NOT_FOUND", "ファイルが見つかりません。")
    if isinstance(storage, LocalStorage):
        path = storage.path(asset.key)
        if not path.is_file():
            problem(404, "ASSET_MISSING", "ファイルが見つかりません。保存場所を確認してください。")
        filename = (
            db.get(Source, db.get(Media, asset.media_id).source_id).original_name
            if download and asset.role == "original"
            else None
        )
        return FileResponse(
            path,
            filename=filename,
            media_type=asset.mime,
            content_disposition_type="attachment" if download else "inline",
            headers={"Cache-Control": "private, no-store"},
        )
    return RedirectResponse(storage.signed_url(asset.key), status_code=307)


@api.get("/library/export")
def export_library(p: Principal = Depends(require_user), db: Session = Depends(get_db)):
    from app.media.serializers import cell_list, group_list, media_list
    from app.models import (
        Cell,
        Collection,
        Shelf,
        collection_cells,
        collection_media,
        shelf_cells,
        shelf_media,
    )

    rate_limit(f"export:{p.user.id}", 5, 60)
    from fastapi.encoders import jsonable_encoder

    groups = {
        kind: group_list(db, model, p.library.id)
        for kind, model in [("shelves", Shelf), ("collections", Collection)]
    }
    result = {
        "schema_version": 2,
        "media": media_list(db, list(db.scalars(select(Media).where(Media.library_id == p.library.id)))),
        "cells": cell_list(db, list(db.scalars(select(Cell).where(Cell.library_id == p.library.id)))),
        **groups,
    }
    for name, table, model, key in [
        ("shelf_media", shelf_media, Shelf, "shelf_id"),
        ("shelf_cells", shelf_cells, Shelf, "shelf_id"),
        ("collection_media", collection_media, Collection, "collection_id"),
        ("collection_cells", collection_cells, Collection, "collection_id"),
    ]:
        result[name] = [
            dict(r._mapping)
            for r in db.execute(
                select(table).join(model, table.c[key] == model.id).where(model.library_id == p.library.id)
            )
        ]
    return JSONResponse(
        jsonable_encoder(result),
        headers={"Content-Disposition": 'attachment; filename="lumvia-library.json"'},
    )


api.include_router(link_shares_router)
app.include_router(api)
