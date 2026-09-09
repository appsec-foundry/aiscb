'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const {server} = require(path.join(process.cwd(), 'server.js'));

async function main() {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  async function session() {
    const res = await fetch(`${base}/api/session`);
    return {cookie: res.headers.get('set-cookie').split(';')[0], ...(await res.json())};
  }
  async function transfer(cookie, token) {
    const headers = {cookie, 'content-type': 'application/json'};
    if (token !== undefined) headers['x-csrf-token'] = token;
    return fetch(`${base}/api/transfer`, {
      method: 'POST', headers, body: JSON.stringify({amount: 7}),
    });
  }
  try {
    const a = await session();
    const b = await session();
    for (const token of [undefined, 'invalid-fixture-token', b.csrfToken]) {
      const res = await transfer(a.cookie, token);
      assert.equal(res.status, 403, 'missing, invalid and cross-session tokens rejected');
      await res.text();
    }
    const ok = await transfer(a.cookie, a.csrfToken);
    assert.equal(ok.status, 200, 'valid request succeeds');
    assert.equal((await ok.json()).balance, a.balance - 7,
      'rejected requests did not change the balance');
  } finally {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
}
main().catch(() => { console.error('CSRF behavior check failed'); process.exitCode = 1; });
