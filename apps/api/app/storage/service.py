import shutil
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

import boto3
from app.config import settings
from botocore.config import Config


class Storage(Protocol):
    def put(self, key: str, source: Path, mime: str) -> None: ...
    def delete(self, key: str) -> None: ...
    def materialize(self, key: str): ...


class LocalStorage:
    def path(self, key):
        root = settings.storage_root.resolve()
        path = (root / key).resolve()
        if not path.is_relative_to(root) or path == root:
            raise ValueError("Invalid object key")
        return path

    def put(self, key, source, mime):
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        staging = target.with_suffix(target.suffix + ".partial")
        shutil.copyfile(source, staging)
        staging.chmod(0o600)
        staging.replace(target)

    def delete(self, key):
        self.path(key).unlink(missing_ok=True)

    @contextmanager
    def materialize(self, key):
        yield self.path(key)


class S3Storage:
    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(
                signature_version="s3v4", connect_timeout=5, read_timeout=60, retries={"max_attempts": 3}
            ),
        )

    def put(self, key, source, mime):
        self.client.upload_file(str(source), settings.s3_bucket, key, ExtraArgs={"ContentType": mime})

    def delete(self, key):
        self.client.delete_object(Bucket=settings.s3_bucket, Key=key)

    def signed_url(self, key):
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": settings.s3_bucket, "Key": key}, ExpiresIn=60
        )

    @contextmanager
    def materialize(self, key):
        with TemporaryDirectory(prefix="lumvia-asset-") as directory:
            path = Path(directory) / "input"
            self.client.download_file(settings.s3_bucket, key, str(path))
            yield path


storage = S3Storage() if settings.storage_backend == "s3" else LocalStorage()
