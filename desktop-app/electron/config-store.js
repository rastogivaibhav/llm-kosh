const fs = require('fs');

function readConfig(configPath) {
  try {
    if (fs.existsSync(configPath)) {
      return JSON.parse(fs.readFileSync(configPath, 'utf8'));
    }
  } catch (e) {
    //
  }
  return {};
}

function writeConfig(configPath, config) {
  try {
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
    return config;
  } catch (e) {
    console.error('Failed to write config', e);
    return null;
  }
}

module.exports = { readConfig, writeConfig };
