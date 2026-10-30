import { useEffect, useRef, useState, type FormEvent } from 'react'
import PhotoProcessing from './PhotoProcessing'
import { ApiError, getInput, getOriginal, saveInput, uploadPhoto, type Draft, type Facts, type Mood, type UploadHandle } from '../api/uploads'

const empty: Facts = { store_name: '', product_name: '', price_text: '', address: null, instagram_handle: null }
const storageKey = 'hanjang.upload-handle.v1'
function restored(): UploadHandle | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(storageKey) || 'null')
    return value && typeof value.token === 'string' && typeof value.upload?.job_id === 'string' ? value : null
  } catch { return null }
}

export default function ProductInput() {
  const [facts, setFacts] = useState<Facts>(empty)
  const [mood, setMood] = useState<Mood | ''>('')
  const [features, setFeatures] = useState('')
  const [useAddress, setUseAddress] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [handle, setHandle] = useState<UploadHandle | null>(restored)
  const needsUpload = useRef(false)
  const [preview, setPreview] = useState('')
  const [draft, setDraft] = useState<Draft | null>(null)
  const [status, setStatus] = useState<'idle' | 'saving' | 'loading' | 'saved' | 'error'>('idle')
  const [message, setMessage] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const busy = status === 'saving' || status === 'loading'
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])

  function changePhoto(next: File | undefined) {
    setDraft(null); setErrors({}); setMessage(''); setStatus('idle')
    if (!next) { setFile(null); setPreview(''); return }
    if (!['image/jpeg', 'image/png'].includes(next.type) || next.size > 10 * 1024 * 1024) {
      setFile(null); setPreview(''); needsUpload.current = true
      setErrors({ photo: '10 MiB 이하의 JPG/PNG 사진을 선택해 주세요.' }); return
    }
    setFile(next); needsUpload.current = true; setPreview(URL.createObjectURL(next))
  }

  function validate() {
    const next: Record<string, string> = {}
    const limits = { store_name: 80, product_name: 80, price_text: 40, address: 200, instagram_handle: 80 }
    for (const key of Object.keys(limits) as (keyof Facts)[]) {
      const text = facts[key]
      const required = ['store_name', 'product_name', 'price_text'].includes(key)
      if ((required && !text?.trim()) || (text !== null && (!text.trim() || [...text].length > limits[key] || /[\u0000-\u001f\u007f-\u009f]/.test(text)))) {
        next[key] = `입력값을 확인해 주세요. 최대 ${limits[key]}자입니다.`
      }
    }
    if (!mood) next.mood = '분위기를 선택해 주세요.'
    if (features && (!features.trim() || [...features].length > 500 || /[\u0000-\u0009\u000b\u000c\u000e-\u001f\u007f-\u009f]/.test(features))) next.product_features = '상품 특징은 공백만 입력하지 말고 최대 500자로 작성해 주세요.'
    if (!file && (!handle || needsUpload.current)) next.photo = '상품 사진을 선택해 주세요.'
    return next
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const next = validate(); setErrors(next)
    if (Object.keys(next).length) { setStatus('error'); setMessage('입력 항목을 확인해 주세요.'); return }
    setStatus('saving'); setMessage('원본 사진과 상품 정보를 저장하고 있습니다.')
    try {
      let current = handle
      if (file && (needsUpload.current || !current)) {
        current = await uploadPhoto(file); setHandle(current); needsUpload.current = false
        try { sessionStorage.setItem(storageKey, JSON.stringify(current)) } catch { /* Saving is still available without tab storage. */ }
      }
      if (!current) throw new Error('사진을 다시 선택해 주세요.')
      await saveInput(current, facts, mood as Mood, { product_features: features === '' ? null : features, use_address_for_copy: useAddress })
      const result = await getInput(current) // Verify through the read endpoint, not the submitted object.
      setDraft(result); setStatus('saved'); setMessage('상품 정보와 원본 사진이 저장됐습니다. 광고 생성은 시작하지 않았습니다.')
    } catch (error) { fail(error) }
  }

  function fail(error: unknown) {
    setStatus('error'); setDraft(null)
    setMessage(error instanceof Error ? error.message : '저장에 실패했습니다. 다시 시도해 주세요.')
    if (error instanceof ApiError) setErrors(Object.fromEntries(error.fields.map(({ field, message }) => [field.replace(/^facts\./, ''), message])))
  }
  async function reload() {
    if (!handle) return
    setStatus('loading'); setMessage('저장된 입력과 원본을 확인하고 있습니다.'); setErrors({})
    try {
      const result = await getInput(handle)
      const original = await getOriginal(handle)
      setFacts(result.facts); setMood(result.mood); setFeatures(result.product_features ?? ''); setUseAddress(result.use_address_for_copy ?? false); setDraft(result); setFile(null); needsUpload.current = false
      setPreview(URL.createObjectURL(original)); setStatus('saved'); setMessage('서버에서 저장된 상품 정보와 원본 사진을 다시 조회했습니다.')
    } catch (error) { fail(error) }
  }

  const labels: Record<keyof Facts, string> = { store_name: '가게명', product_name: '상품명', price_text: '가격', address: '주소 (선택)', instagram_handle: 'Instagram (선택)' }
  return <section className="product-input" aria-labelledby="input-title">
    <h2 id="input-title">상품 정보 입력 및 이미지 업로드</h2>
    <p className="help">원본을 그대로 저장합니다. JPG/PNG · 최대 10 MiB · 24MP 이하 · 가로/세로 256px 이상</p>
    <form onSubmit={submit} noValidate>
      <fieldset disabled={busy}>
        <label htmlFor="photo">상품 사진</label>
        <input id="photo" type="file" accept="image/jpeg,image/png" onChange={(event) => changePhoto(event.target.files?.[0])} aria-describedby="photo-error" />
        {errors.photo && <p id="photo-error" className="field-error">{errors.photo}</p>}
        {preview && <img className="photo-preview" src={preview} alt="원본 상품 사진 미리보기" />}
        <div className="fields">
          {(Object.keys(labels) as (keyof Facts)[]).map((key) => <div key={key}>
            <label htmlFor={key}>{labels[key]}</label>
            <input id={key} value={facts[key] || ''} required={['store_name', 'product_name', 'price_text'].includes(key)}
              onChange={(event) => { setFacts({ ...facts, [key]: event.target.value || (['address', 'instagram_handle'].includes(key) ? null : '') }); setDraft(null); setStatus('idle'); setMessage('') }}
              aria-invalid={!!errors[key]} aria-describedby={`${key}-error`} />
            {key === 'price_text' && <small>예: 10,500원. 입력한 표기 그대로 저장합니다.</small>}
            {errors[key] && <p id={`${key}-error`} className="field-error">{errors[key]}</p>}
          </div>)}
          <div><label htmlFor="mood">광고 분위기</label>
            <select id="mood" value={mood} onChange={(event) => { setMood(event.target.value as Mood | ''); setDraft(null); setStatus('idle'); setMessage('') }} aria-invalid={!!errors.mood}>
              <option value="">선택해 주세요</option><option value="warm">따뜻한 감성</option><option value="minimal">깔끔한 미니멀</option><option value="vivid">활기찬 강렬함</option><option value="premium">고급스러움</option>
            </select>{errors.mood && <p className="field-error">{errors.mood}</p>}
          </div>
        </div>
        <label htmlFor="product_features">상품 특징·강조 포인트 (선택)</label>
        <textarea id="product_features" value={features} rows={3} placeholder="직접 확인한 맛·식감·재료·상품 장점을 적어 주세요."
          aria-invalid={!!errors.product_features} onChange={event => { setFeatures(event.target.value); setDraft(null); setStatus('idle'); setMessage('') }} />
        <small>최대 500자. 사용자 제공 정보로 원문 저장하며, 사진 추정과 구분합니다.</small>
        {errors.product_features && <p className="field-error">{errors.product_features}</p>}
        <label><input type="checkbox" checked={useAddress} onChange={event => { setUseAddress(event.target.checked); setDraft(null); setStatus('idle'); setMessage('') }} /> 지역 홍보 카피에 주소 사용</label>
        <small>이 옵션은 LLM 전송 여부입니다. 저장한 주소와 Instagram은 광고의 별도 정보 영역에 표시되며, 입력하지 않으면 숨깁니다.</small>
        <small>기본은 주소 미전송입니다. 실제 LLM 모드를 승인해 켠 경우에만 가게명·상품명·가격·특징·분위기·현재 사진 단서가 전송됩니다. Instagram과 사진은 전송하지 않습니다.</small>
        <button type="submit">{status === 'saving' ? '저장 중…' : '상품 정보와 사진 저장'}</button>
        <button className="secondary" type="button" disabled={!handle} onClick={reload}>저장 정보 다시 조회</button>
      </fieldset>
    </form>
    {message && <p role={status === 'error' ? 'alert' : 'status'} aria-label="업로드 상태">{message}</p>}
    {draft && <section aria-label="저장된 상품 정보" className="saved-input">
      <h3>서버에 저장된 입력</h3>
      <dl>{(Object.keys(labels) as (keyof Facts)[]).map((key) => <div key={key}><dt>{labels[key]}</dt><dd>{draft.facts[key] ?? '미입력'}</dd></div>)}</dl>
      <p>작업 상태: {draft.status} · 분위기: {draft.mood}</p>
      <p style={{ whiteSpace: 'pre-wrap' }}>상품 특징: {draft.product_features ?? '미입력'}</p>
      <p>주소 카피 활용: {draft.use_address_for_copy ? '사용' : '사용하지 않음'}</p>
      <p>만료: {new Date(draft.expires_at).toLocaleString('ko-KR')} · 사진/입력은 24시간 임시 저장됩니다.</p>
    </section>}
    {draft && handle && <PhotoProcessing key={handle.upload.job_id} handle={handle} draft={draft} />}
    <p className="help">이 탭의 세션으로 다시 조회할 수 있습니다. 서버 재시작·배포 시 작업 정보가 유실될 수 있습니다. 새 사진은 새 작업으로 저장되며 이전 사진도 만료 시 정리됩니다.</p>
  </section>
}
