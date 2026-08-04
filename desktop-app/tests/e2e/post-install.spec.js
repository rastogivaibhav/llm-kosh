const { _electron: electron, expect, test } = require('@playwright/test');

async function launchApp(mode) {
  return electron.launch({
    args: ['.', '--no-sandbox'],
    env: {
      ...process.env,
      NODE_ENV: 'production',
      LLM_KOSH_E2E_MODE: mode,
    },
  });
}

const hasWindowsVisualBaselines = process.platform === 'win32';

test.describe('llm-kosh desktop post-install flow', () => {
  test('shows the minimal source and destination setup', async () => {
    const app = await launchApp('onboarding');
    const page = await app.firstWindow();

    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('body')).toContainText('Welcome to llm-kosh');
    await expect(page.locator('body')).toContainText('Work folder');
    await expect(page.locator('body')).toContainText('LLM-Kosh data folder');
    await expect(page.locator('body')).toContainText('Configure LLM-Kosh');
    if (hasWindowsVisualBaselines) {
      await expect(page).toHaveScreenshot('onboarding.png', { fullPage: true });
    }

    await app.close();
  });

  test('renders the dashboard and MCP controls after install', async () => {
    const app = await launchApp('dashboard');
    const page = await app.firstWindow();

    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('body')).toContainText('System Dashboard');
    await expect(page.locator('body')).toContainText('MCP Server');
    await expect(page.locator('body')).toContainText('Start Server');

    await page.getByTitle('Settings').click();
    await expect(page.locator('body')).toContainText('App Configuration');
    await expect(page.locator('body')).toContainText('Connect to Claude Desktop (MCP)');
    await expect(page.locator('body')).toContainText('"mcpServers"');
    if (hasWindowsVisualBaselines) {
      await expect(page).toHaveScreenshot('settings-mcp.png', { fullPage: true });
    }

    await page.getByTitle('Dashboard').click();
    await expect(page.locator('body')).toContainText('System Dashboard');
    await page.getByTitle('Settings').click();
    await page.getByRole('button', { name: 'Run Local Smoke Test' }).click();
    await expect(page.getByText('create-temp-root')).toBeVisible();
    await expect(page.getByText('daemon')).toBeVisible();

    await app.close();
  });

  test('shows installer-configured source and destination data flowing', async () => {
    const app = await launchApp('configured');
    const page = await app.firstWindow();

    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('body')).toContainText('Data flow');
    await expect(page.locator('body')).toContainText('C:\\e2e\\source');
    await expect(page.locator('body')).toContainText('C:\\e2e\\root');
    await expect(page.locator('body')).toContainText('12');
    await expect(page.locator('body')).toContainText('Ready');

    await app.close();
  });

  test('completes fallback setup and opens the configured data flow', async () => {
    const app = await launchApp('onboarding');
    const page = await app.firstWindow();

    await page.waitForLoadState('domcontentloaded');
    await page.getByRole('button', { name: 'Browse' }).nth(0).click();
    await page.getByRole('button', { name: 'Browse' }).nth(1).click();
    await page.getByRole('button', { name: 'Configure LLM-Kosh' }).click();
    await expect(page.locator('body')).toContainText('Data flow');
    await expect(page.locator('body')).toContainText('Ready');

    await app.close();
  });
});
