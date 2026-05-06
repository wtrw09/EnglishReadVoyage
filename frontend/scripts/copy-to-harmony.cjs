const fs = require('fs');
const path = require('path');

const src = path.resolve(process.cwd(), 'dist');
const dest = path.resolve(process.cwd(), '..', 'harmony', 'entry', 'src', 'main', 'resources', 'rawfile', 'dist');

function copyRecursive(srcDir, destDir) {
  if (!fs.existsSync(destDir)) {
    fs.mkdirSync(destDir, { recursive: true });
  }
  const entries = fs.readdirSync(srcDir, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(srcDir, entry.name);
    const destPath = path.join(destDir, entry.name);
    if (entry.isDirectory()) {
      copyRecursive(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

if (fs.existsSync(src)) {
  if (fs.existsSync(dest)) {
    fs.rmSync(dest, { recursive: true, force: true });
  }
  copyRecursive(src, dest);
  console.log('✅ Copied to: ' + dest);
} else {
  console.error('❌ dist directory not found');
  process.exit(1);
}
