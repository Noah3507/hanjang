import { useEffect, useRef, useState } from 'react'
import { rendering, preview, type RenderState } from '../api/rendering'
import type { CopyState } from '../api/copy'
import type { Draft, UploadHandle } from '../api/uploads'
const labels = { emotional: '감성', price: '가격', visual: '비주얼', brand: '브랜드' }
function AdImage({ handle, asset, label }: { handle: UploadHandle; asset: string; label: string }) {
  const [url, setUrl] = useState(''); const [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false; let objectUrl = ''
    setUrl(''); setError('')
    void preview(handle, asset).then(blob => { if (!cancelled) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl) } }).catch(() => { if (!cancelled) setError('이미지에 접근하지 못했습니다. 상태를 다시 조회해 주세요.') })
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [handle, asset])
  return error ? <p role="alert">{error}</p> : url ? <img src={url} alt={`${label} 전략 광고 PNG`} width="1080" height="1350" onError={() => setError('광고 이미지를 표시하지 못했습니다.')} /> : <p>이미지 조회 중</p>
}
export default function AdRendering({ handle, draft, asset, copy, disabled }: { handle: UploadHandle; draft: Draft; asset: string; copy: CopyState | null; disabled: boolean }) {
  const [state, setState] = useState<RenderState | null>(null)
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const ticket = useRef(0)
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
    <h3>4전략 광고 이미지</h3><p>1080×1350 PNG 미리보기 · 순위·편집·다운로드는 후속 단계입니다.</p>
    <button type="button" disabled={disabled || busy || !copy?.copy_key || !copy.is_current || copy.status !== 'completed'} onClick={() => void update(true)}>광고 4장 렌더링</button>{' '}
    <button type="button" disabled={busy} onClick={() => void update(false)}>광고 상태 다시 조회</button>
    <p role="status">렌더링 상태: {state?.status ?? '조회 중'}</p>
    {error && <p role="alert">{error}</p>}{state?.error && <p role="alert">{state.error.code}: {state.error.message}</p>}
    {stale && <p role="alert">이전 입력·사진·카피의 광고입니다. 최신 결과가 아닙니다. 저장·카피 생성 후 다시 렌더링해 주세요.</p>}
    {state?.mock_copy && state.status !== 'pending' && <p>Mock 카피 사용 · 실제 LLM 생성 광고가 아닙니다.</p>}
    <div className="ad-cards">{state?.candidates.map(c => <article key={c.candidate_id}>
      <h4>{labels[c.strategy]} · {c.strategy}</h4><AdImage handle={handle} asset={c.png.asset_id} label={labels[c.strategy]} />
    </article>)}</div>
  </section>
}
