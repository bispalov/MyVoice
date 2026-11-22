#!/usr/bin/env python3
"""Тесты «Мій голос» v14: проверка возможностей браузера — окно при первом открытии не в Chrome,
строка в «О приложении», пункт справки «🌐 Браузеры», загрузка без озвучки. Браузеры имитируются:
user agent + удаление/подмена SpeechRecognition, speechSynthesis, getVoices. Запуск как test_v1.py."""
import json, sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765/MyVoice/'
URL = BASE + 'index.html'
OK = FAIL = 0
def check(n, c, x=''):
    global OK, FAIL
    if c: OK += 1
    else: FAIL += 1; print('FAIL:', n, x)

UA_CHROME = 'Mozilla/5.0 (Linux; Android 13; SM-A515F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36'
UA_FF = 'Mozilla/5.0 (Android 13; Mobile; rv:132.0) Gecko/132.0 Firefox/132.0'
UA_SAM = 'Mozilla/5.0 (Linux; Android 13; SM-A515F) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/26.0 Chrome/122.0.0.0 Mobile Safari/537.36'
UA_FB = UA_CHROME + ' [FBAN/EMA;FBLC/uk_UA;FBAV/430.0.0.0;]'
TOUR_ALL = "localStorage.setItem('mv.tour.seen',JSON.stringify({home:1,tiles:1,show:1,abc:1,type:1,pb:1}));"
NO_SR = "try{delete window.webkitSpeechRecognition;delete window.SpeechRecognition}catch(e){};Object.defineProperty(window,'webkitSpeechRecognition',{value:undefined,configurable:true});Object.defineProperty(window,'SpeechRecognition',{value:undefined,configurable:true});"
FAKE_SR = "window.webkitSpeechRecognition=function(){};"
NO_TTS = "delete Window.prototype.speechSynthesis;delete window.speechSynthesis;delete window.SpeechSynthesisUtterance;"
def VOICES(langs):  # подмена списка голосов
    return "SpeechSynthesis.prototype.getVoices=function(){return %s.map(l=>({lang:l,name:l,voiceURI:l}))};SpeechSynthesis.prototype.speak=function(){};" % json.dumps(langs)
ST = {'profile': 'words', 'theme': 'dark'}
def page(b, ua=UA_CHROME, extra='', st=ST, lang='uk', w=360, hgt=640, tour=True, keep=False):
    c = b.new_context(viewport={'width': w, 'height': hgt}, service_workers='block', user_agent=ua)
    init = (TOUR_ALL if tour else '') + extra
    if not keep:
        init += f"if(!sessionStorage.getItem('x')){{sessionStorage.setItem('x',1);localStorage.setItem('mv.settings',JSON.stringify({json.dumps(st)}));localStorage.setItem('mv.lang','{lang}');}}"
    c.add_init_script(init)
    pg = c.new_page(); pg.set_default_timeout(6000)
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(2200)
    return c, pg, errs
has = lambda pg: pg.locator('#brw').count() == 1
items = lambda pg: pg.evaluate("[...document.querySelectorAll('#brw .brwi')].map(e=>e.textContent)")

