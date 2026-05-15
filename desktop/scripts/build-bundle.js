/**
 * Build pipeline: Next.js standalone → desktop/resources/frontend/
 * Optional: PyInstaller backend.exe → desktop/resources/backend.exe
 *
 * Usage:
 *   node scripts/build-bundle.js                    # full build
 *   node scripts/build-bundle.js --skip-backend     # frontend only
 *   node scripts/build-bundle.js --skip-frontend    # backend only
 */

const { execSync, spawnSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const DESKTOP = path.resolve(__dirname, '..');
const ROOT = path.resolve(DESKTOP, '..');
const RES = path.join(DESKTOP, 'resources');

const args = process.argv.slice(2);
const skipBackend = args.includes('--skip-backend');
const skipFrontend = args.includes('--skip-frontend');

fs.mkdirSync(RES, { recursive: true });

// === 1. Backend (PyInstaller) ===
if (!skipBackend) {
  console.log('[1/3] Building backend.exe via PyInstaller...');
  execSync('pyinstaller --clean --noconfirm build.spec', {
    cwd: path.join(ROOT, 'backend'),
    stdio: 'inherit',
  });
  const src = path.join(ROOT, 'backend', 'dist', 'backend.exe');
  const dst = path.join(RES, 'backend.exe');
  if (!fs.existsSync(src)) throw new Error('backend.exe not produced by PyInstaller');
  fs.copyFileSync(src, dst);
  console.log(`    -> ${dst} (${(fs.statSync(dst).size / 1024 / 1024).toFixed(1)} MB)`);
} else {
  console.log('[1/3] Backend skipped (--skip-backend)');
}

// === 2. Next.js standalone build ===
if (!skipFrontend) {
  const FRONTEND = path.join(ROOT, 'frontend');
  const npmrcPath = path.join(FRONTEND, '.npmrc');

  console.log('[2/3] Building Next.js standalone...');

  const canSymlink = checkSymlinkSupport();
  let npmrcBackup = null;

  if (!canSymlink) {
    // Windows without Developer Mode: pnpm's isolated-modules linker uses symlinks → EPERM.
    // Temporarily switch to hoisted (flat) node_modules so Next.js can create the standalone
    // output without needing symlink privileges.
    console.log('    (Windows) Switching to hoisted node_modules for the build...');
    npmrcBackup = fs.existsSync(npmrcPath) ? fs.readFileSync(npmrcPath, 'utf8') : null;
    const hoistedConfig = (npmrcBackup || '').replace(/node-linker=.*\n?/g, '') + 'node-linker=hoisted\n';
    fs.writeFileSync(npmrcPath, hoistedConfig);

    const pnpmBin = findPnpm();
    if (!pnpmBin) throw new Error('pnpm not found. Install via: npm i -g pnpm');
    run(`${pnpmBin} install --prefer-offline`, { cwd: FRONTEND });
  }

  try {
    // npm run build works on all platforms (package.json scripts: "build": "next build")
    run('npm run build', {
      cwd: FRONTEND,
      env: { ...process.env, NEXT_OUTPUT: 'standalone' },
    });
  } finally {
    if (!canSymlink) {
      // Restore original .npmrc and pnpm linker
      if (npmrcBackup === null) {
        fs.rmSync(npmrcPath, { force: true });
      } else {
        fs.writeFileSync(npmrcPath, npmrcBackup);
      }
      console.log('    (Windows) Restoring pnpm isolated-modules...');
      const pnpmBin = findPnpm();
      if (pnpmBin) run(`${pnpmBin} install --prefer-offline`, { cwd: FRONTEND });
    }
  }

  const STANDALONE_SRC = path.join(FRONTEND, '.next', 'standalone', 'frontend');
  const NM_SRC = path.join(FRONTEND, '.next', 'standalone', 'node_modules');
  const STATIC_SRC = path.join(FRONTEND, '.next', 'static');
  const PUBLIC_SRC = path.join(FRONTEND, 'public');
  const FE_DEST = path.join(RES, 'frontend');

  console.log('[3/3] Copying standalone -> resources/frontend/...');
  fs.rmSync(FE_DEST, { recursive: true, force: true });
  fs.mkdirSync(FE_DEST, { recursive: true });

  // dereference: true — resolves any symlinks to real files (safe on all platforms)
  const copyOpts = { recursive: true, dereference: true };

  fs.cpSync(STANDALONE_SRC, FE_DEST, copyOpts);
  if (fs.existsSync(NM_SRC)) {
    fs.cpSync(NM_SRC, path.join(FE_DEST, 'node_modules'), copyOpts);
  }
  fs.cpSync(STATIC_SRC, path.join(FE_DEST, '.next', 'static'), copyOpts);
  if (fs.existsSync(PUBLIC_SRC)) {
    fs.cpSync(PUBLIC_SRC, path.join(FE_DEST, 'public'), copyOpts);
  }

  // Fast-fail: verify server.js was produced
  const serverJs = path.join(FE_DEST, 'server.js');
  if (!fs.existsSync(serverJs)) {
    throw new Error(`server.js not found at ${serverJs} — standalone build may have failed`);
  }
  console.log(`    -> ${FE_DEST}/server.js`);
  console.log(`    -> total size: ${getDirSizeMB(FE_DEST).toFixed(0)} MB`);
} else {
  console.log('[2/3 & 3/3] Frontend skipped (--skip-frontend)');
}

console.log('Bundle ready.');

/** Run a shell command, inheriting stdio. Throws on non-zero exit. */
function run(cmd, opts = {}) {
  execSync(cmd, { stdio: 'inherit', shell: true, ...opts });
}

/** Returns true if the OS allows creating symlinks without admin/Developer Mode. */
function checkSymlinkSupport() {
  const testTarget = path.join(os.tmpdir(), `gsd_sl_target_${Date.now()}`);
  const testLink = path.join(os.tmpdir(), `gsd_sl_link_${Date.now()}`);
  fs.writeFileSync(testTarget, '');
  try {
    fs.symlinkSync(testTarget, testLink);
    fs.unlinkSync(testLink);
    return true;
  } catch {
    return false;
  } finally {
    fs.rmSync(testTarget, { force: true });
  }
}

/** Finds pnpm executable. Checks: PATH shim, corepack cache, npx fallback. */
function findPnpm() {
  // 1. Try corepack cache location (AppData/Local/node/corepack/v1/pnpm/<version>/bin/pnpm.cjs)
  const corecacheBase = path.join(os.homedir(), 'AppData', 'Local', 'node', 'corepack', 'v1', 'pnpm');
  if (fs.existsSync(corecacheBase)) {
    const versions = fs.readdirSync(corecacheBase).sort().reverse();
    for (const ver of versions) {
      const bin = path.join(corecacheBase, ver, 'bin', 'pnpm.cjs');
      if (fs.existsSync(bin)) return `node "${bin}"`;
    }
  }
  // 2. Try PATH via spawnSync
  const result = spawnSync('pnpm', ['--version'], { shell: true, encoding: 'utf8' });
  if (result.status === 0) return 'pnpm';
  // 3. npx fallback (slower)
  return 'npx pnpm@10';
}

function getDirSizeMB(dir) {
  let total = 0;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true, recursive: true })) {
    if (entry.isFile()) {
      try {
        const p = path.join(entry.parentPath ?? entry.path, entry.name);
        total += fs.statSync(p).size;
      } catch {}
    }
  }
  return total / 1024 / 1024;
}
