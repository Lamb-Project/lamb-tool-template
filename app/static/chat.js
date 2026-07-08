// Minimal streaming chat client. No framework, no build step — read it,
// change it, ship it.
(function () {
  const thread = document.getElementById("thread");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("msg");
  const token = window.SESSION_TOKEN;

  function addMessage(role, text) {
    const el = document.createElement("div");
    el.className = "msg " + role;
    el.textContent = text;
    thread.appendChild(el);
    thread.scrollTop = thread.scrollHeight;
    return el;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    input.value = "";
    addMessage("user", message);

    const bubble = addMessage("assistant", "");
    const res = await fetch("/chat/send", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Session-Token": token },
      body: JSON.stringify({ message }),
    });
    if (!res.ok) {
      bubble.textContent = "[error: " + res.status + "]";
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      bubble.textContent += decoder.decode(value, { stream: true });
      thread.scrollTop = thread.scrollHeight;
    }
  });
})();
