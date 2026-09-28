const form = document.getElementById("analysis-form");
const symbolInput = document.getElementById("symbol");
const questionInput = document.getElementById("question");
const submitButton = document.getElementById("submit-button");
const buttonLabel = document.querySelector(".button-label");
const buttonLoading = document.querySelector(".button-loading");
const emptyState = document.getElementById("empty-state");
const errorBox = document.getElementById("error-box");
const resultContent = document.getElementById("result-content");
const resultTitle = document.getElementById("result-title");
const resultStatus = document.getElementById("result-status");
const resultMeta = document.getElementById("result-meta");
const reportId = document.getElementById("report-id");
const reportContent = document.getElementById("report-content");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function inlineMarkdown(value) {
  let text = escapeHtml(value);
  text = text.replace(/`([^`]+)`/g, "<code>$1</code>");
  text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  return text;
}

function renderMarkdown(markdown) {
  const lines = String(markdown || "").replaceAll("\r", "").split("\n");
  const html = [];
  let listType = null;
  let inCode = false;

  const closeList = () => {
    if (listType) {
      html.push(`</${listType}>`);
      listType = null;
    }
  };

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      if (inCode) {
        html.push("</code></pre>");
        inCode = false;
      } else {
        closeList();
        html.push("<pre><code>");
        inCode = true;
      }
      continue;
    }

    if (inCode) {
      html.push(`${escapeHtml(line)}\n`);
      continue;
    }

    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      closeList();
      const level = heading[1].length;
      html.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }

    if (/^\s*([-*_])\s*\1\s*\1\s*$/.test(line)) {
      closeList();
      html.push("<hr>");
      continue;
    }

    const unordered = line.match(/^\s*[-*]\s+(.+)$/);
    if (unordered) {
      if (listType !== "ul") {
        closeList();
        listType = "ul";
        html.push("<ul>");
      }
      html.push(`<li>${inlineMarkdown(unordered[1])}</li>`);
      continue;
    }

    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (ordered) {
      if (listType !== "ol") {
        closeList();
        listType = "ol";
        html.push("<ol>");
      }
      html.push(`<li>${inlineMarkdown(ordered[1])}</li>`);
      continue;
    }

    if (/^\s*>\s?/.test(line)) {
      closeList();
      html.push(`<blockquote>${inlineMarkdown(line.replace(/^\s*>\s?/, ""))}</blockquote>`);
      continue;
    }

    if (!line.trim()) {
      closeList();
      html.push('<div class="report-break"></div>');
      continue;
    }

    closeList();
    html.push(`<p>${inlineMarkdown(line)}</p>`);
  }

  if (inCode) html.push("</code></pre>");
  closeList();
  return html.join("");
}

function setLoading(isLoading) {
  submitButton.disabled = isLoading;
  buttonLabel.hidden = isLoading;
  buttonLoading.hidden = !isLoading;
}

function showMeta(bundle, analysisId) {
  const sections = bundle.sections || {};
  const labels = {
    price: "價格",
    technical: "技術面",
    fundamentals: "基本面",
    news: "新聞",
  };
  resultMeta.replaceChildren();
  const symbolChip = document.createElement("span");
  symbolChip.className = "meta-chip";
  symbolChip.innerHTML = `<strong>${escapeHtml(bundle.symbol || "-")}</strong>`;
  resultMeta.appendChild(symbolChip);

  for (const [key, label] of Object.entries(labels)) {
    const chip = document.createElement("span");
    chip.className = "meta-chip";
    const status = sections[key]?.status || "未提供";
    chip.textContent = `${label} · ${status}`;
    resultMeta.appendChild(chip);
  }

  reportId.textContent = analysisId ? `ANALYSIS #${analysisId}` : "LOCAL REPORT";
}

function showError(message) {
  emptyState.hidden = true;
  resultContent.hidden = true;
  errorBox.hidden = false;
  errorBox.textContent = message;
  resultStatus.textContent = "發生錯誤";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const symbol = symbolInput.value.trim();
  const question = questionInput.value.trim();
  if (!symbol || !question) return;

  setLoading(true);
  emptyState.hidden = true;
  errorBox.hidden = true;
  resultContent.hidden = true;
  resultTitle.textContent = "正在整理研究資料…";
  resultStatus.textContent = "處理中";

  try {
    const response = await fetch("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, question }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "分析失敗，請稍後再試。 ");

    const bundle = data.bundle || {};
    resultTitle.textContent = `${bundle.symbol || symbol.toUpperCase()} 研究報告`;
    resultStatus.textContent = "分析完成";
    showMeta(bundle, data.analysis_id);
    reportContent.innerHTML = renderMarkdown(data.report || "目前沒有可顯示的報告。");
    resultContent.hidden = false;
  } catch (error) {
    showError(error.message || "無法連線到分析服務，請稍後再試。");
  } finally {
    setLoading(false);
  }
});

document.querySelectorAll("[data-symbol]").forEach((button) => {
  button.addEventListener("click", () => {
    symbolInput.value = button.dataset.symbol;
    symbolInput.focus();
  });
});
