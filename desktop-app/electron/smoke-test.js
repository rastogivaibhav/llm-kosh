const path = require('path');
const os = require('os');
const fs = require('fs');
const { spawn } = require('child_process');
const { buildCommandArgs } = require('./command-builder');

async function runCommand(exe, command, args) {
  return new Promise((resolve) => {
    const startTime = Date.now();
    let fullArgs;
    try {
      fullArgs = buildCommandArgs(command, args);
    } catch (err) {
      return resolve({
        ok: false, step: command, error: err.message, durationMs: Date.now() - startTime
      });
    }

    const proc = spawn(exe, fullArgs, { shell: false });
    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', d => stdout += d.toString());
    proc.stderr.on('data', d => stderr += d.toString());

    proc.on('close', code => {
      resolve({
        ok: code === 0,
        step: command,
        stdout,
        stderr,
        exitCode: code,
        durationMs: Date.now() - startTime
      });
    });

    proc.on('error', err => {
      resolve({
        ok: false,
        step: command,
        error: err.message,
        durationMs: Date.now() - startTime
      });
    });
  });
}

async function runSmokeTestSequence(exe) {
  const results = [];
  
  // Create a temporary isolated cartridge
  const tempDir = os.tmpdir();
  const testRootPath = fs.mkdtempSync(path.join(tempDir, 'llmkosh-smoke-'));
  
  results.push({ ok: true, step: 'create-temp-root', stdout: testRootPath });

  // 1. Init
  const initRes = await runCommand(exe, 'init', ['--root', testRootPath, '--owner', 'smoketest']);
  results.push(initRes);
  if (!initRes.ok) return cleanupAndReturn(testRootPath, results);

  // 2. Status
  const statusRes = await runCommand(exe, 'status', ['--root', testRootPath]);
  results.push(statusRes);
  if (!statusRes.ok) return cleanupAndReturn(testRootPath, results);

  // 3. Pack
  const packOutPath = path.join(testRootPath, `smoke_pack.zip`);
  const packRes = await runCommand(exe, 'safe-pack', ['--root', testRootPath, 'smoke test query', '--for', 'human', '--out', packOutPath]);
  results.push(packRes);
  if (!packRes.ok) return cleanupAndReturn(testRootPath, results);

  // 4. Validate Pack
  const valPackRes = await runCommand(exe, 'validate-pack', ['--root', testRootPath, packOutPath]);
  results.push(valPackRes);

  // 5. Validate Receipt
  const receiptPath = path.join(testRootPath, `smoke_receipt.md`);
  fs.writeFileSync(receiptPath, '# MEMORY_RECEIPT\n\nSmoke test receipt.', 'utf8');
  const valReceiptRes = await runCommand(exe, 'validate-receipt', ['--root', testRootPath, receiptPath]);
  results.push(valReceiptRes);

  // 6. Absorb
  const absorbRes = await runCommand(exe, 'absorb', ['--root', testRootPath, receiptPath]);
  results.push(absorbRes);

  // 7. Daemon Status
  const serviceRes = await runCommand(exe, 'service', ['status', '--root', testRootPath]);
  results.push(serviceRes);
  if (!serviceRes.ok) {
    const daemonRes = await runCommand(exe, 'daemon', ['status', '--root', testRootPath]);
    results.push(daemonRes);
  }

  return cleanupAndReturn(testRootPath, results);
}

function cleanupAndReturn(dir, results) {
  try {
    fs.rmSync(dir, { recursive: true, force: true });
  } catch (e) {
    // Ignore cleanup errors
  }
  return results;
}

module.exports = { runSmokeTestSequence };
