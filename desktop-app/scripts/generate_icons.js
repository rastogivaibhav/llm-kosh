const { Jimp } = require('jimp');
const pngToIcoObj = require('png-to-ico');
const pngToIco = typeof pngToIcoObj === 'function' ? pngToIcoObj : (pngToIcoObj.default || pngToIcoObj.pngToIco);
const png2icons = require('png2icons');
const fs = require('fs');
const path = require('path');

async function generateIcons() {
  const inputJpg = process.argv[2];
  const buildDir = path.join(__dirname, '../build');
  
  if (!fs.existsSync(buildDir)) {
    fs.mkdirSync(buildDir);
  }

  const pngPath = path.join(buildDir, 'icon.png');
  const icoPath = path.join(buildDir, 'icon.ico');
  const icnsPath = path.join(buildDir, 'icon.icns');

  console.log(`Reading image: ${inputJpg}`);
  
  // Convert JPG to PNG
  const image = await Jimp.read(inputJpg);
  // Ensure it's square and a good size
  image.resize({ w: 256, h: 256 });
  await image.write(pngPath);
  console.log(`Generated: ${pngPath}`);

  // Convert PNG to ICO
  const icoBuffer = await pngToIco(pngPath);
  fs.writeFileSync(icoPath, icoBuffer);
  console.log(`Generated: ${icoPath}`);

  // Convert PNG to ICNS
  const pngBuffer = fs.readFileSync(pngPath);
  const icnsBuffer = png2icons.createICNS(pngBuffer, png2icons.BICUBIC2, 0);
  if (icnsBuffer) {
    fs.writeFileSync(icnsPath, icnsBuffer);
    console.log(`Generated: ${icnsPath}`);
  } else {
    console.error('Failed to generate ICNS');
  }

  console.log('Done!');
}

generateIcons().catch(console.error);
