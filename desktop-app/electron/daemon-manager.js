const { spawn } = require('child_process');
const http = require('http');
const { app, Notification } = require('electron');
const { buildCommandArgs } = require('./command-builder');
const { resolveLlmKoshExecutable } = require('./cli-resolver');

class DaemonManager {
  constructor() {
    this.activeDaemon = null;
    this.logs = [];
    this.uptimeStart = null;
    this.lastEvent = null;
    this.lastError = null;
    this.eventSubscribers = new Set();
  }

  addLog(type, message) {
    const entry = { timestamp: Date.now(), type, message };
    this.logs.unshift(entry);
    if (this.logs.length > 100) this.logs.pop();
    this.emitEvent('daemon-log', entry);
    this.emitEvent('service-log', entry);
    
    // Parse for receipts
    if (type === 'stdout' || type === 'stderr') {
      const lower = message.toLowerCase();
      if (lower.includes('receipt') && lower.includes('intake')) {
        this.notify('Receipt detected', 'A new receipt was detected and moved to intake.');
        this.lastEvent = 'Receipt detected at ' + new Date().toLocaleTimeString();
      } else if (lower.includes('validating') && lower.includes('receipt')) {
        this.lastEvent = 'Validating receipt at ' + new Date().toLocaleTimeString();
      } else if (lower.includes('absorb') && lower.includes('receipt')) {
        this.notify('Receipt absorbed', 'A receipt was absorbed into memory.');
        this.lastEvent = 'Receipt absorbed at ' + new Date().toLocaleTimeString();
      }
    }
  }

  notify(title, body) {
    // Only notify if user hasn't disabled it via config
    if (Notification.isSupported()) {
      new Notification({ title, body }).show();
    }
  }

  subscribe(callback) {
    this.eventSubscribers.add(callback);
    return () => this.eventSubscribers.delete(callback);
  }

  emitEvent(eventName, payload) {
    for (const callback of this.eventSubscribers) {
      try {
        callback(eventName, payload);
      } catch (e) {
        console.error('Subscriber error:', e);
      }
    }
  }

  start(configPath, resourcesPath, rootPath) {
    if (this.activeDaemon) {
      return { ok: false, stderr: 'Daemon is already running.' };
    }

    try {
      const resolveResult = resolveLlmKoshExecutable(configPath, resourcesPath);
      const exe = resolveResult.path;
      if (!exe) throw new Error(resolveResult.error || 'Executable not found.');

      // The sustained service owns its scheduling mode. `--mode` belongs to
      // the deprecated foreground daemon command and is not valid here.
      const rawArgs = ['start', '--root', rootPath];
      
      const fullArgs = buildCommandArgs('service', rawArgs);

      this.activeDaemon = spawn(exe, fullArgs, {
        cwd: app.getPath('home'),
        shell: false 
      });

      this.uptimeStart = Date.now();
      this.lastError = null;
      this.addLog('system', 'Daemon started');

      this.activeDaemon.stdout.on('data', (data) => {
        this.addLog('stdout', data.toString());
      });

      this.activeDaemon.stderr.on('data', (data) => {
        this.addLog('stderr', data.toString());
      });

      this.activeDaemon.on('close', (code) => {
        this.addLog('system', `Daemon exited with code ${code}`);
        this.activeDaemon = null;
        this.uptimeStart = null;
        this.emitEvent('daemon-status-changed', { running: false });
        this.emitEvent('service-status-changed', { running: false });
        if (code !== 0 && code !== null) {
          this.lastError = `Exited with code ${code}`;
          this.notify('Daemon Stopped', `The daemon stopped unexpectedly (code ${code}).`);
        }
      });

      this.activeDaemon.on('error', (err) => {
        this.lastError = err.message;
        this.addLog('error', `Failed to spawn daemon: ${err.message}`);
        this.activeDaemon = null;
        this.uptimeStart = null;
        this.emitEvent('daemon-status-changed', { running: false });
        this.emitEvent('service-status-changed', { running: false });
      });

      this.emitEvent('daemon-status-changed', { running: true });
      this.emitEvent('service-status-changed', { running: true });
      return { ok: true, stdout: 'Daemon started.' };
    } catch (e) {
      this.lastError = e.message;
      return { ok: false, stderr: e.message };
    }
  }

  stop() {
    if (this.activeDaemon) {
      this.activeDaemon.kill();
      this.activeDaemon = null;
      this.uptimeStart = null;
      this.addLog('system', 'Daemon stopped manually');
      this.emitEvent('daemon-status-changed', { running: false });
      this.emitEvent('service-status-changed', { running: false });
      return { ok: true, stdout: 'Daemon stopped.' };
    }
    return { ok: false, stderr: 'No active daemon.' };
  }

  async healthCheck() {
    return new Promise((resolve) => {
      const req = http.get('http://127.0.0.1:5556/health', { timeout: 500 }, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          try { resolve({ running: true, ...JSON.parse(data) }); }
          catch { resolve({ running: true }); }
        });
      });
      req.on('error', () => resolve({ running: false }));
      req.on('timeout', () => { req.destroy(); resolve({ running: false }); });
    });
  }

  async getStatus() {
    const health = await this.healthCheck();
    return {
      running: !!this.activeDaemon || health.running,
      pid: this.activeDaemon ? this.activeDaemon.pid : (health.pid || null),
      uptimeMs: this.uptimeStart ? (Date.now() - this.uptimeStart) : 0,
      uptimeS: health.uptime_s || null,
      healthStatus: health.status || null,
      lastEvent: this.lastEvent,
      lastError: this.lastError,
      logs: this.logs.slice(0, 50)
    };
  }
}

const daemonManager = new DaemonManager();
module.exports = { daemonManager };
