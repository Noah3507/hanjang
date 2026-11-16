import { useEffect, useRef, useState } from 'react'
import { preview, type RenderCandidate } from '../api/rendering'
import type { UploadHandle } from '../api/uploads'

export const strategyLabels = { emotional: '감성', price: '가격', visual: '비주얼', brand: '브랜드' }

function ResultCard({ candidate, handle, onSelectStrategy, selectedStrategy }: { candidate: RenderCandidate; handle: UploadHandle; onSelectStrategy?:(strategy:RenderCandidate['strategy'])=>void;selectedStrategy?:RenderCandidate['strategy'] }) {
  const [url, setUrl] = useState(''); const [error, setError] = useState(''); const [attempt, setAttempt] = useState(0)
  const dialog = useRef<HTMLDialogElement>(null); const trigger = useRef<HTMLButtonElement>(null)
  const label = strategyLabels[candidate.strategy]
  useEffect(() => {
    let cancelled = false; let objectUrl = ''
    setUrl(''); setError('')
    void preview(handle, candidate.png.asset_id).then(blob => {
      if (!cancelled) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl) }
    }).catch(() => { if (!cancelled) setError('광고 이미지에 접근하지 못했습니다. 만료 여부를 확인하거나 다시 시도해 주세요.') })
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [handle, candidate.png.asset_id, attempt])
  function imageFailed() { dialog.current?.close(); setError('광고 이미지를 표시하지 못했습니다.'); setUrl('') }
  return <article aria-label={`${label} 광고 결과`}>
    <h4>{label} · {candidate.strategy}</h4>
    {onSelectStrategy&&<button type="button" aria-pressed={selectedStrategy===candidate.strategy} onClick={()=>onSelectStrategy(candidate.strategy)}>{label} 디자인 전략으로 선택</button>}
    {error ? <><p role="alert">{error}</p><button onClick={() => setAttempt(n => n+1)}>이미지 다시 조회 · {label}</button></>
      : url ? <><button className="ad-preview-button" ref={trigger} aria-label={`${label} 광고 확대 보기`} onClick={() => dialog.current?.showModal()}>
        <img src={url} alt={`${label} 전략 광고 PNG`} width="1080" height="1350" onError={imageFailed} />
        <span>확대 보기</span>
      </button>
      <dialog className="ad-preview-dialog" ref={dialog} aria-label={`${label} 광고 확대`} onClose={() => trigger.current?.focus()}
        onKeyDown={event => { if (event.key === 'Tab') { event.preventDefault(); dialog.current?.querySelector('button')?.focus() } }}>
        <button autoFocus onClick={() => dialog.current?.close()}>확대 화면 닫기 · {label}</button>
        <img src={url} alt={`확대한 ${label} 전략 광고 PNG`} width="1080" height="1350" onError={imageFailed} />
      </dialog></> : <p>이미지 조회 중</p>}
  </article>
}

export default function AdResults({ candidates, handle, snapshot, onSelectStrategy, selectedStrategy }: { candidates: RenderCandidate[]; handle: UploadHandle; snapshot: string; onSelectStrategy?:(strategy:RenderCandidate['strategy'])=>void;selectedStrategy?:RenderCandidate['strategy'] }) {
  return <div className="ad-cards">{candidates.map(c => <ResultCard key={`${snapshot}:${c.candidate_id}:${c.png.asset_id}`} candidate={c} handle={handle} onSelectStrategy={onSelectStrategy} selectedStrategy={selectedStrategy} />)}</div>
}
