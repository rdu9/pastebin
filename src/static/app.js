const API = "/api/v1";
const PAGE_SIZE = 20;
const MAX_PASTE_BYTES = 512 * 1024;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const MAX_IMAGES = 10;
const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"];

const state = { me: null, pendingImages: {}, afterLogin: "#/" };
const view = document.getElementById("view");
const encoder = new TextEncoder();

/* ---------- helpers ---------- */

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (value !== false && value != null) node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function toast(message) {
  const box = document.getElementById("toast");
  box.textContent = message;
  box.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => box.classList.remove("show"), 3400);
}

async function errorMessage(response) {
  if (response.status === 429) {
    const wait = response.headers.get("Retry-After");
    return wait ? `Too many requests. Try again in ${wait}s.` : "Too many requests. Slow down a little.";
  }
  try {
    const data = await response.json();
    if (data.message) return data.message;
    if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg.replace(/^Value error, /, "")).join(", ");
    if (typeof data.detail === "string") return data.detail;
  } catch {}
  return `Request failed (${response.status})`;
}

async function api(method, path, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(API + path, options);
  if (!response.ok) {
    const error = new Error(await errorMessage(response));
    error.status = response.status;
    throw error;
  }
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "";
}

function timeAgo(value) {
  const seconds = Math.round((Date.now() - new Date(value)) / 1000);
  const units = [["year", 31536000], ["month", 2592000], ["day", 86400], ["hour", 3600], ["minute", 60]];
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return rtf.format(-Math.round(seconds / size), unit);
  }
  return "just now";
}

function timeUntil(value) {
  const seconds = Math.round((new Date(value) - Date.now()) / 1000);
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (seconds >= 86400) return rtf.format(Math.round(seconds / 86400), "day");
  if (seconds >= 3600) return rtf.format(Math.round(seconds / 3600), "hour");
  return rtf.format(Math.max(1, Math.round(seconds / 60)), "minute");
}

async function copy(text, label) {
  try {
    await navigator.clipboard.writeText(text);
    toast(`${label} copied`);
  } catch {
    toast("Copy failed. Select and copy manually.");
  }
}

function setActiveNav(name) {
  document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("active", a.dataset.nav === name));
}

function loading() {
  view.replaceChildren(el("section", { class: "card" }, el("div", { class: "skeleton", style: "width:40%" }), el("div", { class: "skeleton" }), el("div", { class: "skeleton", style: "width:75%" })));
}

/* ---------- auth state ---------- */

async function refreshMe() {
  try {
    state.me = await api("GET", "/auth/me");
  } catch {
    state.me = null;
  }
  document.body.classList.toggle("logged-in", !!state.me);
  document.getElementById("user-email").textContent = state.me ? state.me.email : "";
}

document.getElementById("logout-btn").addEventListener("click", async () => {
  try {
    await api("POST", "/auth/logout");
  } catch {}
  await refreshMe();
  toast("Logged out");
  location.hash = "#/";
});

/* ---------- lightbox ---------- */

const lightbox = document.getElementById("lightbox");
function openLightbox(src) {
  lightbox.querySelector("img").src = src;
  lightbox.hidden = false;
}
function closeLightbox() {
  lightbox.hidden = true;
  lightbox.querySelector("img").removeAttribute("src");
}
lightbox.addEventListener("click", closeLightbox);
document.addEventListener("keydown", (e) => e.key === "Escape" && !lightbox.hidden && closeLightbox());

/* ---------- image upload ---------- */

function putToStorage(url, fields, file, onProgress) {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    for (const [key, value] of Object.entries(fields)) form.append(key, value);
    form.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error("storage rejected the file")));
    xhr.onerror = () => reject(new Error("could not reach storage (CORS?)"));
    xhr.send(form);
  });
}

async function uploadImage(pasteUid, item, onProgress) {
  const ticket = await api("POST", "/images/upload-url", {
    paste_uid: pasteUid,
    content_type: item.file.type,
    size_bytes: item.file.size,
  });
  await putToStorage(ticket.url, ticket.fields, item.file, onProgress);
  await api("POST", `/images/${ticket.image_uid}/complete`);
}

