import assert from 'node:assert/strict';
import test from 'node:test';
import { canRestoreRecovery, createCheckpointWriter, recoveryTargetKey } from '../static/js/report_editor/recovery_state.js';

const binding = { revision: 2, revisionHash: 'hash', snapshotHash: 'snapshot', templateHash: 'template' };
const checkpoint = { restorable: true, expired: false, base_revision: 2, base_revision_hash: 'hash',
    snapshot_hash: 'snapshot', template_hash: 'template' };

test('restore requires the exact server revision and source/template binding', () => {
    assert.equal(canRestoreRecovery(checkpoint, binding), true);
    for (const field of ['revision', 'revisionHash', 'snapshotHash', 'templateHash']) {
        assert.equal(canRestoreRecovery(checkpoint, { ...binding, [field]: 'other' }), false);
    }
    assert.equal(canRestoreRecovery({ ...checkpoint, restorable: false }, binding), false);
    assert.equal(canRestoreRecovery({ ...checkpoint, expired: true }, binding), false);
});

test('target matching ignores JSON key ordering but not target identity', () => {
    assert.equal(recoveryTargetKey({ scope: 'daily_note', note_id: 'one' }),
        recoveryTargetKey({ note_id: 'one', scope: 'daily_note' }));
    assert.notEqual(recoveryTargetKey({ scope: 'daily_note', note_id: 'one' }),
        recoveryTargetKey({ note_id: 'two', scope: 'daily_note' }));
});

test('checkpoint writer serializes requests and retains newer dirty content', async () => {
    const writes = [];
    let value = 'first', release;
    const writer = createCheckpointWriter({
        capture: async () => ({ value }),
        put: async payload => {
            writes.push(payload);
            if (writes.length === 1) await new Promise(resolve => { release = resolve; });
            return { sequence: payload.sequence };
        },
    });
    writer.changed();
    const first = writer.flush();
    await new Promise(resolve => setImmediate(resolve));
    value = 'second';
    writer.changed();
    assert.equal(writes.length, 1);
    release();
    await first;
    await writer.flush();
    await writer.stop();
    assert.deepEqual(writes.map(item => [item.sequence, item.value]), [[1, 'first'], [2, 'second']]);
});

test('storage failure does not acknowledge an unsaved checkpoint', async () => {
    let receipts = 0, failures = 0;
    const writer = createCheckpointWriter({
        capture: async () => ({ value: 'text' }),
        put: async () => { throw new Error('offline'); },
        saved: () => { receipts += 1; },
        failed: () => { failures += 1; },
    });
    writer.changed();
    await writer.flush();
    await writer.stop();
    assert.equal(receipts, 0);
    assert.equal(failures, 1);
});
