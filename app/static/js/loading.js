/* Smart loading indicator — shows only for operations that actually take a
   while, tied to the real lifecycle of the request (not a fixed timer).

   How it decides:
   - Every fetch() call anywhere in the app is tracked automatically (this
     file patches window.fetch once, at load time). Callers don't need to
     change anything.
   - If a request settles (success or error) before SHOW_DELAY_MS, nothing
     is ever shown — fast operations stay instant and silent.
   - If it's still going after SHOW_DELAY_MS, the top progress bar fades in.
     Once shown, it stays for at least MIN_VISIBLE_MS so it never flashes.
   - Multiple requests in flight share one counter, so concurrent calls
     never show duplicate/stacked indicators, and the bar only disappears
     once everything has actually finished.
   - Background/poll requests (weather widget, homepage unit-status poll,
     etc.) opt out with `{ silentLoader: true }` in the fetch init — they
     shouldn't nag the user every 30 seconds.
   - Socket.IO reconnect attempts also drive the same indicator, since a
     dropped real-time connection is exactly the kind of "system might look
     frozen" moment this is meant to cover.
*/
(function () {
  "use strict";

  var SHOW_DELAY_MS = 400;   // don't show anything for ops faster than this
  var MIN_VISIBLE_MS = 350;  // once visible, stay at least this long (no flicker)

  var activeCount = 0;
  var showTimer = null;
  var shownAt = null;
  var el = null;

  function ensureEl() {
    if (el) return el;
    el = document.createElement("div");
    el.className = "stms-loader";
    el.setAttribute("aria-hidden", "true");
    el.innerHTML = '<div class="stms-loader__bar"></div>';
    (document.body || document.documentElement).appendChild(el);
    return el;
  }

  function reveal() {
    ensureEl();
    el.classList.add("is-visible");
    shownAt = Date.now();
  }

  function conceal() {
    if (!el || !el.classList.contains("is-visible")) return;
    var elapsed = shownAt ? Date.now() - shownAt : MIN_VISIBLE_MS;
    var wait = Math.max(0, MIN_VISIBLE_MS - elapsed);
    setTimeout(function () {
      if (activeCount <= 0) el.classList.remove("is-visible");
    }, wait);
  }

  function begin() {
    activeCount++;
    if (activeCount === 1) {
      clearTimeout(showTimer);
      showTimer = setTimeout(function () {
        if (activeCount > 0) reveal();
      }, SHOW_DELAY_MS);
    }
  }

  function end() {
    activeCount = Math.max(0, activeCount - 1);
    if (activeCount === 0) {
      clearTimeout(showTimer);
      conceal();
    }
  }

  // Patch fetch once, as early as possible (this script is loaded
  // non-deferred, before other scripts, specifically so it wins the race).
  var nativeFetch = window.fetch;
  if (nativeFetch && !window.__stmsFetchPatched) {
    window.__stmsFetchPatched = true;
    window.fetch = function (input, init) {
      var silent = !!(init && init.silentLoader);
      if (!silent) begin();
      var settle = function () { if (!silent) end(); };
      return nativeFetch.call(this, input, init).then(
        function (res) { settle(); return res; },
        function (err) { settle(); throw err; }
      );
    };
  }

  // Socket.IO: a slow (re)connect is exactly the "looks frozen" case this
  // is meant to cover. window.socket is only created on dashboard pages,
  // and only after this script runs, so poll briefly for it.
  function wireSocket() {
    var s = window.socket;
    if (!s) return false; // not created yet — caller should keep polling
    if (s.__stmsLoaderWired) return true;
    s.__stmsLoaderWired = true;
    s.on("reconnect_attempt", begin);
    s.on("connect", end);
    s.on("reconnect", end);
    s.on("connect_error", end);
    s.on("disconnect", function (reason) {
      // Deliberate disconnects (logout, server told us to go) don't need a
      // loader — only unexpected drops the client will try to recover from.
      if (reason === "io server disconnect" || reason === "io client disconnect") return;
      begin();
    });
    return true;
  }
  if (!wireSocket()) {
    var tries = 0;
    var poll = setInterval(function () {
      tries++;
      if (wireSocket() || tries > 20) clearInterval(poll); // ~5s max
    }, 250);
  }

  // Full page navigations: browsers already show their own progress (tab
  // spinner / URL bar), but beforeunload only ever fires on a genuine
  // navigation — never a false start — so it's safe to bridge the gap with
  // the same bar for visual consistency while the next page loads.
  // A download link fires beforeunload but never navigates — the browser
  // saves the file and stays put — so the bar started and nothing ever
  // stopped it. That is the export spinner that hung at the top of the
  // page. Downloads opt out; real navigations still get the bar.
  var skipNextUnloadBar = false;
  window.addEventListener("beforeunload", function () {
    if (skipNextUnloadBar) { skipNextUnloadBar = false; return; }
    begin();
  });

  function isDownloadLink(a) {
    if (!a) return false;
    if (a.hasAttribute("download") || a.hasAttribute("data-download")) return true;
    return /\/export(\/|$|\?)|\.csv(\?|$)/i.test(a.getAttribute("href") || "");
  }

  document.addEventListener("click", function (e) {
    var a = e.target && e.target.closest && e.target.closest("a[href]");
    if (!isDownloadLink(a)) return;

    // Asked for by the testers: say what is about to be saved rather than
    // having a file appear unannounced.
    var what = a.getAttribute("data-download-label") || "this file";
    if (!window.confirm("Download " + what + "?")) {
      e.preventDefault();
      return;
    }
    skipNextUnloadBar = true;
    // Safety net: if the browser did navigate after all, let the bar work
    // again shortly rather than staying suppressed for the session.
    setTimeout(function () { skipNextUnloadBar = false; }, 4000);
  }, true);

  window.STMSLoader = { begin: begin, end: end };
})();
