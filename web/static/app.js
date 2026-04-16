// LibMate AI — front-end glue (vanilla, single page)

const API = "/api";
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

let CURRENT_BOOK = null;
const WALL = []; // visualizations created during this session

// ------------ boot ------------
document.addEventListener("DOMContentLoaded", async () => {
  await loadLibrary();
  bindModal();
  bindTabs();
  bindActions();
  bindUpload();
  bindChatbot();
  bindReaderZoom();
  bindMicButtons();
  bindAuth();
  applyRoute();
});

// ------------ routing ------------
// Each route shows only the matching <section> (and hides the others),
// so URLs behave like real pages, not in-page anchors.
const ROUTE_SECTIONS = {
  "/": [".hero", "#library"],
  "/library": [".hero", "#library"],
  "/wall": ["#wall"],
  "/me": ["#me"],
  "/about": ["#about"],
};
const ALL_SECTIONS = [".hero", "#library", "#wall", "#me", "#about"];

function applyRoute() {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  const activeSelectors = ROUTE_SECTIONS[path] || ROUTE_SECTIONS["/"];

  // Show active sections, hide the rest.
  ALL_SECTIONS.forEach((sel) => {
    const el = document.querySelector(sel);
    if (!el) return;
    if (activeSelectors.includes(sel)) el.removeAttribute("data-route-hidden");
    else el.setAttribute("data-route-hidden", "");
  });

  // Mark the active nav link (home "/" has no data-route entry).
  $$(".nav-link[data-route]").forEach((a) => {
    a.classList.toggle("active", a.getAttribute("data-route") === path);
  });

  // Every route lands at the top of the "page".
  window.scrollTo({ top: 0, behavior: "instant" });

  // Update the tab title to reflect the current page.
  const titles = {
    "/": "LibMate AI · Thư viện PTIT",
    "/library": "Thư viện · LibMate AI",
    "/wall": "Tường tranh · LibMate AI",
    "/me": "Trang cá nhân · LibMate AI",
    "/about": "Giới thiệu · LibMate AI",
  };
  document.title = titles[path] || titles["/"];

  if (path === "/me") loadProfile();
}

// ------------ library ------------
async function loadLibrary() {
  const grid = $("#books-grid");
  try {
    const res = await fetch(`${API}/library/books`);
    const data = await res.json();
    const books = data.books || [];
    grid.innerHTML = "";
    if (!books.length) {
      grid.innerHTML = `<p class="muted">Chưa có sách nào. Chạy <code>python -m scripts.ingest_ptit</code> để seed dữ liệu mẫu.</p>`;
      updateHero(books, 0);
      return;
    }
    books.forEach((b) => grid.appendChild(bookCard(b)));
    updateHero(books, books.reduce((sum, b) => sum + (b.num_chapters || 0), 0));
  } catch (e) {
    grid.innerHTML = `<p class="muted">Không tải được thư viện: ${e}</p>`;
  }
}

function updateHero(books, chunkCount) {
  const statBooks = $("#stat-books");
  const statChunks = $("#stat-chunks");
  if (statBooks) statBooks.textContent = books.length;
  if (statChunks) statChunks.textContent = chunkCount || "—";

  const stack = $("#hero-stack");
  if (!stack) return;
  // Pick 3 books with cover images, prefer Google Books covers (likely real book covers)
  const withCovers = books.filter((b) => b.cover_url);
  const picks = (withCovers.length >= 3 ? withCovers : books).slice(0, 3);
  stack.innerHTML = "";
  picks.forEach((b) => {
    const card = document.createElement("div");
    card.className = "hero-stack-card";
    if (b.cover_url) {
      const img = document.createElement("img");
      img.src = b.cover_url;
      img.alt = b.title;
      img.loading = "eager";
      card.appendChild(img);
    } else {
      card.innerHTML = `<div class="cover-emoji-fallback">${b.cover_emoji || "📚"}</div>`;
    }
    stack.appendChild(card);
  });
}

function bookCard(b) {
  const el = document.createElement("article");
  el.className = "book-card revealed";
  const cover = b.cover_url
    ? `<div class="cover-img"><img src="${escape(b.cover_url)}" alt="${escape(b.title)}" loading="lazy"
         onerror="this.parentElement.innerHTML='<span class=\\'cover-emoji-fallback\\'>${b.cover_emoji || "📚"}</span>';"/></div>`
    : `<div class="cover-emoji">${b.cover_emoji || "📚"}</div>`;
  const favActive = FAVORITE_IDS.has(b.id) ? " active" : "";
  el.innerHTML = `
    ${cover}
    <button type="button" class="fav-btn${favActive}" data-book-id="${b.id}" aria-label="Yêu thích" title="Yêu thích">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M12 17.3 5.5 21l1.7-7.4L1.5 8.6l7.5-.7L12 1l3 6.9 7.5.7-5.7 5 1.7 7.4z"/></svg>
    </button>
    <h3>${escape(b.title)}</h3>
    <div class="authors">${(b.authors || []).join(" · ")}</div>
    <p class="summary">${escape(b.ai_summary || "")}</p>
    <div class="meta">
      <span class="difficulty">${b.category || "Sách"} · Cấp ${b.difficulty || "?"}</span>
      <span class="open-hint">Mở →</span>
    </div>
  `;
  el.querySelector(".fav-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    toggleFavorite(b.id, e.currentTarget);
  });
  el.addEventListener("click", () => openReader(b));
  return el;
}

async function toggleFavorite(bookId, btn) {
  if (!AUTH.token()) {
    $("#btn-open-auth")?.click();
    return;
  }
  const isFav = FAVORITE_IDS.has(bookId);
  const method = isFav ? "DELETE" : "POST";
  try {
    const res = await authFetch(`${API}/me/favorites/${bookId}`, { method });
    if (!res.ok) return;
    if (isFav) FAVORITE_IDS.delete(bookId);
    else FAVORITE_IDS.add(bookId);
    document.querySelectorAll(`.fav-btn[data-book-id="${bookId}"]`).forEach((b) => {
      b.classList.toggle("active", FAVORITE_IDS.has(bookId));
    });
  } catch (e) {}
}

