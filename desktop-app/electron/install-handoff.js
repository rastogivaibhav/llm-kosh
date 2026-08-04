const fs = require('fs');
const path = require('path');

function parseInstallHandoff(text) {
  const values = {};
  for (const line of String(text || '').split(/\r?\n/)) {
    const separator = line.indexOf('=');
    if (separator <= 0) continue;
    values[line.slice(0, separator).trim()] = line.slice(separator + 1).trim();
  }
  return {
    sourceFolder: values.source || '',
    destinationFolder: values.destination || '',
  };
}

function validateInstallFolders(sourceFolder, destinationFolder, fsModule = fs) {
  if (!sourceFolder || !destinationFolder) {
    return { ok: false, error: 'Both source and destination folders are required.' };
  }
  if (!fsModule.existsSync(sourceFolder) || !fsModule.statSync(sourceFolder).isDirectory()) {
    return { ok: false, error: 'The selected source folder does not exist.' };
  }
  if (!fsModule.existsSync(destinationFolder)) {
    fsModule.mkdirSync(destinationFolder, { recursive: true });
  }
  if (!fsModule.statSync(destinationFolder).isDirectory()) {
    return { ok: false, error: 'The selected destination is not a folder.' };
  }
  const source = path.resolve(sourceFolder).toLowerCase();
  const destination = path.resolve(destinationFolder).toLowerCase();
  const sourcePrefix = source.endsWith(path.sep) ? source : `${source}${path.sep}`;
  const destinationPrefix = destination.endsWith(path.sep) ? destination : `${destination}${path.sep}`;
  if (source === destination || source.startsWith(destinationPrefix) || destination.startsWith(sourcePrefix)) {
    return { ok: false, error: 'Source and destination folders must be separate.' };
  }
  return { ok: true, sourceFolder, destinationFolder };
}

function writeSourcePolicy(destinationFolder, sourceFolder, fsModule = fs) {
  const policyPath = path.join(destinationFolder, 'LLM_KOSH_POLICY.json');
  let policy = {};
  try {
    if (fsModule.existsSync(policyPath)) {
      policy = JSON.parse(fsModule.readFileSync(policyPath, 'utf8')) || {};
    }
  } catch (_) {
    policy = {};
  }
  policy.daemon = policy.daemon || {};
  policy.daemon.watched_directories = [sourceFolder];
  fsModule.writeFileSync(policyPath, JSON.stringify(policy, null, 2));
  return policy;
}

function readInstallHandoff(resourcesPath, fsModule = fs) {
  const handoffPath = path.join(resourcesPath, 'llm-kosh-install.conf');
  if (!fsModule.existsSync(handoffPath)) return null;
  const handoff = parseInstallHandoff(fsModule.readFileSync(handoffPath, 'utf8'));
  return { ...handoff, handoffPath };
}

function removeInstallHandoff(handoffPath, fsModule = fs) {
  try { fsModule.unlinkSync(handoffPath); } catch (_) { /* already consumed */ }
}

module.exports = {
  parseInstallHandoff,
  validateInstallFolders,
  writeSourcePolicy,
  readInstallHandoff,
  removeInstallHandoff,
};
