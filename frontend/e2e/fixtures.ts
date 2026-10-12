import { mkdir, writeFile } from 'node:fs/promises'
import { test as base, expect } from '@playwright/test'

export const test = base.extend<{ diagnostics: void }>({
  diagnostics: [async ({ page }, use, testInfo) => {
    const logs: string[] = []
    const pageErrors: string[] = []
    page.on('console', (message) => logs.push(`[console:${message.type()}] ${message.text()}`))
    page.on('pageerror', (error) => {
      pageErrors.push(error.message)
      logs.push(`[pageerror] ${error.stack || error.message}`)
    })
    page.on('requestfailed', (request) => logs.push(
      `[requestfailed] ${request.method()} ${request.url()} ${request.failure()?.errorText}`,
    ))
    try {
      await use()
      expect(pageErrors, 'Uncaught browser JavaScript errors').toEqual([])
    } finally {
      logs.push(...testInfo.errors.map((error) => `[assertion] ${error.stack || error.message}`))
      await mkdir(testInfo.outputDir, { recursive: true })
      const path = testInfo.outputPath('browser.log')
      await writeFile(path, logs.join('\n'), 'utf8')
      await testInfo.attach('browser diagnostics', { path, contentType: 'text/plain' })
    }
  }, { auto: true }],
})


export { expect }
