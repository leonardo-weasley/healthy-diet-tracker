/* 键盘感知：唤起输入法时给 <html> 加 .kb-open，
   底部胶囊导航与保存条随之向下滑出隐藏（见 app.css）。 */
(function () {
  var root = document.documentElement;
  var vv = window.visualViewport;
  var timer = null;

  function isTyping() {
    var el = document.activeElement;
    if (!el) return false;
    var t = el.tagName;
    return t === 'INPUT' || t === 'TEXTAREA' || t === 'SELECT' || el.isContentEditable === true;
  }

  function apply() {
    if (!vv) return;
    var layoutH = window.innerHeight || root.clientHeight || 0;
    var viewH = vv.height || 0;
    var open = isTyping() && viewH > 0 && layoutH > 0 && (layoutH - viewH) > 110;
    root.classList.toggle('kb-open', open);
  }

  function schedule() {
    if (timer) clearTimeout(timer);
    timer = setTimeout(apply, 60);
  }

  if (vv) {
    vv.addEventListener('resize', schedule);
    vv.addEventListener('scroll', schedule);
    window.addEventListener('resize', schedule);
    window.addEventListener('orientationchange', schedule);
  }
})();
