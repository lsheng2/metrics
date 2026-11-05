import asyncio
import hashlib
import json

import httpx
import pytest

from scripts.validation.project_sdk_join_faults import HttpFaults


def test_should_drop_only_first_submit_after_upstream_has_received_it():
    upstream = []
    faults = HttpFaults(mode='drop_submit')

    async def exercise():
        def handle(request):
            upstream.append(request.method)
            return httpx.Response(202, json={'runId': 'run-1', 'state': 'queued'})

        async with httpx.AsyncClient(transport=faults.wrap(httpx.MockTransport(handle))) as client:
            with pytest.raises(httpx.ReadTimeout):
                await client.post('http://127.0.0.1/api/runs', json={'clientRunKey': 'original'})
            response = await client.get('http://127.0.0.1/api/runs/by-client-key?clientRunKey=original')
            assert response.json()['runId'] == 'run-1'

    asyncio.run(exercise())
    assert upstream == ['POST', 'GET']
    assert faults.triggered is True
    assert faults.events[0]['fault'] == 'drop_submit'


@pytest.mark.parametrize('mode,field,expected', [
    ('wrong_store', 'runStoreId', 'foreign-store'),
    ('wrong_digest', 'sha256', '0' * 64),
])
def test_should_deliver_faulted_result_and_retain_original_response_digest(mode, field, expected):
    original = {'runStoreId': 'real-store', 'sha256': 'a' * 64, 'content': '{}'}
    faults = HttpFaults(mode=mode)

    async def exercise():
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json=original))
        async with httpx.AsyncClient(transport=faults.wrap(transport)) as client:
            response = await client.get('http://127.0.0.1/api/runs/run-1/result')
            assert response.json()[field] == expected
            assert faults.events[0]['received_sha256'] != faults.events[0]['delivered_sha256']

    asyncio.run(exercise())
    assert original['runStoreId'] == 'real-store'


def test_should_corrupt_evidence_consistently_so_business_validation_is_reached():
    content = json.dumps({'evidence': ['comment:999']})
    expected = hashlib.sha256(content.encode()).hexdigest()
    faults = HttpFaults(mode='wrong_evidence', replacement_content=content)

    async def exercise():
        def handle(request):
            if request.url.path.endswith('/result'):
                return httpx.Response(200, json={'content': '{}', 'sha256': 'a' * 64})
            return httpx.Response(200, json={'state': 'succeeded', 'result': {'sha256': 'a' * 64}})

        async with httpx.AsyncClient(transport=faults.wrap(httpx.MockTransport(handle))) as client:
            snapshot = (await client.get('http://127.0.0.1/api/runs/run-1')).json()
            result = (await client.get('http://127.0.0.1/api/runs/run-1/result')).json()
            assert snapshot['result']['sha256'] == result['sha256'] == expected
            assert result['content'] == content

    asyncio.run(exercise())


def test_should_persist_cancel_callback_before_delivering_the_late_result():
    order = []

    async def cancel():
        order.append('cancel_intent')

    faults = HttpFaults(mode='cancel_before_result', on_result=cancel)

    async def exercise():
        def handle(request):
            order.append('upstream_result')
            return httpx.Response(200, json={'content': '{}'})

        async with httpx.AsyncClient(transport=faults.wrap(httpx.MockTransport(handle))) as client:
            await client.get('http://127.0.0.1/api/runs/run-1/result')
            order.append('delivered')

    asyncio.run(exercise())
    assert order == ['upstream_result', 'cancel_intent', 'delivered']
