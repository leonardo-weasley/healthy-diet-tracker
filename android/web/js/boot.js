/* =========================================================================
 * boot.js —— 开屏画面（在 body 最前面同步执行，避免主界面先闪一下）
 *
 * 自定义图片存在 localStorage 的 hdt.splashImage，支持 jpg/png/webp/gif/svg。
 * 每次冷启动显示一次；同一 WebView 会话内跳转页面不再重复显示。
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
    /* localStorage 不可用时退回默认开屏 */
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
      /* 忽略 */
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
  // 兜底：即使计时器被系统挂起，5 秒后也一定进入主界面
  window.setTimeout(hide, 5000);
})();
