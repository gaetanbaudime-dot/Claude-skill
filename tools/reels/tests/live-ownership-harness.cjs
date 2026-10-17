// Exercise the explicit live-check runner with generated credentials and a
// file-backed fake Google transport shared by its independent child process.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { generateKeyPairSync } = require('node:crypto');
const { spawnSync } = require('node:child_process');
const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'reels-live-check-'));
const ledger = path.join(directory, 'ledger.json');
const preload = path.join(directory, 'transport.cjs');
const script = path.join(__dirname, 'live-ownership.cjs');
const appRoot = path.resolve(__dirname, '../../app_clippers');
const header = ['version', 'owner_sha256', 'kind', 'resource_sha256', 'parent_sha256'];
fs.writeFileSync(ledger, JSON.stringify([header]));
fs.writeFileSync(preload, `const fs=require('node:fs'); const ledger=${JSON.stringify(ledger)};
global.fetch=async(value,init={})=>{
 const url=new URL(String(value));
 if(url.origin==='https://oauth2.googleapis.com'&&url.pathname==='/token')return Response.json({access_token:'generated-fixture-token',expires_in:3600});
 if(url.origin!=='https://sheets.googleapis.com'||!url.pathname.startsWith('/v4/spreadsheets/fixture-existing-sheet/values/'))throw Error('Unexpected network');
 const values=JSON.parse(fs.readFileSync(ledger,'utf8'));
 if(init.method==='POST'){const rows=JSON.parse(init.body).values;values.push(...rows);fs.writeFileSync(ledger,JSON.stringify(values));return Response.json({updates:{updatedRows:rows.length}})}
 return Response.json({values});
};`);
const { privateKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
const env = { ...process.env, VERCEL_ENV: 'preview', REELS_LIVE_VERIFY: 'clippers',
  REELS_OWNERSHIP_SPREADSHEET_ID: 'fixture-existing-sheet',
  GOOGLE_SERVICE_ACCOUNT_JSON: JSON.stringify({ client_email: 'fixture@example.invalid',
    private_key: privateKey.export({ type: 'pkcs8', format: 'pem' }) }),
  NODE_OPTIONS: '--require=' + preload };
function run(patch = {}, cwd = appRoot) {
  return spawnSync(process.execPath, [script], { cwd, env: { ...env, ...patch }, encoding: 'utf8', timeout: 30000 });
}
try {
  const result = run();
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.ok, true);
  assert.equal(report.verification.persistedRows, 4);
  assert.equal(report.verification.foreignReferencesDenied, 12);
  assert.equal(report.verification.freshProcess, true);
  assert.equal(report.providerCalls, 0);
  assert.equal(JSON.parse(fs.readFileSync(ledger, 'utf8')).length, 5);
  for (const patch of [{ VERCEL_ENV: 'production' }, { REELS_LIVE_VERIFY: '' },
    { REELS_OWNERSHIP_SPREADSHEET_ID: '' }, { GOOGLE_SERVICE_ACCOUNT_JSON: '' }]) {
    const failure = run(patch);
    assert.equal(failure.status, 1);
    assert.equal(JSON.parse(failure.stderr).stage, 'guard');
    assert.equal(failure.stdout, '');
  }
  assert.equal(JSON.parse(run({}, directory).stderr).stage, 'guard');
  assert.equal(JSON.parse(fs.readFileSync(ledger, 'utf8')).length, 5);
  console.log('Live registry runner: preview/app/config guards, generated credentials, four persistent hashes, fresh process and 12 foreign-owner denials passed offline.');
} finally {
  fs.rmSync(directory, { recursive: true, force: true });
}
