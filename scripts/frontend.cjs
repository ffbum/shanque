const { spawnSync } = require('node:child_process');
const { existsSync } = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const localNode = path.join(root, 'node_modules/node/bin', process.platform === 'win32' ? 'node.exe' : 'node');
const result = spawnSync(existsSync(localNode) ? localNode : process.execPath,
  [path.join(root, 'frontend/node_modules/@umijs/max/bin/max.js'), ...process.argv.slice(2)],
  { cwd: path.join(root, 'frontend'), stdio: 'inherit' });
if (result.error) throw result.error;
process.exit(result.status ?? 1);