/* ---------- new paste ---------- */

function renderNew() {
  setActiveNav("new");
  view.replaceChildren(document.getElementById("tpl-new").content.cloneNode(true));

  const form = document.getElementById("paste-form");
  const textarea = form.elements.content;
  const submit = form.querySelector('button[type="submit"]');
  const byteCount = document.getElementById("byte-count");
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const fileList = document.getElementById("file-list");
  const privateOption = form.elements.visibility.querySelector('option[value="private"]');

  privateOption.disabled = !state.me;
  let files = [];
  let nextId = 0;

  function updateBytes() {
    const size = encoder.encode(textarea.value).length;
    byteCount.textContent = `${formatBytes(size)} / 512 KB`;
    byteCount.classList.toggle("over", size > MAX_PASTE_BYTES);
    submit.disabled = !textarea.value.trim() || size > MAX_PASTE_BYTES;
  }

  function validate(file, index) {
    if (!IMAGE_TYPES.includes(file.type)) return "unsupported type";
    if (file.size > MAX_IMAGE_BYTES) return `too large (${formatBytes(file.size)})`;
    if (index >= MAX_IMAGES) return `max ${MAX_IMAGES} images`;
    return null;
  }

  function addFiles(list) {
    for (const file of list) {
      const duplicate = files.some((f) => f.file.name === file.name && f.file.size === file.size && f.file.lastModified === file.lastModified);
      if (duplicate) continue;
      const accepted = files.filter((f) => f.status !== "rejected").length;
      const reason = validate(file, accepted);
      files.push({
        id: nextId++,
        file,
        preview: IMAGE_TYPES.includes(file.type) ? URL.createObjectURL(file) : null,
        status: reason ? "rejected" : "ready",
        reason,
        progress: 0,
      });
    }
    renderFiles();
  }

  function removeFile(id) {
    const item = files.find((f) => f.id === id);
    if (item?.preview) URL.revokeObjectURL(item.preview);
    files = files.filter((f) => f.id !== id);
    renderFiles();
  }

  function statusText(item) {
    if (item.status === "rejected") return item.reason;
    if (item.status === "uploading") return `${Math.round(item.progress * 100)}%`;
    if (item.status === "done") return "uploaded";
    if (item.status === "failed") return item.reason;
    return formatBytes(item.file.size);
  }

  function renderFiles() {
    fileList.replaceChildren(
      ...files.map((item) =>
        el(
          "li",
          { class: item.status, "data-id": item.id },
          item.preview ? el("img", { src: item.preview, alt: "" }) : el("span"),
          el("div", { class: "file-name" }, el("span", {}, item.file.name)),
          el("span", { class: "file-status" }, statusText(item)),
          item.status === "uploading" || item.status === "done"
            ? el("span")
            : el("button", { type: "button", class: "remove", title: "Remove", onclick: () => removeFile(item.id) }, "×"),
          item.status === "uploading" && el("div", { class: "progress" }, el("span", { style: `width:${item.progress * 100}%` }))
        )
      )
    );
  }

  textarea.addEventListener("input", updateBytes);
  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Tab" && !e.shiftKey) {
      e.preventDefault();
      const { selectionStart: start, selectionEnd: end } = textarea;
      textarea.setRangeText("  ", start, end, "end");
      updateBytes();
    }
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && !submit.disabled) form.requestSubmit();
  });

  const burnBox = form.elements.burn_after_reading;
  burnBox.addEventListener("change", () => {
    dropzone.style.display = burnBox.checked ? "none" : "";
    fileList.style.display = burnBox.checked ? "none" : "";
  });

  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), fileInput.click()));
  fileInput.addEventListener("change", () => {
    addFiles(fileInput.files);
    fileInput.value = "";
  });
  ["dragenter", "dragover"].forEach((type) =>
    dropzone.addEventListener(type, (e) => {
      e.preventDefault();
      dropzone.classList.add("drag");
    })
  );
  ["dragleave", "drop"].forEach((type) => dropzone.addEventListener(type, () => dropzone.classList.remove("drag")));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    addFiles(e.dataTransfer.files);
  });
  form.addEventListener("paste", (e) => {
    const pasted = [...(e.clipboardData?.files || [])];
    if (pasted.length && state.me) {
      e.preventDefault();
      addFiles(pasted);
      toast(`${pasted.length} image${pasted.length > 1 ? "s" : ""} added from clipboard`);
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const toUpload = state.me && !burnBox.checked ? files.filter((f) => f.status === "ready") : [];
    const rejected = files.filter((f) => f.status === "rejected").length;
    if (rejected) toast(`${rejected} rejected file${rejected > 1 ? "s" : ""} will be skipped`);

    submit.disabled = true;
    submit.textContent = "Creating…";

    let paste;
    try {
      paste = await api("POST", "/pastes/", {
        title: form.elements.title.value.trim() || null,
        content: textarea.value,
        language: form.elements.language.value || null,
        visibility: form.elements.visibility.value,
        expires_in: form.elements.expires_in.value,
        burn_after_reading: form.elements.burn_after_reading.checked,
      });
    } catch (error) {
      toast(error.message);
      submit.textContent = "Create paste";
      updateBytes();
      return;
    }

    let uploaded = 0;
    for (const [i, item] of toUpload.entries()) {
      submit.textContent = `Uploading ${i + 1}/${toUpload.length}…`;
      item.status = "uploading";
      renderFiles();
      try {
        await uploadImage(paste.uid, item, (p) => {
          item.progress = p;
          const bar = fileList.querySelector(`[data-id="${item.id}"] .progress span`);
          const label = fileList.querySelector(`[data-id="${item.id}"] .file-status`);
          if (bar) bar.style.width = `${p * 100}%`;
          if (label) label.textContent = `${Math.round(p * 100)}%`;
        });
        item.status = "done";
        uploaded++;
      } catch (error) {
        item.status = "failed";
        item.reason = error.message;
      }
      renderFiles();
    }

    const failed = toUpload.length - uploaded;
    if (failed) toast(`${failed} image${failed > 1 ? "s" : ""} failed to upload`);
    if (uploaded) state.pendingImages[paste.uid] = uploaded;
    files.forEach((f) => f.preview && URL.revokeObjectURL(f.preview));
    location.hash = `#/p/${paste.uid}`;
  });

  updateBytes();
  textarea.focus();
}

