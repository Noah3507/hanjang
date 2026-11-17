import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import GenerationProgress, { completedShare } from './GenerationProgress'

const base = { productName: '아부라소바', strategyName: '가격', error: '', approval: null, onRetry: vi.fn(), onBack: vi.fn() }

describe('generation progress', () => {
  it('checks only the steps that really finished', () => {
    render(<GenerationProgress {...base} steps={{ photo: 'done', copy: 'running', designs: 'waiting', ranking: 'waiting' }} />)
    const items = screen.getAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual(['✓배경 정리 · 완료', '2문구 작성 · 진행 중', '3시안 4개 렌더링 · 대기', '4순위 매기기 · 대기'])
    const bar = screen.getByRole('progressbar', { name: '광고 생성 진행률' })
    expect(Number(bar.getAttribute('aria-valuenow'))).toBeGreaterThanOrEqual(25)
    expect(Number(bar.getAttribute('aria-valuenow'))).toBeLessThan(50)
    expect(screen.getByText(/아부라소바 사진으로 가격 전략 시안 4개/)).toBeInTheDocument()
  })
  it('counts finished steps for the certain share of the bar', () => {
    expect(completedShare({ photo: 'done', copy: 'done', designs: 'running', ranking: 'waiting' })).toBe(0.5)
    expect(completedShare({ photo: 'done', copy: 'done', designs: 'done', ranking: 'failed' })).toBe(1)
  })
  it('shows the failure with retry and back actions', () => {
    const onRetry = vi.fn(), onBack = vi.fn()
    render(<GenerationProgress {...base} error="문구 실패" onRetry={onRetry} onBack={onBack} steps={{ photo: 'done', copy: 'failed', designs: 'waiting', ranking: 'waiting' }} />)
    expect(screen.getByRole('heading', { name: '광고를 만들지 못했습니다' })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('문구 실패')
    fireEvent.click(screen.getByRole('button', { name: '다시 시도' })); fireEvent.click(screen.getByRole('button', { name: '입력으로 돌아가기' }))
    expect(onRetry).toHaveBeenCalledTimes(1); expect(onBack).toHaveBeenCalledTimes(1)
  })
  it('asks before a paid copy call', () => {
    const approve = vi.fn(), decline = vi.fn()
    render(<GenerationProgress {...base} approval={{ approve, decline }} steps={{ photo: 'done', copy: 'running', designs: 'waiting', ranking: 'waiting' }} />)
    expect(screen.getByRole('group', { name: '유료 문구 생성 확인' })).toHaveTextContent('유료 호출이 1회')
    fireEvent.click(screen.getByRole('button', { name: '취소' }))
    expect(decline).toHaveBeenCalledTimes(1); expect(approve).not.toHaveBeenCalled()
  })
})
