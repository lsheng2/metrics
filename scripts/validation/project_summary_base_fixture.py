import argparse
import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
import importlib
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import uuid

import uvicorn


MANIFEST_SHA = 'e7386f82d2bf3963feccc28cfbfda732b9eddb829831d5ba660b50554e5f81c4'


def deny_outbound(*args, **kwargs):
    raise RuntimeError('Outbound connections are forbidden for this synthetic fixture.')


def load_profile(root):
    manifest_bytes = (root / 'manifest.json').read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_SHA:
        raise ValueError('Wrong synthetic contract pack.')
    manifest = json.loads(manifest_bytes)
    for name, expected in manifest['files'].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Contract pack content mismatch.')
    profile = manifest['profiles']['project-reporting.summary@review-1']['profile']
    return json.loads((root / profile).read_text(encoding='utf-8'))


class ExactVectorExecutor:
    execution_mode = 'synthetic'
    backend_id = 'dashboard-w5-join-fixture'

    def __init__(self, vector, observations):
        self.vector = vector
        self.observations = observations

    async def execute(self, compiled):
        content = compiled.messages[-1][1]
        if (hashlib.sha256(content.encode()).hexdigest() != self.vector['input_sha256']
                or json.loads(content) != self.vector['input']):
            raise ValueError('The application input differs from the registered joint vector.')
        with self.observations.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'effectiveInputSha256': compiled.effective_input_sha256,
                                     'inputSha256': self.vector['input_sha256'],
                                     'executionMode': 'synthetic'}) + '\n')
        await asyncio.sleep(0.01)
        return json.dumps(self.vector['output'], ensure_ascii=False, sort_keys=True, separators=(',', ':'))


async def serve(args):
    directory = args.data_dir.resolve()
    directory.mkdir()
    source = args.source_root.resolve() / 'services' / 'app-service'
    sys.path.insert(0, str(source))
    socket.socket.connect = deny_outbound
    socket.socket.connect_ex = deny_outbound
    socket.create_connection = deny_outbound
    candidate = importlib.import_module('app.task_run_candidate')
    registration = importlib.import_module('app.services.app_chat_registration')
    authentication = importlib.import_module('app.services.app_request_auth')
    if not Path(candidate.__file__).resolve().is_relative_to(source):
        raise ValueError('The Base factory was not loaded from the fixed source copy.')
    vector = json.loads(args.fixture.read_text(encoding='utf-8'))
    profile = load_profile(args.pack_root.resolve())
    app_id, credential_ref = 'metrics-dashboard', 'synthetic-integration'
    secret = secrets.token_hex(32)
    app = candidate.create_task_run_candidate(
        data_directory=directory,
        registrations={app_id: replace(registration.BUILTIN_APP_REGISTRATIONS[app_id],
                                       auth=registration.AppAuthPolicy('service_account', credential_ref))},
        credential_secrets={credential_ref: secret}, profiles=[profile],
        grants=[{'sourceAppId': app_id, 'scopeKey': vector['scope_key'], 'enabled': True,
                 'grantRevision': 'dashboard-join-1',
                 'allowedProfiles': [{'key': profile['key'], 'revision': profile['revision']}]}],
        backend=ExactVectorExecutor(vector, directory / 'executor-observations.jsonl'),
    )
    for name, module in tuple(sys.modules.items()):
        if name == 'app' or name.startswith('app.') or name == 'template_runtime' or name.startswith('template_runtime.'):
            origin = getattr(module, '__file__', None)
            if origin is not None and not Path(origin).resolve().is_relative_to(source):
                raise ValueError('Mixed Base source origins are not supported.')
    stop = directory / f'stop-{uuid.uuid4().hex}'
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(128)
        server = uvicorn.Server(uvicorn.Config(app, log_level='warning', access_log=False))
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            async with asyncio.timeout(15):
                while not server.started:
                    if task.done():
                        await task
                        raise RuntimeError('Synthetic fixture exited before readiness.')
                    await asyncio.sleep(0.02)
            token = authentication.sign_app_auth_token(
                source_app_id=app_id, credential_ref=credential_ref, auth_mode='service_account', secret=secret,
                issuer=app_id, audience='ai-base-application-sdk',
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
            connection = {
                'executionMode': 'synthetic', 'qualification': 'synthetic_only', 'contractVersion': 'task-run/1',
                'packVersion': '0.1.0a2', 'pid': os.getpid(), 'scopeKey': vector['scope_key'],
                'sourceAppId': app_id, 'baseUrl': f'http://127.0.0.1:{listener.getsockname()[1]}',
                'credentialRef': credential_ref, 'token': token, 'runStoreId': app.state.task_run_service.run_store_id,
                'stopFile': str(stop), 'grantRevision': 'dashboard-join-1',
                'limitPolicyRevision': 'base-b-cancel-synthetic-1',
            }
            pending = directory / 'connection.tmp'
            pending.write_text(json.dumps(connection), encoding='utf-8')
            pending.replace(directory / 'connection.json')
            print('Synthetic joint fixture ready.', flush=True)
            async with asyncio.timeout(540):
                while not stop.exists() and not task.done():
                    await asyncio.sleep(0.05)
        finally:
            server.should_exit = True
            await asyncio.wait_for(asyncio.shield(task), 15)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--pack-root', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    asyncio.run(serve(parser.parse_args()))


if __name__ == '__main__':
    main()
