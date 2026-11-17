import { useEffect, useState } from 'react'
import { stepOrder, type StepId, type StepState } from '../flow/generate'

export const stepLabels: Record<StepId, string> = { photo: '배경 정리', copy: '문구 작성', designs: '시안 4개 렌더링', ranking: '순위 매기기' }
const stateText: Record<StepState, string> = { waiting: '대기', running: '진행 중', done: '완료', failed: '실패' }

/** Share of the bar that is certain: finished steps only. */
export function completedShare(steps: Record<StepId, StepState>) {
  return stepOrder.filter((id) => steps[id] === 'done' || steps[id] === 'failed').length / stepOrder.length
}

export default function GenerationProgress({ steps, productName, strategyName, error, approval, onRetry, onBack }: {
  steps: Record<StepId, StepState>; productName: string; strategyName: string; error: string
  approval: { approve: () => void; decline: () => void } | null
  onRetry: () => void; onBack: () => void
}) {
  const base = completedShare(steps)
  const running = stepOrder.some((id) => steps[id] === 'running') && !error && !approval
  // Between two real milestones the bar creeps toward, but never reaches, the next one.
  const [creep, setCreep] = useState(0)
  useEffect(() => {
    setCreep(0)
    if (!running) return
    const timer = setInterval(() => setCreep((value) => value + (0.9 - value) * 0.06), 250)
    return () => clearInterval(timer)
  }, [base, running])
  const percent = Math.min(100, Math.round((base + creep / stepOrder.length) * 100))
  const active = stepOrder.find((id) => steps[id] === 'running')
  return <section className="generation-progress" aria-labelledby="generation-title">
    <h2 id="generation-title">{error ? '광고를 만들지 못했습니다' : '광고를 만들고 있습니다'}</h2>
    {!error && <p className="generation-sub">{productName} 사진으로 {strategyName} 전략 시안 4개를 만드는 중이에요.</p>}
    <div className="progress-track" role="progressbar" aria-label="광고 생성 진행률" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
      <span style={{ width: `${percent}%` }} />
    </div>
    <p className="progress-caption"><span>{active ? `${stepLabels[active]} 중` : error ? '중단됨' : '준비 중'}</span><span>{percent}%</span></p>
    <ol className="step-list">{stepOrder.map((id, index) => <li key={id} className={`step ${steps[id]}`}>
      <span className="step-mark" aria-hidden="true">{steps[id] === 'done' ? '✓' : steps[id] === 'failed' ? '!' : index + 1}</span>
      <span>{stepLabels[id]}</span><span className="visually-hidden"> · {stateText[steps[id]]}</span>
    </li>)}</ol>
    {approval && <div className="approval" role="group" aria-label="유료 문구 생성 확인">
      <p>실제 AI 문구 생성이 켜져 있습니다. 계속하면 유료 호출이 1회 발생합니다.</p>
      <button type="button" onClick={approval.approve}>유료 호출 1회 진행</button>
      <button type="button" className="secondary" onClick={approval.decline}>취소</button>
    </div>}
    {error && <div className="generation-error">
      <p role="alert">{error}</p>
      <button type="button" onClick={onRetry}>다시 시도</button>
      <button type="button" className="secondary" onClick={onBack}>입력으로 돌아가기</button>
    </div>}
    {!error && <p className="generation-tip"><strong>알고 계셨나요?</strong> 한장은 상품 사진을 새로 그리거나 색을 보정하지 않아요. 올려 주신 사진으로 배경 정리와 배치만 해요.</p>}
  </section>
}
