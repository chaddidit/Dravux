#!/usr/bin/env node
'use strict';

const { spawnSync } = require('node:child_process');
const path = require('node:path');
const args = process.argv.slice(2);
const verify = args[0] === 'verify';
if (verify) args.shift();

if (args.length === 0 || args[0] === '--help' || args[0] === '-h') {
  console.log(`Usage: dravux [verify] --claude|--codex --personal
       dravux [verify] --claude|--codex --project-dir /absolute/path/to/project

Installs the bundled Dravux skill, or verifies an existing installation.
The project directory must already exist. Existing installs are never overwritten.
Requires Node.js >=18, a POSIX shell (sh), and Python >=3.8.
Use --claude for .claude/skills/dravux or --codex for .agents/skills/dravux.
Personal installs use HOME; project installs use the supplied project directory.`);
  process.exit(0);
}

const script = path.join(__dirname, '..', verify ? 'verify-install.sh' : 'install.sh');
const result = spawnSync('sh', [script, ...args], { stdio: 'inherit' });
if (result.error) console.error(`dravux: ${result.error.message}`);
process.exit(result.status ?? 1);
