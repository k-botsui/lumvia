from fastapi import APIRouter, Depends

from app.auth.service import Principal, require_user
from app.config import settings

router = APIRouter(tags=["Support"])


@router.get("/support")
def support(p: Principal = Depends(require_user)):
    repository = settings.support_github_repository
    return {
        "github_url": f"https://github.com/{repository}/issues/new" if repository else None,
        "local_only": True,
    }
