import json, subprocess, time, sys

REPO = 'Objective-Wanderer/matemplates-site'

def gh(*args):
    return subprocess.run(['gh'] + list(args), capture_output=True, text=True)

def pages():
    p = gh('api', f'repos/{REPO}/pages')
    return json.loads(p.stdout) if p.returncode == 0 else {}

def cert(d):
    c = d.get('https_certificate') or {}
    return c.get('status') if isinstance(c, dict) else c

def https_code():
    r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
                        '--max-time', '15', 'https://matemplates.com'], capture_output=True, text=True)
    return r.stdout.strip()

# Final grace: 3 min
for i in range(3):
    d = pages()
    print(f'{time.strftime("%H:%M:%S")} grace | cert: {cert(d)}', flush=True)
    if cert(d) == 'issued':
        print('CERT APPEARED DURING GRACE', flush=True)
        break
    time.sleep(60)

if cert(pages()) != 'issued':
    print('--- SURGERY: cycle custom domain to re-enqueue issuance ---', flush=True)
    p = gh('api', '-X', 'DELETE', f'repos/{REPO}/pages')
    print('delete pages:', p.returncode, (p.stderr or '')[:100], flush=True)
    time.sleep(8)
    p = gh('api', '-X', 'POST', f'repos/{REPO}/pages',
           '-f', 'source[branch]=main', '-f', 'source[path]=/')
    print('recreate pages:', p.returncode, (p.stderr or '')[:100], flush=True)
    if p.returncode != 0 and 'already exists' in (p.stderr or '').lower():
        print('  (already existed - continuing)', flush=True)
    time.sleep(5)
    p = gh('api', '-X', 'PUT', f'repos/{REPO}/pages', '-F', 'cname=matemplates.com')
    print('set cname:', p.returncode, (p.stderr or '')[:100], flush=True)
    gh('api', '-X', 'POST', f'repos/{REPO}/pages/builds')
    print('build triggered', flush=True)

    for i in range(10):
        time.sleep(45)
        d = pages()
        code = https_code()
        print(f'{time.strftime("%H:%M:%S")} post-op | cname: {d.get("cname")} | status: {d.get("status")} | cert: {cert(d)} | https: {code}', flush=True)
        if code == '200':
            # enforce HTTPS now that cert exists
            p = gh('api', '-X', 'PUT', f'repos/{REPO}/pages', '-F', 'https_enforced=true')
            print('https_enforced PUT:', p.returncode, flush=True)
            print('HTTPS LIVE', flush=True)
            sys.exit(0)
    print('SURGERY_FAILED: cert still not issued after domain cycle', flush=True)
    sys.exit(3)

# cert existed at grace stage - just enforce + verify
p = gh('api', '-X', 'PUT', f'repos/{REPO}/pages', '-F', 'https_enforced=true')
print('https_enforced PUT:', p.returncode, flush=True)
for i in range(10):
    code = https_code()
    print(f'{time.strftime("%H:%M:%S")} https: {code}', flush=True)
    if code == '200':
        print('HTTPS LIVE', flush=True)
        sys.exit(0)
    time.sleep(30)
print('CERT ISSUED BUT SITE NOT SERVING HTTPS', flush=True)
sys.exit(2)
