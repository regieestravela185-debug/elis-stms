(function () {
  const $ = (sel, root = document) => root.querySelector(sel);

  function openModal(id) {
    const el = $(id);
    if (!el) return;
    el.hidden = false;
    document.body.style.overflow = "hidden";
    const first = el.querySelector("input, button, select, textarea");
    requestAnimationFrame(() => first && first.focus());
  }

  // Which modal to reopen once Terms or Privacy is dismissed.
  let returnToModal = null;

  function closeModals() {
    ["#modalLogin", "#modalRegister", "#modalVerifyOtp", "#modalReserve", "#modalUnitDetails", "#modalUnitInquiry", "#modalBuildingUnits", "#modalForgotPassword", "#modalResetPassword", "#modalTerms", "#modalPrivacy"].forEach((id) => {
      const el = $(id);
      if (el) el.hidden = true;
    });
    document.body.style.overflow = "";
  }

  function closeModalsAndReturn() {
    const back = returnToModal;
    returnToModal = null;
    closeModals();
    if (back) { openModal(back); applyFormFeedback(back); }
  }

  document.addEventListener("click", (e) => {
    const t = e.target;
    if (t.closest(".js-open-login")) {
      e.preventDefault();
      closeModals();
      openModal("#modalLogin");
      applyFormFeedback("#modalLogin");
    }
    if (t.closest(".js-open-register")) {
      e.preventDefault();
      closeModals();
      openModal("#modalRegister");
      applyFormFeedback("#modalRegister");
    }
    if (t.classList && t.classList.contains("js-modal-close")) {
      closeModalsAndReturn();
    }
    if (t.classList && t.classList.contains("js-switch-register")) {
      closeModals();
      openModal("#modalRegister");
      applyFormFeedback("#modalRegister");
    }
    if (t.classList && t.classList.contains("js-switch-login")) {
      closeModals();
      openModal("#modalLogin");
      applyFormFeedback("#modalLogin");
    }
    if (t.closest(".js-open-reserve")) {
      e.preventDefault();
      const btn = t.closest(".js-open-reserve");
      const card = btn ? btn.closest(".unit-card") : null;
      const reserveForm = document.getElementById("reserveForm");
      const reserveUnitId = document.getElementById("reserveUnitId");
      const reserveUnitCode = document.getElementById("reserveUnitCode");
      const reserveUnitFloor = document.getElementById("reserveUnitFloor");
      const reserveUnitPrice = document.getElementById("reserveUnitPrice");
      const reserveMonthlyPrice = document.getElementById("reserveMonthlyPrice");
      const reserveDepositAmount = document.getElementById("reserveDepositAmount");
      const reserveDepositTerms = document.getElementById("reserveDepositTerms");
      const reserveTotalPayment = document.getElementById("reserveTotalPayment");
      if (!btn || !card || !reserveForm || !reserveUnitCode) return;
      const unitId = btn.getAttribute("data-unit-id");
      const unitCode = btn.getAttribute("data-unit-code") || "";
      const unitFloor = card.getAttribute("data-unit-floor") || "";
      const unitPrice = card.getAttribute("data-unit-price") || "";
      const unitType = card.getAttribute("data-unit-type") || "";
      if (!unitId) return;
      reserveForm.setAttribute("action", `/user/reserve/${unitId}`);
      reserveForm.setAttribute("data-unit-type", unitType);
      // Reset move-in/move-out so a previous unit's dates don't carry over
      const reserveMoveInDateReset = document.getElementById("reserveMoveInDate");
      const reserveMoveOutDateReset = document.getElementById("reserveMoveOutDate");
      const reserveMoveOutHintReset = document.getElementById("reserveMoveOutHint");
      const reserveMoveOutGroup = document.getElementById("reserveMoveOutGroup");
      const reserveResidentialNote = document.getElementById("reserveResidentialNote");
      const isCommercialUnit = unitType.toLowerCase().includes("commercial");
      if (reserveMoveInDateReset) reserveMoveInDateReset.value = "";
      if (reserveMoveOutDateReset) reserveMoveOutDateReset.value = "";
      // Residential units are month-to-month — no move-out date to collect.
      if (reserveMoveOutGroup) reserveMoveOutGroup.style.display = isCommercialUnit ? "" : "none";
      if (reserveResidentialNote) reserveResidentialNote.style.display = isCommercialUnit ? "none" : "";
      if (reserveMoveOutDateReset) reserveMoveOutDateReset.required = isCommercialUnit;
      if (reserveMoveOutHintReset) {
        reserveMoveOutHintReset.textContent = "Commercial units require a minimum 1-year contract. Pick a move-in date and we'll set this automatically.";
      }
      if (reserveUnitId) reserveUnitId.value = unitId;
      reserveUnitCode.value = unitCode;
      if (reserveUnitFloor) reserveUnitFloor.value = unitFloor ? `${unitFloor}st Floor` : "";
      if (reserveUnitPrice) reserveUnitPrice.value = `₱${unitPrice} / month`;
      if (reserveMonthlyPrice) reserveMonthlyPrice.value = `₱${unitPrice}`;
      // Deposit = one month's rent + ₱1,000 (residential or commercial, same formula)
      const priceNum = parseFloat(String(unitPrice).replace(/,/g, '')) || 0;
      const depositNum = priceNum + 1000;
      const fmt = (n) => `₱${n.toLocaleString('en-PH', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
      if (reserveDepositAmount) reserveDepositAmount.value = fmt(depositNum);
      if (reserveDepositTerms) reserveDepositTerms.innerHTML = `<strong>Deposit Terms:</strong> Your security deposit is one month's rent (₱${priceNum.toLocaleString('en-PH')}) plus ₱1,000, for a total of ${fmt(depositNum)}. Refundable after your contract ends, minus damages and unpaid bills.`;
      if (reserveTotalPayment) {
        const total = priceNum + depositNum;
        reserveTotalPayment.value = fmt(total);
      }
      closeModals();
      openModal("#modalReserve");
    }
    if (t.closest(".js-open-unit-details")) {
      e.preventDefault();
      const btn = t.closest(".js-open-unit-details");
      const card = btn ? btn.closest(".unit-card") : null;
      if (!card) return;
      const title = document.getElementById("unitDetailsTitle");
      const meta = document.getElementById("unitDetailsMeta");
      const inclusion = document.getElementById("unitDetailsInclusion");
      const contract = document.getElementById("unitDetailsContract");
      const desc = document.getElementById("unitDetailsDescription");
      const depositLine = document.getElementById("unitDetailsDeposit");
      const totalLine = document.getElementById("unitDetailsTotal");
      const main = document.getElementById("unitImageMain");
      const thumb1 = document.getElementById("unitImageThumb1");
      const thumb2 = document.getElementById("unitImageThumb2");
      const thumb3 = document.getElementById("unitImageThumb3");
      const thumb4 = document.getElementById("unitImageThumb4");

      const img1 = card.getAttribute("data-unit-image-1") || "";
      const img2 = card.getAttribute("data-unit-image-2") || img1;
      const img3 = card.getAttribute("data-unit-image-3") || img1;
      const img4 = card.getAttribute("data-unit-image-4") || img1;
      const images = [img1, img2, img3, img4];
      if (title) title.textContent = `${card.getAttribute("data-unit-code") || "Unit"} details`;
      if (meta) {
        meta.textContent = `${card.getAttribute("data-unit-type") || "Unit"} • ₱${card.getAttribute("data-unit-price") || "0"} / month • ${card.getAttribute("data-unit-status") || ""}`;
      }
      if (inclusion) inclusion.textContent = card.getAttribute("data-unit-inclusion") || "N/A";
      if (contract) contract.textContent = card.getAttribute("data-unit-contract") || "N/A";
      if (desc) desc.textContent = card.getAttribute("data-unit-description") || "Admin can add more details for this unit.";

      // Deposit = one month's rent + ₱1,000 (residential or commercial, same formula)
      const detailsPriceNum = parseFloat((card.getAttribute("data-unit-price") || "0").replace(/,/g, '')) || 0;
      const detailsDepositNum = detailsPriceNum + 1000;
      const fmtDetails = (n) => `₱${n.toLocaleString('en-PH', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
      if (depositLine) depositLine.innerHTML = `<strong>${fmtDetails(detailsDepositNum)}</strong> — one month's rent + ₱1,000, refundable after contract ends minus damages and unpaid bills.`;
      if (totalLine) totalLine.textContent = `Total payment on reservation: ${fmtDetails(detailsPriceNum)} (Monthly) + ${fmtDetails(detailsDepositNum)} (Deposit) = ${fmtDetails(detailsPriceNum + detailsDepositNum)}`;

      // Set up carousel
      let currentIndex = 0;
      const updateCarousel = (index) => {
        if (main) {
          main.classList.add("fade-out");
          setTimeout(() => {
            main.setAttribute("src", images[index]);
            main.classList.remove("fade-out");
          }, 200);
        }

        // Update thumbnails
        document.querySelectorAll(".unit-thumbnail").forEach((thumb, i) => {
          thumb.classList.toggle("active", i === index);
        });

        // Update dots
        document.querySelectorAll(".carousel-dot").forEach((dot, i) => {
          dot.classList.toggle("active", i === index);
        });

        currentIndex = index;
      };

      // Initialize carousel
      if (main) main.setAttribute("src", images[0]);
      if (thumb1) thumb1.setAttribute("src", images[0]);
      if (thumb2) thumb2.setAttribute("src", images[1]);
      if (thumb3) thumb3.setAttribute("src", images[2]);
      if (thumb4) thumb4.setAttribute("src", images[3]);

      // Create dots
      const dotsContainer = document.getElementById("carouselDots");
      if (dotsContainer) {
        dotsContainer.innerHTML = "";
        images.forEach((_, i) => {
          const dot = document.createElement("button");
          dot.className = `carousel-dot ${i === 0 ? "active" : ""}`;
          dot.addEventListener("click", () => updateCarousel(i));
          dotsContainer.appendChild(dot);
        });
      }

      // Navigation arrows
      const prevBtn = document.getElementById("carouselPrev");
      const nextBtn = document.getElementById("carouselNext");
      if (prevBtn) {
        prevBtn.onclick = () => {
          const newIndex = (currentIndex - 1 + images.length) % images.length;
          updateCarousel(newIndex);
        };
      }
      if (nextBtn) {
        nextBtn.onclick = () => {
          const newIndex = (currentIndex + 1) % images.length;
          updateCarousel(newIndex);
        };
      }

      // Thumbnail clicks
      document.querySelectorAll(".unit-thumbnail").forEach((thumb, i) => {
        thumb.onclick = () => updateCarousel(i);
      });

      // Keyboard navigation
      const handleKeyDown = (e) => {
        if (e.key === "ArrowLeft") {
          const newIndex = (currentIndex - 1 + images.length) % images.length;
          updateCarousel(newIndex);
        } else if (e.key === "ArrowRight") {
          const newIndex = (currentIndex + 1) % images.length;
          updateCarousel(newIndex);
        }
      };

      // Auto-play carousel
      let autoPlayInterval;
      const startAutoPlay = () => {
        autoPlayInterval = setInterval(() => {
          const newIndex = (currentIndex + 1) % images.length;
          updateCarousel(newIndex);
        }, 4000);
      };

      const stopAutoPlay = () => {
        clearInterval(autoPlayInterval);
      };

      // Add event listeners for auto-play control
      const carousel = document.querySelector(".unit-carousel");
      if (carousel) {
        carousel.addEventListener("mouseenter", stopAutoPlay);
        carousel.addEventListener("mouseleave", startAutoPlay);
        carousel.addEventListener("keydown", handleKeyDown);
      }

      // Clean up previous event listeners when modal closes
      const modal = document.getElementById("modalUnitDetails");
      if (modal) {
        const closeHandler = () => {
          stopAutoPlay();
          modal.removeEventListener("hidden", closeHandler);
        };
        modal.addEventListener("hidden", closeHandler);
      }

      closeModals();
      openModal("#modalUnitDetails");
      startAutoPlay();
    }
    if (t.closest(".js-open-forgot-password")) {
      e.preventDefault();
      closeModals();
      openModal("#modalForgotPassword");
      applyFormFeedback("#modalForgotPassword");
    }
    // Terms and Privacy are read FROM another modal (usually Register), so
    // closing them has to put that one back. Closing everything left the
    // user staring at the page with their half-filled form gone.
    if (t.closest(".js-open-terms") || t.closest(".js-open-privacy")) {
      e.preventDefault();
      const openNow = ["#modalRegister", "#modalLogin", "#modalReserve"]
        .find((id) => { const el = $(id); return el && !el.hidden; });
      returnToModal = openNow || null;
      closeModals();
      openModal(t.closest(".js-open-terms") ? "#modalTerms" : "#modalPrivacy");
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModalsAndReturn();
  });

  // ?auth=login|register|verify|forgot_password|reset_password|terms|privacy from auth redirects
  const params = new URLSearchParams(window.location.search);
  const auth = params.get("auth");
  if (auth === "login") openModal("#modalLogin");
  if (auth === "register") openModal("#modalRegister");
  if (auth === "verify") openModal("#modalVerifyOtp");
  if (auth === "forgot_password") openModal("#modalForgotPassword");
  if (auth === "reset_password") openModal("#modalResetPassword");
  if (auth === "terms") openModal("#modalTerms");
  if (auth === "privacy") openModal("#modalPrivacy");

  function applyFormFeedback(modalId) {
    const modal = document.querySelector(modalId);
    if (!modal) return;

    // The message renders above the fields, which on a short screen can sit
    // out of view when the modal opens — testers reported not seeing why a
    // login had failed. Bring it into view and mark it for a moment.
    const note = modal.querySelector(".alert");
    if (note) {
      requestAnimationFrame(() => {
        note.scrollIntoView({ behavior: "smooth", block: "nearest" });
        note.classList.add("alert--attention");
        setTimeout(() => note.classList.remove("alert--attention"), 1600);
      });
    }

    const hasDanger = !!document.querySelector(".flash-stack .flash--danger");
    const hasSuccess = !!document.querySelector(".flash-stack .flash--success");
    const inputs = modal.querySelectorAll(".input");
    inputs.forEach((inp) => {
      inp.classList.remove("is-invalid", "is-valid");
      if (hasDanger) inp.classList.add("is-invalid");
      if (hasSuccess) inp.classList.add("is-valid");
    });
  }

  if (auth === "login") applyFormFeedback("#modalLogin");
  if (auth === "register") applyFormFeedback("#modalRegister");
  if (auth === "verify") applyFormFeedback("#modalVerifyOtp");

  // Auto-dismiss flash messages in modals after 8s — long enough to read
  // (e.g. a "wrong password" notice after a full page reload) but not so
  // long the user has to dismiss it themselves. 8s (not 5s) gives some
  // margin for slower connections/cold starts where the page is still
  // settling (video/assets loading) when the modal first appears.
  function autoDismissModalFlashes() {
    const modalFlashContainers = document.querySelectorAll('.modal .alert');
    modalFlashContainers.forEach((alert) => {
      setTimeout(() => {
        alert.style.transition = 'opacity 0.3s ease-out';
        alert.style.opacity = '0';
        setTimeout(() => {
          alert.remove();
        }, 300);
      }, 8000);
    });
  }

  // Run auto-dismiss when modals open
  if (auth === "login" || auth === "register" || auth === "verify") {
    autoDismissModalFlashes();
  }

  // Live Caps Lock warning on the login password field — the #1 reason a
  // "correct" password still gets rejected, and until now nothing told the
  // user why.
  const loginPasswordInput = document.getElementById("login_password");
  const capsLockWarning = document.getElementById("login_capslock_warning");
  if (loginPasswordInput && capsLockWarning) {
    const checkCapsLock = (e) => {
      const isOn = typeof e.getModifierState === "function" && e.getModifierState("CapsLock");
      capsLockWarning.style.display = isOn ? "flex" : "none";
    };
    loginPasswordInput.addEventListener("keydown", checkCapsLock);
    loginPasswordInput.addEventListener("keyup", checkCapsLock);
    loginPasswordInput.addEventListener("blur", () => { capsLockWarning.style.display = "none"; });
  }

  document.querySelectorAll(".js-unit-card").forEach((el) => {
    el.style.cursor = "pointer";
    const open = () => {
      closeModals();
      openModal("#modalLogin");
    };
    el.addEventListener("click", (e) => {
      // Details/Inquire (and any other button/link) inside the card have
      // their own click handlers and don't require login — only the card
      // background itself should prompt login.
      if (e.target.closest("button, a")) return;
      open();
    });
    el.addEventListener("keydown", (e) => {
      if ((e.key === "Enter" || e.key === " ") && e.target === el) {
        e.preventDefault();
        open();
      }
    });
  });

  // Smooth scroll for in-page nav
  document.querySelectorAll('a.nav__link--scroll[href^="#"]').forEach((a) => {
    a.addEventListener("click", (e) => {
      const id = a.getAttribute("href");
      if (!id || id === "#") return;
      const target = document.querySelector(id);
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  // Sticky nav + scroll shadow
  const nav = $("#siteNav");
  function onScroll() {
    if (!nav) return;
    nav.classList.toggle("nav--scrolled", window.scrollY > 8);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // Reveal on scroll
  const reveals = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && reveals.length) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((en) => {
          if (en.isIntersecting) {
            en.target.classList.add("is-visible");
            io.unobserve(en.target);
          }
        });
      },
      { root: null, threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );
    reveals.forEach((el) => io.observe(el));
  } else {
    reveals.forEach((el) => el.classList.add("is-visible"));
  }

  // Chat FAB
  const fab = $("#chatFab");
  const panel = $("#chatPanel");
  const closeBtn = $("#chatClose");

  // The goodbye plays for 1.5s before the panel hides. Tapping the button
  // again during that window used to run the whole close a second time —
  // another goodbye, another timer — and a timer from the previous close
  // would then shut the panel the user had just reopened. Easy to hit on a
  // phone, where the button is small and double taps are common.
  let chatCloseTimer = null;

  function openChat() {
    if (!panel) return;
    if (chatCloseTimer) { clearTimeout(chatCloseTimer); chatCloseTimer = null; }
    panel.hidden = false;
    const inp = $("#chatInput");
    inp && inp.focus();
  }

  function closeChat() {
    if (!panel || chatCloseTimer) return;   // already saying goodbye
    if (typeof removeFollowUp === "function") removeFollowUp();
    appendChatBubble("Bot", "Salamat sa pag-chat! Kung may tanong ka pa, bumalik ka lang. Have a great day! 😊");
    const log = document.getElementById("chatLog");
    if (log) log.scrollTop = log.scrollHeight;
    chatCloseTimer = setTimeout(() => {
      chatCloseTimer = null;
      panel.hidden = true;
      resetChat();
    }, 1500);
  }

  window.resetChat = resetChat;
  function resetChat() {
    const log = $("#chatLog");
    if (!log) return;
    log.innerHTML = `
      <div class="chat-welcome">
        <div class="chat-welcome__avatar">
          <svg viewBox="0 0 40 40" fill="none"><ellipse cx="20" cy="35.4" rx="10.5" ry="2.2" fill="#000" opacity="0.12"/><path d="M11 8.2c-1-3 1-4 3.1-2.9l1.4 3.9z" fill="#6b4e34"/><path d="M29 8.2c1-3 -1-4 -3.1-2.9l-1.4 3.9z" fill="#6b4e34"/><ellipse cx="20" cy="21.5" rx="13" ry="14" fill="#7a5a3c"/><ellipse cx="15.5" cy="16" rx="7.6" ry="8" fill="#916b46" opacity="0.85"/><path d="M31.5 20a13 14 0 0 1-12.5 15.3A13 14 0 0 0 31.5 20z" fill="#5e4227" opacity="0.55"/><ellipse cx="20" cy="25" rx="7.8" ry="8.2" fill="#efe2c8"/><ellipse cx="18.4" cy="23" rx="4.4" ry="4.8" fill="#f8f0dd" opacity="0.8"/><circle cx="14.8" cy="18.5" r="5.4" fill="#fbf6ea"/><circle cx="25.2" cy="18.5" r="5.4" fill="#fbf6ea"/><circle cx="14.8" cy="19.5" r="5.4" fill="#e6d6b6" opacity="0.32"/><circle cx="25.2" cy="19.5" r="5.4" fill="#e6d6b6" opacity="0.32"/><g class="owl-awake"><circle cx="14.8" cy="18.6" r="2.6" fill="#2b2b30"/><circle cx="25.2" cy="18.6" r="2.6" fill="#2b2b30"/><circle cx="15.8" cy="17.7" r="0.9" fill="#fff"/><circle cx="26.2" cy="17.7" r="0.9" fill="#fff"/></g><g class="owl-asleep"><path d="M12.2 18.8q2.6 2 5.2 0" fill="none" stroke="#5b4326" stroke-width="1.4" stroke-linecap="round"/><path d="M22.6 18.8q2.6 2 5.2 0" fill="none" stroke="#5b4326" stroke-width="1.4" stroke-linecap="round"/><path d="M30 6h3.4l-3.4 3.4h3.4" fill="none" stroke="#7a5a3c" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></g><path d="M20 21l-2.2 2.7h4.4z" fill="#e8a33d"/><path d="M20 21l2.2 2.7h-2.2z" fill="#cf8a26"/><path d="M16.5 35l-1.3 2M18.4 35.4v2M23.5 35l1.3 2M21.6 35.4v2" fill="none" stroke="#e8a33d" stroke-width="1.2" stroke-linecap="round"/></svg>
        </div>
        <div class="chat-welcome__bubble">
          <p><strong>Kumusta! Ako si Ellie 🦉</strong> — ang virtual assistant ng The Elis Center. Matutulungan kita sa pricing, location, viewing, requirements, office hours, reservation, maintenance, at iba pa.</p>
        </div>
      </div>
      <div class="chat-suggestions" id="chatSuggestions">
        <button class="chat-suggestion" data-text="How much is the rent?">How much is rent?</button>
        <button class="chat-suggestion" data-text="What are the requirements?">Requirements</button>
        <button class="chat-suggestion" data-text="Office hours and contact?">Office hours</button>
        <button class="chat-suggestion" data-text="How to reserve a unit?">How to reserve?</button>
        <button class="chat-suggestion" data-text="What is included in the unit?">What's included?</button>
        <button class="chat-suggestion" data-text="Maintenance and repairs">Maintenance</button>
      </div>
    `;
    // Re-bind suggestion buttons
    log.querySelectorAll(".chat-suggestion").forEach((btn) => {
      btn.addEventListener("click", () => {
        const text = btn.getAttribute("data-text");
        if (text) sendQuickMessage(text);
      });
    });
  }

  if (fab && panel) {
    fab.addEventListener("click", () => {
      if (panel.hidden) openChat();
      else closeChat();
    });
    closeBtn && closeBtn.addEventListener("click", closeChat);
  }

  // Homepage units realtime status (database-connected polling) — so a unit
  // flips from "Available" to "Reserved" for anyone already browsing the
  // page the moment someone else submits a reservation for it, not just on
  // their next page load.
  const unitCards = Array.from(document.querySelectorAll(".unit-card[data-unit-id]"));
  const canReserve = !!document.getElementById("reserveForm");
  const STATUS_LABEL = { available: "Available", reserved: "Reserved — Pending Approval", occupied: "Currently Occupied", unpaid: "Currently Occupied" };
  const STATUS_TEXT_CLASS = { available: "status-text--available", reserved: "status-text--reserved" };
  let pollDelay = 30000; // start at 30s; backs off on errors/429
  async function pollHomeUnits() {
    if (!unitCards.length) return;
    try {
      const res = await fetch("/api/units", { silentLoader: true });
      if (!res.ok) { pollDelay = Math.min(pollDelay * 2, 300000); return; }
      pollDelay = 30000; // reset on success
      const data = await res.json();
      const map = new Map((data.units || []).map((u) => [String(u.id), u]));
      unitCards.forEach((card) => {
        const id = card.getAttribute("data-unit-id");
        const unit = id ? map.get(id) : null;
        if (!unit || card.getAttribute("data-unit-status") === unit.status) return;
        card.setAttribute("data-unit-status", unit.status);

        const badge = card.querySelector(".unit-card__status-badge");
        if (badge) {
          badge.className = `unit-card__status-badge badge badge--${unit.status}`;
          badge.textContent = unit.status;
        }

        const statusTextWrap = card.querySelector(".unit-card__status-text");
        if (statusTextWrap) {
          statusTextWrap.setAttribute("data-status", unit.status);
          const cls = STATUS_TEXT_CLASS[unit.status] || "status-text--occupied";
          const label = STATUS_LABEL[unit.status] || "Currently Occupied";
          statusTextWrap.innerHTML = `<span class="status-text ${cls}">${label}</span>`;
        }

        if (!canReserve) return;
        const actions = card.querySelector(".unit-card__actions");
        if (!actions) return;
        const existingButton = actions.querySelector(".js-open-reserve");
        const existingHint = actions.querySelector(".unit-card__hint");
        if (unit.status === "available") {
          if (existingHint) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "btn btn--sm btn--primary js-open-reserve";
            btn.setAttribute("data-unit-id", String(unit.id));
            btn.setAttribute("data-unit-code", unit.unit_code || "");
            btn.textContent = "Reserve";
            existingHint.replaceWith(btn);
          }
        } else if (existingButton) {
          const span = document.createElement("span");
          span.className = "unit-card__hint";
          span.textContent = unit.status;
          existingButton.replaceWith(span);
        } else if (existingHint) {
          existingHint.textContent = unit.status;
        }
      });
    } catch (_) { pollDelay = Math.min(pollDelay * 2, 300000); }
  }
  (function scheduleHomePoll() {
    setTimeout(async function () { await pollHomeUnits(); scheduleHomePoll(); }, pollDelay);
  })();
  pollHomeUnits();

  // Horizontal unit scroller
  const unitsScroll = document.getElementById("unitsScroll");
  const leftBtn = document.getElementById("unitsScrollLeft");
  const rightBtn = document.getElementById("unitsScrollRight");
  if (unitsScroll && leftBtn && rightBtn) {
    const shift = () => Math.max(280, Math.floor(unitsScroll.clientWidth * 0.8));
    leftBtn.addEventListener("click", () => unitsScroll.scrollBy({ left: -shift(), behavior: "smooth" }));
    rightBtn.addEventListener("click", () => unitsScroll.scrollBy({ left: shift(), behavior: "smooth" }));
  }

  // Building picker — clicking a building box pops up the full
  // floor/unit browser for that building in a modal.
  document.querySelectorAll(".building-box").forEach((box) => {
    box.addEventListener("click", () => {
      const buildingId = box.getAttribute("data-building");

      document.querySelectorAll(".building-row").forEach((row) => {
        if (row.getAttribute("data-building") === buildingId) {
          row.classList.add("building-row--active", "building-row--entering");
          row.addEventListener(
            "animationend",
            () => row.classList.remove("building-row--entering"),
            { once: true }
          );
        } else {
          row.classList.remove("building-row--active", "building-row--entering");
        }
      });

      closeModals();
      openModal("#modalBuildingUnits");
    });
  });

  // Floor tab navigation
  document.querySelectorAll(".floor-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const buildingRow = tab.closest(".building-row");
      if (!buildingRow) return;

      // Update active tab
      buildingRow.querySelectorAll(".floor-tab").forEach((t) => t.classList.remove("floor-tab--active"));
      tab.classList.add("floor-tab--active");

      // Show corresponding floor section, crossfading it in
      const floor = tab.getAttribute("data-floor");
      buildingRow.querySelectorAll(".floor-section").forEach((section) => {
        if (section.getAttribute("data-floor") === floor) {
          section.classList.add("floor-section--active", "floor-section--entering");
          section.addEventListener(
            "animationend",
            () => section.classList.remove("floor-section--entering"),
            { once: true }
          );
        } else {
          section.classList.remove("floor-section--active", "floor-section--entering");
        }
      });
    });
  });

  // Units filter
  document.querySelectorAll(".filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("filter-btn--active"));
      btn.classList.add("filter-btn--active");

      const filter = btn.getAttribute("data-filter");
      document.querySelectorAll(".unit-card--compact").forEach((card) => {
        const status = card.getAttribute("data-unit-status");
        if (filter === "available") {
          card.style.display = status === "available" ? "block" : "none";
        } else {
          card.style.display = "block";
        }
      });
    });
  });

  // Floor scroll buttons
  document.querySelectorAll(".scroll-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const direction = btn.getAttribute("data-direction");
      const scrollContainer = btn.closest(".floor-scroll-container").querySelector(".units-scroll");
      if (!scrollContainer) return;

      const scrollAmount = 300;
      if (direction === "left") {
        scrollContainer.scrollBy({ left: -scrollAmount, behavior: "smooth" });
      } else {
        scrollContainer.scrollBy({ left: scrollAmount, behavior: "smooth" });
      }
    });
  });

  // OCR auto-fill (ID type + ID number)
  const reserveUpload = document.getElementById("reserveIdUpload");
  const reserveIdType = document.getElementById("reserveIdType");
  const reserveIdNumber = document.getElementById("reserveIdNumber");
  const reserveMoveInDate = document.getElementById("reserveMoveInDate");
  const reserveMoveOutDate = document.getElementById("reserveMoveOutDate");
  const reserveMoveOutHint = document.getElementById("reserveMoveOutHint");
  const ocrStatus = document.getElementById("ocrStatus");
  if (reserveMoveInDate && reserveMoveOutDate) {
    // Format using LOCAL date parts — Date#toISOString() converts to UTC,
    // which silently shifts the date back a day for timezones ahead of UTC
    // (e.g. Asia/Manila, UTC+8) and was producing an off-by-one move-out date.
    function toLocalDateStr(d) {
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      return `${y}-${m}-${day}`;
    }
    const today = toLocalDateStr(new Date());
    reserveMoveInDate.min = today;
    reserveMoveOutDate.min = today;

    // Commercial units only — minimum 1-year contract term. Residential
    // units have no move-out date to compute (month-to-month, field hidden).
    function minTermMoveOut(moveInStr) {
      const d = new Date(moveInStr + "T00:00:00");
      d.setFullYear(d.getFullYear() + 1);
      return toLocalDateStr(d);
    }

    reserveMoveInDate.addEventListener("change", () => {
      const selectedMoveIn = reserveMoveInDate.value || today;
      const reserveForm = document.getElementById("reserveForm");
      const unitType = (reserveForm ? reserveForm.getAttribute("data-unit-type") || "" : "").toLowerCase();
      const isCommercial = unitType.includes("commercial");
      if (!isCommercial) return;

      const minMoveOut = minTermMoveOut(selectedMoveIn);
      reserveMoveOutDate.min = minMoveOut;
      // Auto-fill the minimum term so users don't have to work it out themselves;
      // they can still push it later, just never earlier than the minimum.
      reserveMoveOutDate.value = minMoveOut;

      if (reserveMoveOutHint) {
        reserveMoveOutHint.textContent = "Set automatically to a 1-year minimum contract for commercial units. You may choose a later date.";
      }
    });
  }

  if (reserveUpload && reserveIdType && reserveIdNumber) {
    // Clearing the file has to clear what was read from it too, or the form
    // keeps describing a photo that is no longer attached.
    const clearBtn = document.getElementById("reserveIdClear");
    if (clearBtn) {
      clearBtn.addEventListener("click", () => {
        reserveUpload.value = "";
        reserveIdType.value = "";
        reserveIdNumber.value = "";
        clearBtn.hidden = true;
        if (ocrStatus) ocrStatus.textContent =
          "Tip: OCR tries to detect ID Type and ID Number after upload. You can still choose the ID type manually from the dropdown.";
      });
    }

    reserveUpload.addEventListener("change", async () => {
      const file = reserveUpload.files && reserveUpload.files[0];
      if (!file) return;
      const allowedIdTypes = new Set([
        "National ID",
        "UMID",
        "PhilHealth",
        "Driver's License",
        "Passport",
        "SSS",
        "Postal ID",
        "PRC ID",
        "Voter's ID",
        "TIN ID",
        "Other",
      ]);
      // A new file describes a new ID, so whatever the last one produced is
      // now wrong. The fields used to be filled only when empty — after a
      // first upload they never were, so choosing a second, different ID
      // left the first one's type and number sitting in the form while the
      // photo underneath had changed.
      reserveIdType.value = "";
      reserveIdNumber.value = "";
      if (clearBtn) clearBtn.hidden = false;

      const fd = new FormData();
      fd.append("id_upload", file);
      if (ocrStatus) ocrStatus.textContent = "Scanning ID (OCR)...";
      try {
        const res = await fetch("/api/ocr-id", { method: "POST", body: fd });
        const data = await res.json();
        const detectedIdType = data.id_type && allowedIdTypes.has(data.id_type) ? data.id_type : (data.id_type ? "Other" : "");
        if (detectedIdType) reserveIdType.value = detectedIdType;
        if (data.id_number) reserveIdNumber.value = data.id_number;
        if (ocrStatus) {
          ocrStatus.textContent = data.id_type || data.id_number
            ? "Read from this photo: " + (data.id_type || "type not detected") +
              (data.id_number ? " \u00b7 " + data.id_number : "") +
              ". Check it against the ID in your hand before you submit."
            : (data.ocr_note ? `${data.ocr_note} Please choose a valid ID from the dropdown and type the ID number manually.` : "OCR could not confidently detect fields. Please choose a valid ID from the dropdown and type the ID number manually.");
        }
      } catch (_) {
        if (ocrStatus) ocrStatus.textContent = "OCR unavailable right now. Please choose a valid ID from the dropdown and type the ID number manually.";
      }
    });
  }

  // Inquiry Form Submission
  const inquiryForm = document.getElementById("inquiryForm");
  const inquiryFormMessage = document.getElementById("inquiryFormMessage");
  if (inquiryForm && inquiryFormMessage) {
    inquiryForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      
      const formData = new FormData(inquiryForm);
      const submitBtn = inquiryForm.querySelector('button[type="submit"]');
      
      // Disable submit button
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Submitting...";
      }
      
      // Hide previous message
      inquiryFormMessage.style.display = "none";
      
      try {
        const res = await fetch("/inquiry/submit", {
          method: "POST",
          body: formData
        });
        
        const data = await res.json();
        
        if (data.success) {
          // Show success message
          inquiryFormMessage.className = "alert alert--success";
          inquiryFormMessage.textContent = data.message;
          inquiryFormMessage.style.display = "block";
          
          // Reset form
          inquiryForm.reset();
          
          // Scroll to message
          inquiryFormMessage.scrollIntoView({ behavior: "smooth", block: "nearest" });
        } else {
          // Show error message
          inquiryFormMessage.className = "alert alert--danger";
          inquiryFormMessage.textContent = data.message || "Failed to submit inquiry. Please try again.";
          inquiryFormMessage.style.display = "block";
        }
      } catch (err) {
        // Show error message
        inquiryFormMessage.className = "alert alert--danger";
        inquiryFormMessage.textContent = "An error occurred. Please try again later.";
        inquiryFormMessage.style.display = "block";
      } finally {
        // Re-enable submit button
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = "Submit Inquiry";
        }
      }
    });
  }
})();

// Auto-open login modal if URL has ?show_login=1 (for ban redirects)
document.addEventListener('DOMContentLoaded', function() {
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get('show_login') === '1') {
    const loginModal = document.getElementById('modalLogin');
    if (loginModal) {
      loginModal.hidden = false;
      document.body.style.overflow = 'hidden';
      const firstInput = loginModal.querySelector('input');
      if (firstInput) {
        setTimeout(() => firstInput.focus(), 100);
      }
      // Clean URL without reloading page
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }
});