/* ---------- paste view ---------- */

function codeBlock(content) {
  return el("pre", { class: "code" }, content.split("\n").map((line) => el("span", { class: "line" }, line || " ")));
}

function imageGrid(uids) {
  if (!uids.length) return null;
  return el(
    "div",
    { class: "images" },
    uids.map((uid) =>
      el("button", { type: "button", title: "Open", onclick: () => openLightbox(`/i/${uid}`) }, el("img", { src: `/i/${uid}?thumb=1`, alt: "", loading: "lazy" }))
    )
  );
}

async function renderPaste(uid) {
  setActiveNav(null);
  loading();

  let paste;
  try {
    paste = await api("GET", `/pastes/${uid}`);
  } catch (error) {
    view.replaceChildren(
      el(
        "section",
        { class: "card empty" },
        el("p", {}, error.status === 404 ? "This paste doesn't exist, has expired, or was already read." : error.message),
        el("a", { class: "btn ghost small", href: "#/" }, "Create a new paste")
      )
    );
    return;
  }

  const isOwner = state.me && paste.owner_uid === state.me.user_uid;
  const isBurn = paste.burn_after_reading;
  const link = `${location.origin}/#/p/${uid}`;

  const tags = el(
    "div",
    { class: "meta" },
    el("span", { class: "tag" }, paste.language || "plain text"),
    el("span", { class: "tag" }, paste.visibility),
    isBurn && el("span", { class: "tag light" }, "burn after reading"),
    el("span", { class: "tag" }, formatBytes(paste.size_bytes)),
    el("span", { class: "tag", title: formatDate(paste.created_at) }, timeAgo(paste.created_at)),
    paste.expires_at && el("span", { class: "tag", title: formatDate(paste.expires_at) }, `expires ${timeUntil(paste.expires_at)}`)
  );

  const actions = el("div", { class: "actions" });
  const body = el("div");

  async function deletePaste() {
    if (!confirm("Delete this paste and its images? This can't be undone.")) return;
    try {
      await api("DELETE", `/pastes/${uid}`);
      toast("Paste deleted");
      location.hash = "#/mine";
    } catch (error) {
      toast(error.message);
    }
  }

  const deleteButton = () => isOwner && el("button", { class: "btn ghost small danger", onclick: deletePaste }, "Delete");

  function showContent(content, burned) {
    body.replaceChildren(codeBlock(content));
    if (burned) body.append(el("p", { class: "notice" }, "This paste has been burned. Copy anything you need now — it's gone once you leave."));
    actions.replaceChildren(
      el("button", { class: "btn ghost small", onclick: () => copy(content, "Content") }, "Copy"),
      !burned && el("button", { class: "btn ghost small", onclick: () => copy(link, "Link") }, "Copy link"),
      !isBurn && el("a", { class: "btn ghost small", href: `${API}/pastes/${uid}/raw`, target: "_blank" }, "Raw"),
      !burned && deleteButton()
    );
  }

  if (isBurn && paste.content == null) {
    actions.replaceChildren(el("button", { class: "btn ghost small", onclick: () => copy(link, "Link") }, "Copy link"), deleteButton());
    body.replaceChildren(
      el(
        "div",
        { class: "burn" },
        el("p", {}, el("strong", {}, "This paste burns after reading."), "Once you reveal it, it's deleted for everyone."),
        el("button", {
          class: "btn",
          onclick: async (event) => {
            if (!confirm("Reveal now? Nobody will be able to open it again.")) return;
            event.target.disabled = true;
            try {
              const revealed = await api("POST", `/pastes/${uid}/reveal`);
              showContent(revealed.content, true);
            } catch (error) {
              toast(error.status === 404 ? "Someone else already read it." : error.message);
              event.target.disabled = false;
            }
          },
        }, "Reveal")
      )
    );
  } else {
    showContent(paste.content, false);
  }

  const gallery = el("div");
  gallery.replaceChildren(imageGrid(paste.images || []) || "");

  view.replaceChildren(
    el("section", { class: "card" }, el("div", { class: "paste-head" }, el("div", {}, el("h1", {}, paste.title || "Untitled"), tags), actions), body, gallery)
  );

  const expected = state.pendingImages[uid] || 0;
  if (expected > (paste.images || []).length) {
    const notice = el("p", { class: "notice" }, `Processing ${expected} image${expected > 1 ? "s" : ""}…`);
    gallery.append(notice);
    let tries = 0;
    const poll = async () => {
      tries++;
      let fresh;
      try {
        fresh = await api("GET", `/pastes/${uid}`);
      } catch {
        return;
      }
      const ready = fresh.images.length;
      gallery.replaceChildren(imageGrid(fresh.images) || "");
      if (ready >= expected) {
        delete state.pendingImages[uid];
        return;
      }
      if (tries >= 8) {
        delete state.pendingImages[uid];
        const missing = expected - ready;
        gallery.append(el("p", { class: "notice" }, `${missing} image${missing > 1 ? "s" : ""} couldn't be processed (not a valid image, or the worker is down).`));
        return;
      }
      gallery.append(notice);
      setTimeout(poll, 1500);
    };
    setTimeout(poll, 1000);
  }
}