// ------------ modal ------------
function bindModal() {
  $$("[data-close]").forEach((el) =>
    el.addEventListener("click", () => $("#reader-modal").setAttribute("hidden", ""))
  );
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") $("#reader-modal").setAttribute("hidden", "");
  });
}

function openReader(book) {
  CURRENT_BOOK = book;
  $("#reader-modal").removeAttribute("hidden");
  const coverEl = $("#reader-cover");
  if (book.cover_url) {
    coverEl.innerHTML = `<img src="${escape(book.cover_url)}" alt="${escape(book.title)}"
      onerror="this.parentElement.textContent='${book.cover_emoji || "📚"}';"/>`;
  } else {
    coverEl.textContent = book.cover_emoji || "📚";
  }
  $("#reader-cat").textContent = book.category || "Sách";
  $("#reader-title").textContent = book.title;
  $("#reader-authors").textContent = (book.authors || []).join(" · ");

  // reset panels
  $("#chat-log").innerHTML = `<p class="muted">Hỏi LibMate bất cứ điều gì về cuốn sách này. Mọi câu trả lời đều kèm trích dẫn.</p>`;
  $("#summary-out").innerHTML = "";
  $("#quiz-out").innerHTML = "";
  $("#flash-out").innerHTML = "";
  $("#viz-out").innerHTML = "";
  $("#viz-input").value = "";
  // reset gen forms so each book starts clean
  const qt = $("#quiz-topic"); if (qt) qt.value = "";
  const qc = $("#quiz-count"); if (qc) qc.value = 5;
  const ft = $("#flash-topic"); if (ft) ft.value = "";
  const fc = $("#flash-count"); if (fc) fc.value = 6;

  // Reset PDF.js reader state — will (re)load on first Đọc sách tab open
  READER_STATE.bookId = null;
  READER_STATE.pdf = null;
  if (READER_STATE.observer) {
    READER_STATE.observer.disconnect();
    READER_STATE.observer = null;
  }
  const pagesEl = $("#reader-pages");
  if (pagesEl) pagesEl.innerHTML = "";
  const statusEl = $("#reader-status");
  if (statusEl) {
    statusEl.hidden = false;
    statusEl.classList.remove("error");
    statusEl.textContent = "Mở tab 'Đọc sách' để bắt đầu.";
  }
  const pageInfo = $("#reader-pageinfo");
  if (pageInfo) pageInfo.textContent = "—";
  const dl = $("#reader-download");
  if (dl) dl.href = `${API}/library/books/${book.id}/file`;

  switchTab("summary");

  if (AUTH.token()) {
    authFetch(`${API}/me/history`, {
      method: "POST",
      body: JSON.stringify({ book_id: book.id, tab: "summary" }),
    }).catch(() => {});
  }
}

// ------------ tabs ------------
function bindTabs() {
  $$(".tab").forEach((t) => t.addEventListener("click", () => switchTab(t.dataset.tab)));
}
function switchTab(name) {
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  $$(".tab-panel").forEach((p) => {
    if (p.dataset.panel === name) p.removeAttribute("hidden");
    else p.setAttribute("hidden", "");
  });
  if (name === "read") loadReaderFrame();
}

// --- PDF.js lazy loader ---
const PDFJS_VERSION = "4.6.82";
let _pdfjsPromise = null;
function getPdfJs() {
  if (_pdfjsPromise) return _pdfjsPromise;
  _pdfjsPromise = import(
    /* webpackIgnore: true */ `https://cdn.jsdelivr.net/npm/pdfjs-dist@${PDFJS_VERSION}/build/pdf.mjs`
  ).then((lib) => {
    lib.GlobalWorkerOptions.workerSrc = `https://cdn.jsdelivr.net/npm/pdfjs-dist@${PDFJS_VERSION}/build/pdf.worker.mjs`;
    return lib;
  });
  return _pdfjsPromise;
}

// PDF.js reader state
let READER_STATE = {
  bookId: null,
  pdf: null,
  observer: null,
  scale: 1.4,
  maxPages: 50,
};

async function loadReaderFrame() {
  if (!CURRENT_BOOK) return;
  const pagesEl = $("#reader-pages");
  const statusEl = $("#reader-status");
  const pageInfo = $("#reader-pageinfo");
  if (!pagesEl || !statusEl) return;

  // only (re)load if book changed
  if (READER_STATE.bookId === CURRENT_BOOK.id && READER_STATE.pdf) return;

  // reset viewer
  if (READER_STATE.observer) {
    READER_STATE.observer.disconnect();
    READER_STATE.observer = null;
  }
  pagesEl.innerHTML = "";
  statusEl.hidden = false;
  statusEl.classList.remove("error");
  statusEl.textContent = "Đang tải sách...";
  READER_STATE.bookId = CURRENT_BOOK.id;
  READER_STATE.pdf = null;

  try {
    const pdfjsLib = await getPdfJs();
    const url = `${API}/library/books/${CURRENT_BOOK.id}/file`;
    const loadingTask = pdfjsLib.getDocument({
      url,
      // don't let PDF.js abort on missing fonts etc.
      disableFontFace: false,
    });
    loadingTask.onProgress = (p) => {
      if (p && p.total) {
        const pct = Math.round((p.loaded / p.total) * 100);
        statusEl.textContent = `Đang tải sách... ${pct}%`;
      }
    };
    const pdf = await loadingTask.promise;
    READER_STATE.pdf = pdf;

    const total = pdf.numPages;
    const cap = Math.min(total, READER_STATE.maxPages);
    if (pageInfo)
      pageInfo.textContent =
        total > cap
          ? `Trang 1–${cap} / ${total} (chỉ xem ${cap} trang đầu)`
          : `${total} trang`;

    // Measure page 1 to get an aspect ratio for placeholder sizing
    const firstPage = await pdf.getPage(1);
    const fvp = firstPage.getViewport({ scale: READER_STATE.scale });
    const aspect = fvp.height / fvp.width;

    // Create placeholders for all capped pages; render lazily on scroll
    for (let i = 1; i <= cap; i++) {
      const wrap = document.createElement("div");
      wrap.className = "pdf-page-wrap";
      wrap.dataset.pageNum = String(i);
      // give each placeholder an approximate size so scrollbar looks right
      wrap.style.width = "min(820px, 96%)";
      wrap.style.aspectRatio = `${fvp.width} / ${fvp.height}`;
      const loading = document.createElement("div");
      loading.className = "pdf-page-loading";
      loading.textContent = `Trang ${i}`;
      wrap.appendChild(loading);
      const num = document.createElement("div");
      num.className = "pdf-page-num";
      num.textContent = `${i} / ${cap}`;
      wrap.appendChild(num);
      pagesEl.appendChild(wrap);
    }

    // Render first page immediately so user sees something right away
    await renderPdfPage(pdf, 1, pagesEl.querySelector('[data-page-num="1"]'));

    statusEl.hidden = true;

    // Lazy-render the rest using IntersectionObserver
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (!e.isIntersecting) return;
          const el = e.target;
          if (el.dataset.rendered === "true") return;
          el.dataset.rendered = "true";
          const n = parseInt(el.dataset.pageNum, 10);
          renderPdfPage(pdf, n, el);
          observer.unobserve(el);
        });
      },
      { root: $("#reader-viewer"), rootMargin: "400px 0px" }
    );
    pagesEl
      .querySelectorAll(".pdf-page-wrap")
      .forEach((el) => observer.observe(el));
    // mark page 1 as rendered so observer skips it
    const first = pagesEl.querySelector('[data-page-num="1"]');
    if (first) first.dataset.rendered = "true";
    READER_STATE.observer = observer;
  } catch (err) {
    console.error("PDF load failed", err);
    READER_STATE.bookId = null;
    statusEl.hidden = false;
    statusEl.classList.add("error");
    statusEl.textContent = "Không tải được sách: " + (err?.message || err);
  }
}

