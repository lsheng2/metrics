export function canRestoreRecovery(checkpoint, binding) {
    return checkpoint?.restorable === true && checkpoint.expired === false
        && checkpoint.base_revision === Number(binding.revision)
        && checkpoint.base_revision_hash === binding.revisionHash
        && checkpoint.snapshot_hash === binding.snapshotHash
        && checkpoint.template_hash === binding.templateHash;
}

export function recoveryTargetKey(value) {
    return JSON.stringify(Object.entries(value || {}).sort(([a], [b]) => a.localeCompare(b)));
}

export function createCheckpointWriter({ capture, put, saved = () => {}, failed = () => {} }) {
    let sequence = 0, generation = 0, acknowledged = 0, timer = null, maximum = null, active = null, stopped = false;
    function clearTimers() { clearTimeout(timer); clearTimeout(maximum); timer = maximum = null; }
    function changed() {
        if (stopped) return;
        generation += 1;
        clearTimeout(timer);
        timer = setTimeout(flush, 1500);
        if (!maximum) maximum = setTimeout(flush, 10000);
    }
    function flush() {
        clearTimers();
        if (stopped || acknowledged === generation) return active || Promise.resolve();
        if (active) return active;
        const target = generation;
        active = (async () => {
            try {
                const value = await capture();
                if (value === null) { acknowledged = target; return; }
                const receipt = await put({ ...value, sequence: ++sequence });
                acknowledged = target;
                saved(receipt);
            } catch (error) {
                failed(error);
            } finally {
                active = null;
                if (!stopped && target !== generation) timer = setTimeout(flush, 1500);
            }
        })();
        return active;
    }
    return {
        changed, flush,
        async stop() { stopped = true; clearTimers(); if (active) await active; },
        resume() { stopped = false; },
    };
}