/* ---------- lists ---------- */

async function renderList(kind, page) {
  const mine = kind === "mine";
  setActiveNav(kind);

  if (mine && !state.me) {
    state.afterLogin = location.hash;
    location.hash = "#/login";
    return;
  }

  loading();

  let items;
  try {
    items = await api("GET", mine ? `/pastes/me/pastes?page=${page}` : `/pastes/?page=${page}`);
  } catch (error) {
    view.replaceChildren(el("section", { class: "card empty" }, error.message));
    return;
  }

  const list = items.length
    ? el(
        "ul",
        { class: "list" },
        items.map((p) =>
          el(
            "li",
            {},
            el(
              "a",
              { href: `#/p/${p.uid}` },
              el("span", { class: "title" }, p.title || "Untitled"),
              el("span", { class: "sub", title: formatDate(p.created_at) }, `${p.language || "plain text"} · ${formatBytes(p.size_bytes)} · ${timeAgo(p.created_at)}`)
            )
          )
        )
      )
    : el(
        "div",
        { class: "empty" },
        el("p", {}, mine ? "You haven't created any pastes yet." : "No public pastes yet."),
        el("a", { class: "btn ghost small", href: "#/" }, "Create one")
      );

  const base = mine ? "#/mine" : "#/public";
  const pager =
    page > 1 || items.length === PAGE_SIZE
      ? el(
          "div",
          { class: "pager" },
          page > 1 ? el("a", { class: "btn ghost small", href: `${base}?page=${page - 1}` }, "← Newer") : el("span"),
          el("span", { class: "muted" }, `Page ${page}`),
          items.length === PAGE_SIZE ? el("a", { class: "btn ghost small", href: `${base}?page=${page + 1}` }, "Older →") : el("span")
        )
      : null;

  view.replaceChildren(el("section", { class: "card" }, el("h1", {}, mine ? "My pastes" : "Public pastes"), list, pager));
}

