from __future__ import annotations

import errno
import shutil
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Tuple

from fastapi import UploadFile

from ..config import get_settings


settings = get_settings()


class UploadPersistenceError(Exception):
    """Raised when an uploaded UFDR archive cannot be persisted to disk."""


class UploadStorageFullError(UploadPersistenceError):
    """Raised when there is insufficient disk space to persist an upload."""


def persist_upload(upload: UploadFile) -> Tuple[Path, Path]:
    """Persist the uploaded UFDR archive to disk and return paths.

    Returns a tuple of (saved_archive_path, extraction_dir).
    """
    uploads_dir = settings.uploads_dir
    extraction_root = settings.extracted_dir

    uploads_dir.mkdir(parents=True, exist_ok=True)
    extraction_root.mkdir(parents=True, exist_ok=True)

    unique_id = uuid.uuid4().hex
    archive_filename = f"{unique_id}_{upload.filename}" if upload.filename else f"{unique_id}.ufdr"
    archive_path = uploads_dir / archive_filename
    extraction_dir = extraction_root / unique_id

    upload.file.seek(0)

    try:
        with archive_path.open("wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)
    except OSError as exc:  # pragma: no cover - depends on environment state
        with suppress(OSError):
            archive_path.unlink()
        if exc.errno == errno.ENOSPC:
            raise UploadStorageFullError("Insufficient disk space while saving UFDR upload") from exc
        raise UploadPersistenceError(f"Failed writing UFDR upload to disk: {exc}") from exc
    finally:
        upload.file.close()

    if extraction_dir.exists():
        shutil.rmtree(extraction_dir)
    extraction_dir.mkdir(parents=True, exist_ok=True)

    return archive_path, extraction_dir
