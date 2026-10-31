import { useEffect, useRef, useState } from 'react'
import { rendering, type RenderState } from '../api/rendering'
import type { CopyState } from '../api/copy'
import type { Draft, UploadHandle } from '../api/uploads'
import AdResults from './AdResults'
import RankingResults from './RankingResults'
import AdEditor from './AdEditor'
export default function AdRendering({ handle, draft, asset, copy, disabled }: { handle: UploadHandle; draft: Draft; asset: string; copy: CopyState | null; disabled: boolean }) {
  const [state, setState] = useState<RenderState | null>(null)
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const ticket = useRef(0)
  const [editingBusy, setEditingBusy] = useState(false)
  useEffect(() => { const id = ++ticket.current; void update(false, id); return () => { ticket.current++ } }, [asset, draft, handle, copy?.copy_key]) // eslint-disable-line react-hooks/exhaustive-deps
  async function update(start: boolean, id = ++ticket.current) {
    setBusy(true); setError('')
    try {
      let next = await rendering(handle, start && copy ? { asset, draft, copy } : undefined)
      for (let i = 0; ; i++) {
        if (id !== ticket.current) return
        setState(next)
        if (next.status !== 'processing') break
        if (i >= 120) throw new Error('렌더링 조회 시간이 초과됐습니다. 상태를 다시 조회해 주세요.')
        await new Promise(resolve => setTimeout(resolve, 1000)); if (id !== ticket.current) return
        next = await rendering(handle)
      }
    } catch (e) { if (id === ticket.current) setError(e instanceof Error ? e.message : '렌더링 오류') }
    finally { if (id === ticket.current) setBusy(false) }
  }
  const stale = state && state.status !== 'pending' && (!state.is_current || disabled || state.source_asset_id !== asset || state.copy_key !== copy?.copy_key)
  return <section aria-label="4전략 광고 이미지" className="ad-rendering">
    <h3>4전략 광고 이미지</h3><p>광고 네 장을 확대해 비교하고 문구 편집·PNG/A4 PDF 다운로드와 시연용 임시 순위를 확인할 수 있습니다.</p>
    <button type="button" disabled={disabled || busy || editingBusy || !copy?.copy_key || !copy.is_current || copy.status !== 'completed'} onClick={() => void update(true)}>광고 4장 렌더링</button>{' '}
    <button type="button" disabled={busy} onClick={() => void update(false)}>광고 상태 다시 조회</button>
    <p role="status">렌더링 상태: {state?.status ?? '조회 중'}</p>
    {error && <p role="alert">{error}</p>}{state?.error && <p role="alert">{state.error.code}: {state.error.message}</p>}
    {stale && <p role="alert">이전 입력·사진·카피의 광고입니다. 최신 결과가 아닙니다. 저장·카피 생성 후 다시 렌더링해 주세요.</p>}
    {state?.mock_copy && state.status !== 'pending' && <p>Mock 카피 사용 · 실제 LLM 생성 광고가 아닙니다.</p>}
    {state?.status === 'pending' && <p>아직 생성된 광고가 없습니다. 최신 카피로 광고를 렌더링해 주세요.</p>}
    {state && <AdResults candidates={state.candidates} handle={handle} snapshot={JSON.stringify([state.revision, stale])} />}
    {state?.status === 'completed' && <AdEditor handle={handle} draft={draft} render={state} disabled={Boolean(stale)||disabled||busy} onBusy={setEditingBusy} onApplied={()=>void update(false)} />}
    {state && (state.status === 'completed' || state.candidates.length > 0) && <RankingResults handle={handle} render={state} disabled={Boolean(stale) || disabled || state.status !== 'completed'} />}
  </section>
}