async function renderPdfPage(pdf, pageNum, wrapEl) {
  try {
    const page = await pdf.getPage(pageNum);
    const viewport = page.getViewport({ scale: READER_STATE.scale });
    const canvas = document.createElement("canvas");
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.floor(viewport.width * ratio);
    canvas.height = Math.floor(viewport.height * ratio);
    canvas.style.width = "100%";
    canvas.style.height = "auto";
    const ctx = canvas.getContext("2d");
    ctx.scale(ratio, ratio);
    await page.render({ canvasContext: ctx, viewport }).promise;
    // swap loading placeholder with canvas, keep page number badge
    const pageBadge = wrapEl.querySelector(".pdf-page-num");
    wrapEl.innerHTML = "";
    wrapEl.appendChild(canvas);
    if (pageBadge) wrapEl.appendChild(pageBadge);
  } catch (e) {
    console.error("Render page", pageNum, "failed", e);
  }
}

// Re-render everything at a new scale (after zoom change)
async function rerenderAllPages() {
  if (!READER_STATE.pdf) return;
  const pagesEl = $("#reader-pages");
  pagesEl.querySelectorAll(".pdf-page-wrap").forEach((el) => {
    el.dataset.rendered = "false";
    el.innerHTML = "";
    const loading = document.createElement("div");
    loading.className = "pdf-page-loading";
    loading.textContent = `Trang ${el.dataset.pageNum}`;
    el.appendChild(loading);
    const num = document.createElement("div");
    num.className = "pdf-page-num";
    num.textContent = `${el.dataset.pageNum}`;
    el.appendChild(num);
  });
  // render visible first, then let observer take care of the rest
  const first = pagesEl.querySelector('[data-page-num="1"]');
  if (first) {
    first.dataset.rendered = "true";
    await renderPdfPage(READER_STATE.pdf, 1, first);
  }
}

function bindReaderZoom() {
  const zv = $("#reader-zoom-value");
  const update = () => {
    if (zv) zv.textContent = `${Math.round(READER_STATE.scale * 100 / 1.4)}%`;
  };
  update();
  $("#reader-zoom-in")?.addEventListener("click", () => {
    READER_STATE.scale = Math.min(READER_STATE.scale + 0.25, 3);
    update();
    rerenderAllPages();
  });
  $("#reader-zoom-out")?.addEventListener("click", () => {
    READER_STATE.scale = Math.max(READER_STATE.scale - 0.25, 0.6);
    update();
    rerenderAllPages();
  });
}

// ------------ actions ------------
function bindActions() {
  $("#chat-form").addEventListener("submit", onAsk);
  $("#btn-summary").addEventListener("click", onSummary);
  $("#quiz-form").addEventListener("submit", (e) => { e.preventDefault(); onQuiz(); });
  $("#flash-form").addEventListener("submit", (e) => { e.preventDefault(); onFlash(); });
  $("#btn-viz").addEventListener("click", onVisualize);
}

