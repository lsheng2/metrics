import assert from 'node:assert/strict';
import test from 'node:test';

import { exportState } from '../static/js/report_exports.js';

const base = 'http://127.0.0.1:8088/projects/example/';
const url = '/projects/p/stages/s/reports/drafts/d/export/';

test('saved revision updates the export URL without using the editor buffer', () => {
    assert.equal(exportState(url, 'markdown', { revision: '2' }, base).href,
        'http://127.0.0.1:8088/projects/p/stages/s/reports/drafts/d/export/?format=markdown&revision=2');
    assert.equal(exportState(url, 'xlsx', { revision: '3' }, base).href,
        'http://127.0.0.1:8088/projects/p/stages/s/reports/drafts/d/export/?format=xlsx&revision=3');
});

test('every existing unsaved lifecycle state removes the actionable link', () => {
    for (const key of ['reportAuthoringDirty', 'reportAuthoringSaving', 'reportAuthoringFailed', 'reportAuthoringUncertain']) {
        assert.deepEqual(exportState(url, 'markdown', { revision: '2', [key]: 'true' }, base),
            { href: null, disabled: true });
    }
    assert.equal(exportState(url, 'markdown', { revision: 'invalid' }, base).disabled, true);
});

test('publication export has no draft revision and foreign URLs cannot become links', () => {
    assert.equal(exportState('/publications/p/export/', 'xlsx', null, base).href,
        'http://127.0.0.1:8088/publications/p/export/?format=xlsx');
    assert.equal(exportState('https://foreign.example.test/export/', 'markdown', null, base).disabled, true);
});
