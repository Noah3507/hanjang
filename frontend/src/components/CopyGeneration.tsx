import { useEffect, useRef, useState } from 'react'
import { copyState, type CopyState } from '../api/copy'
import type { Draft, UploadHandle } from '../api/uploads'
const labels = { emotional: '감성', price: '가격', visual: '비주얼', brand: '브랜드' }

export default function CopyGeneration({ handle, draft, asset, disabled }: { handle: UploadHandle; draft: Draft; asset: string; disabled: boolean }) {
  const [state, setState] = useState<CopyState | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const ticket = useRef(0)
  useEffect(() => {
    const id = ++ticket.current
    setBusy(false); setState(null); setError('')
    void update(false, id)
    return () => { ticket.current++ }
    // GET only on mount/snapshot change; never auto-generate or spend money.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asset, draft, handle])
  async function update(start: boolean, id = ++ticket.current) {
    setBusy(true); setError('')
    try {
      let next = await copyState(handle, start ? { asset, draft } : undefined)
      for (let i = 0; ; i++) {
        if (id !== ticket.current) return
        setState(next)
        if (next.status !== 'processing') break
        if (i >= 90) throw new Error('상태 조회 시간이 초과됐습니다. 다시 조회해 주세요.')
        await new Promise(resolve => setTimeout(resolve, 1000))
        if (id !== ticket.current) return
        next = await copyState(handle)
      }
    } catch (value) { if (id === ticket.current) setError(value instanceof Error ? value.message : '카피 생성 오류') }
    finally { if (id === ticket.current) setBusy(false) }
  }
  return <section aria-label="4전략 광고 카피" className="copy-generation">
    <h3>4전략 광고 카피 초안</h3>
    <p>이미지·순위·편집·다운로드는 생성하지 않습니다. 모든 문구는 사용자 검토가 필요합니다.</p>
    <p>{state?.provider === 'openai' ? `OpenAI 모드 · ${state.model}` : 'Mock 데모 · 고정 예시이며 실제 LLM 생성·품질 검증 결과가 아닙니다.'}</p>
    <button type="button" disabled={disabled || busy} onClick={() => void update(true)}>4전략 카피 생성</button>{' '}
    <button type="button" disabled={busy} onClick={() => void update(false)}>카피 상태 다시 조회</button>
    <p role="status">카피 상태: {state?.status ?? '조회 중'}</p>
    {error && <p role="alert">{error}</p>}
    {state?.error && <p role="alert">{state.error.code}: {state.error.message}</p>}
    {state && state.status !== 'pending' && (!state.is_current || state.source_asset_id !== asset) && <p role="alert">이전 입력 또는 사진의 카피입니다. 후속 광고 렌더링에 사용할 수 없습니다. 저장 후 다시 생성해 주세요.</p>}
    {state?.warnings.length ? <p>안내: {state.warnings.join(', ')}</p> : null}
    {state?.status === 'completed' && <>
      <p>원문 사실: {state.facts.store_name} / {state.facts.product_name} / {state.facts.price_text}</p>
      <p style={{ whiteSpace: 'pre-wrap' }}>사용자 제공 특징: {state.product_features ?? '미입력'}</p>
      <div className="copy-cards">{state.variants.map(v => <article key={v.strategy} aria-label={`${labels[v.strategy]} 전략 카피`}>
        <h4>{labels[v.strategy]} · {v.strategy}</h4><strong>{v.copy.headline}</strong><p>{v.copy.body}</p><p>{v.copy.cta}</p>
      </article>)}</div>
    </>}
    {state?.attempts.map(a => <p key={a.attempt}>시도 {a.attempt}: {a.latency_seconds.toFixed(3)}초 · 입력/출력 토큰 {a.input_tokens ?? '미측정'}/{a.output_tokens ?? '미측정'} · 비용 {a.estimated_cost_usd == null ? '미측정 (Mock은 API 호출 없음)' : `$${a.estimated_cost_usd.toFixed(6)}`}</p>)}
  </section>
}
