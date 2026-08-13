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
    avatar.innerHTML = '<svg class="ellie-ico" viewBox="0 0 40 40" width="18" height="18" fill="none"><path d="M8 17.5a12 12 0 0 1 24 0" fill="none" stroke="#3b4160" stroke-width="2.6" stroke-linecap="round"/><ellipse cx="20" cy="22.5" rx="12.5" ry="13" fill="#f4ecda"/><ellipse cx="20" cy="25.5" rx="7.6" ry="8" fill="#fffdf7"/><circle cx="15" cy="19.5" r="5.2" fill="#fffdf7" stroke="#e6d8ba" stroke-width="0.8"/><circle cx="25" cy="19.5" r="5.2" fill="#fffdf7" stroke="#e6d8ba" stroke-width="0.8"/><g class="owl-awake"><circle cx="15" cy="19.7" r="2.5" fill="#2b2b33"/><circle cx="25" cy="19.7" r="2.5" fill="#2b2b33"/><circle cx="15.9" cy="18.9" r="0.8" fill="#fff"/><circle cx="25.9" cy="18.9" r="0.8" fill="#fff"/></g><g class="owl-asleep"><path d="M12.4 19.8q2.6 2 5.2 0" fill="none" stroke="#2b2b33" stroke-width="1.3" stroke-linecap="round"/><path d="M22.4 19.8q2.6 2 5.2 0" fill="none" stroke="#2b2b33" stroke-width="1.3" stroke-linecap="round"/><path d="M30 7h3.4l-3.4 3.4h3.4" fill="none" stroke="#8a6d1e" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round"/></g><path d="M20 22.4 l-2 2.4 4 0Z" fill="#e8a33d"/><rect x="5.4" y="16" width="4.8" height="7" rx="2.4" fill="#3b4160"/><rect x="29.8" y="16" width="4.8" height="7" rx="2.4" fill="#3b4160"/><path d="M16.4 34.6l-1.4 2.2M18.4 35l0 2.3M23.6 34.6l1.4 2.2M21.6 35l0 2.3" fill="none" stroke="#e8a33d" stroke-width="1.2" stroke-linecap="round"/></svg>';
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

