import json, subprocess, time, sys

REPO = 'Objective-Wanderer/matemplates-site'

def gh(args):
    return subprocess.run(['gh'] + args, capture_output=True, text=True)

def pages_info():
    p = gh(['api', f'repos/{REPO}/pages'])
    return json.loads(p.stdout) if p.returncode == 0 else {}

def cert_state(d):
    c = d.get('https_certificate') or {}
    return c.get('status') if isinstance(c, dict) else c

def rebuild():
    p = gh(['api', '-X', 'POST', f'repos/{REPO}/pages/builds'])
    print('  rebuild triggered:', 'ok' if p.returncode == 0 else (p.stderr or p.stdout)[:120], flush=True)

def live_https():
    """True when https://matemplates.com serves 200 with real content."""
    r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
                        '--max-time', '20', 'https://matemplates.com'], capture_output=True, text=True)
    if r.stdout.strip() != '200':
        return False
    b = subprocess.run(['curl', '-s', '--max-time', '20', 'https://matemplates.com'],
                       capture_output=True, text=True)
    return 'mate' in b.stdout.lower() and '<title' in b.stdout.lower()

print(f'start {time.strftime("%H:%M:%S")}', flush=True)
nudged = False
deadline = time.time() + 45 * 60

while time.time() < deadline:
    d = pages_info()
    enforced, cert = d.get('https_enforced'), cert_state(d)
    print(f'{time.strftime("%H:%M:%S")} | enforced: {enforced} | cert: {cert}', flush=True)

    if cert == 'issued' and not enforced:
        p = gh(['api', '-X', 'PUT', f'repos/{REPO}/pages', '-F', 'https_enforced=true'])
        print('  https_enforced PUT:', 'ok' if p.returncode == 0 else (p.stderr or '')[:120], flush=True)
        time.sleep(10)
        continue

    if enforced and cert == 'issued':
        print('CERT ISSUED + ENFORCED - verifying live site...', flush=True)
        for attempt in range(10):
            if live_https():
                print('LIVE OK: https://matemplates.com serving storefront (200 + title)', flush=True)
                sys.exit(0)
            print(f'  cert live but site not ready yet (attempt {attempt+1})', flush=True)
            time.sleep(30)
        print('WARNING: cert issued but live check never passed - inspect manually', flush=True)
        sys.exit(2)

    if not nudged and time.time() > deadline - 30 * 60:
        rebuild()
        nudged = True

    time.sleep(60)

print('TIMEOUT after 45min - cert still not issued; needs GitHub support/manual Pages settings visit', flush=True)
sys.exit(3)
