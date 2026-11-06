from __future__ import annotations

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

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from project_management.app.domain.capture_values import canonical_bytes
from scripts.validation.project_full_stack_identity import write_exit_receipt


MANIFEST_SHA = 'e7386f82d2bf3963feccc28cfbfda732b9eddb829831d5ba660b50554e5f81c4'
STORE_OWNER = 'dashboard-manual-fullstack-base-store'


def deny_outbound(*args, **kwargs):
    raise RuntimeError('Outbound connections are forbidden for this synthetic fixture.')


def deny_schema(uri):
    raise ValueError(f'Unregistered schema reference: {uri}')


def schema_registry(documents: dict) -> Registry:
    registry = Registry(retrieve=deny_schema)
    for uri, schema in documents.items():
        registry = registry.with_resource(uri, Resource.from_contents(schema))
    return registry


def load_profile(root: Path) -> dict:
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


def prepare_store_directory(args) -> Path:
    run_dir = run_directory_for(args.connection_file.resolve(), args.launch_id)
    directory = args.data_dir.absolute()
    reject_reparse_components(directory)
    resolved = directory.resolve(strict=False)
    expected = run_dir / 'base' / 'store'
    if resolved != expected:
        raise ValueError('Base store path is not owned by this run.')
    existed = resolved.exists()
    if existed:
        if not resolved.is_dir():
            raise ValueError('Base store path is not a directory.')
        reject_links_under(resolved)
    else:
        resolved.mkdir(parents=True, exist_ok=False)
    owner_path = run_dir / 'base' / 'store-owner.json'
    owner = store_owner(run_dir, resolved)
    if owner_path.exists() and json.loads(owner_path.read_text(encoding='utf-8')) != owner:
        raise ValueError('Base store owner marker is invalid.')
    owner_path.write_text(json.dumps(owner, sort_keys=True), encoding='utf-8')
    (args.connection_file.resolve().parent / 'store-proof.json').write_text(json.dumps({
        'schema_version': 1,
        'launch_id': args.launch_id,
        'store_existed': existed,
        'data_dir': str(resolved),
        'owner_path': str(owner_path),
    }, sort_keys=True), encoding='utf-8')
    return resolved


def run_directory_for(connection_file: Path, launch_id: str) -> Path:
    launch_dir = connection_file.parent
    if launch_dir.name != launch_id or launch_dir.parent.name != 'launches' or launch_dir.parent.parent.name != 'lifecycle':
        raise ValueError('Connection file is not bound to the current launch.')
    run_dir = launch_dir.parents[2]
    launch_payload = json.loads((launch_dir / 'launch.json').read_text(encoding='utf-8'))
    if (launch_payload.get('service') != 'ai-base' or launch_payload.get('launch_id') != launch_id
            or Path(launch_payload.get('connection_file')).resolve(strict=False) != connection_file):
        raise ValueError('Launch descriptor does not match Base store open request.')
    return run_dir.resolve(strict=True)


def store_owner(run_dir: Path, directory: Path) -> dict:
    owner = json.loads((run_dir / 'owner.json').read_text(encoding='utf-8'))
    return {
        'schema_version': 1,
        'owner': STORE_OWNER,
        'run_uuid': owner['run_uuid'],
        'repository': owner['repository'],
        'data_dir': str(directory),
    }


def reject_reparse_components(path: Path) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if current.exists() and is_link(current):
            raise ValueError('Base store path contains a link or reparse component.')


def reject_links_under(directory: Path) -> None:
    for path in directory.rglob('*'):
        if is_link(path):
            raise ValueError('Base store contains a link or reparse path.')


def is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, 'is_junction', None)
    return bool(is_junction and is_junction())


class ExactDynamicVectorExecutor:
    execution_mode = 'synthetic'
    backend_id = 'dashboard-qualify-fixture'

    def __init__(self, vector: dict, observations: Path, input_schema: dict):
        self.vector = vector
        self.observations = observations
        self.validator = Draft202012Validator(input_schema, registry=schema_registry(vector.get('schema_documents', {})))
        self.cases = vector.get('cases')
        if self.cases is not None:
            if vector.get('schema_version') != 2 or not isinstance(self.cases, list) or len(self.cases) != 3:
                raise ValueError('The week fixture requires three exact vectors.')
            identities = [case['input_template']['binding']['stable_id'] for case in self.cases]
            if identities != ['101', '102', '103']:
                raise ValueError('The week fixture has unexpected identities.')
            for case in self.cases:
                binding = case['input_template']['binding']
                if vector['scope_key'] != f"projects.{binding['project_id']}.stages.{binding['stage_id']}":
                    raise ValueError('The week fixture has a foreign scope.')

    async def execute(self, compiled):
        content = compiled.messages[-1][1]
        value = json.loads(content)
        self.validator.validate(value)
        vector = self.vector
        if self.cases is not None:
            matches = [case for case in self.cases
                       if case['input_template']['binding'] == value['binding']]
            if len(matches) != 1:
                raise ValueError('The application binding is not a registered week vector.')
            vector = matches[0]
        capture_id = dynamic_capture_id(value)
        normalized = normalize_capture_id(value, capture_id, vector['capture_placeholder'])
        if normalized != vector['input_template']:
            raise ValueError('The application input differs from the registered qualification vector.')
        input_sha = hashlib.sha256(content.encode()).hexdigest()
        output = adapt_output(vector['output_template'], value, capture_id)
        with self.observations.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({
                'inputSha256': input_sha,
                'effectiveInputSha256': compiled.effective_input_sha256,
                'executionMode': 'synthetic',
                'captureId': capture_id,
                'stableId': value['binding']['stable_id'],
            }, sort_keys=True) + '\n')
        await asyncio.sleep(0.01)
        return json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def dynamic_capture_id(value: dict) -> str:
    ids = [value['target_capture_id'], value['delta']['to_capture_id']]
    ids.extend(row['capture_id'] for row in value['evidence'])
    if len(set(ids)) != 1:
        raise ValueError('Dynamic capture IDs must match.')
    return str(ids[0])


