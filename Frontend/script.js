// ==========================================================
// script.js — Skin Intel Bot (FINAL, MERGED)
// Single, polished, non-duplicated file containing all features
// - Chat send/receive (text + image)
// - Image preview & remove
// - History (save/load/delete/clear all) in localStorage
// - Sidebar toggle
// - Custom glassy confirmation modal (re-usable)
// - Conversation preview modal (re-usable)
// - Hospital button (confirmation -> open Google Maps with geolocation fallback)
// - Markdown rendering (uses `marked` if loaded)
// - Speech synthesis speak button for bot replies
// - Typing indicator
// - Inline map card helper + optional backend places fetch
// - Clean API hooks (backendUrl) and graceful error handling
// ==========================================================

(() => {
  "use strict";

  // =====================
  // CONFIG
  // =====================
  const backendUrl = "http://127.0.0.1:5000";
  const MAX_HISTORY = 200;
  const ICONS = { play: "▶️", stop: "⏹️" };
  const VOICE_PREF = {
    preferredName: "Google UK English Female",
    lang: "en-GB",
    rate: 0.95,
    pitch: 1.05,
  };

  // =====================
  // DOM REFS (lazily populated on init)
  // =====================
  let chatBox,
    imageInput,
    sendBtn,
    userInput,
    sidebar,
    hamburgerBtn,
    imagePreview,
    historyList,
    hospitalBtn,
    clearHistoryBtn;

  // =====================
  // STATE
  // =====================
  let selectedFile = null;
  let modalOverlay = null; // conversation preview modal
  let confirmOverlay = null; // confirm modal

  // =====================
  // STARTUP
  // =====================
  document.addEventListener("DOMContentLoaded", init);

  // ============================================================
  // INIT
  // ============================================================
  function init() {
    // query DOM
    chatBox = document.getElementById("chatBox");
    imageInput = document.getElementById("imageInput");
    sendBtn = document.getElementById("sendBtn");
    userInput = document.getElementById("userInput");
    sidebar = document.getElementById("sidebar");
    hamburgerBtn = document.getElementById("hamburgerBtn");
    imagePreview = document.getElementById("imagePreview");
    historyList = document.getElementById("historyList");
    hospitalBtn = document.getElementById("hospitalBtn");
    clearHistoryBtn = document.getElementById("clearHistoryBtn");

    // attach behaviors
    bindSidebarToggle();
    bindImagePreview();
    bindSendAndInput();
    bindClearAll();
    bindHospitalBtn();

    // hide hello splash if present
    const hello = document.querySelector(".hello__div");
    if (hello) setTimeout(() => (hello.style.display = "none"), 4200);

    // ===========================
    // PRIVACY BANNER CONTROLS
    // ===========================
    const privacyBanner = document.getElementById("privacyBanner");
    const privacyCancel = document.getElementById("privacyCancel");
    const privacyContinue = document.getElementById("privacyContinue");

    privacyCancel.addEventListener("click", () => {
      privacyBanner.classList.remove("active");
    });

    privacyContinue.addEventListener("click", async () => {
      privacyBanner.classList.remove("active");

      // Now trigger main confirmation popup
      const ok = await showConfirm({
        title: "Open Nearby Hospitals",
        message: "Open nearby skin hospitals in Google Maps?",
        confirmText: "Open",
        cancelText: "Cancel",
      });

      if (!ok) return;

      // Same location flow as before
      if (!navigator.geolocation) {
        window.open(
          "https://www.google.com/maps/search/skin+hospital+dermatologist",
          "_blank"
        );
        return;
      }

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const lat = pos.coords.latitude;
          const lon = pos.coords.longitude;
          window.open(
            `https://www.google.com/maps/search/skin+hospital+dermatologist/@${lat},${lon},14z`,
            "_blank"
          );
        },
        () => {
          window.open(
            "https://www.google.com/maps/search/skin+hospital+dermatologist",
            "_blank"
          );
        },
        { timeout: 15000 }
      );
    });

    renderHistory();
  }

  // ============================================================
  // SIDEBAR TOGGLE
  // ============================================================
  function bindSidebarToggle() {
    if (!sidebar || !hamburgerBtn) return;
    hamburgerBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      sidebar.classList.toggle("visible");
    });

    document.addEventListener("click", (e) => {
      if (!sidebar.classList.contains("visible")) return;
      const clickedInside = sidebar.contains(e.target);
      const clickedHamburger = hamburgerBtn.contains(e.target);
      if (!clickedInside && !clickedHamburger)
        sidebar.classList.remove("visible");
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && sidebar.classList.contains("visible"))
        sidebar.classList.remove("visible");
    });
  }

  // ============================================================
  // IMAGE PREVIEW HANDLING
  // ============================================================
  function bindImagePreview() {
    if (!imageInput || !imagePreview) return;

    imageInput.addEventListener("change", (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      selectedFile = file;

      const reader = new FileReader();
      reader.onload = () => showImagePreview(reader.result);
      reader.readAsDataURL(file);
    });
  }

  function showImagePreview(dataUrl) {
    if (!imagePreview) return;

    imagePreview.innerHTML = `\n      <img src="${dataUrl}" alt="Preview" />\n      <button class="remove-btn" title="Remove">×</button>\n    `;
    imagePreview.classList.add("active");
    imagePreview.style.display = "block";

    const removeBtn = imagePreview.querySelector(".remove-btn");
    if (removeBtn)
      removeBtn.addEventListener("click", cleanupImagePreview, { once: true });
  }

  function cleanupImagePreview() {
    if (!imagePreview) return;
    imagePreview.classList.remove("active");
    imagePreview.innerHTML = "";
    imagePreview.style.display = "none";
    selectedFile = null;

    if (imageInput) {
      imageInput.value = "";
      // force clear on some browsers
      imageInput.type = "text";
      imageInput.type = "file";
    }
  }

  // ============================================================
  // SEND / INPUT BINDING
  // ============================================================
  function bindSendAndInput() {
    if (sendBtn) sendBtn.addEventListener("click", onSend);
    if (!userInput) return;

    userInput.addEventListener("input", () => {
      userInput.style.height = "auto";
      const newH = Math.min(userInput.scrollHeight, 150);
      userInput.style.height = newH + "px";
      userInput.style.overflowY =
        userInput.scrollHeight > 150 ? "auto" : "hidden";
    });

    userInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        onSend();
      }
    });
  }

  async function onSend() {
    if (!chatBox || !userInput) return;

    const raw = (userInput.value || "").trim();
    const text = raw.slice(0, 1200);
    if (!text && !selectedFile) return;

    if (text) appendUserMessage(text);

    // reset input
    userInput.value = "";
    userInput.style.height = "40px";

    if (selectedFile) {
      appendUserImage(selectedFile);
      try {
        await handleImageUpload(selectedFile);
      } catch (err) {
        console.error("Image upload failed", err);
        appendMessage("bot", "Image upload failed.");
      }
      cleanupImagePreview();
    }

    if (text) await handleTextMessage(text);
  }

  // ============================================================
  // APPEND USER MESSAGES
  // ============================================================
  function appendUserMessage(text) {
    const div = document.createElement("div");
    div.className = "user-message";
    div.textContent = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function appendUserImage(file) {
    const div = document.createElement("div");
    div.className = "user-message";
    div.innerHTML = "<div class='img-loading'>Uploading image...</div>";
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;

    const reader = new FileReader();
    reader.onload = () => {
      div.innerHTML = `<img src="${reader.result}" style="max-width:160px;border-radius:8px;box-shadow:0 0 6px rgba(0,0,0,0.12)" />`;
      chatBox.scrollTop = chatBox.scrollHeight;
    };
    reader.readAsDataURL(file);
  }

  // ============================================================
  // APPEND BOT MESSAGES (with speak button & source badge)
  // ============================================================
  function appendMessage(sender, content, isHTML = false, sourceTag = null) {
    const bubble = document.createElement("div");
    bubble.className = sender === "bot" ? "bot-message" : "user-message";

    if (sender === "bot") {
      const wrapper = document.createElement("div");
      wrapper.className = "bot-message-wrapper";
      wrapper.style.position = "relative";
      wrapper.style.paddingBottom = "40px";

      const msg = document.createElement("div");
      msg.className = "bot-content";
      msg.innerHTML = isHTML ? content : escapeHTML(content);

      const speakBtn = document.createElement("button");
      speakBtn.className = "speak-btn";
      speakBtn.innerHTML = ICONS.play;
      speakBtn.addEventListener("click", () =>
        toggleSpeech(speakBtn, msg.textContent)
      );

      if (sourceTag) {
        const badge = document.createElement("div");
        badge.className = "source-badge";
        badge.dataset.src = sourceTag;
        badge.textContent = mapBadgeText(sourceTag);
        badge.style.position = "absolute";
        badge.style.left = "10px";
        badge.style.bottom = "6px";
        badge.style.fontSize = "11px";
        badge.style.opacity = "0.85";
        wrapper.appendChild(badge);
      }

      wrapper.appendChild(msg);
      wrapper.appendChild(speakBtn);
      bubble.appendChild(wrapper);
    } else {
      bubble.innerHTML = isHTML ? content : escapeHTML(content);
    }

    chatBox.appendChild(bubble);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function mapBadgeText(tag) {
    const map = {
      "local_database + global_llm": "🟢 Local DB + LLM",
      local_database: "🟢 Local DB",
      local_rule: "🟡 Local Rule",
      global_llm: "🔵 LLM",
      "cnn+llm": "🟣 Image Model + LLM",
      "image_model + global_llm": "🟣 Image Model + LLM",
      text_llm: "🔵 Text LLM",
      unknown: "⚪ Unknown",
      none: "⚪ None",
    };
    return map[tag] || `⚪ ${tag}`;
  }

  function toggleSpeech(button, text) {
    const synth = window.speechSynthesis;
    if (!text) return;
    if (synth.speaking) {
      synth.cancel();
      button.innerHTML = ICONS.play;
      return;
    }

    const ut = new SpeechSynthesisUtterance(text);
    const voices = synth.getVoices();
    ut.voice =
      voices.find((v) => v.name === VOICE_PREF.preferredName) || voices[0];
    ut.lang = VOICE_PREF.lang;
    ut.rate = VOICE_PREF.rate;
    ut.pitch = VOICE_PREF.pitch;

    button.innerHTML = ICONS.stop;
    synth.speak(ut);
    ut.onend = () => {
      button.innerHTML = ICONS.play;
    };
  }

  // ============================================================
  // TYPING INDICATOR
  // ============================================================
  function appendBotThinking() {
    if (document.getElementById("thinking")) return;
    const div = document.createElement("div");
    div.id = "thinking";
    div.className = "bot-message";
    div.innerHTML = `<div class="typing-dots" aria-hidden="true"><span></span><span></span><span></span></div>`;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function removeBotThinking() {
    const el = document.getElementById("thinking");
    if (el) el.remove();
  }

  // ============================================================
  // TEXT MESSAGE FLOW -> backend
  // ============================================================
  async function handleTextMessage(message) {
    appendBotThinking();
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 120000);

      const res = await fetch(`${backendUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
        signal: controller.signal,
      });

      clearTimeout(timeout);
      removeBotThinking();

      if (!res.ok) {
        appendMessage(
          "bot",
          "Error: server returned an error. Please try again."
        );
        saveHistory(message, "Error: server error");
        return;
      }

      const data = await res.json();
      const replyRoot = data?.reply || {};
      let botContent =
        replyRoot?.content || replyRoot || "Unexpected server response";
      const sourceTag = replyRoot?.source || "unknown";

      botContent = String(botContent)
        .replace(/markdown format.*\n?/gi, "")
        .replace(/–/g, "-")
        .trim();

      if (typeof marked !== "undefined" && typeof marked.parse === "function") {
        const fixed = enforceMarkdownFormatting(botContent);
        const html = marked.parse(fixed);
        appendMessage("bot", html, true, sourceTag);
      } else {
        const html = botContent
          .split("\n\n")
          .map((p) => `<p>${escapeHTML(p).replace(/\n/g, "<br>")}</p>`)
          .join("");
        appendMessage("bot", html, true, sourceTag);
      }

      saveHistory(message, stripHTML(botContent));
    } catch (err) {
      removeBotThinking();
      console.error("Chat error:", err);
      if (err && err.name === "AbortError") {
        appendMessage("bot", "Request timed out — try a shorter message.");
        saveHistory(message, "Request timed out.");
        return;
      }
      appendMessage("bot", "Error contacting backend. Is the server running?");
      saveHistory(message, "Error contacting backend.");
    }
  }

  function enforceMarkdownFormatting(text) {
    if (!text) return text;
    let t = text;
    t = t.replace(/##\s*(Explanation:)/gi, "## Explanation:\n");
    t = t.replace(/##\s*(Causes:)/gi, "\n## Causes:\n");
    t = t.replace(/##\s*(Self-care Tips:)/gi, "\n## Self-care Tips:\n");
    t = t.replace(/(## [^\n]+)\n(?!\n)/g, "$1\n\n$2");
    t = t.replace(/\n-\s*/g, "\n- ");
    t = t.replace(/([^:\n]) - /g, "$1\n- ");
    t = t.replace(/\n{3,}/g, "\n\n");
    return t.trim();
  }

  // ============================================================
  // IMAGE UPLOAD to /predict
  // ============================================================
  async function handleImageUpload(file) {
    appendBotThinking();
    try {
      const formData = new FormData();
      formData.append("image", file);
      const res = await fetch(`${backendUrl}/predict`, {
        method: "POST",
        body: formData,
      });
      removeBotThinking();
      if (!res.ok) {
        appendMessage("bot", "Error: image prediction failed.");
        saveHistory("Image uploaded", "Error: image prediction failed.");
        return;
      }

      const data = await res.json();

      if (data.reply?.content) {
        const clean = enforceImageMarkdown(data.reply.content);
        const diseaseName = data.disease || "Unknown Condition";
        const confPercent =
          typeof data.confidence === "number"
            ? Math.round(data.confidence * 100)
            : null;

        let finalHTML = `<div style="font-size:1.1rem;font-weight:700;margin-bottom:4px;">${escapeHTML(
          diseaseName
        )}</div>`;
        if (confPercent !== null)
          finalHTML += `<div style="font-size:0.95rem;font-weight:600;opacity:0.8;margin-bottom:10px;">Confidence: ${confPercent}%</div>`;
        finalHTML +=
          typeof marked !== "undefined"
            ? marked.parse(clean)
            : `<pre>${escapeHTML(clean)}</pre>`;

        appendMessage(
          "bot",
          finalHTML,
          true,
          data.reply.source || "image_model + global_llm"
        );
        saveHistory("Image uploaded", stripHTML(clean));
        return;
      }

      const formatted = formatAIResponse(data);
      appendMessage("bot", formatted, true, "image_model");
      saveHistory("Image uploaded", stripHTML(formatted));
    } catch (err) {
      removeBotThinking();
      console.error("Predict error:", err);
      appendMessage(
        "bot",
        "Could not connect to backend for image prediction."
      );
      saveHistory("Image uploaded", "Connection error");
    }
  }

  function enforceImageMarkdown(md) {
    if (!md) return md;
    md = md.replace(/Explanation:/g, "Explanation:\n\n");
    md = md.replace(/Causes:/g, "\n\nCauses:\n\n");
    md = md.replace(/Self-care Tips:/g, "\n\nSelf-care Tips:\n\n");
    md = md.replace(/\n-\s*/g, "\n- ");
    md = md.replace(/([^:\n]) - /g, "$1\n- ");
    md = md.replace(/\n{3,}/g, "\n\n");
    return md.trim();
  }

  // ============================================================
  // helper: format fallback AI response
  // ============================================================
  function formatAIResponse(result) {
    if (!result || typeof result !== "object")
      return `<div>Unexpected response.</div>`;
    const name = result.disease || "Unknown";
    const conf =
      typeof result.confidence === "number"
        ? Math.round(
            result.confidence <= 1 ? result.confidence * 100 : result.confidence
          ) + "%"
        : "N/A";

    let html = `<div style="max-width:100%;overflow-wrap:break-word;white-space:pre-wrap;"><div style="font-weight:600;font-size:1.05rem;margin-bottom:6px;">${escapeHTML(
      name
    )}</div><div style="margin-top:6px;font-weight:600;">Confidence: ${conf}</div>`;
    if (result.llm_response)
      html += `<div style="margin-top:10px;">${
        typeof marked !== "undefined"
          ? marked.parse(result.llm_response)
          : escapeHTML(result.llm_response)
      }</div>`;
    else
      html += `<div style="margin-top:8px;">No additional details available.</div>`;
    html += `</div>`;
    return html;
  }

  // ============================================================
  // HISTORY (localStorage)
  // ============================================================
  function loadHistory() {
    try {
      const raw = localStorage.getItem("skinintel_history");
      return raw ? JSON.parse(raw) : [];
    } catch (err) {
      console.error("Failed to load history", err);
      return [];
    }
  }

  function saveHistory(question, answer) {
    const history = loadHistory();
    history.push({ q: question, a: answer, ts: Date.now() });
    while (history.length > MAX_HISTORY) history.shift();
    localStorage.setItem("skinintel_history", JSON.stringify(history));
    renderHistory();
  }

  function deleteHistoryByTs(ts) {
    const filtered = loadHistory().filter((h) => h.ts !== ts);
    localStorage.setItem("skinintel_history", JSON.stringify(filtered));
    renderHistory();
  }

  // ============================================================
  // RENDER HISTORY
  // ============================================================
  function renderHistory() {
    if (!historyList) return;
    const history = loadHistory();
    historyList.innerHTML = "";

    if (!history.length) {
      const empty = document.createElement("div");
      empty.style.opacity = "0.7";
      empty.textContent = "No conversations yet";
      historyList.appendChild(empty);
      return;
    }

    [...history].reverse().forEach((item) => {
      const row = document.createElement("div");
      row.className = "history-item";
      row.setAttribute("data-ts", item.ts);

      const left = document.createElement("div");
      left.className = "history-left";
      const title = document.createElement("div");
      title.className = "history-title";
      title.textContent =
        (item.q || "").slice(0, 60) + (item.q && item.q.length > 60 ? "…" : "");
      title.style.color = "#000";
      title.style.whiteSpace = "nowrap";
      title.style.overflow = "hidden";
      title.style.textOverflow = "ellipsis";
      const meta = document.createElement("div");
      meta.className = "history-meta";
      meta.textContent = new Date(item.ts).toLocaleString();

      left.appendChild(title);
      left.appendChild(meta);

      const del = document.createElement("button");
      del.className = "del-btn";
      del.title = "Delete";
      del.innerHTML = "🗑️";
      del.addEventListener("click", (e) => {
        e.stopPropagation();
        showConfirm({
          title: "Delete conversation",
          message: "Are you sure you want to delete this conversation?",
          confirmText: "Delete",
          cancelText: "Cancel",
        }).then((ok) => {
          if (ok) deleteHistoryByTs(item.ts);
        });
      });

      row.appendChild(left);
      row.appendChild(del);
      row.addEventListener("click", () => showPopup(item.q, item.a));
      historyList.appendChild(row);
    });

    historyList.scrollTop = 0;
  }

  // ============================================================
  // CONVERSATION PREVIEW (modal)
  // ============================================================
  function createModal() {
    if (modalOverlay) return modalOverlay;

    modalOverlay = document.createElement("div");
    modalOverlay.id = "historyModalOverlay";
    Object.assign(modalOverlay.style, {
      position: "fixed",
      left: "0",
      top: "0",
      width: "100vw",
      height: "100vh",
      display: "none",
      justifyContent: "center",
      alignItems: "center",
      zIndex: "9999",
      background: "rgba(0,0,0,0.35)",
      backdropFilter: "blur(6px)",
      WebkitBackdropFilter: "blur(6px)",
    });

    const box = document.createElement("div");
    box.id = "historyModalBox";
    Object.assign(box.style, {
      width: "min(760px,92vw)",
      maxHeight: "84vh",
      overflowY: "auto",
      background: "#fff",
      borderRadius: "12px",
      padding: "18px 20px",
      boxShadow: "0 10px 30px rgba(0,0,0,0.2)",
      color: "#111",
    });

    const headerRow = document.createElement("div");
    headerRow.style.display = "flex";
    headerRow.style.justifyContent = "space-between";
    headerRow.style.alignItems = "center";
    headerRow.style.marginBottom = "10px";
    const title = document.createElement("div");
    title.innerText = "Conversation preview";
    title.style.fontWeight = "700";
    title.style.fontSize = "16px";

    const closeBtn = document.createElement("button");
    closeBtn.innerText = "Close";
    Object.assign(closeBtn.style, {
      padding: "6px 10px",
      borderRadius: "8px",
      border: "none",
      cursor: "pointer",
      background: "#eee",
    });

    headerRow.appendChild(title);
    headerRow.appendChild(closeBtn);

    const body = document.createElement("div");
    body.id = "historyModalBody";
    body.style.marginTop = "6px";
    body.style.color = "#111";

    const reaskBtn = document.createElement("button");
    reaskBtn.innerText = "Re-ask";
    Object.assign(reaskBtn.style, {
      marginTop: "12px",
      padding: "8px 12px",
      borderRadius: "8px",
      border: "none",
      background: "#0b66ff",
      color: "#fff",
      cursor: "pointer",
    });

    box.appendChild(headerRow);
    box.appendChild(body);
    box.appendChild(reaskBtn);
    modalOverlay.appendChild(box);
    document.body.appendChild(modalOverlay);

    closeBtn.addEventListener("click", hideModal);
    modalOverlay.addEventListener("click", (e) => {
      if (e.target === modalOverlay) hideModal();
    });

    reaskBtn.addEventListener("click", () => {
      const userEl = body.querySelector(".modal-user-text");
      if (userEl && userInput) {
        userInput.value = userEl.dataset.raw || userEl.innerText || "";
        userInput.focus();
      }
      hideModal();
    });

    return modalOverlay;
  }

  function showPopup(userText, botText) {
    const modal = createModal();
    const body = modal.querySelector("#historyModalBody");
    body.innerHTML = "";

    const userBlock = document.createElement("div");
    userBlock.className = "modal-user";
    userBlock.style.marginBottom = "12px";
    const uLabel = document.createElement("div");
    uLabel.innerText = "You:";
    uLabel.style.fontWeight = "600";
    uLabel.style.marginBottom = "6px";
    const uContent = document.createElement("div");
    uContent.className = "modal-user-text";
    uContent.dataset.raw = userText || "";
    uContent.innerHTML =
      typeof marked !== "undefined"
        ? marked.parse(escapeMarkdown(userText || ""))
        : `<div style="white-space:pre-wrap;">${escapeHTML(
            userText || ""
          )}</div>`;
    userBlock.appendChild(uLabel);
    userBlock.appendChild(uContent);

    const botBlock = document.createElement("div");
    botBlock.className = "modal-bot";
    botBlock.style.marginTop = "8px";
    const bLabel = document.createElement("div");
    bLabel.innerText = "Bot:";
    bLabel.style.fontWeight = "600";
    bLabel.style.marginBottom = "6px";
    const bContent = document.createElement("div");
    bContent.innerHTML =
      typeof marked !== "undefined"
        ? marked.parse(escapeMarkdown(botText || ""))
        : `<div style="white-space:pre-wrap;">${escapeHTML(
            botText || ""
          )}</div>`;
    botBlock.appendChild(bLabel);
    botBlock.appendChild(bContent);

    body.appendChild(userBlock);
    body.appendChild(botBlock);
    modal.style.display = "flex";
    document.body.style.overflow = "hidden";
  }

  function hideModal() {
    if (!modalOverlay) return;
    modalOverlay.style.display = "none";
    document.body.style.overflow = "";
  }

  // ============================================================
  // CUSTOM CONFIRM MODAL (glassy)
  // ============================================================
  function ensureConfirmModal() {
    if (confirmOverlay) return confirmOverlay;

    confirmOverlay = document.createElement("div");
    confirmOverlay.id = "customConfirmOverlay";
    Object.assign(confirmOverlay.style, {
      position: "fixed",
      left: "0",
      top: "0",
      width: "100vw",
      height: "100vh",
      display: "none",
      justifyContent: "center",
      alignItems: "center",
      zIndex: "10000",
      background: "rgba(0,0,0,0.32)",
      backdropFilter: "blur(4px)",
    });

    const card = document.createElement("div");
    Object.assign(card.style, {
      width: "min(520px,92vw)",
      background: "rgba(255,255,255,0.06)",
      borderRadius: "12px",
      padding: "18px",
      boxShadow: "0 10px 30px rgba(0,0,0,0.25)",
      backdropFilter: "blur(12px)",
      WebkitBackdropFilter: "blur(12px)",
      border: "1px solid rgba(255,255,255,0.12)",
      color: "#fff",
    });

    const t = document.createElement("div");
    t.id = "confirmTitle";
    t.style.fontWeight = "700";
    t.style.fontSize = "18px";
    t.style.marginBottom = "8px";
    const m = document.createElement("div");
    m.id = "confirmMessage";
    m.style.marginBottom = "14px";
    m.style.opacity = "0.95";

    const actions = document.createElement("div");
    actions.style.display = "flex";
    actions.style.gap = "10px";
    actions.style.justifyContent = "flex-end";
    const cancelBtn = document.createElement("button");
    cancelBtn.id = "confirmCancel";
    cancelBtn.innerText = "Cancel";
    Object.assign(cancelBtn.style, {
      padding: "8px 12px",
      borderRadius: "8px",
      border: "none",
      cursor: "pointer",
      background: "rgba(255,255,255,0.12)",
      color: "#fff",
    });
    const confirmBtn = document.createElement("button");
    confirmBtn.id = "confirmOk";
    confirmBtn.innerText = "Continue";
    Object.assign(confirmBtn.style, {
      padding: "8px 12px",
      borderRadius: "8px",
      border: "none",
      cursor: "pointer",
      background: "#0b66ff",
      color: "#fff",
    });

    actions.appendChild(cancelBtn);
    actions.appendChild(confirmBtn);
    card.appendChild(t);
    card.appendChild(m);
    card.appendChild(actions);
    confirmOverlay.appendChild(card);
    document.body.appendChild(confirmOverlay);

    cancelBtn.addEventListener("click", () => {
      confirmOverlay.dataset.action = "cancelled";
      hideConfirm();
    });
    confirmBtn.addEventListener("click", () => {
      confirmOverlay.dataset.action = "confirmed";
      hideConfirm();
    });
    confirmOverlay.addEventListener("click", (e) => {
      if (e.target === confirmOverlay) {
        confirmOverlay.dataset.action = "cancelled";
        hideConfirm();
      }
    });

    return confirmOverlay;
  }

  // showConfirm returns Promise<boolean>
  function showConfirm({
    title = "Confirm",
    message = "",
    confirmText = "Continue",
    cancelText = "Cancel",
  } = {}) {
    const overlay = ensureConfirmModal();
    const t = overlay.querySelector("#confirmTitle");
    const m = overlay.querySelector("#confirmMessage");
    const ok = overlay.querySelector("#confirmOk");
    const cancel = overlay.querySelector("#confirmCancel");

    t.innerText = title;
    m.innerText = message;
    ok.innerText = confirmText;
    cancel.innerText = cancelText;
    overlay.style.display = "flex";
    document.body.style.overflow = "hidden";

    return new Promise((resolve) => {
      overlay.dataset.action = "";
      const observer = new MutationObserver(() => {
        const action = overlay.dataset.action;
        if (!action) return;
        observer.disconnect();
        resolve(action === "confirmed");
      });
      observer.observe(overlay, {
        attributes: true,
        attributeFilter: ["data-action"],
      });
    });
  }

  function hideConfirm() {
    if (!confirmOverlay) return;
    confirmOverlay.style.display = "none";
    document.body.style.overflow = "";
  }

  // ============================================================
  // BIND CLEAR ALL
  // ============================================================
  function bindClearAll() {
    if (!clearHistoryBtn) return;
    clearHistoryBtn.addEventListener("click", async () => {
      const ok = await showConfirm({
        title: "Clear all history",
        message: "Delete ALL conversation history? This cannot be undone.",
        confirmText: "Delete",
        cancelText: "Cancel",
      });
      if (!ok) return;
      localStorage.removeItem("skinintel_history");
      renderHistory();
    });
  }

  // ============================================================
  // HOSPITAL BUTTON: confirm -> open maps (geolocation fallback)
  // ============================================================
  function bindHospitalBtn() {
    if (!hospitalBtn) return;

    hospitalBtn.addEventListener("click", () => {
      const privacyBanner = document.getElementById("privacyBanner");

      // Slide-down privacy banner
      privacyBanner.classList.add("active");
    });
  }

  // ============================================================
  // append inline map card (optional)
  // ============================================================
  function appendMapCard(query, lat = null, lon = null) {
    const qEncoded = encodeURIComponent(query);
    const iframeSrc =
      lat !== null && lon !== null
        ? `https://www.google.com/maps?q=${qEncoded}&ll=${lat},${lon}&z=14&output=embed`
        : `https://www.google.com/maps?q=${qEncoded}&z=12&output=embed`;
    const mapsSearchUrl =
      lat !== null && lon !== null
        ? `https://www.google.com/maps/search/${qEncoded}/@${lat},${lon},14z`
        : `https://www.google.com/maps/search/${qEncoded}`;

    const cardHTML = `\n    <div class="map-card">\n      <div class="map-iframe-wrap">\n        <iframe src="${iframeSrc}" loading="lazy" allowfullscreen referrerpolicy="no-referrer-when-downgrade"></iframe>\n      </div>\n      <div class="map-card-body">\n        <div style=\"display:flex;justify-content:space-between;align-items:center;\">\n          <strong>🏥 Nearby Skin Hospitals</strong>\n          <a href="${mapsSearchUrl}" class="map-open-link" target="_blank">📍 Open in Google Maps</a>\n        </div>\n      </div>\n    </div>\n    `;

    appendMessage("bot", cardHTML, true);

    setTimeout(() => {
      const btn = chatBox.querySelector(".map-refresh-btn:last-of-type");
      if (!btn) return;
      btn.addEventListener("click", () => {
        if (!navigator.geolocation) {
          appendMessage("bot", "🚫 Geolocation not supported.");
          return;
        }
        appendMessage("bot", "🔍 Refreshing location and maps...");
        navigator.geolocation.getCurrentPosition(
          (p) => appendMapCard(query, p.coords.latitude, p.coords.longitude),
          () => appendMessage("bot", "⚠️ Could not refresh location."),
          { timeout: 15000 }
        );
      });
    }, 100);
  }

  // ============================================================
  // optional: fetch nearby places from backend
  // ============================================================
  async function tryFetchNearbyPlaces(lat, lon, q) {
    if (!backendUrl) return;
    const url = `${backendUrl.replace(
      /\/$/,
      ""
    )}/places?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(
      lon
    )}&q=${encodeURIComponent(q)}`;
    try {
      const res = await fetch(url, { method: "GET" });
      if (!res.ok) return;
      const list = await res.json();
      if (!Array.isArray(list) || !list.length) return;

      const container = document.createElement("div");
      container.classList.add("bot-message", "places-list");
      container.innerHTML = `<div style="font-weight:600;margin-bottom:6px;">Top nearby clinics (from backend)</div>\n        <ul style="margin:0 0 8px 18px;">\n          ${list
        .slice(0, 5)
        .map(
          (p) =>
            `<li style="margin-bottom:6px;">\n            <strong>${escapeHTML(
              p.name
            )}</strong> ${
              p.rating ? `— ⭐ ${escapeHTML(String(p.rating))}` : ""
            }\n            <div style="font-size:13px;color:#444">${escapeHTML(
              p.address || ""
            )}</div>\n            ${
              p.maps_url
                ? `<div style="margin-top:4px;"><a href="${p.maps_url}" target="_blank">Open in Maps</a></div>`
                : ""
            }\n          </li>`
        )
        .join("")}\n        </ul>\n      `;
      chatBox.appendChild(container);
      chatBox.scrollTop = chatBox.scrollHeight;
    } catch (err) {
      console.debug("tryFetchNearbyPlaces failed:", err);
    }
  }

  // ============================================================
  // UTILITIES
  // ============================================================
  function escapeHTML(s) {
    return String(s || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }
  function stripHTML(html) {
    const tmp = document.createElement("div");
    tmp.innerHTML = html || "";
    return (tmp.textContent || tmp.innerText || "").trim();
  }
  function escapeMarkdown(md) {
    return String(md || "");
  }
})();
