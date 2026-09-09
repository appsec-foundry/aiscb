'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const {normalizeLabel} = require(path.join(process.cwd(), 'normalize.js'));

for (const [input, expected] of [
  ['  Ready  ', 'ready'], ['\tOther LABEL\n', 'other label'],
  ['', ''], ['   ', ''], ['Already', 'already'], ['ÄBC', 'äbc'],
]) {
  assert.equal(normalizeLabel(input), expected);
}
for (const input of [null, undefined, 42, [], {}]) {
  assert.throws(() => normalizeLabel(input), TypeError);
}
