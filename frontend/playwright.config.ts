import { fileURLToPath } from 'node:url'
import { defineConfig, devices } from '@playwright/test'

const frontend = fileURLToPath(new URL('.', import.meta.url))
const root = fileURLToPath(new URL('..', import.meta.url))
const python = process.platform === 'win32' ? '".venv/Scripts/python.exe"' : 'python'

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
    baseURL: 'http://127.0.0.1:5173',
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
      command: `${python} -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000`,
      cwd: root,
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: process.platform === 'win32' ? 'npm.cmd run dev' : 'npm run dev',
      cwd: frontend,
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
})
