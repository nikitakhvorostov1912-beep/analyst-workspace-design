// Навигация (scroll-spy) + переключатель темы
(function () {
  // ---- theme ----
  var root = document.documentElement;
  var KEY = 'analyst-audit-theme';
  function applyTheme(t) {
    if (t === 'light') root.setAttribute('data-theme', 'light');
    else root.removeAttribute('data-theme');
    var lbl = document.querySelector('.theme-btn .tlabel');
    if (lbl) lbl.textContent = t === 'light' ? 'Светлая' : 'Тёмная';
  }
  // Мгновенная смена темы: гасим переходы, чтобы var()-backed цвета не залипали.
  function switchTheme(t) {
    root.setAttribute('data-switching', '');
    applyTheme(t);
    void document.body.offsetWidth; // принудительный reflow на новых значениях
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { root.removeAttribute('data-switching'); });
    });
  }
  try { applyTheme(localStorage.getItem(KEY) || 'dark'); } catch (e) { applyTheme('dark'); }
  document.addEventListener('click', function (e) {
    var b = e.target.closest('.theme-btn');
    if (!b) return;
    var next = root.hasAttribute('data-theme') ? 'dark' : 'light';
    switchTheme(next);
    try { localStorage.setItem(KEY, next); } catch (err) {}
  });

  // ---- scroll-spy ----
  var links = Array.prototype.slice.call(document.querySelectorAll('.nav a[href^="#"]'));
  var map = {};
  links.forEach(function (a) {
    var id = a.getAttribute('href').slice(1);
    var sec = document.getElementById(id);
    if (sec) map[id] = a;
  });
  var ids = Object.keys(map);
  function spy() {
    var pos = window.scrollY + 120;
    var current = ids[0];
    ids.forEach(function (id) {
      var sec = document.getElementById(id);
      if (sec && sec.offsetTop <= pos) current = id;
    });
    links.forEach(function (a) { a.classList.remove('active'); });
    if (map[current]) map[current].classList.add('active');
  }
  window.addEventListener('scroll', spy, { passive: true });
  window.addEventListener('resize', spy);
  spy();
})();
