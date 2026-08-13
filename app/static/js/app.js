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
    avatar.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M7 4.5 9 7M17 4.5 15 7"/><path d="M12 3.8c-3.4 0-6.2 2.8-6.2 6.2v2.4a6.2 6.2 0 0 0 12.4 0v-2.4c0-3.4-2.8-6.2-6.2-6.2Z"/><circle cx="9.3" cy="10.4" r="2"/><circle cx="14.7" cy="10.4" r="2"/><circle cx="9.3" cy="10.4" r="0.6" fill="currentColor" stroke="none"/><circle cx="14.7" cy="10.4" r="0.6" fill="currentColor" stroke="none"/><path d="M12 12.5 11 13.9h2Z" fill="currentColor" stroke="none"/><path d="M8.5 19.5 7.3 21M15.5 19.5 16.7 21"/></svg>';
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

