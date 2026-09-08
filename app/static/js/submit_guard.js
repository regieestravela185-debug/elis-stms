/* Stop a form being submitted twice.
 *
 * Testers double-clicked payment, reservation and approval buttons and got
 * two records. Nothing guarded against it: every POST here is a plain form
 * submit, and a browser will happily send the second click before the first
 * response arrives.
 *
 * The guard is on the FORM, not the button, so it also covers Enter in a
 * text field and a second click on a different submit control in the same
 * form. Anything that only reads — search, filters, pagination — is left
 * alone: those are safe to repeat and blocking them would feel broken.
 */
(function () {
  "use strict";

  var SAFE_METHODS = /^(get|dialog)$/i;

  function isReadOnly(form) {
    if (SAFE_METHODS.test(form.getAttribute("method") || "get")) return true;
    return form.hasAttribute("data-allow-resubmit");
  }

  function lock(form) {
    form.dataset.submitting = "1";
    var controls = form.querySelectorAll(
      'button[type="submit"], button:not([type]), input[type="submit"]'
    );
    controls.forEach(function (el) {
      el.classList.add("is-submitting");
      // A disabled submit button is not sent with the form, and some
      // handlers read its name/value — so mark it busy without disabling.
      el.setAttribute("aria-busy", "true");
      if (!el.dataset.originalLabel && el.tagName === "BUTTON") {
        el.dataset.originalLabel = el.innerHTML;
        el.innerHTML = "Please wait…";
      }
    });
  }

  function unlock(form) {
    delete form.dataset.submitting;
    form.querySelectorAll(".is-submitting").forEach(function (el) {
      el.classList.remove("is-submitting");
      el.removeAttribute("aria-busy");
      if (el.dataset.originalLabel) {
        el.innerHTML = el.dataset.originalLabel;
        delete el.dataset.originalLabel;
      }
    });
  }

  document.addEventListener(
    "submit",
    function (e) {
      var form = e.target;
      if (!form || form.tagName !== "FORM" || isReadOnly(form)) return;

      if (form.dataset.submitting === "1") {
        e.preventDefault();
        e.stopImmediatePropagation();
        return;
      }
      lock(form);

      // If the page is still here after a while the submit was cancelled
      // (a validation handler, a declined confirm, a failed fetch), so give
      // the button back rather than leaving it stuck for good.
      setTimeout(function () { unlock(form); }, 12000);
    },
    true
  );

  // Coming back via the bfcache shows the old DOM, buttons and all.
  window.addEventListener("pageshow", function (e) {
    if (!e.persisted) return;
    document.querySelectorAll('form[data-submitting="1"]').forEach(unlock);
  });
})();
