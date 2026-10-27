import { useEffect, useRef, useState } from 'react'
import type { UploadHandle } from '../api/uploads'
import { analysisState, type AnalysisState } from '../api/analysis'

export default function PhotoAnalysis({ handle, asset, disabled }: { handle: UploadHandle; asset: string; disabled: boolean }) {
  const [state, setState] = useState<AnalysisState | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const ticket = useRef(0)
  useEffect(() => {
    const id = ++ticket.current
    setState(null); setBusy(false); setError('')
    void update(undefined, id)
    return () => { ticket.current++ }
    // One upload handle is stable; invalidate in-flight responses on source change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asset, handle])
  async function update(start?: string, id = ++ticket.current) {
    setBusy(true); setError('')
    try {
      let next = await analysisState(handle, start)
      for (let i = 0; ; i++) {
        if (id !== ticket.current) return
        setState(next)
        if (next.status !== 'processing') break
        if (i >= 310) throw new Error('분석 상태 조회 시간이 초과됐습니다. 상태를 다시 조회해 주세요.')
        await new Promise(resolve => setTimeout(resolve, 1000))
        if (id !== ticket.current) return
        next = await analysisState(handle)
      }
    } catch (value) {
      if (id === ticket.current) setError(value instanceof Error ? value.message : '분석 실패')
    } finally { if (id === ticket.current) setBusy(false) }
  }
  const current = state?.is_current && state.source_asset_id === asset
  return <section aria-label="상품 사진 분석" className="photo-analysis">
    <h3>CLIP 시각 단서와 대표색</h3>
    <p>선택한 사진을 분석합니다. 단서는 후보 문구와의 유사도이며 확률·음식 사실·선호도 점수가 아닙니다. 상품명과 가격은 변경하지 않습니다.</p>
    <button type="button" disabled={disabled || busy || !asset} onClick={() => void update(asset)}>선택 사진 분석</button>{' '}
    <button type="button" disabled={busy} onClick={() => void update()}>분석 상태 다시 조회</button>
    <p role="status">분석 상태: {state?.status || '조회 중'}</p>
    {error && <p role="alert">{error}</p>}
    {state?.error && <p role="alert">{state.error.message}</p>}
    {state && state.status !== 'pending' && !current && <p role="alert">이전 사진의 분석 결과입니다. 현재 사진의 후속 광고 생성에는 사용하지 않습니다. 재분석해 주세요.</p>}
    {state?.warnings.length ? <p>분석 경고: {state.warnings.join(', ')} · 사진과 입력은 유지됩니다.</p> : null}
    {state?.status === 'completed' && <>
      <p>CLIP: {state.clip.status === 'available' ? '실제 모델 시각 단서' : '사용 불가 · 추정 단서 없음'}</p>
      <ul>{[...(state.clip.cues || [])].sort((a, b) => b.similarity - a.similarity).map(cue =>
        <li key={cue.candidate_id}>{cue.label}: {cue.similarity.toFixed(3)} (cosine similarity)</li>)}</ul>
      <h4>대표색 · 유효 샘플 픽셀 비중</h4>
      <p>원본 사진의 배경색이 포함될 수 있습니다. 투명 픽셀은 제외합니다.</p>
      <ul className="palette">{state.palette.colors.map(color => <li key={color.hex}>
        <span aria-hidden="true" style={{ backgroundColor: color.hex, display: 'inline-block', width: 24, height: 24, border: '1px solid #666' }} />{' '}
        {color.hex} · RGB {color.rgb.join(', ')} · {(color.proportion * 100).toFixed(1)}%
      </li>)}</ul>
    </>}
  </section>
}
