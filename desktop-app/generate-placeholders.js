const fs = require('fs');
const path = require('path');

const buildDir = path.join(__dirname, 'build');
if (!fs.existsSync(buildDir)) {
  fs.mkdirSync(buildDir);
}

// Minimal 1x1 valid PNG base64
const base64Png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';

fs.writeFileSync(path.join(buildDir, 'icon.png'), Buffer.from(base64Png, 'base64'));
// We just write the PNG data as ICO/ICNS as placeholders. electron-builder may complain but often accepts or ignores if it's just a file.
// Ideally, we'd use real formats, but for a placeholder this will fulfill the file requirement.
fs.writeFileSync(path.join(buildDir, 'icon.ico'), Buffer.from(base64Png, 'base64'));
fs.writeFileSync(path.join(buildDir, 'icon.icns'), Buffer.from(base64Png, 'base64'));

console.log('Placeholder icons generated in build/');
