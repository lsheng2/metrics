from html.parser import HTMLParser
import time
from urllib.parse import urlsplit
from uuid import UUID

import requests


class RunStateParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'h2' and dict(attrs).get('id') == 'project-run-state':
            self.active = True

    def handle_endtag(self, tag):
        if tag == 'h2':
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


class RuntimeJoinHttp:
    def __init__(self, manifest, directory, *, user='alice'):
        self.base = f'http://127.0.0.1:{manifest["app_port"]}'
        self.directory = directory
        self.counter = 0
        self.csrf_name = manifest['cookies']['csrf']
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.auth = tuple(manifest['auth'][user][key] for key in ('username', 'password'))
        self.referer = self.base + manifest['routes']['project_stage_reports']

    def close(self):
        self.session.close()

    def request(self, method, path, *, data=None, payload=None, fragment=False):
        if path.startswith('http'):
            parsed = urlsplit(path)
            if f'{parsed.scheme}://{parsed.netloc}' != self.base:
                raise ValueError('Qualification HTTP target must be the owned app.')
            path = parsed.path + (f'?{parsed.query}' if parsed.query else '')
        headers = {'Referer': self.referer}
        if fragment:
            headers['HX-Request'] = 'true'
        if method != 'GET':
            headers['X-CSRFToken'] = self.session.cookies.get(self.csrf_name, '')
        response = self.session.request(
            method, self.base + path, data=data, json=payload, headers=headers,
            timeout=20, allow_redirects=False,
        )
        self.counter += 1
        suffix = 'json' if 'application/json' in response.headers.get('Content-Type', '') else 'html'
        (self.directory / f'{self.counter:03d}-{response.status_code}.{suffix}').write_bytes(response.content)
        return response

    def wait_run(self, path, *, seconds=180):
        deadline = time.monotonic() + seconds
        while True:
            response = self.request('GET', path, fragment=True)
            if response.status_code != 200:
                raise AssertionError(f'Run observation failed: HTTP {response.status_code}')
            parser = RunStateParser()
            parser.feed(response.text)
            state = ''.join(parser.parts).strip()
            if state in {'draft_ready', 'partial', 'failed', 'canceled', 'interrupted'}:
                return state
            if not state or time.monotonic() >= deadline:
                raise AssertionError(f'Run did not finish: {state}')
            time.sleep(0.2)

    def json_result(self, method, path, *, payload=None):
        response = self.request(method, path, payload=payload)
        value = response.json()
        if response.status_code not in {200, 202} or value.get('error') is not None:
            raise AssertionError(f'Business request failed: HTTP {response.status_code}, {value.get("error")}')
        return value['result']

    def wait_assist(self, path, *, seconds=120):
        deadline = time.monotonic() + seconds
        while True:
            result = self.json_result('GET', path)
            if result['state'] not in {'prepared', 'observing', 'unknown'}:
                return result
            if time.monotonic() >= deadline:
                raise AssertionError(f'Assist did not finish: {result["state"]}')
            time.sleep(0.2)


def operation_id(response):
    if response.status_code != 302:
        raise AssertionError(f'Run submission failed: HTTP {response.status_code}')
    location = response.headers['Location']
    identifier = urlsplit(location).path.rstrip('/').rsplit('/', 1)[-1]
    UUID(identifier)
    return identifier, location
