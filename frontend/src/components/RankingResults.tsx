import { useEffect, useRef, useState } from 'react'
import { rankingState, type RankingState } from '../api/ranking'
import type { RenderState } from '../api/rendering'
import type { UploadHandle } from '../api/uploads'
import { strategyLabels } from './AdResults'

export default function RankingResults({ handle, render, disabled }: { handle: UploadHandle; render: RenderState; disabled: boolean }) {
  const [state, setState] = useState<RankingState | null>(null)
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  const ticket = useRef(0)
  const signature = JSON.stringify([handle.upload.job_id, render.revision, render.source_asset_id, render.copy_key,
    render.candidates.map(c => [c.candidate_id, c.png.asset_id, c.revision])])
  const [receivedFor, setReceivedFor] = useState('')
  useEffect(() => {
    setState(null); setError(''); setReceivedFor('')
    const id = ++ticket.current
    if (!disabled && render.status === 'completed') void update(false, id)
    else setBusy(false)
    return () => { ticket.current++ }
    // Snapshot values, not object identity, define an in-flight request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, disabled, render.status, render.is_current])
  async function update(start: boolean, id = ++ticket.current) {
    setBusy(true); setError('')
    try {
      let next = await rankingState(handle, start ? render : undefined)
      for (let i=0; ; i++) {
        if (id !== ticket.current) return
        if (next.ranking && (next.revision === render.revision) &&
          (next.ranking.items.some(item => !render.candidates.some(c => c.candidate_id === item.candidate_id)))) {
          throw new Error('순위와 광고 결과가 일치하지 않습니다. 광고를 다시 조회해 주세요.')
        }
        setState(next); setReceivedFor(signature)
        if (next.status !== 'processing') break
        if (i >= 30) throw new Error('순위 조회 시간이 초과됐습니다. 다시 조회해 주세요.')
        await new Promise(resolve => setTimeout(resolve, 1000))
        if (id !== ticket.current) return
        next = await rankingState(handle)
      }
    } catch (e) { if (id === ticket.current) { setState(null); setError(e instanceof Error ? e.message : '순위 조회 오류') } }
    finally { if (id === ticket.current) setBusy(false) }
  }
  const current = !disabled && render.is_current && receivedFor === signature && state?.is_current && state.revision === render.revision
  const ranking = current && state.status === 'completed' ? state.ranking : null
  return <section aria-label="광고 임시 순위" className="ranking-results">
    <h4>광고 임시 순위</h4>
    <p className="mock-ranking-notice">시연용 임시 순위이며 실제 광고 품질 평가 결과가 아닙니다</p>
    <p className="help">MockRanker는 고정 시험값을 사용합니다. 실제 ML 모델은 연결되지 않았으며 선호 확률·CTR·매출 예측을 제공하지 않습니다.</p>
    <button disabled={disabled || busy || render.status !== 'completed'} onClick={() => void update(true)}>임시 순위 확인</button>{' '}
    <button disabled={disabled || busy} onClick={() => void update(false)}>순위 다시 조회</button>
    <p role="status">순위 상태: {busy ? '조회 중' : state?.status ?? '미조회'}</p>
    {error && <p role="alert">{error}</p>}{state?.error && <p role="alert">{state.error.message}</p>}
    {(disabled || (state && state.status !== 'pending' && !current)) && <p className="ranking-stale">현재 광고와 일치하는 순위가 아닙니다. 최신 광고를 조회한 후 임시 순위를 확인해 주세요.</p>}
    {!busy && !error && state?.status === 'pending' && <p>아직 생성된 순위가 없습니다.</p>}
    {ranking && <><p>순위 출처: {ranking.source === 'mock' ? 'MockRanker · 시연용' : ranking.source === 'fallback_mock' ? 'Mock 대체 결과' : '모델 상대 선호 순위'}</p>
      <ol>{ranking.items.map(item => { const c = render.candidates.find(c => c.candidate_id === item.candidate_id); return <li key={item.candidate_id}>{item.rank}위 · {c ? strategyLabels[c.strategy] : '알 수 없는 광고'}{c ? ` · ${c.strategy}` : ''}</li> })}</ol>
    </>}
  </section>
}
