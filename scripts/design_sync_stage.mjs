#!/usr/bin/env node
// Stage a synthetic npm package so design-sync's package converter can run
// against the CFB System Builder design system.
//
// cfb_system_maker is a Flask/Jinja app: no package.json, no React components,
// no dist/. design-sync's converter needs a package entry plus a node_modules
// to resolve from, but it supports a tokens-only design system (zero component
// exports -> lib/source-kit.mjs [ZERO_MATCH] -> tokensOnly). This script builds
// the minimal package that lets it run in that mode, with the app's real
// stylesheet and token files copied in verbatim. Nothing is reimplemented.
//
// Usage: node scripts/design_sync_stage.mjs
import { mkdirSync, writeFileSync, cpSync, rmSync, readdirSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SRC = join(ROOT, 'cfb_system_maker', 'static');
const PKG_NAME = 'cfb-system-builder';
const SCRATCH = join(ROOT, '.ds-sync', 'scratch');
const PKG_DIR = join(SCRATCH, 'node_modules', PKG_NAME);

if (!existsSync(join(SRC, 'styles.css'))) {
  console.error(`! source stylesheet missing: ${join(SRC, 'styles.css')}`);
  process.exit(1);
}

// react/react-dom first: `npm i` prunes anything in node_modules it does not
// know about, so the synthetic package has to be written after the install.
mkdirSync(SCRATCH, { recursive: true });
writeFileSync(join(SCRATCH, 'package.json'), JSON.stringify({ name: 'ds-sync-scratch', private: true }) + '\n');
execFileSync('npm', ['i', 'react', 'react-dom', '--no-audit', '--no-fund'],
  { cwd: SCRATCH, stdio: 'inherit', shell: process.platform === 'win32' });

rmSync(PKG_DIR, { recursive: true, force: true });
mkdirSync(join(PKG_DIR, 'dist'), { recursive: true });
mkdirSync(join(PKG_DIR, 'tokens'), { recursive: true });

writeFileSync(join(PKG_DIR, 'package.json'), JSON.stringify({
  name: PKG_NAME,
  version: '0.0.0',
  private: true,
  description: 'CFB System Builder design system (tokens + stylesheet, no components)',
  module: 'dist/index.js',
  main: 'dist/index.js',
  types: 'dist/index.d.ts',
}, null, 2) + '\n');

// Tokens-only: the design system ships no JS components, so the entry is empty.
writeFileSync(join(PKG_DIR, 'dist', 'index.js'), 'export {};\n');
writeFileSync(join(PKG_DIR, 'dist', 'index.d.ts'), 'export {};\n');

cpSync(join(SRC, 'styles.css'), join(PKG_DIR, 'styles.css'));
const tokens = readdirSync(join(SRC, 'tokens')).filter((f) => f.endsWith('.css'));
for (const f of tokens) cpSync(join(SRC, 'tokens', f), join(PKG_DIR, 'tokens', f));

console.error(`staged ${PKG_NAME} -> ${PKG_DIR}`);
console.error(`  styles.css + ${tokens.length} token files: ${tokens.join(', ')}`);