/* ---------- auth pages ---------- */

function renderAuth(mode) {
  setActiveNav(null);
  if (state.me) {
    location.hash = "#/";
    return;
  }
  const isLogin = mode === "login";

  const form = el(
    "form",
    {},
    el("input", { name: "email", type: "email", placeholder: "Email", required: true, autocomplete: "email" }),
    el("input", {
      name: "password",
      type: "password",
      placeholder: isLogin ? "Password" : "Password (at least 8 characters)",
      required: true,
      minlength: isLogin ? false : "8",
      autocomplete: isLogin ? "current-password" : "new-password",
    }),
    el("button", { type: "submit", class: "btn" }, isLogin ? "Log in" : "Create account")
  );

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const button = form.querySelector("button");
    button.disabled = true;
    const credentials = { email: form.elements.email.value.trim(), password: form.elements.password.value };
    try {
      if (!isLogin) await api("POST", "/auth/register", credentials);
      await api("POST", "/auth/login", credentials);
      await refreshMe();
      toast(isLogin ? "Welcome back" : "Account created");
      const target = state.afterLogin;
      state.afterLogin = "#/";
      location.hash = target;
    } catch (error) {
      toast(error.message);
      button.disabled = false;
    }
  });

  view.replaceChildren(
    el(
      "section",
      { class: "card auth-box" },
      el("h1", {}, isLogin ? "Log in" : "Sign up"),
      form,
      el("p", {}, isLogin ? "No account? " : "Already have one? ", el("a", { href: isLogin ? "#/register" : "#/login" }, isLogin ? "Sign up" : "Log in"))
    )
  );
  form.elements.email.focus();
}

/* ---------- router ---------- */

function route() {
  closeLightbox();
  window.scrollTo(0, 0);
  const [path, query] = location.hash.replace(/^#/, "").split("?");
  const page = Math.max(1, parseInt(new URLSearchParams(query).get("page") || "1", 10));
  const pasteMatch = path.match(/^\/p\/([0-9a-f-]{36})$/i);

  if (pasteMatch) return renderPaste(pasteMatch[1]);
  if (path === "/public") return renderList("public", page);
  if (path === "/mine") return renderList("mine", page);
  if (path === "/login") return renderAuth("login");
  if (path === "/register") return renderAuth("register");
  return renderNew();
}

window.addEventListener("hashchange", route);
refreshMe().then(route);