async function onAsk(e) {
  e.preventDefault();
  const input = $("#chat-input");
  const q = input.value.trim();
  if (!q || !CURRENT_BOOK) return;
  input.value = "";

  const log = $("#chat-log");
  // wipe placeholder on first ask
  if (log.querySelector("p.muted")) log.innerHTML = "";

  const userEl = document.createElement("div");
  userEl.className = "chat-msg user";
  userEl.textContent = q;
  log.appendChild(userEl);
  log.scrollTop = log.scrollHeight;

  const loading = document.createElement("div");
  loading.className = "chat-msg ai loading";
  loading.textContent = "LibMate đang lật trang...";
  log.appendChild(loading);
  log.scrollTop = log.scrollHeight;

  try {
    const res = await fetch(`${API}/reader/${CURRENT_BOOK.id}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    const data = await res.json();
    loading.classList.remove("loading");
    loading.innerHTML = `
      <div>${escape(data.answer || "(trống)")}</div>
      ${
        (data.citations || []).length
          ? `<div class="citations">${data.citations
              .map(
                (c) =>
                  `<div class="cite-row"><span class="cite-tag">[${escape(c.chapter || "Đoạn")} · tr.${
                    c.page ?? "?"
                  }]</span> ${escape(c.excerpt || "")}</div>`
              )
              .join("")}</div>`
          : ""
      }
    `;
    log.scrollTop = log.scrollHeight;
  } catch (err) {
    loading.classList.remove("loading");
    loading.textContent = "Lỗi: " + err;
  }
}

async function onSummary() {
  const out = $("#summary-out");
  out.innerHTML = `<p class="loading">Đang tóm tắt...</p>`;
  try {
    const res = await fetch(`${API}/reader/${CURRENT_BOOK.id}/summary`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ length: "200 từ" }),
    });
    const data = await res.json();
    out.textContent = data.summary || "(trống)";
  } catch (e) {
    out.innerHTML = `<p class="muted">Lỗi: ${e}</p>`;
  }
}

async function onQuiz() {
  const out = $("#quiz-out");
  const topic = $("#quiz-topic")?.value.trim() || "";
  const n = clampCount($("#quiz-count")?.value, 5);
  out.innerHTML = `<p class="loading">Đang sinh ${n} câu quiz${topic ? ` về "${escape(topic)}"` : ""}...</p>`;
  try {
    const res = await fetch(`${API}/reader/${CURRENT_BOOK.id}/quiz`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ n, topic }),
    });
    const data = await res.json();
    const questions = data.questions || [];
    if (!questions.length) {
      out.innerHTML = `<p class="muted">Không sinh được câu hỏi.</p>`;
      return;
    }
    renderQuiz(out, questions);
  } catch (e) {
    out.innerHTML = `<p class="muted">Lỗi: ${e}</p>`;
  }
}

// Return "A" / "B" / "C" / "D" regardless of how the LLM phrased `answer`.
function normalizeQuizAnswer(answer, choices) {
  if (answer == null) return "A";
  const raw = String(answer).trim();
  // Case 1: single letter A-D (possibly with trailing punctuation)
  const m = raw.match(/^([A-D])\b/i);
  if (m) return m[1].toUpperCase();
  // Case 2: number 1-4 or 0-3
  const num = parseInt(raw, 10);
  if (!Number.isNaN(num)) {
    const idx = num >= 1 && num <= choices.length ? num - 1 : num;
    if (idx >= 0 && idx < choices.length) return String.fromCharCode(65 + idx);
  }
  // Case 3: full text of one of the choices — match by substring
  const norm = (s) => String(s).replace(/^\s*[A-D][.):]\s*/i, "").trim().toLowerCase();
  const target = norm(raw);
  for (let i = 0; i < choices.length; i++) {
    if (norm(choices[i]) === target) return String.fromCharCode(65 + i);
  }
  for (let i = 0; i < choices.length; i++) {
    if (norm(choices[i]).includes(target) || target.includes(norm(choices[i]))) {
      return String.fromCharCode(65 + i);
    }
  }
  // Fallback
  return "A";
}

function renderQuiz(container, questions) {
  container.innerHTML = "";
  const selections = new Array(questions.length).fill(null);

  // Normalize every question's answer to an index-based letter A/B/C/D.
  // LLMs sometimes return just "A", sometimes "A.", sometimes the full option text.
  questions.forEach((q) => {
    q.__letter = normalizeQuizAnswer(q.answer, q.choices || []);
  });

  questions.forEach((q, qi) => {
    const el = document.createElement("div");
    el.className = "quiz-q";
    const choices = (q.choices || [])
      .map((c, ci) => {
        const letter = String.fromCharCode(65 + ci); // A, B, C, D...
        const stripped = String(c).replace(/^\s*[A-D][.):]\s*/i, "");
        return `
        <li data-choice="${letter}">
          <label>
            <input type="radio" name="q-${qi}" value="${letter}" />
            <span><strong>${letter}.</strong> ${escape(stripped)}</span>
          </label>
        </li>`;
      })
      .join("");
    el.innerHTML = `
      <div class="q-index">Câu ${qi + 1} / ${questions.length}</div>
      <div class="q-text">${escape(q.q || "")}</div>
      <ul>${choices}</ul>
      <div class="explain">
        <div class="explain-head"></div>
        <div class="explain-body">${escape(q.explain || "")}</div>
      </div>
    `;
    el.querySelectorAll('input[type="radio"]').forEach((input) => {
      input.addEventListener("change", () => {
        selections[qi] = input.value;
        el.querySelectorAll("li").forEach((li) => li.classList.remove("selected"));
        input.closest("li").classList.add("selected");
        updateSubmitState();
      });
    });
    container.appendChild(el);
  });

  // Submit bar
  const bar = document.createElement("div");
  bar.className = "quiz-bar";
  bar.innerHTML = `
    <div class="quiz-progress"><span>0</span> / ${questions.length} câu đã chọn</div>
    <button type="button" class="btn btn-primary" disabled>Nộp bài</button>
  `;
  container.appendChild(bar);

  const submitBtn = bar.querySelector("button");
  const progressSpan = bar.querySelector(".quiz-progress span");

  function updateSubmitState() {
    const answered = selections.filter((s) => s !== null).length;
    progressSpan.textContent = answered;
    submitBtn.disabled = answered !== questions.length;
  }

  submitBtn.addEventListener("click", () => {
    let correct = 0;
    const qEls = container.querySelectorAll(".quiz-q");
    qEls.forEach((el, qi) => {
      const q = questions[qi];
      const picked = selections[qi]; // "A" | "B" | "C" | "D"
      const answerLetter = q.__letter; // normalized
      const isCorrect = picked === answerLetter;
      if (isCorrect) correct += 1;
      el.classList.add("revealed");
      el.classList.toggle("q-correct", isCorrect);
      el.classList.toggle("q-wrong", !isCorrect);
      el.querySelectorAll("li").forEach((li) => {
        const c = li.dataset.choice;
        li.querySelector('input[type="radio"]').disabled = true;
        if (c === answerLetter) li.classList.add("correct");
        if (c === picked && !isCorrect) li.classList.add("wrong");
      });
      const head = el.querySelector(".explain-head");
      head.innerHTML = isCorrect
        ? `<strong class="ok">✓ Đúng.</strong> Đáp án ${escape(answerLetter)}.`
        : `<strong class="bad">✗ Sai.</strong> Bạn chọn ${escape(picked || "(không chọn)")}, đáp án đúng là ${escape(answerLetter || "(thiếu)")}.`;
    });

    // Result banner
    const score = document.createElement("div");
    score.className = "quiz-score";
    const pct = Math.round((correct / questions.length) * 100);
    score.innerHTML = `
      <div class="score-num">${correct}<span>/${questions.length}</span></div>
      <div class="score-text">Bạn đúng ${correct} trên ${questions.length} câu (${pct}%).</div>
      <button type="button" class="btn btn-ghost" id="btn-retry">Làm lại</button>
    `;
    bar.replaceWith(score);
    score.querySelector("#btn-retry").addEventListener("click", () => renderQuiz(container, questions));
    container.scrollIntoView({ behavior: "smooth", block: "start" });

    if (AUTH.token() && CURRENT_BOOK) {
      authFetch(`${API}/me/quiz`, {
        method: "POST",
        body: JSON.stringify({
          book_id: CURRENT_BOOK.id,
          score: correct,
          total: questions.length,
          topic: ($("#quiz-topic")?.value || "").trim() || null,
        }),
      }).catch(() => {});
    }
  });

  updateSubmitState();
}

async function onFlash() {
  const out = $("#flash-out");
  const topic = $("#flash-topic")?.value.trim() || "";
  const n = clampCount($("#flash-count")?.value, 6);
  out.innerHTML = `<p class="loading">Đang sinh ${n} flashcards${topic ? ` về "${escape(topic)}"` : ""}...</p>`;
  try {
    const res = await fetch(`${API}/reader/${CURRENT_BOOK.id}/flashcards`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ n, topic }),
    });
    const data = await res.json();
    out.innerHTML = "";
    (data.cards || []).forEach((c) => {
      const el = document.createElement("div");
      el.className = "flashcard";
      el.innerHTML = `
        <div class="flashcard-inner">
          <div class="face front">${escape(c.term || "")}</div>
          <div class="face back">${escape(c.definition || "")}</div>
        </div>
      `;
      el.addEventListener("click", () => el.classList.toggle("flipped"));
      out.appendChild(el);
    });
    if (!out.children.length) out.innerHTML = `<p class="muted">Không sinh được flashcard.</p>`;
  } catch (e) {
    out.innerHTML = `<p class="muted">Lỗi: ${e}</p>`;
  }
}

async function onVisualize() {
  const txt = $("#viz-input").value.trim();
  const out = $("#viz-out");
  if (!txt) {
    out.innerHTML = `<p class="muted">Hãy dán một đoạn văn trước.</p>`;
    return;
  }
  out.innerHTML = `<p class="loading">Đang hình hoá đoạn văn...</p>`;
  try {
    const res = await fetch(`${API}/visualize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ excerpt: txt, book_id: CURRENT_BOOK?.id || null }),
    });
    const data = await res.json();
    const sourceLabel = {
      gemini: "sinh bằng Gemini",
      fal: "sinh bằng fal.ai LCM",
      stub: "ảnh mẫu (chưa cấu hình khoá sinh ảnh)",
    }[data.source || (data.stub ? "stub" : "gemini")] || "";
    out.innerHTML = `
      <img src="${data.image_url}" alt="Visualization" />
      <div class="viz-prompt">${escape(data.prompt || "")}${sourceLabel ? ` · <em>${sourceLabel}</em>` : ""}</div>
    `;
    WALL.push({ url: data.image_url, prompt: data.prompt });
    refreshWall();
  } catch (e) {
    out.innerHTML = `<p class="muted">Lỗi: ${e}</p>`;
  }
}

