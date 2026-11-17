#!/usr/bin/env python3
"""Настоящий service worker «Мій голос» рядом с «Говоримо разом» и «Знову слова» на одном сайте.
Запуск: python3 MyVoice/tests/test_sw.py <папка MyVoice> <папка Govorim> <папка SpeechRehab>
Тест сам собирает временный сайт, поднимает сервер, проверяет установку, обновление, офлайн и чужие кэши."""
import sys, os, shutil, tempfile, threading, functools, http.server, re
from playwright.sync_api import sync_playwright

MV, GV, SR = sys.argv[1:4]
root = tempfile.mkdtemp()
for src, name in [(MV, 'MyVoice'), (GV, 'Govorim'), (SR, 'SpeechRehab')]:
    shutil.copytree(src, os.path.join(root, name), ignore=shutil.ignore_patterns('.git', 'tests'))
shutil.copytree(MV, os.path.join(root, 'copy', 'MyVoice'), ignore=shutil.ignore_patterns('.git', 'tests'))

class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache'); super().end_headers()
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8766), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()
H = 'http://127.0.0.1:8766'
VCUR = re.search(r"const V = '([^']+)'", open(os.path.join(MV, 'sw.js'), encoding='utf8').read()).group(1)

OK = FAIL = 0
def check(n, c, x=''):
    global OK, FAIL
    if c: OK += 1
    else: FAIL += 1; print('FAIL:', n, x)

INIT = "if(!localStorage.getItem('mv.settings'))localStorage.setItem('mv.settings',JSON.stringify({profile:'words'}));localStorage.setItem('mv.tour.seen',JSON.stringify({home:1,tiles:1,show:1,abc:1,type:1}));localStorage.setItem('aac.tour.seen',JSON.stringify({home:1,tiles:1,hear:1,show:1,abc:1}));"
def ready(pg):
    pg.wait_for_function("navigator.serviceWorker&&navigator.serviceWorker.controller", timeout=20000)
def keys(pg): return sorted(pg.evaluate("caches.keys()"))

with sync_playwright() as p:
    b = p.chromium.launch()
    c = b.new_context(viewport={'width': 360, 'height': 640})
    c.add_init_script(INIT)
    pg = c.new_page(); pg.set_default_timeout(20000)
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    for app in ['Govorim', 'SpeechRehab', 'MyVoice']:
        pg.goto(f'{H}/{app}/index.html'); ready(pg); pg.wait_for_timeout(300)
        if pg.evaluate("!navigator.serviceWorker.controller"): pg.reload(); ready(pg)
    k = keys(pg)
    check('three caches', any(x.startswith('govorim-') for x in k) and any(x.startswith('speech-rehab-') for x in k) and VCUR+':/MyVoice/' in k, k)
    check('myvoice cache content', pg.evaluate(f"caches.open('{VCUR}:/MyVoice/').then(c=>c.keys()).then(r=>r.map(x=>new URL(x.url).pathname))") == ['/MyVoice/', '/MyVoice/index.html', '/MyVoice/manifest.json', '/MyVoice/icon-192.png', '/MyVoice/icon-512.png'])
    check('scope', pg.evaluate("navigator.serviceWorker.getRegistration().then(r=>new URL(r.scope).pathname)") == '/MyVoice/')
    regs = pg.evaluate("navigator.serviceWorker.getRegistrations().then(r=>r.map(x=>new URL(x.scope).pathname).sort())")
    check('three registrations', regs == ['/Govorim/', '/MyVoice/', '/SpeechRehab/'], regs)
    # манифест: id и ярлыки резолвятся в /MyVoice/
    man = pg.evaluate("fetch('manifest.json').then(r=>r.json())")
    check('manifest id', man['id'] == '/MyVoice/')
    check('shortcuts', [s['url'] for s in man['shortcuts']] == ['./index.html?open=card', './index.html?open=type', './index.html?open=yn'])
    # данные приложений не пересекаются
    pg.evaluate("localStorage.setItem('aac.settings',JSON.stringify({level:'L1'}))")
    pg.reload(); pg.wait_for_timeout(400)
    check('govorim settings ignored', pg.evaluate("settings.level") == 'L2')

    # обновление MyVoice до v2: свой старый кэш удаляется, чужие остаются
    swp = os.path.join(root, 'MyVoice', 'sw.js'); ip = os.path.join(root, 'MyVoice', 'index.html')
    t1 = open(swp, encoding='utf8').read(); t2 = open(ip, encoding='utf8').read()   # сначала прочитать, потом перезаписать
    N = int(re.search(r"const APP_VERSION = (\d+);", t2).group(1)); N2 = N + 1
    open(swp, 'w', encoding='utf8').write(t1.replace(f"'myvoice-v{N}'", f"'myvoice-v{N2}'"))
    open(ip, 'w', encoding='utf8').write(t2.replace(f'const APP_VERSION = {N};', f'const APP_VERSION = {N2};'))
    pg.reload();
    pg.wait_for_function(f"typeof APP_VERSION!=='undefined'&&APP_VERSION==={N2}", timeout=25000)
    pg.wait_for_timeout(800)
    k = keys(pg)
    check('updated cache', f'myvoice-v{N2}:/MyVoice/' in k and f'myvoice-v{N}:/MyVoice/' not in k, k)
    check('others kept after update', any(x.startswith('govorim-') for x in k) and any(x.startswith('speech-rehab-') for x in k), k)

    # копия в другой папке того же сайта — свой кэш
    pg.goto(f'{H}/copy/MyVoice/index.html'); ready(pg); pg.wait_for_timeout(300)
    k = keys(pg)
    check('copy own cache', VCUR+':/copy/MyVoice/' in k and f'myvoice-v{N2}:/MyVoice/' in k, k)

    # офлайн
    c.set_offline(True)
    for app, sel in [('MyVoice', '#typeBtn'), ('Govorim', '#micBtn'), ('copy/MyVoice', '#typeBtn')]:
        pg.goto(f'{H}/{app}/index.html'); pg.wait_for_selector(sel, timeout=10000)
        check(f'offline {app}', pg.locator(sel).count() == 1)
    pg.goto(f'{H}/MyVoice/index.html?open=card'); pg.wait_for_selector('#card', timeout=10000)
    check('offline shortcut card', pg.locator('#card').count() == 1)
    pg.goto(f'{H}/MyVoice/index.html'); pg.wait_for_selector('#typeBtn')
    pg.click('#typeBtn'); pg.click('.tykb .letters .lt >> nth=0')
    check('offline typing', len(pg.evaluate('tyText')) == 1)
    c.set_offline(False)
    check('no page errors', not errs, errs)
    b.close()
srv.shutdown(); shutil.rmtree(root, ignore_errors=True)
print(f'OK {OK}  FAIL {FAIL}')
sys.exit(1 if FAIL else 0)
