const fs = require('fs');
const os = require('os');
const path = require('path');
const {
  parseInstallHandoff,
  validateInstallFolders,
  writeSourcePolicy,
} = require('../electron/install-handoff');

describe('installer source/destination handoff', () => {
  test('parses the installer contract', () => {
    expect(parseInstallHandoff('source=C:\\work\r\ndestination=C:\\kosh\r\n')).toEqual({
      sourceFolder: 'C:\\work',
      destinationFolder: 'C:\\kosh',
    });
  });

  test('rejects overlapping source and destination folders', () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'llm-kosh-handoff-'));
    const source = path.join(root, 'source');
    const destination = path.join(source, 'data');
    fs.mkdirSync(source, { recursive: true });
    expect(validateInstallFolders(source, destination).ok).toBe(false);
  });

  test('writes a reference-only source policy', () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'llm-kosh-policy-'));
    const source = path.join(root, 'source');
    const destination = path.join(root, 'data');
    fs.mkdirSync(source, { recursive: true });
    fs.mkdirSync(destination, { recursive: true });
    const policy = writeSourcePolicy(destination, source);
    expect(policy.daemon.watched_directories).toEqual([source]);
    expect(JSON.parse(fs.readFileSync(path.join(destination, 'LLM_KOSH_POLICY.json'), 'utf8')).daemon.watched_directories).toEqual([source]);
  });
});
