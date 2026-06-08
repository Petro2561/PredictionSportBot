function getSessionId() {
  const params = new URLSearchParams(window.location.search);
  return window.__PREDICTION_SID__ || params.get("sid") || "";
}

function parseMatchesFromQuery() {
  const params = new URLSearchParams(window.location.search);
  const raw = params.get("matches") || "";
  if (!raw) return [];

  return raw.split(",").map((pair) => {
    const separator = pair.indexOf("|");
    if (separator === -1) {
      const dash = pair.indexOf("-");
      return {
        firstTeam: pair.slice(0, dash).trim(),
        secondTeam: pair.slice(dash + 1).trim(),
      };
    }
    return {
      firstTeam: pair.slice(0, separator).trim(),
      secondTeam: pair.slice(separator + 1).trim(),
    };
  });
}

async function fetchMatches(query) {
  const response = await fetch(`/api/matches?${query}`);
  if (response.ok) {
    return response.json();
  }
  return null;
}

async function loadMatches() {
  if (Array.isArray(window.__PREDICTION_MATCHES__)) {
    return window.__PREDICTION_MATCHES__;
  }

  const sessionId = getSessionId();
  if (sessionId) {
    const matches = await fetchMatches(`sid=${encodeURIComponent(sessionId)}`);
    if (matches) return matches;
  }

  return parseMatchesFromQuery();
}

function defaultScore(value) {
  return Number.isInteger(value) && value >= 0 ? value : 0;
}

function createMatchCard(match, index) {
  const card = document.createElement("section");
  card.className = "match-card";
  card.dataset.index = String(index);
  const homeScore = defaultScore(match.firstScore);
  const awayScore = defaultScore(match.secondScore);

  card.innerHTML = `
    <div class="match-number">Матч ${index + 1}</div>
    <h2 class="match-title">${escapeHtml(match.firstTeam)} — ${escapeHtml(match.secondTeam)}</h2>
    <div class="score-row">
      <div class="score-field">
        <label for="home-${index}">${escapeHtml(match.firstTeam)}</label>
        <input id="home-${index}" type="number" min="0" max="99" inputmode="numeric" value="${homeScore}" placeholder="0" required />
      </div>
      <div class="score-separator">:</div>
      <div class="score-field">
        <label for="away-${index}">${escapeHtml(match.secondTeam)}</label>
        <input id="away-${index}" type="number" min="0" max="99" inputmode="numeric" value="${awayScore}" placeholder="0" required />
      </div>
    </div>
    <div class="error-text"></div>
  `;

  return card;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function validateCard(card) {
  const home = card.querySelector('input[id^="home-"]');
  const away = card.querySelector('input[id^="away-"]');
  const errorEl = card.querySelector(".error-text");
  const homeValue = home.value.trim();
  const awayValue = away.value.trim();

  if (homeValue === "" || awayValue === "") {
    card.classList.add("error");
    errorEl.textContent = "Укажите счёт для обеих команд";
    return null;
  }

  const firstScore = Number(homeValue);
  const secondScore = Number(awayValue);

  if (!Number.isInteger(firstScore) || !Number.isInteger(secondScore) || firstScore < 0 || secondScore < 0 || firstScore > 99 || secondScore > 99) {
    card.classList.add("error");
    errorEl.textContent = "Счёт должен быть целым числом от 0 до 99";
    return null;
  }

  card.classList.remove("error");
  errorEl.textContent = "";
  return { firstScore, secondScore };
}

function renderForm(matches) {
  const root = document.getElementById("matches");
  if (root.querySelector(".match-card")) {
    document.getElementById("submit-btn").disabled = !matches.length;
    return;
  }

  root.innerHTML = "";

  if (!matches.length) {
    root.innerHTML =
      '<div class="empty-state">Матчи для прогноза не найдены.<br><br>' +
      "Откройте форму через бота: /start → «Сделать прогноз».<br>" +
      "Нужна полная ссылка вида /p/...</div>";
    document.getElementById("submit-btn").disabled = true;
    return;
  }

  matches.forEach((match, index) => {
    root.appendChild(createMatchCard(match, index));
  });
}

function collectPredictions(matches) {
  const cards = [...document.querySelectorAll(".match-card")];
  const result = [];
  let hasError = false;

  cards.forEach((card, index) => {
    const scores = validateCard(card);
    if (!scores) {
      hasError = true;
      return;
    }
    result.push({
      firstTeam: matches[index].firstTeam,
      secondTeam: matches[index].secondTeam,
      firstScore: scores.firstScore,
      secondScore: scores.secondScore,
    });
  });

  if (hasError) {
    const firstError = document.querySelector(".match-card.error");
    firstError?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  return hasError ? null : result;
}

function setSubmitState(button, loading, text) {
  button.disabled = loading;
  button.textContent = text;
}

function showStatus(message, isError = false) {
  let status = document.getElementById("submit-status");
  if (!status) {
    status = document.createElement("div");
    status.id = "submit-status";
    status.className = "submit-status";
    document.querySelector(".submit-bar").prepend(status);
  }
  status.textContent = message;
  status.classList.toggle("error", isError);
}

async function submitPredictions(predictions) {
  const submitBtn = document.getElementById("submit-btn");
  const sessionId = getSessionId();
  if (!sessionId) {
    showStatus("Не найдена сессия формы. Откройте ссылку из бота заново.", true);
    return;
  }

  setSubmitState(submitBtn, true, "Отправка...");
  try {
    const response = await fetch("/api/predictions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sid: sessionId, predictions }),
    });
    const data = await response.json();
    if (!response.ok) {
      showStatus(data.error || "Не удалось сохранить прогнозы", true);
      setSubmitState(submitBtn, false, "Отправить");
      return;
    }

    showStatus("Прогнозы сохранены. Подтверждение отправлено в Telegram-бот.");
    setSubmitState(submitBtn, true, "Сохранено");
  } catch (error) {
    showStatus("Ошибка сети. Проверьте подключение к интернету.", true);
    setSubmitState(submitBtn, false, "Отправить");
  }
}

async function init() {
  const matchesFromPage = Array.isArray(window.__PREDICTION_MATCHES__)
    ? window.__PREDICTION_MATCHES__
    : null;

  const matches = matchesFromPage ?? (await loadMatches());
  renderForm(matches);

  document.getElementById("submit-btn").addEventListener("click", async () => {
    const predictions = collectPredictions(matches);
    if (!predictions) return;
    await submitPredictions(predictions);
  });
}

document.addEventListener("DOMContentLoaded", init);
