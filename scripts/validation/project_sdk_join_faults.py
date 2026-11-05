import hashlib
import json

import httpx


class HttpFaults:
    def __init__(self, *, mode='none', replacement_content=None, on_result=None):
        self.mode = mode
        self.replacement_content = replacement_content
        self.on_result = on_result
        self.events = []
        self.triggered = False

    def wrap(self, upstream=None):
        return ObservedTransport(self, upstream or httpx.AsyncHTTPTransport(retries=0, trust_env=False))


class ObservedTransport(httpx.AsyncBaseTransport):
    def __init__(self, faults, upstream):
        self.faults = faults
        self.upstream = upstream

    async def handle_async_request(self, request):
        response = await self.upstream.handle_async_request(request)
        original = await response.aread()
        await response.aclose()
        value = json.loads(original)
        event = {
            'method': request.method, 'path': request.url.path,
            'client_run_key': request.url.params.get('clientRunKey'),
            'request_sha256': hashlib.sha256(request.content).hexdigest(),
            'status': response.status_code, 'received_sha256': hashlib.sha256(original).hexdigest(),
            'fault': None,
        }
        self.faults.events.append(event)
        mode = self.faults.mode
        is_result = request.url.path.endswith('/result') and response.status_code == 200
        if mode == 'drop_submit' and not self.faults.triggered and request.method == 'POST' and request.url.path == '/api/runs':
            event['fault'] = mode
            self.faults.triggered = True
            raise httpx.ReadTimeout('Synthetic loss after receiving the actual submit response.', request=request)
        if mode == 'wrong_evidence':
            replacement = self.faults.replacement_content
            replacement_sha = hashlib.sha256(replacement.encode()).hexdigest()
            if is_result:
                value.update(content=replacement, sha256=replacement_sha)
            elif value.get('state') == 'succeeded':
                value['result']['sha256'] = replacement_sha
        elif is_result and mode == 'wrong_store':
            value['runStoreId'] = 'foreign-store'
        elif is_result and mode == 'wrong_digest':
            value['sha256'] = '0' * 64
        elif is_result and mode == 'cancel_before_result' and not self.faults.triggered:
            await self.faults.on_result()
        if is_result and mode != 'none':
            self.faults.triggered = True
            event['fault'] = mode
        delivered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        event['delivered_sha256'] = hashlib.sha256(delivered).hexdigest()
        return httpx.Response(response.status_code, content=delivered, headers={'content-type': 'application/json'})

    async def aclose(self):
        await self.upstream.aclose()
