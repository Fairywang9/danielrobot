#!/usr/bin/env python3
"""Publish explicitly selected static files, with a reviewed plan and rollback."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import sys
import urllib.request
import uuid

SOURCE = Path(__file__).resolve().parent.parent
HOST = '47.116.100.27'
SITE = 'https://upspeedtech.com'
ROOT = '/usr/share/nginx/html'

# Sent over the authenticated SSH channel, never installed in the public site.
# Keep compatible with the server's system Python.
REMOTE = r'''
import base64, hashlib, json, os, pathlib, shutil, sys, tarfile, tempfile
ROOT = pathlib.Path('/usr/share/nginx/html')
BACKUPS = pathlib.Path('/var/backups/upspeedtech')
ALLOWED = {'.html', '.css', '.js', '.json', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.pdf', '.woff', '.woff2', '.ico', '.xml', '.txt'}

def target(name):
    p = pathlib.PurePosixPath(name)
    if p.is_absolute() or not p.parts or any(x in ('', '.', '..') or x.startswith('.') for x in p.parts):
        raise ValueError('Invalid public path: ' + name)
    if p.parts[0] in ('deployment', 'scripts', 'tools', 'outputs', 'artifacts') or p.suffix.lower() not in ALLOWED:
        raise ValueError('Not a static website file: ' + name)
    dest = ROOT.joinpath(*p.parts)
    if dest.resolve() != dest or not str(dest).startswith(str(ROOT) + '/'):
        raise ValueError('Symlink or path escape: ' + name)
    if dest.exists() and not dest.is_file():
        raise ValueError('Target is not a regular file: ' + name)
    return dest

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

def release_path(value):
    if len(value) != 32 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Invalid release ID')
    return BACKUPS / 'releases' / value

def atomic(path, data, metadata=None):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    fd, temporary = tempfile.mkstemp(prefix='.upspeed-deploy-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, metadata['mode'] if metadata else 0o644)
        os.chown(temporary, metadata['uid'] if metadata else 0, metadata['gid'] if metadata else 0)
        if metadata and 'times' in metadata:
            os.utime(temporary, tuple(metadata['times']))
        os.replace(temporary, str(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def write_manifest(directory, manifest):
    # Manifests and backups are outside the public web root.
    temporary = directory / 'manifest.tmp'
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    os.replace(str(temporary), str(directory / 'manifest.json'))

def restore(directory, manifest):
    for entry in manifest['files']:
        dest = target(entry['path'])
        if entry['before'] is None:
            if dest.exists():
                dest.unlink()
        else:
            data = (directory / 'originals' / entry['path']).read_bytes()
            if hashlib.sha256(data).hexdigest() != entry['before']:
                raise ValueError('Damaged backup: ' + entry['path'])
            atomic(dest, data, entry['metadata'])

request = json.load(sys.stdin)
operation = request['operation']
if ROOT.resolve() != ROOT or not ROOT.is_dir():
    raise ValueError('Unexpected website root')

if operation == 'plan':
    result = {'root': str(ROOT), 'files': []}
    for item in request['files']:
        dest = target(item['path'])
        result['files'].append({'path': item['path'], 'before': digest(dest), 'after': item['after']})
elif operation == 'snapshot':
    BACKUPS.mkdir(parents=True, exist_ok=True, mode=0o700)
    dest = BACKUPS / ('site-' + request['release'] + '.tar.gz')
    if dest.exists():
        raise ValueError('Snapshot already exists')
    with tarfile.open(str(dest), 'w:gz') as archive:
        archive.add(str(ROOT), arcname='html')
    os.chmod(str(dest), 0o600)
    result = {'snapshot': str(dest), 'bytes': dest.stat().st_size}
elif operation == 'publish':
    payloads = []
    seen = set()
    for item in request['files']:
        if item['path'] in seen:
            raise ValueError('Duplicate path')
        seen.add(item['path'])
        dest = target(item['path'])
        if digest(dest) != item['before']:
            raise ValueError('Server file changed since plan: ' + item['path'])
        data = base64.b64decode(item['data'], validate=True)
        if hashlib.sha256(data).hexdigest() != item['after']:
            raise ValueError('Payload checksum mismatch: ' + item['path'])
        metadata = None
        if dest.exists():
            st = dest.stat()
            metadata = {'mode': st.st_mode & 0o777, 'uid': st.st_uid, 'gid': st.st_gid, 'times': [st.st_atime, st.st_mtime]}
        payloads.append((item, dest, data, metadata))
    directory = release_path(request['release'])
    directory.mkdir(parents=True, mode=0o700)
    os.chmod(str(BACKUPS), 0o700)
    manifest = {'release': request['release'], 'status': 'prepared', 'files': []}
    for item, dest, data, metadata in payloads:
        if metadata:
            original = directory / 'originals' / item['path']
            original.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copy2(str(dest), str(original))
        manifest['files'].append({'path': item['path'], 'before': item['before'], 'after': item['after'], 'metadata': metadata})
    write_manifest(directory, manifest)
    try:
        for item, dest, data, metadata in payloads:
            # Preserve existing owner/mode, but use current modification time.
            install_metadata = dict(metadata) if metadata else None
            if install_metadata:
                install_metadata.pop('times')
            atomic(dest, data, install_metadata)
        for item, dest, data, metadata in payloads:
            if digest(dest) != item['after']:
                raise ValueError('Installed checksum mismatch: ' + item['path'])
    except Exception:
        restore(directory, manifest)
        manifest['status'] = 'rolled_back'
        write_manifest(directory, manifest)
        raise
    manifest['status'] = 'published'
    write_manifest(directory, manifest)
    result = {'release': request['release'], 'backup': str(directory), 'files': manifest['files']}
elif operation == 'rollback':
    directory = release_path(request['release'])
    manifest = json.loads((directory / 'manifest.json').read_text())
    # Refuse to overwrite a later publication or a manual server edit.
    for entry in manifest['files']:
        current = digest(target(entry['path']))
        if current not in (entry['before'], entry['after']):
            raise ValueError('File changed after this release: ' + entry['path'])
    restore(directory, manifest)
    manifest['status'] = 'rolled_back'
    write_manifest(directory, manifest)
    result = {'release': request['release'], 'status': 'rolled_back', 'files': manifest['files']}
else:
    raise ValueError('Unknown operation')
print(json.dumps(result, ensure_ascii=False))
'''


def connection(args):
    config_path = Path(args.connection).expanduser().resolve()
    config = json.loads(config_path.read_text())
    key = (config_path.parent / config['key']).resolve()
    known_hosts = (config_path.parent / config['known_hosts']).resolve()
    if key.stat().st_mode & 0o077:
        raise ValueError('Private key permissions must be 600 or stricter')
    return ['ssh', '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
            '-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UserKnownHostsFile=' + str(known_hosts), '-i', str(key), 'admin@' + HOST]


def remote(args, request):
    command = 'sudo -n python3 -c ' + shlex.quote(REMOTE)
    result = subprocess.run(connection(args) + [command], input=json.dumps(request).encode(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace').strip())
    return json.loads(result.stdout)


def local_file(name):
    pure = PurePosixPath(name)
    if pure.is_absolute() or any(part.startswith('.') or part == '..' for part in pure.parts):
        raise ValueError('Invalid source path: ' + name)
    path = SOURCE / name
    if path.resolve() != path or not path.is_file():
        raise ValueError('Not a regular source file: ' + name)
    return path


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def verify(files, field, release):
    from urllib.parse import quote
    for item in files:
        if item[field] is None:
            continue
        url = SITE + '/' + quote(item['path']) + '?publish_check=' + release
        request = urllib.request.Request(url, headers={'Cache-Control': 'no-cache', 'Accept-Encoding': 'identity'})
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read()
        if checksum(data) != item[field]:
            raise RuntimeError('Live page checksum mismatch: ' + item['path'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connection', required=True, help='Local connection JSON; contains key paths, never upload it')
    subs = parser.add_subparsers(dest='operation', required=True)
    plan = subs.add_parser('plan')
    plan.add_argument('--output', required=True)
    plan.add_argument('files', nargs='+', help='Explicit paths relative to the website repository; publish entry pages last')
    publish = subs.add_parser('publish')
    publish.add_argument('plan')
    rollback = subs.add_parser('rollback')
    rollback.add_argument('release')
    subs.add_parser('snapshot')
    args = parser.parse_args()
    if args.operation == 'plan':
        if len(set(args.files)) != len(args.files):
            raise ValueError('Duplicate file path')
        files = [{'path': name, 'after': checksum(local_file(name).read_bytes())} for name in args.files]
        result = remote(args, {'operation': 'plan', 'files': files})
        result.update({'host': HOST, 'site': SITE, 'release': uuid.uuid4().hex})
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.operation == 'snapshot':
        print(json.dumps(remote(args, {'operation': 'snapshot', 'release': uuid.uuid4().hex}), indent=2))
    elif args.operation == 'publish':
        plan = json.loads(Path(args.plan).read_text())
        if (plan['host'], plan['root'], plan['site']) != (HOST, ROOT, SITE):
            raise ValueError('Plan is for a different website')
        files = []
        for item in plan['files']:
            data = local_file(item['path']).read_bytes()
            if checksum(data) != item['after']:
                raise ValueError('Local file changed after plan: ' + item['path'])
            files.append(dict(item, data=base64.b64encode(data).decode()))
        result = remote(args, {'operation': 'publish', 'release': plan['release'], 'files': files})
        try:
            verify(result['files'], 'after', result['release'])
        except Exception as error:
            recovery = remote(args, {'operation': 'rollback', 'release': result['release']})
            raise RuntimeError('Live verification failed; server files restored: ' + str(error)) from error
        print(json.dumps({'release': result['release'], 'backup': result['backup'], 'verified': [x['path'] for x in files]}, indent=2))
    else:
        result = remote(args, {'operation': 'rollback', 'release': args.release})
        verify(result['files'], 'before', args.release)
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Publish error: ' + str(error), file=sys.stderr)
        sys.exit(1)