function refreshWall() {
  const grid = $("#wall-grid");
  if (!WALL.length) return;
  grid.innerHTML = "";
  WALL.forEach((v) => {
    const img = document.createElement("img");
    img.src = v.url;
    img.alt = v.prompt;
    grid.appendChild(img);
  });
}

// ------------ upload ------------
function bindUpload() {
  const modal = $("#upload-modal");
  const fileInput = $("#upload-file");
  const drop = $("#upload-drop");
  const nameEl = $("#upload-file-name");
  const form = $("#upload-form");
  const status = $("#upload-status");
  const submitBtn = $("#btn-upload-submit");

  const open = () => {
    modal.removeAttribute("hidden");
    status.textContent = "";
    status.classList.remove("error", "success");
  };
  const close = () => modal.setAttribute("hidden", "");

  ["#btn-open-upload", "#btn-open-upload-hero", "#btn-open-upload-section"].forEach((sel) => {
    const el = $(sel);
    if (el) el.addEventListener("click", open);
  });
  $$("[data-close-upload]").forEach((el) => el.addEventListener("click", close));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.hasAttribute("hidden")) close();
  });

  drop.addEventListener("click", () => fileInput.click());

  // Drag and drop
  ["dragenter", "dragover"].forEach((ev) =>
    drop.addEventListener(ev, (e) => {
      e.preventDefault();
      drop.classList.add("dragging");
    })
  );
  ["dragleave", "drop"].forEach((ev) =>
    drop.addEventListener(ev, (e) => {
      e.preventDefault();
      drop.classList.remove("dragging");
    })
  );
  drop.addEventListener("drop", (e) => {
    const f = e.dataTransfer?.files?.[0];
    if (f) {
      fileInput.files = e.dataTransfer.files;
      updateFileName(f);
    }
  });

  fileInput.addEventListener("change", () => {
    const f = fileInput.files?.[0];
    if (f) updateFileName(f);
  });

  function updateFileName(f) {
    nameEl.textContent = f.name;
    // Auto-fill title from filename if empty
    const titleInput = $("#upload-title");
    if (!titleInput.value) {
      titleInput.value = f.name.replace(/\.pdf$/i, "").replace(/[_-]+/g, " ").trim();
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = fileInput.files?.[0];
    if (!f) {
      status.textContent = "Hãy chọn một file PDF nhé ♡";
      status.classList.add("error");
      return;
    }
    const title = $("#upload-title").value.trim();
    if (!title) {
      status.textContent = "Quên điền tiêu đề rồi ✿";
      status.classList.add("error");
      return;
    }
    const fd = new FormData();
    fd.append("file", f);
    fd.append("title", title);
    fd.append("authors", $("#upload-authors").value);
    fd.append("category", $("#upload-category").value);
    fd.append("difficulty", $("#upload-difficulty").value);

    submitBtn.disabled = true;
    status.classList.remove("error", "success");
    status.textContent = "LibMate đang đọc cuốn sách của bạn... ✦";

    try {
      const res = await fetch(`${API}/library/upload`, { method: "POST", body: fd });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      status.classList.add("success");
      status.textContent = `Xong ♡ Đã thêm "${data.book.title}" (${data.num_chunks} đoạn).`;
      await loadLibrary();
      setTimeout(() => {
        close();
        form.reset();
        nameEl.textContent = "Chạm hoặc kéo thả PDF vào đây";
      }, 1200);
    } catch (err) {
      status.classList.add("error");
      status.textContent = "Không tải được: " + err.message;
    } finally {
      submitBtn.disabled = false;
    }
  });
}

