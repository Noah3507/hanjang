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

  return (
    <main className="foundation">
      <span className="eyebrow">SERVICE FOUNDATION</span>
      <h1>Hanjang</h1>
      <p className="intro">사진 한 장에서 시작하는 우리 가게 광고.</p>
      <section className="connection" aria-labelledby="connection-title">
        <h2 id="connection-title">개발 환경 연결 상태</h2>
        <p role="status" aria-label="백엔드 연결 상태" className={`status ${connection}`}>
          <span className="dot" aria-hidden="true" />{labels[connection]}
        </p>
        <p className="help">
          {connection === 'connected'
            ? 'FastAPI health API가 정상 응답했습니다. 광고 기능의 준비 상태를 의미하지 않습니다.'
            : connection === 'unavailable'
              ? '백엔드 서버 실행과 환경변수 설정을 확인한 뒤 다시 시도해 주세요.'
              : '로컬 FastAPI 서버의 응답을 확인하고 있습니다.'}
        </p>
        <button disabled={connection === 'checking'} onClick={() => setAttempt((value) => value + 1)}>
          연결 다시 확인
        </button>
      </section>
      <ProductInput />
      <p className="notice">상품 입력·사진 처리·카피·광고 PNG 생성과 결과 확대·Mock 임시 순위를 제공합니다. 실제 ML 순위·문구 편집·다운로드는 아직 구현되지 않았습니다.</p>
    </main>
  )
}
