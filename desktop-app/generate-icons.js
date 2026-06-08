const Jimp = require('jimp');
const png2icons = require('png2icons');
const fs = require('fs');
const path = require('path');

const buildDir = path.join(__dirname, 'build');
if (!fs.existsSync(buildDir)) {
  fs.mkdirSync(buildDir);
}

const resourcesDir = path.join(__dirname, 'resources', 'bin');
if (!fs.existsSync(resourcesDir)) {
  fs.mkdirSync(resourcesDir, { recursive: true });
}
fs.writeFileSync(path.join(resourcesDir, 'README.md'), 'Sidecar binaries should be placed here.\n');

async function generate() {
  const image = new Jimp.Jimp({ width: 256, height: 256, color: 0x00000000 }); // Transparent background
  // Draw a simple shape or text if we want, or just leave it transparent with a dot so it's not totally empty
  image.setPixelColor(0xFFFFFFFF, 128, 128);
  
  const pngPath = path.join(buildDir, 'icon.png');
  await image.writeAsync(pngPath);
  
  const pngBuffer = fs.readFileSync(pngPath);
  
  const icoBuffer = png2icons.createICO(pngBuffer, png2icons.BICUBIC, 0, false);
  if (icoBuffer) {
    fs.writeFileSync(path.join(buildDir, 'icon.ico'), icoBuffer);
  }
  
  const icnsBuffer = png2icons.createICNS(pngBuffer, png2icons.BICUBIC, 0);
  if (icnsBuffer) {
    fs.writeFileSync(path.join(buildDir, 'icon.icns'), icnsBuffer);
  }
  
  console.log('Valid placeholder icons generated.');
}

generate().catch(console.error);
