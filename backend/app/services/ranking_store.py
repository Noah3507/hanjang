"""Ranking is bound to a current render and private PNG content snapshots."""
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from threading import RLock
from PIL import Image
from app.ml_adapter.mock_ranker import MockRanker, STRATEGIES
from app.schemas.ranking import Ranking, RankingResponse, RankingError
from app.services.copy_store import digest
from app.services.uploads import UploadError


@dataclass
class Entry:
    identity: str
    response: RankingResponse


class RankingStore:
    def __init__(self, uploads, renders, ranker=None):
        self.uploads, self.renders = uploads, renders
        self.ranker = ranker if ranker is not None else MockRanker()
        self.lock = RLock()

    def context(self, owner, job):
        record = self.uploads.get(owner, job)
        if not record.renders:
            return record, None, None, None
        try:
            render = self.renders.get(owner, job)
        except UploadError as error:
            if error.status != 409:
                raise
            return record, None, None, None
        if render.status != 'completed' or not render.is_current:
            return record, render, None, None
        candidates = render.candidates
        if (len(candidates) != 4 or len({c.candidate_id for c in candidates}) != 4
            or len({c.png.asset_id for c in candidates}) != 4 or {c.strategy for c in candidates} != STRATEGIES
            or any(c.revision != render.revision or c.png.revision != render.revision
                   or c.facts != record.draft.facts for c in candidates)):
            raise UploadError(409, 'RANKING_CANDIDATES_INVALID', '광고 네 장의 정보가 일치하지 않습니다. 광고를 다시 조회해 주세요.')
        identity = digest({'revision': render.revision, 'source': render.source_asset_id,
            'copy': render.copy_key, 'candidates': [c.model_dump(mode='json', by_alias=True) for c in candidates]})
        hashes = []
        for c in candidates:
            # An asset from another job must never become a ranking input.
            if self.uploads.assets.get(c.png.asset_id) != job or c.png.asset_id not in record.derived:
                raise UploadError(404, 'RESOURCE_NOT_FOUND', '광고 이미지에 접근할 수 없습니다. 다시 렌더링해 주세요.')
            data, mime = self.uploads.read_asset(owner, c.png.asset_id)
            try:
                with Image.open(BytesIO(data)) as image:
                    if mime != 'image/png' or image.format != 'PNG' or image.mode != 'RGB' or image.size != (1080, 1350):
                        raise ValueError('Invalid final PNG')
                    image.verify()
            except Exception:
                raise UploadError(409, 'RANKING_ASSET_INVALID', '광고 이미지가 올바르지 않습니다. 다시 렌더링해 주세요.') from None
            hashes.append(sha256(data).hexdigest())
        return record, render, identity, digest({'identity': identity, 'pngs': hashes})

    def blank(self, job, record, render):
        return RankingResponse(job_id=job, status='pending', status_url=f'/api/v1/jobs/{job}/ranking',
            revision=render.revision if render else None, expires_at=record.upload.expires_at)

    def get(self, owner, job):
        with self.lock, self.renders.locked():
            record, render, _, key = self.context(owner, job)
            entry = record.rankings.get(key) or record.rankings.get(record.last_ranking)
            if entry is None:
                return self.blank(job, record, render)
            result = entry.response.model_copy(deep=True)
            result.is_current = key is not None and record.rankings.get(key) is entry
            return result

    def start(self, owner, job, body):
        with self.lock, self.renders.locked():
            record, render, identity, key = self.context(owner, job)
            if key is None:
                raise UploadError(409, 'RANKING_RENDER_NOT_READY', '최신 광고 네 장의 생성이 완료된 후 다시 시도해 주세요.')
            if body.expected_render_revision != render.revision or set(body.expected_candidate_ids) != {c.candidate_id for c in render.candidates}:
                raise UploadError(409, 'RANKING_SOURCE_CHANGED', '광고 결과가 변경됐습니다. 최신 광고를 다시 조회해 주세요.')
            if any(e.identity == identity and k != key for k, e in record.rankings.items()):
                raise UploadError(409, 'RANKING_ASSET_CHANGED', '광고 이미지가 변경됐습니다. 다시 렌더링해 주세요.')
            entry = record.rankings.get(key)
            if entry and entry.response.status in ('processing', 'completed'):
                record.last_ranking = key
                return self.get(owner, job), None
            response = self.blank(job, record, render)
            response.status, response.is_current = 'processing', True
            response.warnings = ['MOCK_RANKING_NOT_QUALITY_EVALUATION']
            record.rankings[key] = Entry(identity, response)
            record.last_ranking = key
            return response.model_copy(deep=True), (key, render.revision, [c.model_copy(deep=True) for c in render.candidates])

    def finish(self, owner, job, task):
        key, revision, candidates = task
        try:
            result = Ranking.model_validate(self.ranker.rank(candidates, revision).model_dump(mode='json'))
            if result.revision != revision or {i.candidate_id for i in result.items} != {c.candidate_id for c in candidates}:
                raise ValueError('Ranking output does not match render')
            with self.lock, self.renders.locked():
                record, _, _, current_key = self.context(owner, job)
                response = record.rankings[key].response
                response.status, response.ranking = 'completed', result
                response.is_current = current_key == key
        except Exception:
            with self.lock, self.renders.locked():
                try:
                    record = self.uploads.get(owner, job)
                except UploadError:
                    return  # Never publish after TTL or cleanup.
                response = record.rankings[key].response
                response.status, response.ranking, response.is_current = 'failed', None, False
                response.error = RankingError(code='RANKING_FAILED', message='임시 순위를 확인하지 못했습니다. 광고는 유지됩니다. 다시 시도해 주세요.')