// ------------ floating chatbot ------------
function bindChatbot() {
  const root = $("#chatbot");
  const toggle = $("#chatbot-toggle");
  const closeBtn = $("#chatbot-close");
  const form = $("#chatbot-form");
  const input = $("#chatbot-input");
  const log = $("#chatbot-log");
  if (!root || !toggle || !form || !input || !log) return;

  let busy = false;

  const open = () => {
    root.setAttribute("data-open", "true");
    setTimeout(() => input.focus(), 200);
  };
  const close = () => root.setAttribute("data-open", "false");

  toggle.addEventListener("click", () => {
    const isOpen = root.getAttribute("data-open") === "true";
    if (isOpen) close();
    else open();
  });
  closeBtn.addEventListener("click", close);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && root.getAttribute("data-open") === "true") close();
  });

  // suggestion chips
  $$(".chatbot-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      input.value = chip.textContent.trim();
      form.requestSubmit();
    });
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q || busy) return;
    input.value = "";
    busy = true;

    // Hide suggestions after first send
    const sug = log.querySelector(".chatbot-suggestions");
    if (sug) sug.remove();

    appendChatbotMsg(log, "user", q);
    const loading = appendChatbotMsg(log, "bot loading", "Đang tìm trong thư viện...");
    log.scrollTop = log.scrollHeight;

    try {
      const res = await fetch(`${API}/library/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      loading.remove();

      const msg = appendChatbotMsg(log, "bot", "");
      msg.textContent = data.answer || "(không có câu trả lời)";

      if ((data.citations || []).length) {
        const cites = document.createElement("div");
        cites.className = "cb-citations";
        data.citations.forEach((c) => {
          const row = document.createElement("div");
          row.className = "cb-cite";
          row.innerHTML = `
            <strong>${escape(c.book_title || "")} · ${escape(c.chapter || "Đoạn")} · tr.${c.page ?? "?"}</strong>
            ${escape(c.excerpt || "")}
          `;
          cites.appendChild(row);
        });
        msg.appendChild(cites);
      }
      log.scrollTop = log.scrollHeight;
    } catch (err) {
      loading.remove();
      appendChatbotMsg(log, "bot", "Có lỗi khi gọi trợ lý: " + err.message);
    } finally {
      busy = false;
    }
  });
}

function appendChatbotMsg(log, kind, text) {
  const el = document.createElement("div");
  el.className = "chatbot-msg " + kind;
  el.textContent = text;
  log.appendChild(el);
  return el;
}

// ------------ mic (Web Speech API voice input) ------------
function bindMicButtons() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const buttons = $$(".mic-btn[data-mic-for]");
  if (!SR) {
    // Browser without Web Speech API (e.g. Firefox): hide all mic buttons.
    buttons.forEach((b) => b.classList.add("unsupported"));
    return;
  }

  // One shared recognizer, repurposed per button.
  let active = null; // currently listening button (if any)
  const recognizer = new SR();
  recognizer.lang = "vi-VN";
  recognizer.interimResults = true;
  recognizer.continuous = false;
  recognizer.maxAlternatives = 1;

  recognizer.onresult = (e) => {
    if (!active) return;
    const input = document.getElementById(active.getAttribute("data-mic-for"));
    if (!input) return;
    let transcript = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      transcript += e.results[i][0].transcript;
    }
    input.value = transcript.trim();
    // Fire input event so any listeners (counters, etc.) see it
    input.dispatchEvent(new Event("input", { bubbles: true }));
  };

  recognizer.onerror = (e) => {
    console.warn("SpeechRecognition error:", e.error);
  };

  const stop = () => {
    if (active) {
      active.classList.remove("listening");
      active = null;
    }
    try { recognizer.stop(); } catch (_) {}
  };

  recognizer.onend = () => {
    // Auto-submit if we got a result and the button belongs to a form
    if (active) {
      const input = document.getElementById(active.getAttribute("data-mic-for"));
      const form = active.closest("form");
      active.classList.remove("listening");
      active = null;
      if (input && input.value.trim() && form) {
        form.requestSubmit();
      }
    }
  };

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (active === btn) {
        // toggle: stop listening
        stop();
        return;
      }
      // if another button was listening, stop it first
      if (active) stop();
      // clear target input for fresh capture
      const input = document.getElementById(btn.getAttribute("data-mic-for"));
      if (input) {
        input.value = "";
        input.focus();
      }
      active = btn;
      btn.classList.add("listening");
      try {
        recognizer.start();
      } catch (err) {
        console.warn("recognizer.start failed:", err);
        stop();
      }
    });
  });
}

// ------------ utils ------------
function clampCount(value, fallback) {
  const n = parseInt(value, 10);
  if (Number.isNaN(n)) return fallback;
  return Math.max(3, Math.min(20, n));
}

// ------------ auth ------------
const AUTH = {
  token: () => localStorage.getItem("libmate_token") || "",
  user: () => {
    try { return JSON.parse(localStorage.getItem("libmate_user") || "null"); }
    catch (e) { return null; }
  },
  set(token, user) {
    if (token) localStorage.setItem("libmate_token", token);
    if (user) localStorage.setItem("libmate_user", JSON.stringify(user));
  },
  clear() {
    localStorage.removeItem("libmate_token");
    localStorage.removeItem("libmate_user");
    FAVORITE_IDS.clear();
  },
};

const FAVORITE_IDS = new Set();

async function authFetch(url, opts = {}) {
  const headers = new Headers(opts.headers || {});
  const token = AUTH.token();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (opts.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const res = await fetch(url, { ...opts, headers });
  if (res.status === 401) {
    AUTH.clear();
    renderUserChip(null);
  }
  return res;
}

async function refreshFavorites() {
  FAVORITE_IDS.clear();
  if (!AUTH.token()) return;
  try {
    const res = await authFetch(`${API}/me/favorites`);
    if (!res.ok) return;
    const data = await res.json();
    (data.items || []).forEach((b) => FAVORITE_IDS.add(b.id));
    document.querySelectorAll(".fav-btn[data-book-id]").forEach((btn) => {
      btn.classList.toggle("active", FAVORITE_IDS.has(parseInt(btn.dataset.bookId, 10)));
    });
  } catch (e) {}
}

function bindAuth() {
  renderUserChip(AUTH.user());

  const modal = $("#auth-modal");
  const openBtn = $("#btn-open-auth");
  const form = $("#auth-form");
  const registerOnly = $$(".auth-register-only");
  const nameInput = $("#auth-name");
  const msvInput = $("#auth-msv");
  const dobInput = $("#auth-dob");
  const majorInput = $("#auth-major");
  const emailInput = $("#auth-email");
  const passwordInput = $("#auth-password");
  const password2Input = $("#auth-password2");
  const submitBtn = $("#btn-auth-submit");
  const submitLabel = $("#auth-submit-label");
  const alertEl = $("#auth-alert");
  const title = $("#auth-title");
  const sub = $("#auth-sub");
  const tabs = $$(".auth-tab");
  const rowLogin = $("#auth-row-login");
  const terms = $("#auth-terms");
  const swapText = $("#auth-swap-text");
  const swapBtn = $("#auth-swap-btn");
  const pwHint = $("#auth-password-hint");
  const pwToggle = $("#auth-password-toggle");

  let mode = "login";
  const setAlert = (msg, kind = "error") => {
    if (!msg) { alertEl.hidden = true; alertEl.textContent = ""; return; }
    alertEl.hidden = false;
    alertEl.className = `auth-alert auth-alert-${kind}`;
    alertEl.textContent = msg;
  };

  const applyMode = (m) => {
    mode = m;
    tabs.forEach((t) => t.classList.toggle("active", t.dataset.authTab === m));
    const isRegister = m === "register";
    registerOnly.forEach((el) => (el.hidden = !isRegister));
    if (isRegister) {
      title.textContent = "Tạo tài khoản mới";
      sub.textContent = "Tham gia LibMate để mở khoá hỏi đáp và ôn tập cá nhân hoá.";
      submitLabel.textContent = "Đăng ký";
      rowLogin.hidden = true;
      terms.hidden = false;
      pwHint.hidden = false;
      passwordInput.setAttribute("autocomplete", "new-password");
      swapText.textContent = "Đã có tài khoản?";
      swapBtn.textContent = "Đăng nhập";
      swapBtn.dataset.target = "login";
    } else {
      title.textContent = "Chào mừng bạn quay lại";
      sub.textContent = "Đăng nhập để lưu tiến độ đọc và lịch sử quiz của bạn.";
      submitLabel.textContent = "Đăng nhập";
      rowLogin.hidden = false;
      terms.hidden = true;
      pwHint.hidden = true;
      passwordInput.setAttribute("autocomplete", "current-password");
      swapText.textContent = "Chưa có tài khoản?";
      swapBtn.textContent = "Đăng ký ngay";
      swapBtn.dataset.target = "register";
    }
    setAlert("");
    setTimeout(() => (isRegister ? nameInput : emailInput).focus(), 60);
  };

  const open = (m = "login") => {
    modal.hidden = false;
    document.body.classList.add("modal-open");
    applyMode(m);
  };
  const close = () => {
    modal.hidden = true;
    document.body.classList.remove("modal-open");
    setAlert("");
  };

  openBtn?.addEventListener("click", () => open("login"));
  $$("[data-close-auth]", modal).forEach((el) => el.addEventListener("click", close));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.hidden) close();
  });
  tabs.forEach((t) => t.addEventListener("click", () => applyMode(t.dataset.authTab)));
  swapBtn.addEventListener("click", () => applyMode(swapBtn.dataset.target));

  pwToggle.addEventListener("click", () => {
    const isHidden = passwordInput.type === "password";
    passwordInput.type = isHidden ? "text" : "password";
    pwToggle.setAttribute("aria-label", isHidden ? "Ẩn mật khẩu" : "Hiện mật khẩu");
    pwToggle.classList.toggle("active", isHidden);
  });

  $("#auth-forgot")?.addEventListener("click", (e) => {
    e.preventDefault();
    setAlert("Tính năng khôi phục mật khẩu sẽ sớm có mặt. Vui lòng liên hệ quản trị thư viện.", "info");
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = emailInput.value.trim();
    const password = passwordInput.value;
    if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      setAlert("Email không hợp lệ."); emailInput.focus(); return;
    }
    if (password.length < 6) {
      setAlert("Mật khẩu phải có ít nhất 6 ký tự."); passwordInput.focus(); return;
    }
    const payload = { email, password };
    if (mode === "register") {
      const name = nameInput.value.trim();
      const msv = msvInput.value.trim();
      const dob = dobInput.value;
      const major = majorInput.value;
      const password2 = password2Input.value;
      if (!name) { setAlert("Vui lòng nhập họ và tên."); nameInput.focus(); return; }
      if (msv && !/^[A-Za-z0-9]{4,20}$/.test(msv)) {
        setAlert("Mã sinh viên chỉ gồm chữ và số, 4–20 ký tự."); msvInput.focus(); return;
      }
      if (password !== password2) {
        setAlert("Mật khẩu nhập lại không khớp."); password2Input.focus(); return;
      }
      payload.name = name;
      if (msv) payload.student_id = msv.toUpperCase();
      if (dob) payload.birthdate = dob;
      if (major) payload.major = major;
    }
    submitBtn.disabled = true;
    submitBtn.classList.add("loading");
    const prevLabel = submitLabel.textContent;
    submitLabel.textContent = mode === "register" ? "Đang tạo tài khoản..." : "Đang đăng nhập...";
    setAlert("");
    try {
      const res = await fetch(`${API}/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Không thành công");
      AUTH.set(data.token, data.user);
      renderUserChip(data.user);
      close();
      form.reset();
      if (window.location.pathname === "/me") loadProfile();
    } catch (err) {
      setAlert(err.message || String(err));
    } finally {
      submitBtn.disabled = false;
      submitBtn.classList.remove("loading");
      submitLabel.textContent = prevLabel;
    }
  });

  // User chip menu
  const chip = $("#nav-user-chip");
  const menu = $("#nav-user-menu");
  chip?.addEventListener("click", (e) => {
    e.stopPropagation();
    menu.hidden = !menu.hidden;
  });
  document.addEventListener("click", () => { if (menu) menu.hidden = true; });
  $("#btn-logout")?.addEventListener("click", async () => {
    try { await fetch(`${API}/auth/logout`, { method: "POST" }); } catch (e) {}
    AUTH.clear();
    renderUserChip(null);
    menu.hidden = true;
    if (window.location.pathname === "/me") loadProfile();
  });

  // Verify stored token still valid
  if (AUTH.token()) {
    fetch(`${API}/auth/me`, { headers: { Authorization: `Bearer ${AUTH.token()}` } })
      .then((r) => r.json())
      .then((d) => {
        if (!d.user) { AUTH.clear(); renderUserChip(null); }
        else { AUTH.set(null, d.user); renderUserChip(d.user); }
      })
      .catch(() => {});
  }
}

