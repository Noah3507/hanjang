import { useEffect, useRef, useState } from 'react'
import type { UploadHandle } from '../api/uploads'
import { choosePhoto, photoBlob, photoState, type PhotoState } from '../api/photos'
import PhotoAnalysis from './PhotoAnalysis'

const warningText: Record<string, string> = {
  PHOTO_MODEL_UNAVAILABLE: '배경 제거 모델이 없습니다. 자동 다운로드 없이 원본을 사용합니다.',
  PHOTO_PROCESSING_FAILED: '배경 제거에 실패했습니다. 원본을 사용해 주세요.',
  PHOTO_PROCESSING_TIMEOUT: '배경 제거 제한 시간이 초과됐습니다. 원본을 사용합니다.',
  PHOTO_MASK_INVALID: '유효한 배경 제거 마스크를 얻지 못했습니다. 원본을 사용합니다.',
  PHOTO_MASK_REVIEW_REQUIRED: '상품 일부가 손상됐을 수 있습니다. 원본과 비교해 주세요. 원본을 기본 선택했습니다.',
}
export default function PhotoProcessing({ handle }: { handle: UploadHandle }) {
  const [state, setState] = useState<PhotoState | null>(null)
  const [original, setOriginal] = useState('')
  const [processed, setProcessed] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const mounted = useRef(false)
  const urls = useRef<string[]>([])
  const run = useRef(0)
  function fail(value: unknown) { if (mounted.current) setError(value instanceof Error ? value.message : '사진 처리 오류가 발생했습니다.') }
  async function show(next: PhotoState) {
    if (!mounted.current) return
    setState(next)
    if (next.processed) {
      const blob = await photoBlob(handle, next.processed.asset_id)
      if (mounted.current) {
        const url = URL.createObjectURL(blob); urls.current.push(url); setProcessed(url)
      }
    }
  }
  async function poll(next: PhotoState, ticket: number) {
    for (let i = 0; next.status === 'processing' || next.status === 'pending'; i++) {
      if (!mounted.current || ticket !== run.current) return
      setState(next)
      if (i >= 130) throw new Error('상태 조회 시간이 초과됐습니다. 상태 다시 조회를 눌러 주세요.')
      await new Promise((resolve) => setTimeout(resolve, 1000))
      if (!mounted.current || ticket !== run.current) return
      next = await photoState(handle)
    }
    await show(next)
  }
  useEffect(() => {
    mounted.current = true
    const ticket = ++run.current
    void (async () => {
      try {
        const blob = await photoBlob(handle, handle.upload.asset_id)
        if (!mounted.current || ticket !== run.current) return
        const url = URL.createObjectURL(blob); urls.current.push(url); setOriginal(url)
        const next = await photoState(handle)
        if (!mounted.current || ticket !== run.current) return
        if (next.status === 'processing') { setBusy(true); await poll(next, ticket); setBusy(false) }
        else await show(next)
      } catch (value) { fail(value); if (mounted.current) setBusy(false) }
    })()
    return () => { mounted.current = false; run.current++; urls.current.forEach(URL.revokeObjectURL); urls.current = [] }
    // The parent keys this component by job ID; handle stays fixed for its lifetime.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handle])
  async function process(start: boolean) {
    setBusy(true); setError(''); const ticket = ++run.current
    try {
      const next = await photoState(handle, start)
      if (start || next.status === 'processing') await poll(next, ticket)
      else await show(next)
    } catch (value) { fail(value) }
    finally { if (mounted.current) setBusy(false) }
  }
  async function select(source: 'original' | 'processed') {
    setBusy(true); setError('')
    try { await show(await choosePhoto(handle, source)) } catch (value) { fail(value) }
    finally { if (mounted.current) setBusy(false) }
  }
  return <section className="photo-processing" aria-label="사진 전처리">
    <h3>배경 제거 및 사진 선택</h3>
    <p>원본은 보존합니다. 색 보정·상품 재생성·자르기 없이 배경 제거와 비율 유지 축소만 적용합니다.</p>
    <p>사진 처리 상태: {state?.status || '조회 중'} · 광고 생성은 시작하지 않습니다.</p>
    <button type="button" disabled={busy || !state || state.status === 'completed'} onClick={() => void process(true)}>배경 제거 시작</button>{' '}
    <button type="button" disabled={busy} onClick={() => void process(false)}>사진 상태 다시 조회</button>
    {error && <p role="alert">{error}</p>}
    <div role="status">{state?.warnings.map((warning) => <p key={warning}>{warningText[warning] || '처리 결과를 확인하고 원본 사용을 검토해 주세요.'}</p>)}</div>
    <div className="photo-comparison">
      <div>{original && <img src={original} alt="서버 보존 원본 사진" />}<button type="button" disabled={busy || !state} aria-pressed={state?.photo_source === 'original'} onClick={() => void select('original')}>원본 사용</button></div>
      <div>{processed && <img src={processed} alt="배경 제거 처리본 사진" />}<button type="button" disabled={busy || !state?.processed} aria-pressed={state?.photo_source === 'processed'} onClick={() => void select('processed')}>처리본 사용</button></div>
    </div>
    <p>선택된 사진: {state?.photo_source === 'processed' ? '처리본' : '원본'}</p>
    <p className="help">자동 검사는 상품 손상을 모두 판별하지 못합니다. 윤곽·색·누락 여부를 직접 비교해 주세요. 원본과 처리본은 업로드 시점부터 24시간 후 삭제됩니다.</p>
    {state && <PhotoAnalysis handle={handle} disabled={busy || state.status === 'processing'} asset={state.photo_source === 'processed' && state.processed ? state.processed.asset_id : state.original.asset_id} />}
  </section>
}
