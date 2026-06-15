function buildCommandArgs(command, args) {
  const allowedCommands = ['status', 'init', 'pack', 'safe-pack', 'validate-pack', 'validate-receipt', 'absorb', 'daemon', 'service', 'install', 'uninstall', 'desktop'];
  
  if (!allowedCommands.includes(command)) {
    throw new Error(`Security Violation: Command '${command}' is not allowed in Phase 4.`);
  }

  // Ensure args is an array
  const safeArgs = Array.isArray(args) ? [...args] : [];

  // Security: block dangerous flags
  if (safeArgs.includes('--allow-secrets')) {
    throw new Error(`Security Violation: The '--allow-secrets' flag is blocked by the UI security policy.`);
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
      throw new Error(`Security Violation: ${command} subcommand '${subcommand}' is not allowed.`);
    }

    const modeIndex = safeArgs.indexOf('--mode');
    if (modeIndex !== -1 && modeIndex + 1 < safeArgs.length) {
      const mode = safeArgs[modeIndex + 1];
      const allowedModes = ['auto', 'polling', 'watchdog'];
      if (!allowedModes.includes(mode)) {
        throw new Error(`Security Violation: Service mode '${mode}' is not allowed.`);
      }
    }
  }

  if (command === 'install' || command === 'uninstall' || command === 'desktop') {
    if (safeArgs.length > 0) {
      throw new Error(`Security Violation: Command '${command}' does not accept arguments.`);
    }
  }

  const rootIndex = safeArgs.indexOf('--root');
  if (rootIndex !== -1 && rootIndex + 1 < safeArgs.length) {
    const rootValue = safeArgs.splice(rootIndex, 2);
    return [rootValue[0], rootValue[1], command, ...safeArgs];
  }

  return [command, ...safeArgs];
}

module.exports = { buildCommandArgs };
