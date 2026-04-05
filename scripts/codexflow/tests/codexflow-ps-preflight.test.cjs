const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const isWindows = process.platform === 'win32';

const runPowerShell = (scriptPath, extraArgs = []) => {
  return spawnSync(
    'powershell',
    ['-ExecutionPolicy', 'Bypass', '-File', scriptPath, ...extraArgs],
    {
      encoding: 'utf8',
      cwd: process.cwd(),
    }
  );
};

const getOutput = (result) => `${result.stdout || ''}${result.stderr || ''}`;

test('extract script rejects root WorkRoot without TrimEnd runtime crash', { skip: !isWindows }, () => {
  const script = path.join(process.cwd(), 'scripts', 'codexflow', 'extract-installed-codexflow.ps1');
  const result = runPowerShell(script, [
    '-InstallRoot',
    'D:\\apps\\CodexFlow\\win-unpacked',
    '-WorkRoot',
    'C:\\',
    '-DryRun',
  ]);

  assert.notEqual(result.status, 0, 'expected non-zero exit status for unsafe WorkRoot');
  const output = getOutput(result);
  assert.match(output, /Unsafe WorkRoot/i);
  assert.doesNotMatch(output, /Cannot convert argument "trimChars"/i);
});

test('apply script fails fast on unsafe WorkRoot before install checks', { skip: !isWindows }, () => {
  const script = path.join(process.cwd(), 'scripts', 'codexflow', 'apply-history-visibility-patch.ps1');
  const result = runPowerShell(script, [
    '-InstallRoot',
    'D:\\apps\\CodexFlow\\win-unpacked',
    '-LaunchCmd',
    '',
    '-WorkRoot',
    'C:\\',
  ]);

  assert.notEqual(result.status, 0, 'expected non-zero exit status for unsafe WorkRoot');
  const output = getOutput(result);
  assert.match(output, /Unsafe WorkRoot/i);
  assert.doesNotMatch(output, /InstallRoot not found/i);
  assert.doesNotMatch(output, /Cannot convert argument "trimChars"/i);
});
