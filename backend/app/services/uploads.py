from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import re
import secrets
from threading import RLock
import uuid
import warnings

from PIL import Image, UnidentifiedImageError

from app.schemas.upload import DraftResponse, InputDraft, UploadResponse
from app.schemas.photo import PhotoAsset, PhotoResponse

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 24_000_000
MIN_SIDE = 256
TTL = timedelta(hours=24)


def now() -> datetime:
    return datetime.now(timezone.utc)


class UploadError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def validate_image(data: bytes, content_type: str | None) -> tuple[int, int, str]:
    if len(data) > MAX_BYTES:
        raise UploadError(413, "FILE_TOO_LARGE", "사진은 10 MiB 이하로 올려 주세요.")
    if content_type not in {"image/jpeg", "image/png"}:
        raise UploadError(415, "UNSUPPORTED_MEDIA", "JPG 또는 PNG 사진만 사용할 수 있습니다.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                mime = {"JPEG": "image/jpeg", "PNG": "image/png"}.get(image.format)
                if mime != content_type:
                    raise UploadError(415, "UNSUPPORTED_MEDIA", "파일의 실제 형식과 JPG/PNG 형식이 일치해야 합니다.")
                width, height = image.size
                if width * height > MAX_PIXELS:
                    raise UploadError(413, "FILE_TOO_LARGE", "사진은 24 메가픽셀 이하여야 합니다.")
                if min(width, height) < MIN_SIDE:
                    raise UploadError(422, "INVALID_IMAGE", "사진의 가로와 세로는 각각 256px 이상이어야 합니다.")
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()  # Decode to reject truncated files; never re-encode.
        return width, height, mime
    except (Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise UploadError(413, "FILE_TOO_LARGE", "사진의 해상도가 너무 큽니다.") from None
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise UploadError(422, "INVALID_IMAGE", "읽을 수 있는 JPG/PNG 사진을 선택해 주세요.") from None


@dataclass
class Record:
    owner: str  # Hash of session token, never a filesystem component.
    upload: UploadResponse
    path: Path
    draft: InputDraft | None = None
    photo: PhotoResponse | None = None
    derived: dict[str, Path] = field(default_factory=dict)
    analyses: dict = field(default_factory=dict)
    last_analysis: str | None = None
    copies: dict = field(default_factory=dict)
    last_copy: str | None = None
    renders: dict = field(default_factory=dict)
    last_render: str | None = None
    rankings: dict = field(default_factory=dict)
    last_ranking: str | None = None


class PrivateUploadStore:
    """One-server memory metadata + original bytes on private local disk."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.sessions: dict[str, datetime] = {}
        self.records: dict[str, Record] = {}
        self.assets: dict[str, str] = {}
        self.lock = RLock()

    def safe_path(self, name: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}\.(jpg|png)", name):
            raise UploadError(404, "RESOURCE_NOT_FOUND", "사진을 찾을 수 없습니다.")
        path = self.root / name
        if path.is_symlink() or path.resolve().parent != self.root:
            raise UploadError(404, "RESOURCE_NOT_FOUND", "사진을 찾을 수 없습니다.")
        return path

    def create_session(self) -> tuple[str, datetime]:
        token = secrets.token_urlsafe(32)
        expires = now() + TTL
        with self.lock:
            self.sessions[sha256(token.encode()).hexdigest()] = expires
        return token, expires

    def authenticate(self, token: str | None) -> str:
        owner = sha256((token or "").encode()).hexdigest()
        with self.lock:
            expiry = self.sessions.get(owner)
        if expiry is None or expiry <= now():
            raise UploadError(401, "SESSION_REQUIRED", "세션이 없거나 만료됐습니다. 다시 업로드해 주세요.")
        return owner

    def save(self, owner: str, data: bytes, dimensions: tuple[int, int, str]) -> UploadResponse:
        width, height, mime = dimensions
        asset = uuid.uuid4().hex
        job = uuid.uuid4().hex
        created = now()
        upload = UploadResponse(
            job_id=job, asset_id=asset, width=width, height=height, mime_type=mime,
            sha256=sha256(data).hexdigest(), created_at=created, expires_at=created + TTL,
        )
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.safe_path(asset + (".jpg" if mime == "image/jpeg" else ".png"))
        try:
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as output:
                output.write(data)
        except OSError:
            raise UploadError(503, "SERVICE_UNAVAILABLE", "사진을 저장할 수 없습니다. 잠시 후 다시 시도해 주세요.") from None
        with self.lock:
            self.records[job] = Record(owner, upload, path)
            self.assets[asset] = job
        return upload

    def get(self, owner: str, job: str) -> Record:
        with self.lock:
            record = self.records.get(job)
            if record is None or record.owner != owner:
                raise UploadError(404, "RESOURCE_NOT_FOUND", "작업을 찾을 수 없습니다.")
            if record.upload.expires_at <= now():
                raise UploadError(410, "RESOURCE_EXPIRED", "업로드가 만료됐습니다. 다시 올려 주세요.")
            return record

    def save_draft(self, owner: str, job: str, draft: InputDraft) -> DraftResponse:
        with self.lock:
            record = self.get(owner, job)
            # Legacy clients do not know the optional S5a fields: omission preserves them.
            updates = draft.model_dump()
            if record.draft:
                for name in ('product_features', 'use_address_for_copy'):
                    if name not in draft.model_fields_set:
                        updates[name] = getattr(record.draft, name)
            record.draft = InputDraft.model_validate(updates)
            return self.get_draft(owner, job)

    def get_draft(self, owner: str, job: str) -> DraftResponse:
        with self.lock:
            record = self.get(owner, job)
            if record.draft is None:
                raise UploadError(409, "INPUT_NOT_SAVED", "상품 정보가 아직 저장되지 않았습니다.")
            return DraftResponse(job_id=job, **record.draft.model_dump(), expires_at=record.upload.expires_at)

    def read_asset(self, owner: str, asset: str) -> tuple[bytes, str]:
        with self.lock:
            record = self.get(owner, self.assets.get(asset, ""))
            try:
                path = record.path if asset == record.upload.asset_id else record.derived.get(asset)
                if path is None:
                    raise UploadError(404, "RESOURCE_NOT_FOUND", "사진을 찾을 수 없습니다.")
                data = self.safe_path(path.name).read_bytes()
            except OSError:
                raise UploadError(404, "RESOURCE_NOT_FOUND", "원본 사진을 찾을 수 없습니다.") from None
            return data, record.upload.mime_type if asset == record.upload.asset_id else "image/png"

    def photo_state(self, owner: str, job: str) -> PhotoResponse:
        with self.lock:
            record = self.get(owner, job)
            if record.photo is None:
                record.photo = PhotoResponse(job_id=job, status="pending", expires_at=record.upload.expires_at,
                    original=PhotoAsset(**record.upload.model_dump()))
            return record.photo.model_copy(deep=True)

    def start_photo(self, owner: str, job: str) -> tuple[PhotoResponse, bool]:
        with self.lock:
            state = self.photo_state(owner, job)
            if state.status == "processing":
                raise UploadError(409, "PHOTO_PROCESSING_BUSY", "사진을 처리 중입니다. 완료 후 확인해 주세요.")
            if state.status == "completed":
                return state, False
            if any(r.photo and r.photo.status == "processing" for r in self.records.values()):
                raise UploadError(503, "PHOTO_PROCESSING_BUSY", "다른 사진을 처리 중입니다. 잠시 후 다시 시도해 주세요.")
            record = self.get(owner, job)
            record.photo.status = "processing"
            record.photo.warnings = []
            record.photo.photo_source = "original"
            return record.photo.model_copy(deep=True), True

    def finish_photo(self, owner: str, job: str, processor) -> None:
        written = []
        try:
            record = self.get(owner, job)
            data, _ = self.read_asset(owner, record.upload.asset_id)
            result = processor(data)
            with self.lock:
                record = self.get(owner, job)  # TTL may have elapsed during inference.
                processed = None
                if result.png:
                    for content in [result.png, result.mask_png]:
                        if content is None:
                            continue
                        asset = uuid.uuid4().hex
                        path = self.safe_path(asset + ".png")
                        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                        written.append((asset, path))
                        with os.fdopen(descriptor, "wb") as output:
                            output.write(content)
                        # Orphans after restart retain the upload's 24h clock.
                        timestamp = record.upload.created_at.timestamp()
                        os.utime(path, (timestamp, timestamp))
                    asset = written[0][0]
                    processed = PhotoAsset(asset_id=asset, width=result.width, height=result.height,
                                           mime_type="image/png", sha256=sha256(result.png).hexdigest())
                record.derived.update(dict(written))
                for asset, _ in written:
                    self.assets[asset] = job
                record.photo.processed = processed
                record.photo.status = "completed" if processed else "failed"
                record.photo.warnings = result.warnings
                record.photo.photo_source = "processed" if processed and not result.warnings else "original"
        except Exception:
            for _, path in written:
                path.unlink(missing_ok=True)
            with self.lock:
                record = self.records.get(job)
                if record and record.owner == owner:
                    record.photo.status = "failed"
                    record.photo.photo_source = "original"
                    record.photo.warnings = ["PHOTO_PROCESSING_FAILED"]

    def select_photo(self, owner: str, job: str, source: str) -> PhotoResponse:
        with self.lock:
            state = self.photo_state(owner, job)
            if state.status == "processing":
                raise UploadError(409, "PHOTO_PROCESSING_BUSY", "처리 완료 후 사진을 선택해 주세요.")
            if source == "processed" and state.processed is None:
                raise UploadError(409, "PHOTO_NOT_READY", "사용할 처리본이 없습니다. 원본을 사용해 주세요.")
            self.get(owner, job).photo.photo_source = source
            return self.photo_state(owner, job)

    def cleanup(self) -> None:
        with self.lock:
            current = now()
            for job, record in list(self.records.items()):
                if record.upload.expires_at <= current:
                    self.safe_path(record.path.name).unlink(missing_ok=True)
                    for asset, path in record.derived.items():
                        self.safe_path(path.name).unlink(missing_ok=True)
                        self.assets.pop(asset, None)
                    self.assets.pop(record.upload.asset_id, None)
                    del self.records[job]
            self.sessions = {key: value for key, value in self.sessions.items() if value > current}
            if self.root.is_dir():
                # Only generated original files in this dedicated directory.
                for path in self.root.iterdir():
                    if re.fullmatch(r"[a-f0-9]{32}\.(jpg|png)", path.name) and not path.is_symlink():
                        safe = self.safe_path(path.name)
                        if safe.stat().st_mtime <= (current - TTL).timestamp():
                            safe.unlink(missing_ok=True)
