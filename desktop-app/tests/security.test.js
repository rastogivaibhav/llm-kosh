const { buildCommandArgs } = require('../electron/command-builder');

describe('Command Builder Security Validation', () => {
  test('allows status command', () => {
    const result = buildCommandArgs('status', ['--root', '/foo']);
    expect(result).toEqual(['status', '--root', '/foo']);
  });

  test('allows init command', () => {
    const result = buildCommandArgs('init', ['--root', '/foo', '--owner', 'user']);
    expect(result).toEqual(['init', '--root', '/foo', '--owner', 'user']);
  });

  test('rejects arbitrary commands like malicious-cmd', () => {
    expect(() => {
      buildCommandArgs('malicious-cmd', ['something']);
    }).toThrow(/Security Violation/);
  });

  test('rejects shell injection attempts by rejecting unknown command string', () => {
    expect(() => {
      buildCommandArgs('status && rm -rf /', []);
    }).toThrow(/Security Violation/);
  });

  test('forces arguments to be an array', () => {
    const result = buildCommandArgs('status', '--root /foo');
    expect(result).toEqual(['status']); // Invalid string arg becomes empty array
  });

  test('allows safe-pack command', () => {
    const result = buildCommandArgs('safe-pack', ['--root', '/foo', 'Update auth', '--for', 'claude']);
    expect(result).toEqual(['safe-pack', '--root', '/foo', 'Update auth', '--for', 'claude']);
  });

  test('allows pack command', () => {
    const result = buildCommandArgs('pack', ['--root', '/foo', 'Fix bug']);
    expect(result).toEqual(['pack', '--root', '/foo', 'Fix bug']);
  });

  test('blocks --allow-secrets flag entirely', () => {
    expect(() => {
      buildCommandArgs('safe-pack', ['--root', '/foo', '--allow-secrets']);
    }).toThrow(/--allow-secrets' flag is blocked/);
  });

  test('pack command rejects unknown target', () => {
    expect(() => {
      buildCommandArgs('pack', ['--for', 'malicious-ai']);
    }).toThrow(/Unknown target 'malicious-ai'/);
  });

  test('include-private requires explicit option to be passed in', () => {
    // In our architecture, the main.js translates the UI explicit toggle into an argument.
    // The command builder simply ensures args are an array. If someone sneaks it in, it's allowed
    // only because the builder doesn't block it, BUT we should verify that it passes through.
    const result = buildCommandArgs('pack', ['--include-private']);
    expect(result).toContain('--include-private');
  });

  test('validate-pack called correctly', () => {
    const result = buildCommandArgs('validate-pack', ['--root', '/foo', '/path/to/pack.zip']);
    expect(result).toEqual(['validate-pack', '--root', '/foo', '/path/to/pack.zip']);
  });

  test('validate-receipt called correctly', () => {
    const result = buildCommandArgs('validate-receipt', ['--root', '/foo', '/path/to/receipt.md']);
    expect(result).toEqual(['validate-receipt', '--root', '/foo', '/path/to/receipt.md']);
  });

  test('absorb called correctly', () => {
    const result = buildCommandArgs('absorb', ['--root', '/foo', '/path/to/receipt.md']);
    expect(result).toEqual(['absorb', '--root', '/foo', '/path/to/receipt.md']);
  });

  test('rejects auto-absorb or unknown command', () => {
    expect(() => {
      buildCommandArgs('auto-absorb', ['--root', '/foo']);
    }).toThrow(/Security Violation: Command 'auto-absorb' is not allowed/);
  });

  test('allows daemon once with valid mode', () => {
    const result = buildCommandArgs('daemon', ['once', '--root', '/foo', '--mode', 'watchdog']);
    expect(result).toEqual(['daemon', 'once', '--root', '/foo', '--mode', 'watchdog']);
  });

  test('allows daemon start and status', () => {
    const r1 = buildCommandArgs('daemon', ['start', '--root', '/foo']);
    expect(r1).toEqual(['daemon', 'start', '--root', '/foo']);

    const r2 = buildCommandArgs('daemon', ['status', '--root', '/foo']);
    expect(r2).toEqual(['daemon', 'status', '--root', '/foo']);
  });

  test('rejects unknown daemon subcommand', () => {
    expect(() => {
      buildCommandArgs('daemon', ['hack', '--root', '/foo']);
    }).toThrow(/Daemon subcommand 'hack' is not allowed/);
  });

  test('rejects unknown daemon mode', () => {
    expect(() => {
      buildCommandArgs('daemon', ['start', '--mode', 'skynet']);
    }).toThrow(/Daemon mode 'skynet' is not allowed/);
  });
});
