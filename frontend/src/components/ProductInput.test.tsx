import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ProductInput from './ProductInput'
import { ApiError, getInput, getOriginal, saveInput, uploadPhoto } from '../api/uploads'
import { generateAds, GenerationCancelled } from '../flow/generate'

vi.mock('../flow/generate', async (load) => ({ ...await load<typeof import('../flow/generate')>(), generateAds: vi.fn() }))
vi.mock('../api/uploads', async (load) => ({ ...await load<typeof import('../api/uploads')>(),
  getInput: vi.fn(), getOriginal: vi.fn(), saveInput: vi.fn(), uploadPhoto: vi.fn(),
}))
const handle = { token: 'test-only-token', upload: { job_id: 'job', asset_id: 'asset', width: 300, height: 300,
  mime_type: 'image/png' as const, sha256: 'a'.repeat(64), created_at: '2026-10-12T00:00:00Z', expires_at: '2026-10-13T00:00:00Z' } }
const facts = { store_name: '  테스트 가게  ', product_name: '한글 메뉴 🍜', price_text: ' 10,500 원 ', address: null, instagram_handle: null }
const saved = { job_id: 'job', status: 'pending' as const, facts, mood: 'warm' as const, expires_at: handle.upload.expires_at }

beforeEach(() => {
  vi.clearAllMocks(); sessionStorage.clear()
  URL.createObjectURL = vi.fn(() => 'blob:test-only')
  URL.revokeObjectURL = vi.fn()
  vi.mocked(uploadPhoto).mockResolvedValue(handle)
  vi.mocked(saveInput).mockResolvedValue(saved)
  vi.mocked(getInput).mockResolvedValue(saved)
  vi.mocked(getOriginal).mockResolvedValue(new Blob(['fixture']))
})
function fill() {
  fireEvent.change(screen.getByLabelText('상품 사진'), { target: { files: [new File(['fixture'], 'photo.png', { type: 'image/png' })] } })
  fireEvent.change(screen.getByLabelText('가게명'), { target: { value: facts.store_name } })
  fireEvent.change(screen.getByLabelText('상품명'), { target: { value: facts.product_name } })
  fireEvent.change(screen.getByLabelText('가격'), { target: { value: facts.price_text } })
  fireEvent.change(screen.getByLabelText('광고 분위기'), { target: { value: 'warm' } })
}
describe('product input', () => {
  it('blocks empty inputs without calling upload APIs', () => {
    render(<ProductInput />)
    fireEvent.click(screen.getByRole('button', { name: '상품 정보와 사진 저장' }))
    expect(screen.getByRole('alert')).toHaveTextContent('입력 항목')
    expect(uploadPhoto).not.toHaveBeenCalled()
  })
  it('preserves the exact facts and shows the server-read draft', async () => {
    render(<ProductInput />); fill()
    fireEvent.click(screen.getByRole('button', { name: '상품 정보와 사진 저장' }))
    await waitFor(() => expect(saveInput).toHaveBeenCalledWith(handle, facts, 'warm', { product_features: null, use_address_for_copy: false }))
    await waitFor(() => expect(screen.getByRole('region', { name: '저장된 상품 정보' })).toBeInTheDocument())
    expect(getInput).toHaveBeenCalledWith(handle)
    expect(within(screen.getByRole('region', { name: '저장된 상품 정보' })).getByText('작업 상태: pending · 분위기: warm')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '저장 정보 다시 조회' }))
    await waitFor(() => expect(getOriginal).toHaveBeenCalledWith(handle))
    expect(screen.getByLabelText('가게명')).toHaveValue(facts.store_name)
    expect(screen.getByLabelText('가격')).toHaveValue(facts.price_text)
  })
  it('starts with the price strategy and a warm mood so only the photo and three facts are required', () => {
    render(<ProductInput />)
    expect(screen.getByRole('radio', { name: /가격 전략/ })).toBeChecked()
    expect(screen.getAllByRole('radio')).toHaveLength(4)
    expect(screen.getByLabelText('광고 분위기')).toHaveValue('warm')
    expect(screen.getByLabelText('상품 사진')).toHaveAccessibleDescription(/JPG, PNG/)
  })
  it('hands the chosen strategy to the design step of the saved job', async () => {
    render(<ProductInput />); fill()
    fireEvent.click(screen.getByRole('radio', { name: /비주얼 전략/ }))
    fireEvent.click(screen.getByRole('button', { name: '상품 정보와 사진 저장' }))
    await waitFor(() => expect(screen.getByRole('region', { name: '저장된 상품 정보' })).toBeInTheDocument())
    expect(sessionStorage.getItem('hanjang-v3-strategy:job')).toBe('visual')
    expect(saveInput).toHaveBeenCalledWith(handle, facts, 'warm', { product_features: null, use_address_for_copy: false })
  })
  it('does not start generation while the input is incomplete', () => {
    render(<ProductInput />)
    fireEvent.click(screen.getByRole('button', { name: '광고 생성하기' }))
    expect(screen.getByRole('alert')).toHaveTextContent('입력 항목')
    expect(generateAds).not.toHaveBeenCalled()
  })
  it('saves, shows real step progress, then returns with the result notice', async () => {
    let finish: (value: unknown) => void = () => {}
    vi.mocked(generateAds).mockImplementation((_handle, _draft, _strategy, options) => {
      options.onStep('photo', 'done'); options.onStep('copy', 'running')
      return new Promise((resolve) => { finish = resolve as (value: unknown) => void })
    })
    render(<ProductInput />); fill()
    fireEvent.click(screen.getByRole('radio', { name: /브랜드 전략/ }))
    fireEvent.click(screen.getByRole('button', { name: '광고 생성하기' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: '광고를 만들고 있습니다' })).toBeInTheDocument())
    expect(generateAds).toHaveBeenCalledWith(handle, saved, 'brand', expect.anything())
    expect(screen.getAllByRole('listitem')[0]).toHaveTextContent('배경 정리 · 완료')
    expect(screen.queryByRole('region', { name: '사진 전처리' })).not.toBeInTheDocument()
    finish({ rankingError: null })
    await waitFor(() => expect(screen.getByRole('status', { name: '업로드 상태' })).toHaveTextContent('시안 4개와 참고 순위가 준비됐습니다.'))
    expect(screen.getByRole('heading', { name: '브랜드 전략 시안 4개' })).toBeInTheDocument()
    expect(document.querySelector('.product-input')).toHaveClass('results-only')
    expect(screen.queryByRole('button', { name: '광고 생성하기' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '저장된 상품 정보' })).not.toBeInTheDocument()
    expect(document.querySelector('.photo-processing')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '입력 수정하고 다시 만들기' }))
    expect(document.querySelector('.product-input')).not.toHaveClass('results-only')
    expect(screen.getByRole('button', { name: '광고 생성하기' })).toBeInTheDocument()
    expect(screen.getByLabelText('가게명')).toHaveValue(facts.store_name)
  })
  it('reports a ranking failure without hiding the designs', async () => {
    vi.mocked(generateAds).mockResolvedValue({ rankingError: '모델을 사용할 수 없습니다.' } as never)
    render(<ProductInput />); fill()
    fireEvent.click(screen.getByRole('button', { name: '광고 생성하기' }))
    await waitFor(() => expect(screen.getByRole('status', { name: '업로드 상태' })).toHaveTextContent('순위는 계산하지 못했습니다: 모델을 사용할 수 없습니다.'))
  })
  it('shows a failed step with retry, and returns quietly after a declined paid call', async () => {
    vi.mocked(generateAds).mockRejectedValueOnce(new Error('문구를 만들지 못했습니다.'))
    render(<ProductInput />); fill()
    fireEvent.click(screen.getByRole('button', { name: '광고 생성하기' }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('문구를 만들지 못했습니다.'))
    vi.mocked(generateAds).mockRejectedValueOnce(new GenerationCancelled())
    fireEvent.click(screen.getByRole('button', { name: '다시 시도' }))
    await waitFor(() => expect(screen.getByRole('status', { name: '업로드 상태' })).toHaveTextContent('광고 생성을 중단했습니다.'))
    expect(generateAds).toHaveBeenCalledTimes(2)
  })
  it('keeps the optional fields folded until the user opens them, and opens them for an error inside', () => {
    render(<ProductInput />)
    const more = screen.getByText('추가 정보 (선택)').closest('details')!
    expect(more).not.toHaveAttribute('open')
    fireEvent.click(screen.getByText('추가 정보 (선택)'))
    expect(more).toHaveAttribute('open')
    fireEvent.click(screen.getByText('추가 정보 (선택)'))
    expect(more).not.toHaveAttribute('open')
    fill(); fireEvent.change(screen.getByLabelText('상품 특징·강조 포인트 (선택)'), { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: '상품 정보와 사진 저장' }))
    expect(more).toHaveAttribute('open')
  })
  it('rejects unsupported file types before uploading', () => {
    render(<ProductInput />)
    fireEvent.change(screen.getByLabelText('상품 사진'), { target: { files: [new File(['svg'], 'photo.svg', { type: 'image/svg+xml' })] } })
    expect(screen.getByText('10 MiB 이하의 JPG/PNG 사진을 선택해 주세요.')).toBeInTheDocument()
    expect(uploadPhoto).not.toHaveBeenCalled()
  })
  it('shows server validation failures without a false success', async () => {
    vi.mocked(uploadPhoto).mockRejectedValue(new ApiError('읽을 수 있는 사진을 선택해 주세요.'))
    render(<ProductInput />); fill()
    fireEvent.click(screen.getByRole('button', { name: '상품 정보와 사진 저장' }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('읽을 수 있는 사진'))
    expect(screen.queryByRole('region', { name: '저장된 상품 정보' })).not.toBeInTheDocument()
  })
  it('rejects a long price instead of silently truncating it', () => {
    render(<ProductInput />); fill()
    const value = '1'.repeat(41)
    fireEvent.change(screen.getByLabelText('가격'), { target: { value } })
    fireEvent.click(screen.getByRole('button', { name: '상품 정보와 사진 저장' }))
    expect(screen.getByLabelText('가격')).toHaveValue(value)
    expect(screen.getByText('입력값을 확인해 주세요. 최대 40자입니다.')).toBeInTheDocument()
    expect(uploadPhoto).not.toHaveBeenCalled()
  })
})
