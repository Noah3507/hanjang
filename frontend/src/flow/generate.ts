import { photoState, type PhotoState } from '../api/photos'
import { analysisState, type AnalysisState } from '../api/analysis'
import { copyState, type CopyState } from '../api/copy'
import { rendering, type RenderState } from '../api/rendering'
import { createDesigns, getDesigns, rankDesigns, type DesignState, type Strategy } from '../api/designs'
import type { Draft, UploadHandle } from '../api/uploads'

/** One click runs the same API calls as the step-by-step buttons, in the same order. */
export type StepId = 'photo' | 'analysis' | 'copy' | 'designs' | 'ranking'
export type StepState = 'waiting' | 'running' | 'done' | 'failed'
export const stepOrder: StepId[] = ['photo', 'analysis', 'copy', 'designs', 'ranking']
export interface GenerateResult { photo: PhotoState; analysis: AnalysisState | null; copy: CopyState; render: RenderState; designs: DesignState; rankingError: string | null }
export interface GenerateOptions {
  onStep: (step: StepId, state: StepState) => void
  /** Asked only when the server would make a paid copy call. Resolve false to stop before spending. */
  approvePaidCopy: () => Promise<boolean>
  cancelled?: () => boolean
  wait?: (ms: number) => Promise<void>
}
export class GenerationCancelled extends Error { constructor() { super('광고 생성을 중단했습니다.') } }

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

export async function generateAds(handle: UploadHandle, draft: Draft, strategy: Strategy, options: GenerateOptions): Promise<GenerateResult> {
  const wait = options.wait ?? sleep
  const check = () => { if (options.cancelled?.()) throw new GenerationCancelled() }
  async function poll<T>(first: T, busy: (value: T) => boolean, next: () => Promise<T>, limit: number, timeoutMessage: string) {
    let value = first
    for (let i = 0; busy(value); i++) {
      check()
      if (i >= limit) throw new Error(timeoutMessage)
      await wait(1000)
      check()
      value = await next()
    }
    return value
  }
  async function step<T>(id: StepId, work: () => Promise<T>) {
    check(); options.onStep(id, 'running')
    try { const value = await work(); options.onStep(id, 'done'); return value }
    catch (error) { options.onStep(id, 'failed'); throw error }
  }

  // Background removal. The server keeps the original when the mask needs review; that choice is not overridden here.
  const photo = await step('photo', async () => {
    let state = await photoState(handle)
    if (state.status === 'pending') state = await photoState(handle, true)
    return poll(state, (s) => s.status === 'pending' || s.status === 'processing', () => photoState(handle), 130, '배경 정리 시간이 초과됐습니다. 다시 시도해 주세요.')
  })
  const asset = photo.photo_source === 'processed' && photo.processed ? photo.processed.asset_id : photo.original.asset_id

  // Photo analysis gives the copy step its visual hints and palette. It is optional: a failure is shown and the run goes on.
  check(); options.onStep('analysis', 'running')
  let analysis: AnalysisState | null = null
  try {
    let state = await analysisState(handle)
    const reusable = state.status === 'completed' && state.is_current && state.source_asset_id === asset
    if (!reusable) {
      if (state.status !== 'processing' || state.source_asset_id !== asset) state = await analysisState(handle, asset)
      state = await poll(state, (s) => s.status === 'processing', () => analysisState(handle), 150, '사진 분석 시간이 초과됐습니다.')
    }
    analysis = state.status === 'completed' ? state : null
  } catch (error) { if (error instanceof GenerationCancelled) throw error }
  options.onStep('analysis', analysis ? 'done' : 'failed')

  const copy = await step('copy', async () => {
    let state = await copyState(handle)
    const reusable = state.status === 'completed' && state.is_current && state.source_asset_id === asset
    if (!reusable) {
      if (state.status !== 'processing') {
        if (state.provider === 'openai' && !await options.approvePaidCopy()) throw new GenerationCancelled()
        check()
        state = await copyState(handle, { asset, draft })
      }
      state = await poll(state, (s) => s.status === 'processing', () => copyState(handle), 90, '문구 작성 시간이 초과됐습니다. 다시 시도해 주세요.')
    }
    if (state.status !== 'completed') throw new Error(state.error?.message || '문구를 만들지 못했습니다. 다시 시도해 주세요.')
    return state
  })

  const { render, designs } = await step('designs', async () => {
    // The design service takes its copy from the four-strategy render, so that render runs first without being shown.
    let rendered = await rendering(handle)
    const current = rendered.status === 'completed' && rendered.is_current && rendered.source_asset_id === asset && rendered.copy_key === copy.copy_key
    if (!current) {
      if (rendered.status !== 'processing') rendered = await rendering(handle, { asset, draft, copy })
      rendered = await poll(rendered, (s) => s.status === 'processing', () => rendering(handle), 120, '광고 렌더링 시간이 초과됐습니다. 다시 시도해 주세요.')
    }
    if (rendered.status !== 'completed') throw new Error(rendered.error?.message || '광고를 렌더링하지 못했습니다. 다시 시도해 주세요.')

    let state = await getDesigns(handle, strategy)
    const matches = (s: DesignState) => s.is_current && s.source_revision === rendered.revision && s.source_asset_id === rendered.source_asset_id && s.copy_key === rendered.copy_key
    if (!(state.status === 'completed' && matches(state))) {
      if (state.status !== 'processing') state = await createDesigns(handle, strategy, rendered)
      state = await poll(state, (s) => s.status === 'processing', () => getDesigns(handle, strategy), 180, '시안 렌더링 시간이 초과됐습니다. 다시 시도해 주세요.')
    }
    if (state.status !== 'completed') throw new Error(state.error?.message || '시안 4개를 만들지 못했습니다. 입력 길이를 확인하고 다시 시도해 주세요.')
    return { render: rendered, designs: state }
  })

  // A ranking failure keeps the four designs: they are shown without a rank, never with a substitute one.
  check(); options.onStep('ranking', 'running')
  let ranked = designs
  let rankingError: string | null = null
  try {
    if (!ranked.ranking) ranked = await rankDesigns(handle, strategy, ranked)
    if (!ranked.ranking) rankingError = ranked.ranking_error?.message || '순위를 계산하지 못했습니다.'
  } catch (error) { rankingError = error instanceof Error ? error.message : '순위를 계산하지 못했습니다.' }
  options.onStep('ranking', rankingError ? 'failed' : 'done')
  return { photo, analysis, copy, render, designs: ranked, rankingError }
}
