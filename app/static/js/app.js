/**
 * Global debounce utility — waits for user to stop typing before executing.
 * Usage: element.addEventListener('input', debounce(filterTable, 400));
 */
function debounce(fn, delay) {
  let timer;
  return function(...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

function appendChatBubble(role, text) {
  const log = document.getElementById("chatLog");
  if (!log) return;

  const bubble = document.createElement("div");
  bubble.className = `chat-bubble chat-bubble--${role === "You" ? "user" : "bot"}`;

  const avatar = document.createElement("div");
  avatar.className = "chat-bubble__avatar";
  if (role === "You") {
    avatar.textContent = "You";
  } else {
    // Ellie the owl (awake at night, asleep by day)
    avatar.innerHTML = '<svg class="panda-ico" viewBox="0 0 40 40" width="18" height="18" fill="none"><circle cx="11.5" cy="11" r="5" fill="#2f2f33"/><circle cx="28.5" cy="11" r="5" fill="#2f2f33"/><circle cx="20" cy="22" r="13.5" fill="#fff"/><ellipse cx="14.6" cy="20" rx="4.2" ry="5.2" fill="#2f2f33" transform="rotate(-12 14.6 20)"/><ellipse cx="25.4" cy="20" rx="4.2" ry="5.2" fill="#2f2f33" transform="rotate(12 25.4 20)"/><g class="owl-awake"><circle cx="15" cy="20.6" r="1.7" fill="#fff"/><circle cx="25" cy="20.6" r="1.7" fill="#fff"/><circle cx="15.4" cy="21" r="0.85" fill="#1c1c1e"/><circle cx="25.4" cy="21" r="0.85" fill="#1c1c1e"/></g><g class="owl-asleep"><path d="M12.6 20.8q2.4 1.8 4.8 0" stroke="#fff" stroke-width="1.3" stroke-linecap="round"/><path d="M22.6 20.8q2.4 1.8 4.8 0" stroke="#fff" stroke-width="1.3" stroke-linecap="round"/><path d="M30.5 8h3.2l-3.2 3.2h3.2" stroke="#2f2f33" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round"/></g><ellipse cx="20" cy="25" rx="1.9" ry="1.3" fill="#2f2f33"/><path d="M20 26.2v1.5" stroke="#2f2f33" stroke-width="0.9" stroke-linecap="round"/><path d="M20 27.7q-1.6 0.9 -2.8 -0.2" stroke="#2f2f33" stroke-width="0.9" stroke-linecap="round"/><path d="M20 27.7q1.6 0.9 2.8 -0.2" stroke="#2f2f33" stroke-width="0.9" stroke-linecap="round"/></svg>';
  }

  const content = document.createElement("div");
  content.className = "chat-bubble__text";
  content.textContent = text;

  bubble.appendChild(avatar);
  bubble.appendChild(content);
  log.appendChild(bubble);
  log.scrollTop = log.scrollHeight;
}

function showTyping() {
  const el = document.getElementById("chatTyping");
  if (el) el.hidden = false;
  const log = document.getElementById("chatLog");
  if (log) log.scrollTop = log.scrollHeight;
}

function hideTyping() {
  const el = document.getElementById("chatTyping");
  if (el) el.hidden = true;
}

function hideSuggestions() {
  const el = document.getElementById("chatSuggestions");
  if (el) el.style.display = "none";
}

function removeFollowUp() {
  const existing = document.getElementById("chatFollowUp");
  if (existing) existing.remove();
}

function showFollowUp() {
  removeFollowUp();
  const log = document.getElementById("chatLog");
  if (!log) return;

  const wrap = document.createElement("div");
  wrap.id = "chatFollowUp";
  wrap.className = "chat-followup";

  const msg = document.createElement("div");
  msg.className = "chat-followup__text";
  msg.textContent = "May iba pa ba akong matutulungan? / Anything else I can help with?";
  wrap.appendChild(msg);

  const btns = document.createElement("div");
  btns.className = "chat-followup__buttons";

  const askBtn = document.createElement("button");
  askBtn.className = "chat-suggestion chat-suggestion--active";
  askBtn.textContent = "Ask another question";
  askBtn.addEventListener("click", () => {
    removeFollowUp();
    const inp = document.getElementById("chatInput");
    if (inp) inp.focus();
  });

  const endBtn = document.createElement("button");
  endBtn.className = "chat-suggestion chat-suggestion--end";
  endBtn.textContent = "End chat";
  endBtn.addEventListener("click", () => {
    endChatGracefully();
  });

  btns.appendChild(askBtn);
  btns.appendChild(endBtn);
  wrap.appendChild(btns);
  log.appendChild(wrap);
  log.scrollTop = log.scrollHeight;
}

function endChatGracefully() {
  removeFollowUp();
  appendChatBubble("Bot", "Salamat sa pag-chat! Kung may tanong ka pa, bumalik ka lang. Have a great day! 😊");
  const log = document.getElementById("chatLog");
  if (log) log.scrollTop = log.scrollHeight;
  setTimeout(() => {
    if (typeof resetChat === "function") resetChat();
  }, 2500);
}

async function chatbotSend() {
  const input = document.getElementById("chatInput");
  if (!input) return;
  const msg = (input.value || "").trim();
  if (!msg) return;
  input.value = "";

  // "end" / "reset" / "new" command — show goodbye then reset
  const lower = msg.toLowerCase();
  if (lower === "end" || lower === "reset" || lower === "new" || lower === "restart") {
    hideSuggestions();
    removeFollowUp();
    appendChatBubble("You", msg);
    showTyping();
    setTimeout(() => {
      hideTyping();
      endChatGracefully();
    }, 800);
    return;
  }

  hideSuggestions();
  removeFollowUp();
  appendChatBubble("You", msg);
  showTyping();

  try {
    const res = await fetch("/chatbot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg }),
    });
    const data = await res.json();
    hideTyping();
    appendChatBubble("Bot", data.reply || "…");
    showFollowUp();
  } catch (err) {
    hideTyping();
    appendChatBubble("Bot", "Sorry, I had trouble connecting. Please try again.");
    showFollowUp();
  }
}

function sendQuickMessage(text) {
  const input = document.getElementById("chatInput");
  if (input) input.value = text;
  chatbotSend();
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".flash-stack .flash").forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity .25s ease, transform .25s ease";
      el.style.opacity = "0";
      el.style.transform = "translateY(-6px)";
      setTimeout(() => el.remove(), 260);
    }, 3000);
  });

  document.querySelectorAll("[data-toggle-password]").forEach((toggle) => {
    const form = toggle.closest("form");
    if (!form) return;
    const passwordInput = form.querySelector("[data-password-input]");
    if (!passwordInput) return;

    toggle.addEventListener("change", () => {
      passwordInput.type = toggle.checked ? "text" : "password";
    });
  });

  // Mobile sidebar toggle
  const sidebar = document.querySelector(".dash__side");
  const sidebarBackdrop = document.querySelector(".js-sidebar-backdrop");
  const toggleButtons = document.querySelectorAll(".js-toggle-sidebar");

  function toggleSidebar() {
    sidebar?.classList.toggle("is-open");
    sidebarBackdrop?.classList.toggle("is-open");
  }

  function closeSidebar() {
    sidebar?.classList.remove("is-open");
    sidebarBackdrop?.classList.remove("is-open");
  }

  toggleButtons.forEach((button) => {
    button.addEventListener("click", toggleSidebar);
  });

  sidebarBackdrop?.addEventListener("click", closeSidebar);

  // Close sidebar when clicking a link
  sidebar?.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", closeSidebar);
  });

  // Payment amount auto-fill
  const paymentTenantSelect = document.getElementById("paymentTenantSelect");
  const paymentAmountInput = document.getElementById("paymentAmountInput");

  if (paymentTenantSelect && paymentAmountInput) {
    paymentTenantSelect.addEventListener("change", function() {
      const selectedOption = this.options[this.selectedIndex];
      const price = selectedOption.getAttribute("data-price");
      if (price) {
        paymentAmountInput.value = price;
      }
    });
  }

  const send = document.getElementById("chatSend");
  const input = document.getElementById("chatInput");
  if (send) send.addEventListener("click", chatbotSend);
  if (input) {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") chatbotSend();
    });
  }

  // Quick suggestion buttons
  document.querySelectorAll(".chat-suggestion").forEach((btn) => {
    btn.addEventListener("click", () => {
      const text = btn.getAttribute("data-text");
      if (text) sendQuickMessage(text);
    });
  });
});

