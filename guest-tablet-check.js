// link-check.js — the guest-tablet flag checker (one shared file, 2026-10-31).
//
// The flag: at tablet setup, a tap on the setup page saves a small flag in
// this browser's storage for the claypnw.github.io site — localStorage key
// "hearthGuestTablet", value "1". Only pages on this site can read it.
//
// What this file does at page load: it reads the flag. If the flag stands,
// every link carrying data-login-link (a link that leans on a login, marked
// at build time) is replaced by its own words as plain text — no link, no
// login wall. If no flag stands, it changes nothing.
(function () {
  function run() {
    var marked = false;
    try {
      marked = window.localStorage.getItem('hearthGuestTablet') === '1';
    } catch (e) {
      marked = false;
    }
    if (!marked) { return; }
    var links = document.querySelectorAll('a[data-login-link]');
    for (var i = 0; i < links.length; i++) {
      var a = links[i];
      if (!a.parentNode) { continue; }
      var span = document.createElement('span');
      span.textContent = a.textContent;
      a.parentNode.replaceChild(span, a);
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }
})();
