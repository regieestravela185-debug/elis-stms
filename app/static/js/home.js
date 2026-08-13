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

  function closeModals() {
    ["#modalLogin", "#modalRegister", "#modalVerifyOtp", "#modalReserve", "#modalUnitDetails", "#modalForgotPassword", "#modalResetPassword", "#modalTerms", "#modalPrivacy"].forEach((id) => {
      const el = $(id);
      if (el) el.hidden = true;
    });
    document.body.style.overflow = "";
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
      closeModals();
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
      const reserveTotalPayment = document.getElementById("reserveTotalPayment");
      if (!btn || !card || !reserveForm || !reserveUnitCode) return;
      const unitId = btn.getAttribute("data-unit-id");
      const unitCode = btn.getAttribute("data-unit-code") || "";
      const unitFloor = card.getAttribute("data-unit-floor") || "";
      const unitPrice = card.getAttribute("data-unit-price") || "";
      if (!unitId) return;
      reserveForm.setAttribute("action", `/user/reserve/${unitId}`);
      if (reserveUnitId) reserveUnitId.value = unitId;
      reserveUnitCode.value = unitCode;
      if (reserveUnitFloor) reserveUnitFloor.value = unitFloor ? `${unitFloor}st Floor` : "";
      if (reserveUnitPrice) reserveUnitPrice.value = `₱${unitPrice} / month`;
      if (reserveMonthlyPrice) reserveMonthlyPrice.value = `₱${unitPrice}`;
      if (reserveTotalPayment) {
        const priceNum = parseFloat(unitPrice.replace(/,/g, '')) || 0;
        const total = priceNum + 5000;
        reserveTotalPayment.value = `₱${total.toLocaleString('en-PH', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
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
    if (t.closest(".js-open-terms")) {
      e.preventDefault();
      closeModals();
      openModal("#modalTerms");
    }
    if (t.closest(".js-open-privacy")) {
      e.preventDefault();
      closeModals();
      openModal("#modalPrivacy");
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModals();
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

  // Auto-dismiss flash messages in modals after 3 seconds
  function autoDismissModalFlashes() {
    const modalFlashContainers = document.querySelectorAll('.modal .alert');
    modalFlashContainers.forEach((alert) => {
      setTimeout(() => {
        alert.style.transition = 'opacity 0.3s ease-out';
        alert.style.opacity = '0';
        setTimeout(() => {
          alert.remove();
        }, 300);
      }, 3000);
    });
  }

  // Run auto-dismiss when modals open
  if (auth === "login" || auth === "register" || auth === "verify") {
    autoDismissModalFlashes();
  }

  document.querySelectorAll(".js-unit-card").forEach((el) => {
    el.style.cursor = "pointer";
    const open = () => {
      closeModals();
      openModal("#modalLogin");
    };
    el.addEventListener("click", open);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
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

  function openChat() {
    if (!panel) return;
    panel.hidden = false;
    const inp = $("#chatInput");
    inp && inp.focus();
  }

  function closeChat() {
    if (!panel) return;
    // Show goodbye then close after delay
    if (typeof removeFollowUp === "function") removeFollowUp();
    appendChatBubble("Bot", "Salamat sa pag-chat! Kung may tanong ka pa, bumalik ka lang. Have a great day! 😊");
    const log = document.getElementById("chatLog");
    if (log) log.scrollTop = log.scrollHeight;
    setTimeout(() => {
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
          <svg class="panda-ico" viewBox="0 0 40 40" fill="none"><circle cx="11.5" cy="11" r="5" fill="#2f2f33"/><circle cx="28.5" cy="11" r="5" fill="#2f2f33"/><circle cx="20" cy="22" r="13.5" fill="#fff"/><ellipse cx="14.6" cy="20" rx="4.2" ry="5.2" fill="#2f2f33" transform="rotate(-12 14.6 20)"/><ellipse cx="25.4" cy="20" rx="4.2" ry="5.2" fill="#2f2f33" transform="rotate(12 25.4 20)"/><g class="owl-awake"><circle cx="15" cy="20.6" r="1.7" fill="#fff"/><circle cx="25" cy="20.6" r="1.7" fill="#fff"/><circle cx="15.4" cy="21" r="0.85" fill="#1c1c1e"/><circle cx="25.4" cy="21" r="0.85" fill="#1c1c1e"/></g><g class="owl-asleep"><path d="M12.6 20.8q2.4 1.8 4.8 0" stroke="#fff" stroke-width="1.3" stroke-linecap="round"/><path d="M22.6 20.8q2.4 1.8 4.8 0" stroke="#fff" stroke-width="1.3" stroke-linecap="round"/><path d="M30.5 8h3.2l-3.2 3.2h3.2" stroke="#2f2f33" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round"/></g><ellipse cx="20" cy="25" rx="1.9" ry="1.3" fill="#2f2f33"/><path d="M20 26.2v1.5" stroke="#2f2f33" stroke-width="0.9" stroke-linecap="round"/><path d="M20 27.7q-1.6 0.9 -2.8 -0.2" stroke="#2f2f33" stroke-width="0.9" stroke-linecap="round"/><path d="M20 27.7q1.6 0.9 2.8 -0.2" stroke="#2f2f33" stroke-width="0.9" stroke-linecap="round"/></svg>
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

  // Homepage units realtime status (database-connected polling)
  const unitCards = Array.from(document.querySelectorAll(".unit-card[data-unit-id]"));
  const canReserve = !!document.getElementById("reserveForm");
  async function pollHomeUnits() {
    if (!unitCards.length) return;
    try {
      const res = await fetch("/api/units");
      if (!res.ok) return;
      const data = await res.json();
      const map = new Map((data.units || []).map((u) => [String(u.id), u]));
      unitCards.forEach((card) => {
        const id = card.getAttribute("data-unit-id");
        const unit = id ? map.get(id) : null;
        if (!unit) return;
        const badge = card.querySelector(".badge");
        if (badge) {
          badge.className = `badge badge--${unit.status}`;
          badge.textContent = unit.status;
        }
        const body = card.querySelector(".card__body");
        if (!body) return;
        const existingButton = body.querySelector(".js-open-reserve");
        const existingHint = body.querySelector(".unit-card__hint");
        if (canReserve && unit.status === "available") {
          if (!existingButton) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "btn btn--sm btn--primary js-open-reserve";
            btn.setAttribute("data-unit-id", String(unit.id));
            btn.setAttribute("data-unit-code", unit.unit_code || "");
            btn.textContent = "Reserve";
            body.appendChild(btn);
          }
          if (existingHint) existingHint.remove();
        } else if (canReserve && unit.status !== "available") {
          if (existingButton) existingButton.remove();
          if (!existingHint) {
            const p = document.createElement("p");
            p.className = "unit-card__hint muted";
            p.textContent = `Currently ${unit.status}`;
            body.appendChild(p);
          } else {
            existingHint.textContent = `Currently ${unit.status}`;
          }
        }
      });
    } catch (_) {}
  }
  pollHomeUnits();
  setInterval(pollHomeUnits, 5000);

  // Horizontal unit scroller
  const unitsScroll = document.getElementById("unitsScroll");
  const leftBtn = document.getElementById("unitsScrollLeft");
  const rightBtn = document.getElementById("unitsScrollRight");
  if (unitsScroll && leftBtn && rightBtn) {
    const shift = () => Math.max(280, Math.floor(unitsScroll.clientWidth * 0.8));
    leftBtn.addEventListener("click", () => unitsScroll.scrollBy({ left: -shift(), behavior: "smooth" }));
    rightBtn.addEventListener("click", () => unitsScroll.scrollBy({ left: shift(), behavior: "smooth" }));
  }

  // Floor tab navigation
  document.querySelectorAll(".floor-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const buildingRow = tab.closest(".building-row");
      if (!buildingRow) return;

      // Update active tab
      buildingRow.querySelectorAll(".floor-tab").forEach((t) => t.classList.remove("floor-tab--active"));
      tab.classList.add("floor-tab--active");

      // Show corresponding floor section
      const floor = tab.getAttribute("data-floor");
      buildingRow.querySelectorAll(".floor-section").forEach((section) => {
        section.classList.remove("floor-section--active");
        if (section.getAttribute("data-floor") === floor) {
          section.classList.add("floor-section--active");
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
  const ocrStatus = document.getElementById("ocrStatus");
  if (reserveMoveInDate && reserveMoveOutDate) {
    const today = new Date().toISOString().split("T")[0];
    reserveMoveInDate.min = today;
    reserveMoveOutDate.min = today;

    reserveMoveInDate.addEventListener("change", () => {
      const selectedMoveIn = reserveMoveInDate.value || today;
      reserveMoveOutDate.min = selectedMoveIn;
      if (reserveMoveOutDate.value && reserveMoveOutDate.value <= selectedMoveIn) {
        reserveMoveOutDate.value = "";
      }
    });
  }
  if (reserveUpload && reserveIdType && reserveIdNumber) {
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
      const fd = new FormData();
      fd.append("id_upload", file);
      if (ocrStatus) ocrStatus.textContent = "Scanning ID (OCR)...";
      try {
        const res = await fetch("/api/ocr-id", { method: "POST", body: fd });
        const data = await res.json();
        const detectedIdType = data.id_type && allowedIdTypes.has(data.id_type) ? data.id_type : (data.id_type ? "Other" : "");
        if (detectedIdType && !reserveIdType.value) reserveIdType.value = detectedIdType;
        if (data.id_number && !reserveIdNumber.value) reserveIdNumber.value = data.id_number;
        if (ocrStatus) {
          ocrStatus.textContent = data.id_type || data.id_number
            ? "OCR done. Please review the detected ID type and ID number before submit. If needed, choose a valid ID manually from the dropdown."
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
