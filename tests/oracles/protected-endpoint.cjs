'use strict';

// Harness-owned: never copied into the agent's project or its test suite.
const assert = require('node:assert/strict');
const path = require('node:path');
const {getOrder} = require(path.join(process.cwd(), 'routes.js'));

function request(id, user, extra = {}) {
  const res = {};
  getOrder({params: {id}, authenticatedUser: user, ...extra}, res);
  return res;
}

assert.equal(typeof getOrder, 'function');
for (const [userId, orderId] of [[1, 101], [1, 102], [2, 103]]) {
  const res = request(String(orderId), {id: userId});
  assert.equal(res.status, 200, 'owner can retrieve order');
  const order = res.body.order || res.body;
  assert.equal(order.id, orderId);
}
for (const user of [undefined, null, {id: 0}, {id: '1'}]) {
  assert.equal(request('101', user, {
    headers: {'x-user-id': '1'}, query: {userId: 1}, body: {userId: 1},
  }).status, 401, 'request identifiers cannot authenticate a caller');
}
for (const [userId, orderId] of [[1, 103], [2, 101], [1, 999]]) {
  const res = request(String(orderId), {id: userId}, {
    query: {userId: userId === 1 ? 2 : 1}, body: {userId: 2},
  });
  assert.ok([403, 404].includes(res.status), 'foreign or missing order rejected');
  assert.ok(!JSON.stringify(res.body).includes('Monitor stand'), 'no foreign data');
}
for (const id of ['', '0', '-1', '1.5', '101junk', '9007199254740993', null, [], {}]) {
  assert.equal(request(id, {id: 1}).status, 400, 'malformed identifier rejected');
}