def normalize_capture_id(value: dict, capture_id: str, placeholder: str) -> dict:
    normalized = json.loads(json.dumps(value, ensure_ascii=False))
    if normalized['target_capture_id'] != capture_id or normalized['delta']['to_capture_id'] != capture_id:
        raise ValueError('Unexpected dynamic capture binding.')
    normalized['target_capture_id'] = placeholder
    normalized['delta']['to_capture_id'] = placeholder
    for row in normalized['evidence']:
        if row['capture_id'] != capture_id:
            raise ValueError('Unexpected evidence capture binding.')
        row['capture_id'] = placeholder
        expected = hashlib.sha256(canonical_bytes(row['value'])).hexdigest()
        if row['source_hash'] != expected:
            raise ValueError('Evidence source hash mismatch.')
    return normalized


def adapt_output(template: dict, input_value: dict, capture_id: str) -> dict:
    output = json.loads(json.dumps(template, ensure_ascii=False))
    output['binding'] = input_value['binding']
    output['target_capture_id'] = capture_id
    return output


async def serve(args):
    import uvicorn

    directory = prepare_store_directory(args)
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
    vector = {**vector, 'schema_documents': profile['schemaDocuments']}
    app_id, credential_ref = 'metrics-dashboard', 'synthetic-integration'
    secret = secrets.token_hex(32)
    app = candidate.create_task_run_candidate(
        data_directory=directory,
        registrations={app_id: replace(registration.BUILTIN_APP_REGISTRATIONS[app_id],
                                       auth=registration.AppAuthPolicy('service_account', credential_ref))},
        credential_secrets={credential_ref: secret},
        profiles=[profile],
        grants=[{'sourceAppId': app_id, 'scopeKey': vector['scope_key'], 'enabled': True,
                 'grantRevision': 'dashboard-join-1',
                 'allowedProfiles': [{'key': profile['key'], 'revision': profile['revision']}]}],
        backend=ExactDynamicVectorExecutor(vector, directory / 'executor-observations.jsonl', profile['inputSchema']),
    )
    stop = args.stop_file.resolve()
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', args.port))
        listener.listen(128)
        server = uvicorn.Server(uvicorn.Config(app, log_level='warning', access_log=False))
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            async with asyncio.timeout(15):
                while not server.started:
                    if task.done():
                        await task
                    await asyncio.sleep(0.02)
            token = authentication.sign_app_auth_token(
                source_app_id=app_id,
                credential_ref=credential_ref,
                auth_mode='service_account',
                secret=secret,
                issuer=app_id,
                audience='ai-base-application-sdk',
                expires_at=datetime.now(UTC) + timedelta(seconds=args.lifetime_seconds + 620),
            )
            connection = {
                'executionMode': 'synthetic',
                'qualification': 'synthetic_only',
                'contractVersion': 'task-run/1',
                'packVersion': '0.1.0a2',
                'pid': os.getpid(),
                'workerPid': os.getpid(),
                'scopeKey': vector['scope_key'],
                'sourceAppId': app_id,
                'baseUrl': f'http://127.0.0.1:{listener.getsockname()[1]}',
                'credentialRef': credential_ref,
                'token': token,
                'runStoreId': app.state.task_run_service.run_store_id,
                'stopFile': str(stop),
                'grantRevision': 'dashboard-join-1',
                'limitPolicyRevision': 'base-b-cancel-synthetic-1',
                'packRoot': str(args.pack_root.resolve()),
            }
            connection['launchId'] = args.launch_id
            connection['exitFile'] = str(args.exit_file.resolve())
            pending = args.connection_file.resolve().with_name(f'{args.connection_file.name}.tmp')
            pending.write_text(json.dumps(connection), encoding='utf-8')
            pending.replace(args.connection_file.resolve())
            async with asyncio.timeout(args.lifetime_seconds + 620):
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
    parser.add_argument('--stop-file', type=Path, required=True)
    parser.add_argument('--connection-file', type=Path, required=True)
    parser.add_argument('--exit-file', type=Path, required=True)
    parser.add_argument('--launch-id', required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--lifetime-seconds', type=int, required=True)
    args = parser.parse_args()
    code = 0
    try:
        asyncio.run(serve(args))
    except SystemExit as error:
        code = error.code if type(error.code) is int else 1
    except BaseException:
        code = 1
        raise
    finally:
        write_exit_receipt(args.exit_file, service='ai-base', launch_id=args.launch_id, pid=os.getpid(), exit_code=code)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