function renderUserChip(user) {
  const loginBtn = $("#btn-open-auth");
  const userBox = $("#nav-user");
  const meLink = $(".nav-link-me");
  if (!loginBtn || !userBox) return;
  if (!user) {
    loginBtn.hidden = false;
    userBox.hidden = true;
    if (meLink) meLink.hidden = true;
    return;
  }
  loginBtn.hidden = true;
  userBox.hidden = false;
  if (meLink) meLink.hidden = false;
  const initial = (user.name || user.email || "?").trim().charAt(0).toUpperCase();
  $("#nav-user-avatar").textContent = initial;
  $("#nav-user-name").textContent = user.name || user.email.split("@")[0];
  $("#nav-user-full").textContent = user.name || user.email;
  $("#nav-user-email").textContent = user.email;
  refreshFavorites();
}

// ------------ profile page ------------
async function loadProfile() {
  const guest = $("#me-guest");
  const content = $("#me-content");
  const hello = $("#me-hello");
  const sub = $("#me-sub");

  const user = AUTH.user();
  if (!AUTH.token() || !user) {
    guest.hidden = false;
    content.hidden = true;
    hello.textContent = "Xin chào, bạn đọc 👋";
    sub.textContent = "Đây là không gian riêng của bạn — nơi lưu lại sách đã đọc, sách yêu thích và kết quả ôn tập.";
    $("#me-login-cta")?.addEventListener("click", () => $("#btn-open-auth")?.click(), { once: true });
    return;
  }

  guest.hidden = true;
  content.hidden = false;
  hello.textContent = `Xin chào, ${user.name || user.email.split("@")[0]} 👋`;
  sub.textContent = "Đây là hoạt động đọc sách gần đây của bạn trong LibMate.";

  try {
    const [statsRes, histRes, favRes, quizRes] = await Promise.all([
      authFetch(`${API}/me/stats`),
      authFetch(`${API}/me/history`),
      authFetch(`${API}/me/favorites`),
      authFetch(`${API}/me/quiz`),
    ]);
    const stats = (await statsRes.json()) || {};
    $("#stat-books-read").textContent = stats.books_read || 0;
    $("#stat-favorites").textContent = stats.favorites || 0;
    $("#stat-quizzes").textContent = stats.quizzes_done || 0;
    $("#stat-avg").textContent = (stats.avg_score || 0) + "%";

    renderMiniList($("#me-history"), (await histRes.json()).items, "Chưa có sách nào trong lịch sử.");
    renderMiniList($("#me-favorites"), (await favRes.json()).items, "Chưa có sách nào được yêu thích.");
    renderQuizHistory($("#me-quizzes"), (await quizRes.json()).items);
  } catch (e) {
    content.innerHTML = `<p class="muted">Không tải được dữ liệu cá nhân: ${escape(String(e))}</p>`;
  }
}

