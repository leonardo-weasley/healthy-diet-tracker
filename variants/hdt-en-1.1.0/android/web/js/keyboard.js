/* Keyboard awareness: add .kb-open to <html> when the on-screen keyboard opens,
   so the bottom capsule navigation and the "Save this meal" bar slide down out
   of view (see app.css). When the keyboard closes, .kb-open is removed and both
   bars slide back up from the bottom (CSS transitions).

   Detection note: the app uses Android windowSoftInputMode="adjustResize", where
   window.innerHeight shrinks together with visualViewport.height. Comparing the
   two (the old approach) always yields ~0, so the keyboard was never detected.
   Instead we remember the full-screen height seen while no keyboard is shown and
   compare the current visible height against that baseline. */
(function () {
  var root = document.documentElement;
  var vv = window.visualViewport;
  var timer = null;
  var baseline = 0;      // full visible height while the keyboard is closed
  var openState = false;
  var THRESHOLD = 120;   // px of viewport hidden by the keyboard

  function isTyping() {
    var el = document.activeElement;
    if (!el) return false;
    var t = el.tagName;
    return t === 'INPUT' || t === 'TEXTAREA' || t === 'SELECT' || el.isContentEditable === true;
  }

  /* The smaller of the two heights: whichever the platform shrinks when the
     keyboard appears (visual viewport, layout viewport, or both) is captured. */
  function currentHeight() {
    var vh = (vv && vv.height > 0) ? vv.height : Infinity;
    var ih = (window.innerHeight > 0) ? window.innerHeight : Infinity;
    var h = Math.min(vh, ih);
    return isFinite(h) ? h : 0;
  }

  function apply() {
    var h = currentHeight();
    if (h > baseline) baseline = h;   // keyboard closed, or rotated to a taller screen

    var drop = baseline > 0 ? (baseline - h) : 0;
    var open = isTyping() && drop > THRESHOLD;
    if (open !== openState) {
      openState = open;
      root.classList.toggle('kb-open', open);
    }
  }

  function schedule(delay) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(apply, delay || 60);
  }

  if (vv) {
    vv.addEventListener('resize', function () { schedule(60); });
    vv.addEventListener('scroll', function () { schedule(60); });
  }
  window.addEventListener('resize', function () { schedule(60); });
  window.addEventListener('orientationchange', function () {
    baseline = 0;            // re-measure after rotation
    schedule(250);
  });

  /* Focus events make the toggle responsive and cover platforms where the
     viewport resize fires late. Blur waits a moment so the keyboard can close. */
  document.addEventListener('focusin', function () { schedule(80); }, true);
  document.addEventListener('focusout', function () { schedule(220); }, true);

  apply(); // initial sample while no keyboard is shown
})();
