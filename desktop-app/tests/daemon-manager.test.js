jest.mock('electron', () => ({
  app: { getPath: jest.fn(() => '/mock/home') },
  Notification: { isSupported: jest.fn(() => false) }
}));
const { daemonManager } = require('../electron/daemon-manager');

describe('Daemon Manager', () => {
  beforeEach(() => {
    daemonManager.activeDaemon = null;
    daemonManager.logs = [];
    daemonManager.uptimeStart = null;
    daemonManager.lastEvent = null;
    daemonManager.eventSubscribers.clear();
  });

  test('prevents duplicate daemon starts', () => {
    daemonManager.activeDaemon = { pid: 1234 }; // fake running
    
    const res = daemonManager.start('/config.json', '/res', '/cartridge');
    expect(res.ok).toBe(false);
    expect(res.stderr).toContain('already running');
  });

  test('parses receipts for notification', () => {
    // We mock Notification if necessary, but testing logic state is enough
    daemonManager.addLog('stdout', '12:00:00 [INFO] A new receipt was detected and moved to intake.');
    expect(daemonManager.lastEvent).toContain('Receipt detected');

    daemonManager.addLog('stdout', '12:01:00 [INFO] Absorb receipt 123 into memory');
    expect(daemonManager.lastEvent).toContain('Receipt absorbed');
  });

  test('stores limited logs', () => {
    for (let i = 0; i < 150; i++) {
      daemonManager.addLog('stdout', `Log ${i}`);
    }
    expect(daemonManager.logs.length).toBe(100);
    // the newest log is at index 0 (unshift)
    expect(daemonManager.logs[0].message).toBe('Log 149');
  });
});