function renderMiniList(container, items, emptyMsg) {
  if (!items || !items.length) {
    container.innerHTML = `<p class="muted">${emptyMsg}</p>`;
    return;
  }
  container.innerHTML = "";
  items.slice(0, 6).forEach((b) => {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "me-item";
    const cover = b.cover_url
      ? `<img src="${escape(b.cover_url)}" alt="${escape(b.title)}" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'me-item-emoji',textContent:'${b.cover_emoji || "📚"}'}))">`
      : `<span class="me-item-emoji">${b.cover_emoji || "📚"}</span>`;
    el.innerHTML = `
      <div class="me-item-cover">${cover}</div>
      <div class="me-item-body">
        <strong>${escape(b.title)}</strong>
        <span>${escape((b.authors || []).join(" · ") || b.category || "")}</span>
      </div>
    `;
    el.addEventListener("click", () => {
      history.pushState({}, "", "/library");
      applyRoute();
      openReader(b);
    });
    container.appendChild(el);
  });
}

function renderQuizHistory(container, items) {
  if (!items || !items.length) {
    container.innerHTML = `<p class="muted">Chưa có kết quả quiz nào. Mở một cuốn sách và thử sinh quiz.</p>`;
    return;
  }
  container.innerHTML = "";
  items.forEach((q) => {
    const row = document.createElement("div");
    row.className = "me-quiz-row";
    const pct = q.percent || 0;
    const cls = pct >= 80 ? "good" : pct >= 50 ? "mid" : "low";
    const when = q.at ? new Date(q.at * 1000).toLocaleString("vi-VN") : "";
    row.innerHTML = `
      <div class="me-quiz-book">
        <strong>${escape(q.book?.title || "Sách không còn tồn tại")}</strong>
        <span class="muted">${escape(q.topic || "Tổng quát")} · ${when}</span>
      </div>
      <div class="me-quiz-score ${cls}">
        <strong>${q.score}/${q.total}</strong>
        <span>${pct}%</span>
      </div>
    `;
    container.appendChild(row);
  });
}

function escape(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
