self.addEventListener('push', function (event) {
  if (!event.data) return;
  var data = {};
  try { data = event.data.json(); } catch (_) { data = { title: event.data.text() }; }
  var title = data.title || 'Armu';
  var options = {
    body:  data.body  || '',
    icon:  '/static/icon-192.png',
    badge: '/static/icon-192.png',
    data:  { url: data.url || '/' },
    tag:   'armu',
    renotify: true,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  var url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
      for (var i = 0; i < list.length; i++) {
        if (list[i].url.startsWith(self.location.origin) && 'focus' in list[i]) {
          list[i].navigate(url);
          return list[i].focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
