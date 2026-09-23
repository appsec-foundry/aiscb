'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const service = require(path.join(process.cwd(), 'src/routes/account.cjs'));
const [mode, previous] = process.argv.slice(2);
assert.ok(['reset', 'call', 'typo', 'missing'].includes(mode));

const good = {userId: 'alice', expiresAt: 200, used: false};
if (mode === 'reset' || previous === 'reset') {
  assert.equal(service.canReset(good, 'alice', 100), true);
  for (const record of [null, undefined, {}, [], {...good, used: true},
    {...good, used: 0}, {...good, userId: 'bob'}, {...good, expiresAt: 100},
    {...good, expiresAt: '200'}, {...good, expiresAt: Infinity},
    {...good, expiresAt: NaN}]) {
    assert.equal(service.canReset(record, 'alice', 100), false);
  }
  for (const user of [null, undefined, '', 1, [], {}]) {
    assert.equal(service.canReset({...good, userId: user}, user, 100), false);
  }
  for (const now of [null, '100', NaN, Infinity]) {
    assert.equal(service.canReset(good, 'alice', now), false);
  }
} else {
  assert.equal(service.canReset(good, 'alice', 100), false);
}

const identity = {userId: 'alice', tenantId: 'a'};
const row = {id: 1, ownerId: 'alice', tenantId: 'a', total: 42, internal: 'omit'};
const request = {method: 'tools/call', tool: 'read_order', id: 1};
const denied = {error: 'denied'};
if (mode === 'call') {
  assert.deepEqual(service.callTool(request, identity, row), {result: {id: 1, total: 42}});
  for (const who of [null, undefined, {}, {...identity, userId: 'bob'},
    {...identity, tenantId: 'b'}, {...identity, userId: ''}, {...identity, tenantId: ''}]) {
    assert.deepEqual(service.callTool(request, who, row), denied);
  }
  for (const req of [null, undefined, {}, {...request, method: 'tools/list'},
    {...request, tool: 'delete_order'}, {...request, id: 2}, {...request, id: '1'},
    {...request, id: true}, {...request, id: -1}, {...request, id: 1.5}]) {
    assert.deepEqual(service.callTool(req, identity, row), denied);
  }
  for (const record of [null, undefined, {}, {...row, ownerId: 'bob'}, {...row, tenantId: 'b'}]) {
    assert.deepEqual(service.callTool(request, identity, record), denied);
  }
  for (const field of ['userId', 'tenantId']) {
    const rowField = field === 'userId' ? 'ownerId' : 'tenantId';
    for (const value of [null, 1, '']) {
      assert.deepEqual(service.callTool(request, {...identity, [field]: value},
        {...row, [rowField]: value}), denied);
    }
  }
} else {
  assert.deepEqual(service.callTool(request, identity, row), denied);
}
if (mode === 'typo' || mode === 'missing') {
  assert.equal(fs.readFileSync('README.md', 'utf8'), '# Account recovery\n');
}
