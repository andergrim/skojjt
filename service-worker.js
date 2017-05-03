// Intercept fetch events and check against application cache.
self.addEventListener('fetch', function(e) {
	if (e.request.url != 'http://localhost:8080/') {
		e.respondWith(
			caches.match(e.request).then(function(response) {
				return response || fetch(e.request);
			})
		);
	}
});

// Cache static assets and start page on service worker install.
self.addEventListener('install', function(e) {
	console.log('Service worker install triggered.');

	e.waitUntil(
		caches.open('skojjt').then(function(cache) {
			return cache.addAll([
				'/js/bootstrap.min.js',
				'/js/datatables.min.js',
				'/js/jquery-1.12.2.min.js',
				'/js/app.js',
				'/css/theme.min.css',
				'/css/datatables.min.css',
				'/css/app.css',
				'/fonts/glyphicons-halflings-regular.eot',
				'/fonts/glyphicons-halflings-regular.svg',
				'/fonts/glyphicons-halflings-regular.ttf',
				'/fonts/glyphicons-halflings-regular.woff',
				'/fonts/glyphicons-halflings-regular.woff2',
				'/img/favicon.ico',
				'/img/apple-touch-icon.png',
				'/img/favicon-192x192.png',
				'/img/favicon-144x144.png',
				'/img/favicon-96x96.png',
				'/img/favicon-48x48.png',
				'/img/favicon-32x32.png',
				'/img/favicon-16x16.png'
			]);
		})
	);
});