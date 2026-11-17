import type { Strategy } from '../api/designs'

export const strategies: Strategy[] = ['emotional', 'price', 'visual', 'brand']
export const defaultStrategy: Strategy = 'price'
export const strategyHints: Record<Strategy, string> = {
  emotional: '분위기와 문구 중심',
  price: '금액과 혜택을 크게',
  visual: '사진을 가장 크게',
  brand: '상호를 또렷하게',
}
/** One key per upload job; the input form writes it and the design step reads it. */
export const strategyStorageKey = (jobId: string) => `hanjang-v3-strategy:${jobId}`
export function storedStrategy(jobId: string): Strategy {
  try {
    const value = sessionStorage.getItem(strategyStorageKey(jobId))
    return strategies.includes(value as Strategy) ? value as Strategy : defaultStrategy
  } catch { return defaultStrategy }
}
