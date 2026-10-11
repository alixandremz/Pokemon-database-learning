const MAX_SCORE = 10;

const outputEl = document.getElementById("output");
const screenEl = document.getElementById("screen");
const scoreEl = document.getElementById("score");
const scoreBarEl = document.getElementById("score-bar");
const sqlInput = document.getElementById("sql-input");
const guessInput = document.getElementById("guess-input");
const runBtn = document.getElementById("run-btn");
const guessBtn = document.getElementById("guess-btn");
const newGameBtn = document.getElementById("new-game-btn");
const revealEl = document.getElementById("reveal");
const revealImg = document.getElementById("reveal-img");
const revealName = document.getElementById("reveal-name");
const panelEl = document.getElementById("panel");

let sessionId = null;
let busy = false;
let history = [];
let historyIndex = 0;
let schemaCache = null;

function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  for (const child of children) {
    node.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return node;
}

function clearOutput() {
  outputEl.replaceChildren();
}

function showStatus(text, kind = "info") {
  clearOutput();
  outputEl.append(el("p", { className: "status " + kind, textContent: text }));
}

function showError(text) {
  showStatus(text, "error");
}

async function api(path, body) {
  const res = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return res.json();
}

function setBusy(value) {
  busy = value;
  runBtn.disabled = value;
  guessBtn.disabled = value;
  newGameBtn.disabled = value;
}

function updateScore(score, suddenDeath) {
  scoreEl.textContent = score;
  scoreBarEl.replaceChildren();
  for (let i = 0; i < MAX_SCORE; i++) {
    scoreBarEl.append(el("span", { className: i < score ? "seg on" : "seg" }));
  }
  scoreBarEl.classList.toggle("danger", !!suddenDeath);
}

function hideReveal() {
  revealEl.hidden = true;
  revealImg.removeAttribute("src");
}

function showReveal(spriteUrl, name) {
  revealImg.src = spriteUrl;
  revealImg.alt = "sprite de " + name;
  revealImg.onerror = () => { revealEl.hidden = true; };
  revealName.textContent = name;
  revealEl.hidden = false;
}

function renderTable(columns, rows, truncated) {
  clearOutput();
  if (!rows || rows.length === 0) {
    showStatus("a consulta não retornou nenhuma linha.", "info");
    return;
  }
  const thead = el("thead", {}, el("tr", {}, ...columns.map((c) => el("th", { textContent: c }))));
  const tbody = el("tbody", {}, ...rows.map((row) =>
    el("tr", {}, ...row.map((cell) =>
      el("td", { textContent: cell === null ? "NULL" : String(cell) })))));
  outputEl.append(
    el("p", { className: "status info", textContent: rows.length + " linha(s)" + (truncated ? " (mostrando as primeiras)" : "") }),
    el("div", { className: "table-wrap" }, el("table", {}, thead, tbody)),
  );
}

async function startGame() {
  if (busy) return;
  setBusy(true);
  hideReveal();
  history = [];
  historyIndex = 0;
  try {
    const data = await api("/game/start", {});
    sessionId = data.session_id;
    updateScore(data.score, data.sudden_death);
    showStatus("um pokémon foi sorteado e escondido no banco.\nuse SELECT nas views mystery_* para descobrir quem é.", "info");
  } catch (e) {
    showError("não foi possível iniciar a partida: " + e.message);
  } finally {
    setBusy(false);
  }
}

async function runQuery() {
  if (busy || !sessionId) return;
  const sql = sqlInput.value.trim();
  if (!sql) return;

  setBusy(true);
  showStatus("consultando...", "info");
  try {
    const data = await api("/game/query", { session_id: sessionId, sql });
    if (data.score !== undefined) updateScore(data.score, data.sudden_death);
    if (data.error) {
      showError(data.error);
    } else {
      renderTable(data.columns, data.rows, data.truncated);
      pushHistory(sql);
      handleGameOver(data);
    }
  } catch (e) {
    showError("falha na consulta: " + e.message);
  } finally {
    setBusy(false);
  }
}

async function makeGuess() {
  if (busy || !sessionId) return;
  const name = guessInput.value.trim();
  if (!name) return;

  setBusy(true);
  try {
    const data = await api("/game/guess", { session_id: sessionId, name });
    if (data.score !== undefined) updateScore(data.score, data.sudden_death);
    if (data.error) {
      showError(data.error);
    } else {
      showStatus(data.message, data.correct ? "win" : "wrong");
      if (data.game_over && data.sprite_url) showReveal(data.sprite_url, data.secret_name);
      if (data.game_over) guessInput.value = "";
    }
  } catch (e) {
    showError("falha no palpite: " + e.message);
  } finally {
    setBusy(false);
  }
}

