// Версия кэша. При каждом изменении файлов приложения увеличивайте число —
// тогда установленное приложение скачает новые файлы и обновится само.
const V = 'myvoice-v11';

// Папка приложения берётся из адреса самого sw.js (на GitHub Pages — /MyVoice/),
// поэтому копию можно разместить в любой папке любого сайта без правки путей.
const BASE = new URL('./', self.location).pathname,
      PAGE = BASE + 'index.html',
      // Имя кэша включает папку: копии в разных папках одного сайта не мешают друг другу
      CN = V + ':' + BASE,
      F = ['', 'index.html', 'manifest.json', 'icon-192.png', 'icon-512.png'].map(f => BASE + f);

// Удаляем только свои старые кэши (myvoice-vNN:/папка/).
// Кэши других приложений сайта («Говоримо разом» govorim-*, «Знову слова») не трогаем.
const isOld = k => k !== CN && k.startsWith('myvoice-') && k.endsWith(':' + BASE);
const isLex = p => p.startsWith(BASE + 'lex/');

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CN)
      // cache:'reload' — берём свежие файлы с сервера, а не из HTTP-кэша браузера
      .then(c => c.addAll(F.map(u => new Request(u, { cache: 'reload' }))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(k => Promise.all(k.filter(isOld).map(x => caches.delete(x))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  if (url.origin !== self.location.origin) return;
  // Запросы к другим приложениям сайта (/Govorim/, /SpeechRehab/ …) не перехватываем
  if (!url.pathname.startsWith(BASE)) return;
  // Списки слов из репозитория (lex/…): сначала сеть, при успехе кладём в кэш, офлайн берём из кэша
  if (isLex(url.pathname)) {
    e.respondWith(
      caches.open(CN).then(c =>
        fetch(e.request)
          .then(r => { if (r.ok) c.put(e.request, r.clone()); return r; })
          .catch(() => c.match(e.request).then(r => r || Response.error()))
      )
    );
    return;
  }
  // index.html?open=card (ярлык из меню значка) — тот же файл из кэша (ignoreSearch)
  e.respondWith(
    caches.open(CN).then(c =>
      c.match(e.request, { ignoreSearch: true })
        .then(r => r || fetch(e.request).catch(() => c.match(PAGE).then(p => p || Response.error())))
    )
  );
});
