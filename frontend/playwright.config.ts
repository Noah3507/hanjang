import { fileURLToPath } from 'node:url'
import { defineConfig, devices } from '@playwright/test'

const frontend = fileURLToPath(new URL('.', import.meta.url))
const root = fileURLToPath(new URL('..', import.meta.url))
const python = process.env.PLAYWRIGHT_PYTHON ? `"${process.env.PLAYWRIGHT_PYTHON}"` : process.platform === 'win32' ? '".venv/Scripts/python.exe"' : 'python'
const frontendPort = process.env.PLAYWRIGHT_FRONTEND_PORT || '5173'
const backendPort = process.env.PLAYWRIGHT_BACKEND_PORT || '8000'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 30_000,
  outputDir: '../artifacts/playwright/results',
  reporter: [
    ['list'],
    ['html', { outputFolder: '../artifacts/playwright/report', open: 'never' }],
    ['json', { outputFile: '../artifacts/playwright/results.json' }],
  ],
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
  },
  projects: [{
    name: 'chromium',
    use: {
      ...devices['Desktop Chrome'],
      ...(process.env.PLAYWRIGHT_CHANNEL === 'chrome' ? { channel: 'chrome' } : {}),
    },
  }],
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port ${backendPort}`,
      cwd: root,
      url: `http://127.0.0.1:${backendPort}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: `${process.platform === 'win32' ? 'npm.cmd' : 'npm'} run dev -- --port ${frontendPort}`,
      cwd: frontend,
      url: `http://127.0.0.1:${frontendPort}`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
})
