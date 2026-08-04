function buildCommandArgs(command, args) {
  const allowedCommands = [
    'status', 'init', 'query', 'embed', 'inbox', 'intake', 'processor',
    'audit', 'heal', 'quarantine', 'pack', 'safe-pack', 'validate-pack',
    'validate-receipt', 'absorb', 'daemon', 'service', 'install',
    'uninstall', 'desktop', 'brain'
  ];
  
  if (!allowedCommands.includes(command)) {
    throw new Error(`Security Violation: Command '${command}' is not allowed in Phase 4.`);
  }

  // Ensure args is an array
  const safeArgs = Array.isArray(args) ? [...args] : [];

  // Security: block dangerous flags
  if (safeArgs.includes('--allow-secrets')) {
    throw new Error(`Security Violation: The '--allow-secrets' flag is blocked by the UI security policy.`);
  }

  // The renderer gets a narrow, explicit CLI surface. Never turn this bridge
  // into a generic process runner (the old benchmark views attempted that).
  const rootIndex = safeArgs.indexOf('--root');
  if (rootIndex >= 0 && (!safeArgs[rootIndex + 1] || safeArgs[rootIndex + 1].startsWith('--'))) {
    throw new Error('Security Violation: --root requires a directory path.');
  }
  const commandArgs = rootIndex >= 0
    ? safeArgs.filter((value, index) => index !== rootIndex && index !== rootIndex + 1)
    : [...safeArgs];
  const rejectExtra = (message) => { throw new Error(`Security Violation: ${message}`); };

  if (command === 'query') {
    if (commandArgs.some((value) => value.startsWith('--') && value !== '--semantic')) {
      rejectExtra('query only accepts --semantic.');
    }
  } else if (command === 'embed' || command === 'audit') {
    if (commandArgs.length) rejectExtra(`${command} does not accept arguments.`);
  } else if (command === 'init') {
    for (let i = 0; i < commandArgs.length; i += 1) {
      const option = commandArgs[i];
      if (option === '--owner' || option === '--mode') {
        if (!commandArgs[i + 1] || commandArgs[i + 1].startsWith('--')) {
          rejectExtra(`${option} requires a value.`);
        }
        if (option === '--mode' && !['personal', 'company-brain'].includes(commandArgs[i + 1])) {
          rejectExtra(`Unknown cartridge mode '${commandArgs[i + 1]}'.`);
        }
        i += 1;
      } else {
        rejectExtra(`init option '${option}' is not allowed.`);
      }
    }
  } else if (command === 'inbox') {
    for (let i = 0; i < commandArgs.length; i += 1) {
      if (commandArgs[i] === '--project') {
        if (!commandArgs[i + 1] || commandArgs[i + 1].startsWith('--')) {
          rejectExtra('inbox --project requires a value.');
        }
        i += 1;
      } else if (commandArgs[i].startsWith('--')) {
        rejectExtra(`inbox option '${commandArgs[i]}' is not allowed.`);
      }
    }
  } else if (command === 'intake') {
    if (commandArgs.length !== 1 || commandArgs[0] !== 'scan') {
      rejectExtra("intake only exposes the 'scan' action to the desktop.");
    }
  } else if (command === 'processor') {
    if (commandArgs.length !== 1 || commandArgs[0] !== 'run') {
      rejectExtra("processor only exposes the 'run' action to the desktop.");
    }
  } else if (command === 'heal') {
    if (commandArgs.length !== 1 || commandArgs[0] !== '--safe') {
      rejectExtra('heal only exposes --safe to the desktop.');
    }
  } else if (command === 'quarantine') {
    if (commandArgs.length !== 1 || commandArgs[0] !== '--list') {
      rejectExtra('quarantine only exposes --list to the desktop.');
    }
  } else if (command === 'brain') {
    if (commandArgs.length < 1 || !['init', 'health'].includes(commandArgs[0])) {
      rejectExtra("brain only exposes the 'init' and 'health' actions to the desktop.");
    }
    if (commandArgs[0] === 'health' && commandArgs.length > 2) {
      rejectExtra('brain health does not accept extra arguments.');
    }
  }

  // If pack/safe-pack, validate target if provided
  if (command === 'pack' || command === 'safe-pack') {
    const forIndex = safeArgs.indexOf('--for');
    if (forIndex !== -1 && forIndex + 1 < safeArgs.length) {
      const target = safeArgs[forIndex + 1];
      const allowedTargets = ['chatgpt', 'claude', 'gemini', 'deepseek', 'codex', 'human'];
      if (!allowedTargets.includes(target)) {
        throw new Error(`Security Violation: Unknown target '${target}'.`);
      }
    }
  }

  // If daemon/service, validate subcommand and mode
  if (command === 'daemon' || command === 'service') {
    const subcommand = safeArgs[0];
    const allowedSubcommands = command === 'daemon'
      ? ['once', 'start', 'status']
      : ['install', 'uninstall', 'start', 'stop', 'restart', 'status'];
    if (!allowedSubcommands.includes(subcommand)) {
      const label = command === 'daemon' ? 'Daemon subcommand' : 'Service subcommand';
      throw new Error(`Security Violation: ${label} '${subcommand}' is not allowed.`);
    }

    const modeIndex = safeArgs.indexOf('--mode');
    if (modeIndex !== -1 && modeIndex + 1 < safeArgs.length) {
      const mode = safeArgs[modeIndex + 1];
      const allowedModes = ['auto', 'polling', 'watchdog'];
      if (!allowedModes.includes(mode)) {
        throw new Error(`Security Violation: Daemon mode '${mode}' is not allowed.`);
      }
    }
  }

  if (command === 'install') {
    if (safeArgs.length > 0 && !(safeArgs.length === 2 && safeArgs[0] === '--mode' && ['personal', 'company-brain'].includes(safeArgs[1]))) {
      throw new Error(`Security Violation: Command '${command}' only accepts --mode personal|company-brain.`);
    }
  } else if (command === 'uninstall' || command === 'desktop') {
    if (safeArgs.length > 0) {
      throw new Error(`Security Violation: Command '${command}' does not accept arguments.`);
    }
  }

  if (rootIndex !== -1 && rootIndex + 1 < safeArgs.length) {
    const rootArgs = safeArgs.splice(rootIndex, 2);
    return [...rootArgs, command, ...safeArgs];
  }

  return [command, ...safeArgs];
}

module.exports = { buildCommandArgs };
