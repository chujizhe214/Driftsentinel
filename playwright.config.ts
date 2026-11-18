import { defineConfig, devices } from '@playwright/test'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
const chrome = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  expect: { timeout: 10000 },
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:8010',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ...devices['Desktop Chrome'],
    viewport: { width: 1440, height: 1000 },
    launchOptions: existsSync(chrome) ? { executablePath: chrome } : {},
  },
  webServer: {
    command: 'python -m uvicorn backend.app:app --host 127.0.0.1 --port 8010',
    url: 'http://127.0.0.1:8010/api/health',
    env: { DRIFTSENTINEL_DATA_DIR: resolve('test-workspace', `run-${Date.now()}`) },
    reuseExistingServer: false,
    timeout: 30000,
  },
})
