import { useEffect, useRef, useState } from 'react'
import { preview } from '../api/rendering'
import type { UploadHandle } from '../api/uploads'

export type AssetEntry = { url?: string; error?: boolean }
/** Loads each ad image once and shares the object URL between the slide and its thumbnail. */
export function useAssetUrls(handle: UploadHandle, assets: string[]) {
  const [entries, setEntries] = useState<Record<string, AssetEntry>>({})
  const cache = useRef(new Map<string, string>())
  const key = assets.join(',')
  useEffect(() => {
    let dead = false
    const wanted = new Set(assets)
    for (const [asset, url] of cache.current) if (!wanted.has(asset)) { URL.revokeObjectURL(url); cache.current.delete(asset) }
    setEntries(Object.fromEntries(assets.filter((a) => cache.current.has(a)).map((a) => [a, { url: cache.current.get(a) }])))
    for (const asset of assets) {
      if (cache.current.has(asset)) continue
      void preview(handle, asset).then((blob) => {
        if (dead) return
        const url = URL.createObjectURL(blob); cache.current.set(asset, url)
        setEntries((value) => ({ ...value, [asset]: { url } }))
      }).catch(() => { if (!dead) setEntries((value) => ({ ...value, [asset]: { error: true } })) })
    }
    return () => { dead = true }
    // The joined ids are the identity of the list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handle, key])
  useEffect(() => { const held = cache.current; return () => { for (const url of held.values()) URL.revokeObjectURL(url); held.clear() } }, [])
  return entries
}