function handleGameOver(data) {
  if (data.sudden_death && !data.game_over) {
    showError("atenção: última chance! o próximo palpite decide o jogo.");
  }
  if (data.game_over) {
    showError("fim de jogo. clique em 'nova partida'.");
  }
}

function pushHistory(sql) {
  if (history[history.length - 1] !== sql) history.push(sql);
  historyIndex = history.length;
}

function navigateHistory(direction) {
  if (history.length === 0) return;
  historyIndex = Math.min(history.length, Math.max(0, historyIndex + direction));
  sqlInput.value = historyIndex < history.length ? history[historyIndex] : "";
}

/* ---- painéis de ajuda ---- */

function renderHelp() {
  return el("div", { className: "prose" },
    el("p", {}, "O banco tem quase todas as tabelas do projeto veekun/pokedex. ",
      "Consulte livremente as tabelas normais para comparar pokémon que você já conhece."),
    el("p", { textContent: "Estas views só existem durante a partida e revelam o pokémon secreto (cada consulta a elas custa 1 ponto):" }),
    el("ul", {},
      el("li", {}, el("code", { textContent: "mystery_pokemon" }), " — altura, peso, geração, tipos, tamanho da linha evolutiva"),
      el("li", {}, el("code", { textContent: "mystery_pokemon_stats" }), " — stats base"),
      el("li", {}, el("code", { textContent: "mystery_pokemon_abilities" }), " — habilidades"),
      el("li", {}, el("code", { textContent: "mystery_pokemon_moves" }), " — movimentos")),
    el("p", { textContent: "Exemplos para começar:" }),
    el("pre", { textContent:
      "SELECT * FROM mystery_pokemon;\n" +
      "SELECT * FROM mystery_pokemon_stats ORDER BY base_value DESC;\n" +
      "-- compare a altura com pokémon que você conhece:\n" +
      "SELECT sp.identifier FROM pokemon p\n" +
      "  JOIN pokemon_species sp ON sp.id = p.species_id\n" +
      "  WHERE p.height = (SELECT height FROM mystery_pokemon);" }));
}

function renderRules() {
  const rows = [
    ["Placar inicial", "10 pontos"],
    ["Cada query nas views mystery_*", "−1 ponto"],
    ["Cada palpite (certo ou errado)", "−1 ponto"],
    ["Placar chega a 0", "1 última chance (sudden death)"],
    ["Acertou o nome", "vitória"],
    ["Errou a chance final", "derrota — o pokémon é revelado"],
  ];
  return el("table", { className: "rules" },
    el("tbody", {}, ...rows.map(([a, b]) =>
      el("tr", {}, el("th", { textContent: a }), el("td", { textContent: b })))));
}

function renderSchema(schema) {
  const views = el("div", {},
    el("h3", { textContent: "views do jogo" }),
    ...schema.mystery_views.map((v) =>
      el("details", { className: "schema-item", open: false },
        el("summary", {}, el("code", { textContent: v.name }),
          el("span", { className: "hint", textContent: " " + v.description })),
        el("p", { className: "hint", textContent: v.columns.join(", ") }))));

  const tables = el("div", {},
    el("h3", { textContent: "tabelas do banco" }),
    ...schema.tables.map((t) =>
      el("details", { className: "schema-item" },
        el("summary", {}, el("code", { textContent: t.name })),
        el("p", { className: "hint", textContent: t.columns.join(", ") }))));

  return el("div", {}, views, tables);
}

async function renderPanel(name) {
  panelEl.replaceChildren(el("p", { className: "hint", textContent: "carregando..." }));
  if (name === "help") return panelEl.replaceChildren(renderHelp());
  if (name === "rules") return panelEl.replaceChildren(renderRules());
  if (name === "schema") {
    try {
      schemaCache = schemaCache || await api("/game/schema");
      panelEl.replaceChildren(renderSchema(schemaCache));
    } catch (e) {
      panelEl.replaceChildren(el("p", { className: "status error", textContent: "não foi possível carregar o schema: " + e.message }));
    }
  }
}

/* ---- eventos ---- */

runBtn.addEventListener("click", runQuery);
guessBtn.addEventListener("click", makeGuess);
newGameBtn.addEventListener("click", startGame);

sqlInput.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    runQuery();
  } else if (e.key === "ArrowUp" && sqlInput.selectionStart === 0 && sqlInput.selectionEnd === 0) {
    e.preventDefault();
    navigateHistory(-1);
  } else if (e.key === "ArrowDown" && sqlInput.selectionStart === sqlInput.value.length && sqlInput.selectionEnd === sqlInput.value.length) {
    e.preventDefault();
    navigateHistory(1);
  }
});

guessInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    makeGuess();
  }
});

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.setAttribute("aria-selected", String(t === tab)));
    renderPanel(tab.dataset.panel);
  });
});

updateScore(0, false);
renderPanel("help");
startGame();
