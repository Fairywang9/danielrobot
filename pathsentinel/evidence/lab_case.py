"""A reproducible, local-only authorization fixture for the BP demonstration.

All records and identities are synthetic. This is a new bounded experiment,
not a customer assessment or a benchmark of the existing platform.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pathlib import Path
from datetime import datetime, timezone
from threading import Thread
import json
import hashlib

REPORTS = {
    'report-a': {'tenant_id': 'tenant-a', 'report_id': 'report-a', 'content': 'Synthetic report A'},
    'report-b': {'tenant_id': 'tenant-b', 'report_id': 'report-b', 'content': 'Synthetic report B'},
}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        parts = self.path.strip('/').split('/')
        user_tenant = 'tenant-a' if self.headers.get('Authorization') == 'Bearer demo-alice' else None
        code, body = 404, {'error': 'not_found'}
        if not user_tenant:
            code, body = 401, {'error': 'unauthenticated'}
        elif len(parts) == 3 and parts[0] in {'before', 'after'} and parts[1] == 'reports':
            report = REPORTS.get(parts[2])
            if report:
                # Before: authentication alone does not enforce object ownership.
                # After: require the authenticated tenant to own the requested object.
                if parts[0] == 'after' and report['tenant_id'] != user_tenant:
                    code, body = 403, {'error': 'forbidden'}
                else:
                    code, body = 200, report
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

def run():
    root = Path(__file__).resolve().parent
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    tests = []
    cases = [
        ('before-cross-tenant', '/before/reports/report-b', 200, '修复前跨租户请求'),
        ('after-cross-tenant', '/after/reports/report-b', 403, '修复后跨租户请求'),
        ('after-same-tenant', '/after/reports/report-a', 200, '修复后合法请求'),
    ]
    try:
        for case_id, path, expected, label in cases:
            req = Request(f'http://127.0.0.1:{server.server_port}{path}', headers={'Authorization': 'Bearer demo-alice'})
            try:
                with urlopen(req, timeout=3) as resp:
                    status, body = resp.status, json.loads(resp.read())
            except HTTPError as err:
                status, body = err.code, json.loads(err.read())
            assert status == expected, (case_id, status, expected)
            if case_id == 'before-cross-tenant':
                assert body['tenant_id'] == 'tenant-b'
            if case_id == 'after-cross-tenant':
                assert 'content' not in body
            tests.append({'id': case_id, 'label': label, 'method': 'GET', 'path': path, 'principal': 'Alice / tenant-a', 'status': status, 'body': body, 'expected_status': expected, 'passed': status == expected})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    data = {'fixture': 'PS-LAB-001', 'data_type': 'synthetic', 'scope': 'local loopback HTTP fixture only', 'executed_at': datetime.now(timezone.utc).isoformat(), 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'tests': tests, 'finding': {'title': '报告读取接口缺少租户归属校验', 'classification': 'CWE-639', 'business_effect': '普通用户可读取另一租户的合成报告', 'remediation': '在服务端校验当前租户与目标报告的tenant_id一致'}}
    (root / 'case-evidence.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'fixture': data['fixture'], 'tests': len(tests), 'passed': sum(t['passed'] for t in tests), 'statuses': [t['status'] for t in tests], 'evidence': str(root/'case-evidence.json')}, ensure_ascii=False))

if __name__ == '__main__':
    run()
