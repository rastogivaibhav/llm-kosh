const { runSmokeTestSequence } = require('../electron/smoke-test');
const fs = require('fs');

jest.mock('child_process', () => {
  return {
    spawn: jest.fn(() => {
      return {
        stdout: { on: jest.fn((event, cb) => cb('mock output')) },
        stderr: { on: jest.fn() },
        on: jest.fn((event, cb) => {
          if (event === 'close') cb(0);
        })
      };
    })
  };
});

describe('Smoke Test Sequence', () => {
  test('runs successfully against temporary isolated dir', async () => {
    // Need to mock fs since we actually write to temp dir
    // But since mkdtempSync actually writes to real tmp in Node, it's safer to mock it, or let it run.
    // If we let it run, we're doing a real integration test of just the logic mapping, but spawn is mocked.
    const results = await runSmokeTestSequence('mock-exe');
    
    // Check results
    expect(results).toBeDefined();
    
    const steps = results.map(r => r.step);
    expect(steps).toContain('create-temp-root');
    expect(steps).toContain('init');
    expect(steps).toContain('status');
    expect(steps).toContain('safe-pack');
    expect(steps).toContain('validate-pack');
    expect(steps).toContain('validate-receipt');
    expect(steps).toContain('absorb');
    expect(steps).toContain('daemon');
    
    // Everything should be ok=true because mock returns code 0
    results.forEach(r => expect(r.ok).toBe(true));
  });
});
