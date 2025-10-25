import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: 'tests/e2e',
  use: {
    baseURL: 'http://localhost:5000',
    browserName: 'chromium',
    headless: true,
  },
  webServer: {
    command: 'python -m flask run --port=5000',
    env: { FLASK_APP: 'app.py' },
    port: 5000,
    timeout: 120 * 1000,
    reuseExistingServer: true,
  },
});