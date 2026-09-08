/* Keep letters out of number fields.
 *
 * <input type="number"> accepts "e", "E", "+" and "-" because they are
 * valid in scientific notation — so a peso field would take "1e40", which
 * the server has to reject. Testers reported typing "e" into a field
 * labelled "number only", which is a fair complaint: the field said one
 * thing and behaved another way.
 *
 * The server-side check stays: this is about not letting the character be
 * typed in the first place, not about trusting the browser.
 */
(function () {
  "use strict";

  var BLOCKED = ["e", "E", "+"];

  function isMoney(el) {
    // A field that may legitimately go negative keeps its minus sign.
    return el.type === "number" && el.min !== undefined && el.min !== "" ?
      parseFloat(el.min) >= 0 : el.type === "number";
  }

  document.addEventListener("keydown", function (e) {
    var el = e.target;
    if (!el || el.tagName !== "INPUT" || el.type !== "number") return;
    var blocked = BLOCKED.slice();
    if (isMoney(el)) blocked.push("-");
    if (blocked.indexOf(e.key) !== -1) e.preventDefault();
  });

  // Pasting sidesteps keydown entirely.
  document.addEventListener("paste", function (e) {
    var el = e.target;
    if (!el || el.tagName !== "INPUT" || el.type !== "number") return;
    var text = (e.clipboardData || window.clipboardData).getData("text");
    if (/[eE+]/.test(text) || (isMoney(el) && text.indexOf("-") !== -1)) {
      e.preventDefault();
    }
  });
})();
