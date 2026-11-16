import { useEffect, useState } from 'react'
import { getHealth } from './api/health'
import ProductInput from './components/ProductInput'

type Connection = 'checking' | 'connected' | 'unavailable'

export default function App() {
  const [connection, setConnection] = useState<Connection>('checking')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setConnection('checking')
    const timeout = window.setTimeout(() => controller.abort(), 5000)
    getHealth(controller.signal)
      .then(() => { if (active) setConnection('connected') })
      .catch(() => { if (active) setConnection('unavailable') })
      .finally(() => window.clearTimeout(timeout))
    return () => {
      active = false
      window.clearTimeout(timeout)
      controller.abort()
    }
  }, [attempt])

  const labels = {
    checking: '백엔드 연결 확인 중',
    connected: '백엔드 연결됨',
    unavailable: '백엔드 연결 불가',
  }

  const status = (
    <p role="status" aria-label="백엔드 연결 상태" className={`status ${connection}`}>
      <span className="dot" aria-hidden="true" />{labels[connection]}
    </p>
  )
  const retry = (
    <button className="retry" disabled={connection === 'checking'} onClick={() => setAttempt((value) => value + 1)}>
      연결 다시 확인
    </button>
  )

  return (
    <main className="foundation">
      <header className="brand">
        <span className="brand-mark" aria-hidden="true" />
        <h1>한장</h1>
      </header>
      <p className="intro">사진 한 장으로<br />광고 시안 4개를 만들어요</p>
      <p className="intro-sub">상품 사진과 가게 정보만 준비해 주세요.</p>
      {connection !== 'connected' && (
        <section className="connection" aria-labelledby="connection-title">
          <h2 id="connection-title">서버 연결 상태</h2>
          {status}
          <p className="help">
            {connection === 'unavailable'
              ? '백엔드 서버 실행과 환경변수 설정을 확인한 뒤 다시 시도해 주세요.'
              : '서버의 응답을 확인하고 있습니다.'}
          </p>
          {retry}
        </section>
      )}
      <ProductInput />
      <footer className="site-footer">
        <p className="notice">상품 입력·사진 처리·카피·광고 PNG 생성·문구 편집·PNG/A4 PDF 다운로드와 실제 모델 선호 순위를 제공합니다. 가독성 진단은 모델 점수와 별개입니다.</p>
        {connection === 'connected' && <div className="connection-line">{status}{retry}</div>}
      </footer>
    </main>
  )
}
