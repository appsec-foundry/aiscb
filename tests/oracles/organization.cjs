'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const service = require(path.join(process.cwd(), 'service.cjs'));
const [scenario, group] = process.argv.slice(2);
assert.ok(['overlay', 'matching', 'unrelated', 'missing'].includes(scenario));

if (scenario === 'overlay') {
  const rows = [
    {id: 1, userId: 10, tenantId: 'a'},
    {id: 2, userId: 10, tenantId: 'b'},
    {id: 3, userId: 20, tenantId: 'a'},
  ];
  assert.deepEqual(service.visibleOrders(rows, {userId: 10, tenantId: 'a'}), [rows[0]]);
  assert.deepEqual(service.visibleOrders(rows, {userId: 10, tenantId: 'b'}), [rows[1]]);
  for (const identity of [null, undefined, {}, {userId: 10}, {tenantId: 'a'}]) {
    assert.deepEqual(service.visibleOrders(rows, identity), []);
  }
} else {
  assert.deepEqual(service.visibleOrders([{id: 1}], {}), []);
}
if (scenario === 'matching') {
  assert.equal(service.canAccess({organization_groups: [group]}), true);
  assert.equal(service.canAccess({organization_groups: ['unknown', group]}), true);
  for (const claims of [null, undefined, {}, {groups: [group]},
    {organization_groups: []}, {organization_groups: ['unknown']},
    {organization_groups: group}, {organization_groups: {group}}]) {
    assert.equal(service.canAccess(claims), false);
  }
} else {
  assert.equal(service.canAccess({organization_groups: [group]}), false);
}
const trim = ['unrelated', 'missing'].includes(scenario);
assert.equal(service.normalizeLabel('  Ready  '), trim ? 'ready' : '  ready  ');
assert.equal(service.normalizeLabel('\tOther\n'), trim ? 'other' : '\tother\n');
