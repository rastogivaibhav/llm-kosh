const { _electron: electron, expect, test } = require('@playwright/test');

async function launchApp(mode) {
  return electron.launch({
    args: ['.'],
    env: {
      ...process.env,
      NODE_ENV: 'production',
      LLM_KOSH_E2E_MODE: mode,
    },
  });
}

test.describe('llm-kosh desktop post-install flow', () => {
  test('shows onboarding when the installed CLI is unavailable', async () => {
    const app = await launchApp('onboarding');
    const page = await app.firstWindow();

    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('body')).toContainText('Welcome to llm-kosh');
    await expect(page.locator('body')).toContainText('CLI Not Found');
    await expect(page.locator('body')).toContainText('Create New Cartridge');
    await expect(page).toHaveScreenshot('onboarding.png', { fullPage: true });

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
    await expect(page).toHaveScreenshot('settings-mcp.png', { fullPage: true });

    await page.getByTitle('Dashboard').click();
    await expect(page.locator('body')).toContainText('System Dashboard');
    await page.getByTitle('Settings').click();
    await page.getByRole('button', { name: 'Run Local Smoke Test' }).click();
    await expect(page.getByText('create-temp-root')).toBeVisible();
    await expect(page.getByText('daemon')).toBeVisible();

    await app.close();
  });
});
