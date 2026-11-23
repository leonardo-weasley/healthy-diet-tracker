/* =========================================================================
 * boot.js —— Splash screen (runs synchronously at the top of body to avoid a flash of the main UI)
 *
 * A custom image is stored in localStorage as hdt.splashImage; jpg/png/webp/gif/svg are supported.
 * Shown once per cold start; navigating within the same WebView session does not show it again.
 * ========================================================================= */
(function () {
  "use strict";

  var SPLASH_KEY = "hdt.splashImage";
  var SHOWN_KEY = "hdt.splashShown";
  var splash = document.getElementById("hdt-splash");
  if (!splash) return;

  var root = document.documentElement;
  var alreadyShown = false;
  try {
    alreadyShown = sessionStorage.getItem(SHOWN_KEY) === "1";
  } catch (err) {
    alreadyShown = false;
  }

  if (alreadyShown) {
    splash.parentNode.removeChild(splash);
    return;
  }

  root.classList.add("hdt-splash-lock");

  try {
    var image = localStorage.getItem(SPLASH_KEY);
    if (image) {
      var media = document.getElementById("hdt-splash-media");
      if (media) {
        media.style.backgroundImage = 'url("' + image.replace(/"/g, "%22") + '")';
        splash.classList.add("has-image");
      }
    }
  } catch (err) {
    /* Fall back to the default splash when localStorage is unavailable */
  }

  var skip = document.getElementById("hdt-splash-skip");
  var count = document.getElementById("hdt-splash-count");
  var remaining = 3;
  var timer = null;
  var hidden = false;

  function hide() {
    if (hidden) return;
    hidden = true;
    if (timer) window.clearInterval(timer);
    try {
      sessionStorage.setItem(SHOWN_KEY, "1");
    } catch (err) {
      /* Ignore */
    }
    splash.classList.add("is-hiding");
    root.classList.remove("hdt-splash-lock");
    window.setTimeout(function () {
      if (splash.parentNode) splash.parentNode.removeChild(splash);
    }, 340);
  }

  function tick() {
    remaining -= 1;
    if (remaining <= 0) {
      hide();
      return;
    }
    if (count) count.textContent = String(remaining);
  }

  timer = window.setInterval(tick, 1000);
  if (skip) skip.addEventListener("click", hide);
  // Fallback: enter the main UI after 5 seconds even if the timer is suspended
  window.setTimeout(hide, 5000);
})();