with sync_playwright() as p:
    b = p.chromium.launch()
    # Chrome, всё есть (голоса подменены — есть украинский)
    c, pg, errs = page(b, UA_CHROME, FAKE_SR + VOICES(['uk-UA', 'ru-RU', 'en-US']))
    check('chrome: no window', not has(pg))
    pg.click('#settingsBtn'); pg.click('#sett .sg[data-g=about] .sgh')
    t = pg.inner_text('#abBrw'); check('about line chrome', 'розпізнавання мовлення ✔' in t and 'озвучення ✔' in t, t)
    check('no errors chrome', not errs, errs); c.close()
    # Chrome, список голосов пуст (ещё не загрузился) — окна нет
    c, pg, errs = page(b, UA_CHROME, FAKE_SR + VOICES([]))
    check('empty voices: no window', not has(pg)); c.close()
    # Firefox Android: нет распознавания
    c, pg, errs = page(b, UA_FF, NO_SR + VOICES(['uk-UA']))
    check('firefox: window', has(pg))
    it = items(pg); check('firefox: only sr item', len(it) == 1 and it[0].startswith('🎤') and 'не працює' in it[0], it)
    check('firefox: title', 'частина функцій' in pg.inner_text('#brw h2'))
    check('firefox: chrome button', pg.locator('#brwChrome').count() == 1 and 'package=com.android.chrome' in pg.get_attribute('#brwChrome', 'href'))
    check('firefox: note about backup', 'Зберегти копію даних' in pg.inner_text('#brw .brwn'))
    check('tour not offered under window', not pg.evaluate('tourQuiet()'))
    pg.click('#brwOk'); check('ok closes', not has(pg))
    check('seen stored', pg.evaluate("localStorage.getItem('mv.brw.seen')") == 'sr')
    check('tour quiet again', pg.evaluate('tourQuiet()'))
    pg.click('#settingsBtn'); pg.click('#sett .sg[data-g=about] .sgh')
    t = pg.inner_text('#abBrw'); check('about line firefox', 'розпізнавання мовлення ✖' in t and 'озвучення ✔' in t, t)
    pg.click('#closeSettBtn')
    pg.reload(); pg.wait_for_timeout(2200)
    check('firefox: not shown second time', not has(pg))
    check('no errors firefox', not errs, errs); c.close()
    # «Назад» закрывает (и тоже запоминает)
    c, pg, errs = page(b, UA_FF, NO_SR + VOICES(['uk-UA']))
    check('back: window', has(pg))
    pg.evaluate('history.back()'); pg.wait_for_timeout(400)
    check('system back closes', not has(pg))
    check('back: stays in app', pg.url.startswith(URL))
    check('back: seen', pg.evaluate("localStorage.getItem('mv.brw.seen')") == 'sr')
    c.close()
    # Samsung Internet: распознавание с ограничениями
    c, pg, errs = page(b, UA_SAM, FAKE_SR + VOICES(['uk-UA']))
    it = items(pg); check('samsung: limited item', len(it) == 1 and 'з обмеженнями' in it[0], it)
    check('samsung: chrome button', pg.locator('#brwChrome').count() == 1)
    pg.click('#brwOk'); pg.click('#settingsBtn'); pg.click('#sett .sg[data-g=about] .sgh')
    check('about line samsung', 'з обмеженнями' in pg.inner_text('#abBrw'))
    c.close()
    # нет голоса для языка — только пункт про голос, без кнопки Chrome
    c, pg, errs = page(b, UA_CHROME, FAKE_SR + VOICES(['en-US']))
    it = items(pg); check('no voice: item', len(it) == 1 and 'українська' in it[0] and 'Синтез' in it[0], it)
    check('no voice: no chrome button', pg.locator('#brwChrome').count() == 0)
    pg.click('#brwOk'); check('no voice: seen', pg.evaluate("localStorage.getItem('mv.brw.seen')") == 'voice-uk')
    # другой язык без голоса — другой набор, показать снова
    pg.evaluate("setLang('ru')"); pg.evaluate("brwDone=false;brwMaybe()"); pg.wait_for_timeout(300)
    it = items(pg); check('other set shown again', has(pg) and len(it) == 1 and ('русск' in it[0].lower() or 'російськ' in it[0]), it)
    c.close()
    # нет озвучки — пункт первым, загрузка без ошибок, приложение работает
    c, pg, errs = page(b, UA_FF, NO_SR + NO_TTS)
    check('no tts: loads', pg.locator('#main .tile').count() > 0)
    it = items(pg); check('no tts: tts first', len(it) == 2 and it[0].startswith('🔊') and 'говорити за вас' in it[0] and it[1].startswith('🎤'), it)
    pg.click('#brwOk')
    pg.click('#main .tile >> nth=0'); pg.wait_for_timeout(200)
    pg.evaluate("$('#typeBtn').click()"); pg.wait_for_timeout(200)
    pg.evaluate("tyText='Привіт ';tyRefresh()"); pg.click('#tySay'); pg.wait_for_timeout(200)
    pg.evaluate("ynOpen()"); pg.click('.ynb >> nth=0'); pg.evaluate("ynClose()")
    pg.evaluate("cardOpen()"); pg.wait_for_timeout(100)
    pg.click('#card .row button >> nth=0')
    pg.evaluate("cardClose&&cardClose();pbOpen()"); pg.click('#pbYes'); pg.wait_for_timeout(100)
    pg.click('#settingsBtn'); pg.click('#sett .sg[data-g=about] .sgh')
    t = pg.inner_text('#abBrw'); check('about no tts', 'озвучення ✖' in t, t)
    check('no tts: no errors', not errs, errs)
    c.close()
    # встроенный браузер Facebook — плашка вместо окна
    c, pg, errs = page(b, UA_FB, NO_SR + VOICES(['uk-UA']))
    check('facebook: banner', pg.locator('#iab').count() == 1)
    check('facebook: no window', not has(pg))
    c.close()
    # первый запуск: окно не перекрывает мастер, показывается после него
    c, pg, errs = page(b, UA_FF, NO_SR + VOICES(['uk-UA']), st={'theme': 'dark'})
    check('setup shown', pg.evaluate("!!$('#setup')&&getComputedStyle($('#setup')).display!=='none'"))
    check('no window over setup', not has(pg))
    pg.evaluate("settings.profile='words';settings.selMode='tap';setupDone()"); pg.wait_for_timeout(2000)
    check('window after setup', has(pg))
    check('no errors setup', not errs, errs)
    c.close()
    # обучение не перекрывает окно (обучение не видено)
    c, pg, errs = page(b, UA_FF, NO_SR + VOICES(['uk-UA']), tour=False)
    pg.wait_for_timeout(800)
    check('window shown', has(pg))
    check('no tour offer while window', pg.locator('#tourBox').count() == 0 or not pg.is_visible('#tourBox'))
    c.close()
    # справка: пункт после install во всех языках, длины совпадают; в справке 🎤 экрана
    c, pg, errs = page(b, UA_CHROME, FAKE_SR + VOICES(['uk-UA']))
    for l, t in [('uk', '🌐 Браузери'), ('ru', '🌐 Браузеры'), ('en', '🌐 Browsers')]:
        n = pg.evaluate(f"U.{l}.helpDoc.s.length"); k = pg.evaluate("HELP_KEYS.length")
        check(f'help length {l}', n == k, (n, k))
        i = pg.evaluate("HELP_KEYS.indexOf('browser')")
        check(f'help after install {l}', i == pg.evaluate("HELP_KEYS.indexOf('install')") + 1)
        check(f'help title {l}', pg.evaluate(f"U.{l}.helpDoc.s[{i}][0]").startswith(t))
    check('help ctx show', 'browser' in pg.evaluate("HELP_CTX.show"))
    c.close()
    # вёрстка окна: 360/313/277/240 × uk/ru/en, тёмная
    for (w, hg) in [(360, 640), (313, 556), (277, 492), (240, 427)]:
        for l in ['uk', 'ru', 'en']:
            c, pg, errs = page(b, UA_FF, NO_SR + NO_TTS, lang=l, w=w, hgt=hg)
            check(f'window {l} {w}', has(pg))
            check(f'title visible first {l} {w}', pg.evaluate("(()=>{const r=$('#brw h2').getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight})()"))
            ok = pg.evaluate("""(()=>{const bx=$('#brw .brwbox').getBoundingClientRect();
              const inside=[...document.querySelectorAll('#brw .brwbox *')].every(e=>{const r=e.getBoundingClientRect();return r.width===0||(r.left>=bx.left-1&&r.right<=bx.right+1)});
              return bx.left>=0&&bx.right<=innerWidth&&inside&&$('.brwbox').scrollWidth<=$('.brwbox').clientWidth+1})()""")
            check(f'fits {l} {w}', ok)
            pg.evaluate("$('#brwOk').scrollIntoView({block:'nearest'})")
            r = pg.evaluate("(()=>{const r=$('#brwOk').getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&r.height>=52})()")
            check(f'ok reachable {l} {w}', r)
            bg = pg.evaluate("getComputedStyle($('#brw .brwbox')).backgroundColor")
            lum = sum(int(x) for x in bg[bg.index('(') + 1:bg.index(')')].split(',')[:3]) / 765
            check(f'dark panel {l} {w}', lum < 0.3, bg)
            pg.click('#brwOk'); check(f'ok works {l} {w}', not has(pg))
            check(f'no errors {l} {w}', not errs, errs)
            c.close()
    b.close()
print(f'OK {OK}  FAIL {FAIL}')
sys.exit(1 if FAIL else 0)
