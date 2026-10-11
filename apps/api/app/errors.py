from fastapi import HTTPException


def problem(status: int, code: str, message: str):
    raise HTTPException(status, detail={"code": code, "message": message})
