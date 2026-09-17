const JOB_ORDER = ["드루", "어쎄", "네크", "슴딘"];
const CLASS_RANKS = ["S", "A", "B", "C", "D"];
const DEFAULT_CLASS_RANK = "C";
const CLASS_RANK_SCORES = { S: 5, A: 4, B: 3, C: 2, D: 1 };
const USER_A = "삭제";
const USERS_B = ["123", "456"];
const AUTOCOMPLETE_LIMIT = 12;
const CLASS_SORT_MIN_GAMES = 50;
const CURRENT_GAMES_POLL_INTERVAL_MS = 60000;
const KOREA_TIME_ZONE = "Asia/Seoul";
const TIER_THRESHOLD_NAMES = ["마스터", "다이아", "플래티넘", "골드", "실버"];
const PAGE_NAMES = new Set(["home", "rank", "history", "stats", "teams", "notice", "admin"]);
const ADMIN_PERMISSION_OPTIONS = [
  ["game:create", "경기 등록"],
  ["game:cancel", "경기 취소"],
  ["game:restore", "경기 복구"],
  ["season:manage", "시즌"],
  ["notice:manage", "공지"],
  ["player:manage", "유저"],
  ["mmr:manage", "MMR"],
  ["admin:manage", "권한"],
];

const state = {
  me: null,
  seasons: [],
  rankings: [],
  history: [],
  currentGames: [],
  currentGamesTimer: null,
  appSettings: {
    discord_url: null,
  },
  historyPage: {
    page: 1,
    pageSize: 20,
    total: 0,
    totalPages: 0,
    query: "",
    allSeasons: false,
  },
  summary: null,
  playerStats: [],
  duoStats: [],
  notices: [],
  adminSeasons: [],
  adminPlayers: [],
  editingAdminPlayerId: null,
  adminNotices: [],
  adminUsers: [],
  adminScoringRule: null,
  statSorts: {
    player: { key: "rank", direction: "asc" },
    duo: { key: "index", direction: "asc" },
  },
  teamPlayers: [],
  playerMetaDataMap: new Map(),
  selectedSeasonId: null,
  lastGeneratedTextResult: "",
  lastGeneratedTeam1Players: [],
  lastGeneratedTeam2Players: [],
  currentTeamBuilderGameId: null,
  currentTeamBuilderGameStatus: "draft",
  currentTeamBuilderTeams: null,
  currentEditingHistoryGameId: null,
  currentEditingNoticeId: null,
};

async function loadStatus() {
  const seasonSelect = document.querySelector("#season-select");

  try {
    const [meResponse, seasonsResponse, teamPlayersResponse, settingsResponse] = await Promise.all([
      fetch("/api/auth/me"),
      fetch("/api/seasons"),
      fetch("/api/team-builder/players"),
      fetch("/api/settings"),
    ]);

    state.me = await meResponse.json();
    renderAuthState();
    state.seasons = await seasonsResponse.json();
    state.teamPlayers = await teamPlayersResponse.json();
    state.appSettings = settingsResponse.ok ? await settingsResponse.json() : { discord_url: null };
    updateTeamPlayerMeta();

    renderSeasons(seasonSelect);
    renderTeamInputs();
    attachEvents();
    await loadSeasonData(seasonSelect.value);
    startCurrentGamesPolling();
  } catch (error) {
    console.error(error);
  }
}

async function refreshTeamPlayers() {
  const response = await fetch("/api/team-builder/players");
  state.teamPlayers = await response.json();
  updateTeamPlayerMeta();
}

function updateTeamPlayerMeta() {
  state.playerMetaDataMap = new Map(
    state.teamPlayers.map((player) => [
      player.player_name,
      { tier: player.current_tier ?? "" },
    ])
  );
}

function attachEvents() {
  document.querySelector("#season-select").addEventListener("change", (event) => {
    loadSeasonData(event.target.value);
  });
  document.querySelector("#clear-team-button").addEventListener("click", resetTeams);
  document.querySelector("#build-team-button").addEventListener("click", createTeams);
  document.querySelector("#copy-team-button").addEventListener("click", copyResult);
  document.querySelector("#refresh-duos-button").addEventListener("click", loadDuoStats);
  document.querySelector("#duo-all-seasons").addEventListener("change", loadDuoStats);
  document.querySelector("#search-duo-button").addEventListener("click", searchDuoMatchup);
  document.querySelector("#admin-player-form").addEventListener("submit", createAdminPlayer);
  document.querySelector("#admin-player-new").addEventListener("click", () => {
    resetAdminPlayerForm();
    setAdminPlayerMessage("신규 유저를 등록할 수 있습니다.", false);
  });
  setupAdminClassRankSelects();
  document.querySelectorAll("[data-admin-tab]").forEach((button) => {
    button.addEventListener("click", () => showAdminPanel(button.dataset.adminTab));
  });
  document.querySelector("#admin-season-create-form").addEventListener("submit", createAdminSeason);
  document.querySelector("#admin-notice-form").addEventListener("submit", saveAdminNotice);
  document.querySelector("#admin-notice-reset").addEventListener("click", resetAdminNoticeForm);
  document.querySelector("#admin-refresh-notices").addEventListener("click", loadAdminNotices);
  document.querySelector("#admin-notice-body-list").addEventListener("click", (event) => {
    const editButton = event.target.closest("[data-admin-edit-notice]");
    const deleteButton = event.target.closest("[data-admin-delete-notice]");
    if (editButton) editAdminNotice(Number(editButton.dataset.adminEditNotice));
    if (deleteButton) deleteAdminNotice(Number(deleteButton.dataset.adminDeleteNotice));
  });
  document.querySelector("#admin-refresh-seasons").addEventListener("click", loadAdminSeasons);
  document.querySelector("#admin-include-disabled-seasons").addEventListener("change", loadAdminSeasons);
  document.querySelector("#admin-season-body").addEventListener("click", (event) => {
    const openButton = event.target.closest("[data-admin-open-season]");
    const closeButton = event.target.closest("[data-admin-close-season]");
    const disableButton = event.target.closest("[data-admin-disable-season]");
    const ruleButton = event.target.closest("[data-admin-season-rule]");
    if (openButton) openAdminSeason(Number(openButton.dataset.adminOpenSeason));
    if (closeButton) closeAdminSeason(Number(closeButton.dataset.adminCloseSeason));
    if (disableButton) disableAdminSeason(Number(disableButton.dataset.adminDisableSeason));
    if (ruleButton) openSeasonRuleModal(Number(ruleButton.dataset.adminSeasonRule));
  });
  document.querySelector("#season-rule-close").addEventListener("click", closeSeasonRuleModal);
  document.querySelector("#season-rule-confirm").addEventListener("click", closeSeasonRuleModal);
  document.querySelector("#admin-refresh-players").addEventListener("click", loadAdminPlayers);
  document.querySelector("#admin-include-inactive").addEventListener("change", loadAdminPlayers);
  document.querySelector("#admin-player-search").addEventListener("keydown", (event) => {
    if (event.key === "Enter") loadAdminPlayers();
  });
  document.querySelector("#admin-player-body").addEventListener("click", (event) => {
    const row = event.target.closest("[data-admin-player-row]");
    const editButton = event.target.closest("[data-admin-edit-player]");
    const deleteButton = event.target.closest("[data-admin-delete-player]");
    const restoreButton = event.target.closest("[data-admin-restore-player]");
    if (editButton) loadAdminPlayerIntoForm(Number(editButton.dataset.adminEditPlayer));
    if (deleteButton) deleteAdminPlayer(Number(deleteButton.dataset.adminDeletePlayer));
    if (restoreButton) restoreAdminPlayer(Number(restoreButton.dataset.adminRestorePlayer));
    if (row && !deleteButton && !restoreButton) {
      loadAdminPlayerIntoForm(Number(row.dataset.adminPlayerRow));
    }
  });
  document.querySelector("#admin-mmr-form").addEventListener("submit", saveAdminScoringRule);
  document.querySelector("#admin-setting-form").addEventListener("submit", saveAdminSettings);
  document.querySelector("#admin-mmr-simulate").addEventListener("click", openMmrSimulator);
  document.querySelectorAll("[data-mmr-tab]").forEach((button) => {
    button.addEventListener("click", () => showMmrSection(button.dataset.mmrTab));
  });
  document.querySelector("#mmr-simulator-form").addEventListener("submit", (event) => {
    event.preventDefault();
    renderMmrSimulation();
  });
  document.querySelector("#mmr-simulator-form").addEventListener("input", renderMmrSimulation);
  document.querySelector("#mmr-simulator-close").addEventListener("click", closeMmrSimulator);
  document.querySelector("#mmr-simulator-cancel").addEventListener("click", closeMmrSimulator);
  document.querySelector("#admin-refresh-users").addEventListener("click", loadAdminUsers);
  document.querySelector("#admin-user-body").addEventListener("click", (event) => {
    const saveButton = event.target.closest("[data-admin-save-user]");
    const disableButton = event.target.closest("[data-admin-disable-user]");
    const restoreButton = event.target.closest("[data-admin-restore-user]");
    if (saveButton) saveAdminUserPermissions(Number(saveButton.dataset.adminSaveUser));
    if (disableButton) disableAdminUser(Number(disableButton.dataset.adminDisableUser));
    if (restoreButton) restoreAdminUser(Number(restoreButton.dataset.adminRestoreUser));
  });
  document.querySelector("#team-result").addEventListener("click", (event) => {
    const startButton = event.target.closest("#start-game-button");
    const resultButton = event.target.closest("#submit-result-button");
    if (startButton) startTeamBuilderGame();
    if (resultButton) submitTeamBuilderResult();
  });
  document.querySelector("#current-game-panel").addEventListener("click", (event) => {
    const restoreButton = event.target.closest("[data-load-current-game]");
    if (restoreButton) loadCurrentGameIntoTeamBuilder(restoreButton.dataset.loadCurrentGame);
  });
  document.querySelector("#history-list").addEventListener("click", (event) => {
    const cancelButton = event.target.closest("[data-history-cancel]");
    const restoreButton = event.target.closest("[data-history-restore]");
    const editResultButton = event.target.closest("[data-history-edit-result]");
    if (cancelButton) cancelHistoryGame(cancelButton.dataset.historyCancel);
    if (restoreButton) restoreHistoryGame(restoreButton.dataset.historyRestore);
    if (editResultButton) editHistoryGameResult(editResultButton.dataset.historyEditResult);
  });
  document.querySelector("#result-edit-form").addEventListener("submit", submitHistoryResultEdit);
  document.querySelector("#result-edit-close").addEventListener("click", closeResultEditModal);
  document.querySelector("#result-edit-cancel").addEventListener("click", closeResultEditModal);
  document.querySelector("#result-edit-modal").addEventListener("click", (event) => {
    if (event.target.id === "result-edit-modal") closeResultEditModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !document.querySelector("#result-edit-modal").hidden) {
      closeResultEditModal();
    }
  });
  document.querySelector("#history-search-button").addEventListener("click", () => {
    state.historyPage.query = document.querySelector("#history-search-input").value.trim();
    state.historyPage.allSeasons = document.querySelector("#history-all-seasons").checked;
    loadHistoryPage(1);
  });
  document.querySelector("#history-search-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      state.historyPage.query = event.target.value.trim();
      state.historyPage.allSeasons = document.querySelector("#history-all-seasons").checked;
      loadHistoryPage(1);
    }
  });
  document.querySelector("#history-all-seasons").addEventListener("change", (event) => {
    state.historyPage.allSeasons = event.target.checked;
    loadHistoryPage(1);
  });
  document.querySelector("#history-clear-search-button").addEventListener("click", () => {
    document.querySelector("#history-search-input").value = "";
    state.historyPage.query = "";
    loadHistoryPage(1);
  });
  document.querySelector("#player-stats-head").addEventListener("click", (event) => {
    const button = event.target.closest("[data-player-sort]");
    if (button) sortStatsTable("player", button.dataset.playerSort);
  });
  document.querySelector("#duo-stats-head").addEventListener("click", (event) => {
    const button = event.target.closest("[data-duo-sort]");
    if (button) sortStatsTable("duo", button.dataset.duoSort);
  });
  document.querySelector("#history-page-size").addEventListener("change", (event) => {
    state.historyPage.pageSize = Number(event.target.value);
    loadHistoryPage(1);
  });
  document.querySelector("#history-first-page").addEventListener("click", () => loadHistoryPage(1));
  document.querySelector("#history-prev-page").addEventListener("click", () => {
    loadHistoryPage(state.historyPage.page - 1);
  });
  document.querySelector("#history-next-page").addEventListener("click", () => {
    loadHistoryPage(state.historyPage.page + 1);
  });
  document.querySelector("#history-last-page").addEventListener("click", () => {
    loadHistoryPage(state.historyPage.totalPages);
  });
  document.querySelectorAll("[data-page-link]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      navigateToPage(link.dataset.pageLink, true);
    });
  });
  window.addEventListener("popstate", () => navigateToPage(getPageFromHash(), false));
  window.addEventListener("hashchange", () => navigateToPage(getPageFromHash(), false));
  document.querySelector(".stats-tabs").addEventListener("click", (event) => {
    const tab = event.target.closest("[data-stats-tab]");
    if (tab) switchStatsPanel(tab.dataset.statsTab);
  });
  document.querySelector("#ranking-body").addEventListener("click", (event) => {
    const target = event.target.closest("[data-player-id]");
    if (target) openPlayerDetail(Number(target.dataset.playerId));
  });
  document.querySelector("#duo-stats-body").addEventListener("click", (event) => {
    const target = event.target.closest("[data-duo-left]");
    if (!target) return;
    document.querySelector("#duo-player-1").value = target.dataset.duoLeft;
    document.querySelector("#duo-player-2").value = target.dataset.duoRight;
    searchDuoMatchup();
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".autocomplete-host")) hideAllAutocomplete();
  });
  setupNameAutocomplete(document.querySelector("#duo-player-1"));
  setupNameAutocomplete(document.querySelector("#duo-player-2"));
  navigateToPage(getPageFromHash(), false);
}

function getPageFromHash() {
  const hashValue = window.location.hash.replace("#", "").trim();
  if (!hashValue || hashValue === "top") return "home";
  return PAGE_NAMES.has(hashValue) ? hashValue : "home";
}

function navigateToPage(pageName, updateUrl) {
  let nextPage = PAGE_NAMES.has(pageName) ? pageName : "home";
  if (nextPage === "admin" && !canAccessAdminPage()) nextPage = "home";
  document.querySelectorAll("[data-page]").forEach((section) => {
    const isActive = section.dataset.page === nextPage;
    section.hidden = !isActive;
    section.classList.toggle("active", isActive);
  });

  const toolbar = document.querySelector(".page-toolbar");
  if (toolbar) toolbar.hidden = !["rank", "history", "stats"].includes(nextPage);

  if (nextPage === "admin") {
    if (state.adminSeasons.length === 0) loadAdminSeasons();
    if (state.adminPlayers.length === 0) loadAdminPlayers();
    if (state.adminNotices.length === 0) loadAdminNotices();
    if (state.me?.is_super && state.adminUsers.length === 0) loadAdminUsers();
    if (hasPermission("mmr:manage") && !state.adminScoringRule) loadAdminScoringRule();
  }
  if (nextPage === "notice") {
    loadNotices();
  }
  if (nextPage === "teams" && state.currentTeamBuilderGameId) {
    syncTeamBuilderGameStatus()
      .then((game) => {
        if (game?.status === "CANCELED") {
          showTeamMessage(
            "이 경기는 다른 화면에서 취소되었습니다. 결과입력은 할 수 없습니다.",
            true,
            false
          );
        }
      })
      .catch((error) => showTeamMessage(error.message, true, false));
  }

  document.querySelectorAll("[data-page-link]").forEach((link) => {
    const isActive = link.dataset.pageLink === nextPage;
    link.classList.toggle("active", isActive);
    if (link.classList.contains("brand")) {
      link.setAttribute("aria-current", isActive ? "page" : "false");
    } else if (isActive) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  });

  if (updateUrl) {
    const nextHash = `#${nextPage}`;
    if (window.location.hash !== nextHash) {
      history.pushState(null, "", nextHash);
    }
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function switchStatsPanel(panelName) {
  document.querySelectorAll("[data-stats-tab]").forEach((tab) => {
    const isActive = tab.dataset.statsTab === panelName;
    tab.classList.toggle("active", isActive);
    tab.setAttribute("aria-selected", String(isActive));
  });
  document.querySelectorAll("[data-stats-panel]").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.statsPanel === panelName);
  });
}

function sortStatsTable(tableName, key) {
  const currentSort = state.statSorts[tableName];
  const defaultDirection = ["player_name", "duo_name"].includes(key) ? "asc" : "desc";
  const direction =
    currentSort.key === key
      ? currentSort.direction === "asc"
        ? "desc"
        : "asc"
      : defaultDirection;

  state.statSorts[tableName] = { key, direction };
  if (tableName === "player") renderPlayerStats();
  if (tableName === "duo") renderDuoStats();
}

function renderSeasons(seasonSelect) {
  seasonSelect.innerHTML = state.seasons
    .map((season) => `<option value="${season.id}">${escapeHtml(season.name)}</option>`)
    .join("");
}

async function loadSeasonData(seasonId) {
  state.selectedSeasonId = seasonId;
  state.historyPage.query = document.querySelector("#history-search-input")?.value.trim() ?? "";
  state.historyPage.allSeasons = document.querySelector("#history-all-seasons")?.checked ?? false;
  state.historyPage.page = 1;
  state.historyPage.pageSize = Number(
    document.querySelector("#history-page-size")?.value ?? state.historyPage.pageSize
  );
  const [summaryResponse, rankingsResponse, historyResponse, playerStatsResponse] =
    await Promise.all([
      fetch(`/api/summary?season_id=${seasonId}`),
      fetch(`/api/rankings?season_id=${seasonId}&limit=500`),
      fetch(
        `/api/history-page?${historyQueryParams(seasonId, 1, state.historyPage.pageSize)}`
      ),
      fetch("/api/player-stats?all_seasons=true&limit=500"),
    ]);

  state.summary = await summaryResponse.json();
  state.rankings = await rankingsResponse.json();
  applyHistoryPayload(await historyResponse.json());
  state.playerStats = await playerStatsResponse.json();

  renderSummaryStats();
  renderHomeSummary();
  renderRankings();
  renderHistory();
  renderPlayerStats();
  await loadDuoStats();
  await loadCurrentGames();
  clearTeamResultOnly();
  hidePlayerDetail();
  document.querySelector("#duo-matchup-result").innerHTML = "";
}

function applyHistoryPayload(payload) {
  state.history = payload.items ?? [];
  state.historyPage = {
    page: payload.page ?? 1,
    pageSize: payload.page_size ?? state.historyPage.pageSize,
    total: payload.total ?? 0,
    totalPages: payload.total_pages ?? 0,
    query: payload.query ?? "",
    allSeasons: payload.all_seasons ?? false,
  };
}

async function loadHistoryPage(page) {
  if (!state.selectedSeasonId) return;
  const targetPage = Math.max(1, Math.min(page, state.historyPage.totalPages || 1));
  const response = await fetch(
    `/api/history-page?${historyQueryParams(
      state.selectedSeasonId,
      targetPage,
      state.historyPage.pageSize
    )}`
  );
  applyHistoryPayload(await response.json());
  renderHistory();
}

async function refreshAfterGameMutation(historyPage = state.historyPage.page) {
  if (!state.selectedSeasonId) return;
  const [summaryResponse, rankingsResponse, playerStatsResponse] = await Promise.all([
    fetch(`/api/summary?season_id=${state.selectedSeasonId}`),
    fetch(`/api/rankings?season_id=${state.selectedSeasonId}&limit=500`),
    fetch("/api/player-stats?all_seasons=true&limit=500"),
  ]);

  state.summary = await summaryResponse.json();
  state.rankings = await rankingsResponse.json();
  state.playerStats = await playerStatsResponse.json();

  renderSummaryStats();
  renderHomeSummary();
  renderRankings();
  renderPlayerStats();
  await Promise.all([loadHistoryPage(historyPage), loadDuoStats(), loadCurrentGames()]);
}

function historyQueryParams(seasonId, page, pageSize) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (state.historyPage.allSeasons) {
    params.set("all_seasons", "true");
  } else {
    params.set("season_id", seasonId);
  }
  if (state.historyPage.query) params.set("q", state.historyPage.query);
  if (hasPermission("game:restore")) params.set("include_canceled", "true");
  return params.toString();
}

function startCurrentGamesPolling() {
  if (state.currentGamesTimer) window.clearInterval(state.currentGamesTimer);
  state.currentGamesTimer = window.setInterval(loadCurrentGames, CURRENT_GAMES_POLL_INTERVAL_MS);
}

async function loadCurrentGames() {
  const panel = document.querySelector("#current-game-panel");
  if (!panel) return;

  const params = new URLSearchParams();
  if (state.selectedSeasonId) params.set("season_id", state.selectedSeasonId);

  try {
    const response = await fetch(`/api/current-games?${params.toString()}`);
    if (!response.ok) throw new Error("현재 진행중 경기 조회에 실패했습니다.");
    state.currentGames = await response.json();
    renderCurrentGames();
  } catch (error) {
    console.error(error);
    panel.innerHTML = `
      <span class="panel-label">Live Match</span>
      <strong>조회 실패</strong>
      <span>진행중 경기 상태를 불러오지 못했습니다.</span>
    `;
  }
}

function renderCurrentGames() {
  const panel = document.querySelector("#current-game-panel");
  if (!panel) return;

  if (!state.currentGames.length) {
    panel.innerHTML = `
      <span class="panel-label">Live Match</span>
      <strong>진행중 경기 없음</strong>
      <span>경기시작을 누르면 이곳에 바로 표시됩니다.</span>
    `;
    return;
  }

  panel.innerHTML = `
    <div class="current-game-heading">
      <span class="panel-label">Live Match</span>
      <strong>현재 진행중</strong>
    </div>
    <div class="current-game-list">
      ${state.currentGames.map(renderCurrentGameCard).join("")}
    </div>
  `;
}

function renderCurrentGameCard(game) {
  const teamA = game.players.filter((player) => player.side === "A");
  const teamB = game.players.filter((player) => player.side === "B");
  return `
    <article class="current-game-card">
      <div class="current-game-meta">
        <span>${escapeHtml(game.season_name ?? `시즌 ${game.season_id}`)}</span>
        <span>${formatKoreaTime(game.played_at)}</span>
      </div>
      <div class="current-game-teams">
        ${renderCurrentGameTeam("1팀", teamA)}
        <span class="current-game-vs">VS</span>
        ${renderCurrentGameTeam("2팀", teamB)}
      </div>
      ${renderCurrentGameActions(game)}
    </article>
  `;
}

function renderCurrentGameActions(game) {
  const discordUrl = state.appSettings?.discord_url;
  const actions = [];
  if (discordUrl) {
    actions.push(
      `<a class="current-game-discord-button" href="${escapeHtml(discordUrl)}" target="_blank" rel="noopener noreferrer">디스코드</a>`
    );
  }
  if (canManageGames()) {
    actions.push(
      `<button type="button" class="current-game-load-button" data-load-current-game="${escapeHtml(
        game.id
      )}">팀짜기로 불러오기</button>`
    );
  }
  if (!actions.length) return "";
  return `<div class="current-game-actions">${actions.join("")}</div>`;
}

function renderCurrentGameTeam(label, players) {
  return `
    <section>
      <strong>${escapeHtml(label)}</strong>
      <div>
        ${players
          .map(
            (player) =>
              `<span>${escapeHtml(player.player_name)} <small>${escapeHtml(
                player.class_name ?? "-"
              )}</small></span>`
          )
          .join("")}
      </div>
    </section>
  `;
}

async function loadCurrentGameIntoTeamBuilder(gameId) {
  const game = state.currentGames.find((item) => item.id === gameId);
  if (!game) {
    showTeamMessage("진행중 경기 정보를 찾지 못했습니다.", true, false);
    navigateToPage("teams", true);
    return;
  }

  const seasonSelect = document.querySelector("#season-select");
  if (seasonSelect && String(seasonSelect.value) !== String(game.season_id)) {
    seasonSelect.value = String(game.season_id);
    await loadSeasonData(String(game.season_id));
  } else {
    state.selectedSeasonId = String(game.season_id);
  }

  const teamA = game.players
    .filter((player) => player.side === "A")
    .sort((left, right) => left.slot - right.slot)
    .map(currentGamePlayerToTeamBuilderPlayer);
  const teamB = game.players
    .filter((player) => player.side === "B")
    .sort((left, right) => left.slot - right.slot)
    .map(currentGamePlayerToTeamBuilderPlayer);
  restoreTeamBuilderInputs([...teamA, ...teamB]);

  state.currentTeamBuilderGameId = game.id;
  state.currentTeamBuilderGameStatus = "in_progress";
  state.currentTeamBuilderTeams = { teamA, teamB };
  state.lastGeneratedTeam1Players = teamA.map((player) => ({ id: player.id, job: player.job }));
  state.lastGeneratedTeam2Players = teamB.map((player) => ({ id: player.id, job: player.job }));
  displayTeams(teamA, teamB, getAllCharacterIdsFromTeams(teamA, teamB).join(), {
    gameId: game.id,
    status: "in_progress",
  });
  navigateToPage("teams", true);
  showTeamMessage("진행중 경기를 팀짜기 화면으로 불러왔습니다. 결과를 입력할 수 있습니다.", false, false);
}

function currentGamePlayerToTeamBuilderPlayer(player) {
  return {
    id: player.player_name,
    job: player.class_name ?? "-",
    rank: DEFAULT_CLASS_RANK,
    isAllCharacterBonus: false,
  };
}

function restoreTeamBuilderInputs(players) {
  players.slice(0, 8).forEach((player, index) => {
    const input = document.querySelector(`#id${index + 1}`);
    if (input) input.value = player.id;
    document.querySelectorAll(`#job${index + 1} input`).forEach((checkbox) => {
      checkbox.checked = true;
    });
  });
}

function getAllCharacterIdsFromTeams(teamA, teamB) {
  return [...teamA, ...teamB]
    .filter((player) => player.isAllCharacterBonus)
    .map((player) => player.id);
}

async function cancelHistoryGame(gameId) {
  const reason = window.prompt("취소 사유를 입력해주세요. 비워도 취소할 수 있습니다.", "");
  if (reason === null) return;

  try {
    const response = await fetch(`/api/admin/games/${encodeURIComponent(gameId)}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: reason.trim() || null }),
    });
    if (!response.ok) throw new Error(await readErrorMessage(response, "이력 취소에 실패했습니다."));
    await refreshAfterGameMutation(state.historyPage.page);
  } catch (error) {
    window.alert(error.message);
  }
}

async function restoreHistoryGame(gameId) {
  const reason = window.prompt("원복 사유를 입력해주세요. 비워도 원복할 수 있습니다.", "");
  if (reason === null) return;

  try {
    const response = await fetch(`/api/admin/games/${encodeURIComponent(gameId)}/restore`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: reason.trim() || null }),
    });
    if (!response.ok) throw new Error(await readErrorMessage(response, "이력 원복에 실패했습니다."));
    await refreshAfterGameMutation(state.historyPage.page);
  } catch (error) {
    window.alert(error.message);
  }
}

async function editHistoryGameResult(gameId) {
  const game = state.history.find((item) => item.id === gameId);
  if (!game) {
    window.alert("수정할 경기를 찾지 못했습니다.");
    return;
  }

  state.currentEditingHistoryGameId = gameId;
  document.querySelector("#result-edit-title").textContent = "경기 결과 수정";
  document.querySelector("#result-edit-meta").textContent = [
    formatKoreaDateTime(game.played_at),
    game.season_name ?? `시즌 ${game.season_id}`,
    game.legacy_game_id ?? game.id,
  ].join(" · ");

  const teamA = game.players.filter((player) => player.side === "A");
  const teamB = game.players.filter((player) => player.side === "B");
  document.querySelector("#result-edit-teams").innerHTML = `
    ${renderResultEditTeam("1팀", teamA, game.winner_side === "A")}
    ${renderResultEditTeam("2팀", teamB, game.winner_side === "B")}
  `;

  document.querySelector("#result-edit-winner-a").checked = game.winner_side !== "B";
  document.querySelector("#result-edit-winner-b").checked = game.winner_side === "B";
  document.querySelector("#result-edit-score-a").value = game.score_a ?? 0;
  document.querySelector("#result-edit-score-b").value = game.score_b ?? 0;
  setResultEditMessage("");

  const modal = document.querySelector("#result-edit-modal");
  modal.hidden = false;
  document.body.classList.add("modal-open");
  document.querySelector("#result-edit-score-a").focus();
}

function renderResultEditTeam(label, players, isCurrentWinner) {
  return `
    <section class="result-edit-team ${isCurrentWinner ? "winner" : ""}">
      <div class="result-edit-team-head">
        <strong>${escapeHtml(label)}</strong>
        ${isCurrentWinner ? "<span>현재 승리팀</span>" : ""}
      </div>
      <div class="result-edit-player-grid">
        ${players
          .map(
            (player) => `
              <span class="result-edit-player">
                <small class="${jobClass(player.class_name ?? "-")}">${escapeHtml(player.class_name ?? "-")}</small>
                <strong>${escapeHtml(player.player_name)}</strong>
              </span>
            `
          )
          .join("")}
      </div>
    </section>
  `;
}

async function submitHistoryResultEdit(event) {
  event.preventDefault();
  const gameId = state.currentEditingHistoryGameId;
  if (!gameId) return;

  const winnerSide = document.querySelector('input[name="result-edit-winner-side"]:checked')?.value;
  const scoreA = Number(document.querySelector("#result-edit-score-a").value);
  const scoreB = Number(document.querySelector("#result-edit-score-b").value);
  if (!winnerSide) {
    setResultEditMessage("승리팀을 선택해주세요.", true);
    return;
  }
  if (!Number.isInteger(scoreA) || !Number.isInteger(scoreB) || scoreA < 0 || scoreB < 0) {
    setResultEditMessage("스코어는 0 이상의 정수로 입력해주세요.", true);
    return;
  }

  const winnerScore = winnerSide === "A" ? scoreA : scoreB;
  const loserScore = winnerSide === "A" ? scoreB : scoreA;
  if (winnerScore <= loserScore) {
    setResultEditMessage("승리팀 점수는 패배팀 점수보다 높아야 합니다.", true);
    return;
  }

  const saveButton = document.querySelector("#result-edit-save");
  saveButton.disabled = true;
  setResultEditMessage("저장 중입니다...");
  try {
    const response = await fetch(`/api/admin/games/${encodeURIComponent(gameId)}/result`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        winner_side: winnerSide,
        score_a: scoreA,
        score_b: scoreB,
      }),
    });
    if (!response.ok) throw new Error(await readErrorMessage(response, "결과 수정에 실패했습니다."));
    closeResultEditModal();
    await refreshAfterGameMutation(state.historyPage.page);
  } catch (error) {
    setResultEditMessage(error.message, true);
  } finally {
    saveButton.disabled = false;
  }
}

function closeResultEditModal() {
  state.currentEditingHistoryGameId = null;
  document.querySelector("#result-edit-modal").hidden = true;
  document.body.classList.remove("modal-open");
  setResultEditMessage("");
}

function setResultEditMessage(message, isError = false) {
  const element = document.querySelector("#result-edit-message");
  element.textContent = message;
  element.classList.toggle("error-text", isError);
}

async function loadDuoStats() {
  const allSeasons = document.querySelector("#duo-all-seasons")?.checked ?? false;
  const minGames = allSeasons ? "20" : "3";
  const params = new URLSearchParams({
    min_games: minGames,
    limit: "300",
    all_seasons: String(allSeasons),
  });
  if (!allSeasons && state.selectedSeasonId) params.set("season_id", state.selectedSeasonId);

  const response = await fetch(`/api/duos?${params.toString()}`);
  state.duoStats = (await response.json()).map((row, index) => ({
    ...row,
    default_rank: index + 1,
  }));
  renderDuoStats();
}

function renderSummaryStats() {
  const stats = [
    ["시즌", state.summary.season_name ?? "-"],
    ["시즌 상태", state.summary.season_status ?? "-"],
    ["시즌 경기", state.summary.season_games.toLocaleString("ko-KR")],
    ["랭킹 인원", state.summary.ranked_players.toLocaleString("ko-KR")],
    ["전체 경기", state.summary.total_games.toLocaleString("ko-KR")],
    ["전체 플레이어", state.summary.total_players.toLocaleString("ko-KR")],
    ["최고 점수", state.summary.top_rating ?? "-"],
    ["전체 시즌", state.summary.total_seasons.toLocaleString("ko-KR")],
  ];

  document.querySelector("#stat-grid").innerHTML = stats
    .map(
      ([label, value]) => `
        <article class="stat-card">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </article>
      `
    )
    .join("");
}

function renderHomeSummary() {
  const title = document.querySelector("#home-season-title");
  const grid = document.querySelector("#home-summary-grid");
  if (!title || !grid || !state.summary) return;

  title.textContent = state.summary.season_name ?? "시즌 정보";
  const stats = [
    ["상태", formatSeasonStatus(state.summary.season_status)],
    ["시즌 경기", state.summary.season_games.toLocaleString("ko-KR")],
    ["랭킹 인원", state.summary.ranked_players.toLocaleString("ko-KR")],
    ["전체 경기", state.summary.total_games.toLocaleString("ko-KR")],
    ["전체 플레이어", state.summary.total_players.toLocaleString("ko-KR")],
    ["최고 점수", state.summary.top_rating ?? "-"],
  ];

  grid.innerHTML = stats
    .map(
      ([label, value]) => `
        <article class="home-summary-card">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </article>
      `
    )
    .join("");
}

function renderRankings() {
  const rankingBody = document.querySelector("#ranking-body");
  if (!state.rankings.length) {
    rankingBody.innerHTML = `<tr><td colspan="7" class="muted">랭킹 데이터가 없습니다.</td></tr>`;
    return;
  }

  rankingBody.innerHTML = state.rankings
    .map(
      (row) => `
        <tr class="clickable-row" data-player-id="${row.player_id}">
          <td>${row.rank ?? "-"}</td>
          <td>
            <button type="button" class="link-button" data-player-id="${row.player_id}">
              ${escapeHtml(row.player_name)}
            </button>
          </td>
          <td>${renderTierBadge(row.tier, "compact")}</td>
          <td>${row.rating}</td>
          <td>${row.wins}</td>
          <td>${row.losses}</td>
          <td>${formatRate(row.win_rate)}</td>
        </tr>
      `
    )
    .join("");
}

function renderHistory() {
  const historyList = document.querySelector("#history-list");
  if (!state.history.length) {
    historyList.innerHTML = `<div class="history-item muted">경기 이력이 없습니다.</div>`;
    renderHistoryPagination();
    return;
  }

  historyList.innerHTML = state.history
    .map((game) => {
      const teamA = game.players.filter((player) => player.side === "A");
      const teamB = game.players.filter((player) => player.side === "B");
      const teamAWon = game.winner_side === "A";
      const teamBWon = game.winner_side === "B";
      const isInProgress = game.status === "IN_PROGRESS";
      const leftLabel = isInProgress ? "1팀" : teamAWon ? "승리팀" : "패배팀";
      const rightLabel = isInProgress ? "2팀" : teamBWon ? "승리팀" : "패배팀";
      return `
        <article class="history-item compact-history-card ${game.status === "CANCELED" ? "canceled-history-card" : ""}">
          <div class="history-card-head">
            <div class="history-meta">
              <span>${formatKoreaDateTime(game.played_at)}</span>
              <span>${escapeHtml(game.season_name ?? `시즌 ${game.season_id}`)}</span>
              <span>${escapeHtml(game.legacy_game_id ?? game.id)}</span>
              <span>${escapeHtml(formatGameStatus(game.status))}</span>
            </div>
            ${renderHistoryActions(game)}
          </div>
          <div class="history-matchup">
            ${renderHistoryTeam(leftLabel, teamA, teamAWon, game.team_a_average_score)}
            <div class="history-score-block">
              <strong>${formatHistoryScore(game.score_a)}</strong>
              <span>:</span>
              <strong>${formatHistoryScore(game.score_b)}</strong>
            </div>
            ${renderHistoryTeam(rightLabel, teamB, teamBWon, game.team_b_average_score)}
          </div>
        </article>
      `;
    })
    .join("");
  renderHistoryPagination();
}

function renderHistoryActions(game) {
  const canCancel = hasPermission("game:cancel");
  const canRestore = hasPermission("game:restore");
  const canEditResult = hasPermission("game:create");
  if (!canCancel && !canRestore && !canEditResult) return "";

  const seasonOpen = isSeasonOpen(game.season_id);
  if (!seasonOpen) {
    return `
      <div class="history-admin-actions">
        <button type="button" disabled title="종료된 시즌의 경기는 변경할 수 없습니다.">종료 시즌</button>
      </div>
    `;
  }

  if (game.status === "CANCELED" && canRestore) {
    return `
      <div class="history-admin-actions">
        <button type="button" data-history-restore="${escapeHtml(game.id)}">취소 원복</button>
      </div>
    `;
  }

  if ((game.status === "ACTIVE" || game.status === "IN_PROGRESS") && (canCancel || canEditResult)) {
    return `
      <div class="history-admin-actions">
        ${
          game.status === "ACTIVE" && canEditResult
            ? `<button type="button" data-history-edit-result="${escapeHtml(game.id)}">결과 수정</button>`
            : ""
        }
        ${
          canCancel
            ? `<button type="button" class="danger-button" data-history-cancel="${escapeHtml(game.id)}">
                이력 취소
              </button>`
            : ""
        }
      </div>
    `;
  }

  return "";
}

function renderHistoryPagination() {
  const { page, pageSize, total, totalPages } = state.historyPage;
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = total === 0 ? 0 : Math.min(page * pageSize, total);
  const queryLabel = state.historyPage.query ? `검색 "${state.historyPage.query}" · ` : "";
  const scopeLabel = state.historyPage.allSeasons ? "전체 경기 · " : "";
  document.querySelector("#history-page-info").textContent =
    totalPages === 0
      ? `${scopeLabel}${queryLabel}0건`
      : `${scopeLabel}${queryLabel}${page} / ${totalPages} 페이지 · ${start}-${end} / ${total.toLocaleString(
          "ko-KR"
        )}건`;
  document.querySelector("#history-first-page").disabled = page <= 1;
  document.querySelector("#history-prev-page").disabled = page <= 1;
  document.querySelector("#history-next-page").disabled = page >= totalPages;
  document.querySelector("#history-last-page").disabled = page >= totalPages;
}

function renderHistoryTeam(label, players, isWinner, averageScore) {
  return `
    <section class="history-team ${isWinner ? "winner" : ""}">
      <div class="history-team-head">
        <span>${escapeHtml(label)}</span>
        <small>평균 ${formatHistoryAverageRating(averageScore)}</small>
      </div>
      <div class="history-player-grid">
        ${players.map(renderHistoryPlayer).join("")}
      </div>
    </section>
  `;
}

function renderHistoryPlayer(player) {
  const className = player.class_name ?? "-";
  return `
    <span class="history-player">
      <small class="${jobClass(className)}">${escapeHtml(className)}</small>
      <strong>${escapeHtml(player.player_name)}</strong>
      <em>
        ${formatHistoryRating(player.rating_before, player.rating_recorded)}
        <b class="${historyDeltaClass(player.rating_delta)}">${formatHistoryDelta(player.rating_delta)}</b>
      </em>
    </span>
  `;
}

function formatHistoryRating(value, recorded = true) {
  if (!recorded) return "기록 없음";
  if (!value || Number(value) <= 0) return "배치 중";
  return Number(value).toLocaleString("ko-KR");
}

function formatHistoryAverageRating(value) {
  if (!value || Number(value) <= 0) return "산정 전";
  return Number(value).toLocaleString("ko-KR");
}

function formatHistoryDelta(value) {
  if (value === null || value === undefined || Number(value) === 0) return "";
  return formatSignedNumber(Number(value));
}

function historyDeltaClass(value) {
  if (value === null || value === undefined || Number(value) === 0) return "";
  return Number(value) > 0 ? "delta-up" : "delta-down";
}

function renderPlayerStats() {
  const body = document.querySelector("#player-stats-body");
  if (!state.playerStats.length) {
    body.innerHTML = `<tr><td colspan="11" class="muted">개인전적 데이터가 없습니다.</td></tr>`;
    return;
  }

  body.innerHTML = sortedPlayerStats()
    .map((row, index) => {
      return `
        <tr>
          <td>${row.rank ?? index + 1}</td>
          <td>${escapeHtml(row.player_name)}</td>
          <td>${row.trophy ?? "-"}</td>
          <td>${row.games_played}</td>
          <td>${row.wins}</td>
          <td>${row.losses}</td>
          <td>${formatRate(row.win_rate)}</td>
          ${JOB_ORDER.map((job) => `<td>${formatClassStats(row, job)}</td>`).join("")}
        </tr>
      `;
    })
    .join("");
  updateSortIndicators("player");
}

function renderDuoStats() {
  const body = document.querySelector("#duo-stats-body");
  if (!state.duoStats.length) {
    body.innerHTML = `<tr><td colspan="6" class="muted">듀오전적 데이터가 없습니다.</td></tr>`;
    return;
  }

  body.innerHTML = sortedDuoStats()
    .map(
      (row, index) => `
        <tr>
          <td>${row.default_rank ?? index + 1}</td>
          <td>
            <button
              type="button"
              class="link-button"
              data-duo-left="${escapeHtml(row.players[0])}"
              data-duo-right="${escapeHtml(row.players[1])}"
            >
              ${escapeHtml(row.duo_name)}
            </button>
          </td>
          <td>${row.total_games}</td>
          <td>${row.wins}</td>
          <td>${row.losses}</td>
          <td>${formatRate(row.win_rate)}</td>
        </tr>
      `
    )
    .join("");
  updateSortIndicators("duo");
}

function sortedPlayerStats() {
  const { key, direction } = state.statSorts.player;
  return [...state.playerStats].sort((left, right) => {
    return comparePlayerStats(left, right, key, direction);
  });
}

function sortedDuoStats() {
  const { key, direction } = state.statSorts.duo;
  return [...state.duoStats].sort((left, right) => {
    return compareDuoStats(left, right, key, direction);
  });
}

function comparePlayerStats(left, right, key, direction) {
  if (key.startsWith("class:")) {
    const className = key.split(":")[1];
    const leftClass = getClassStat(left, className);
    const rightClass = getClassStat(right, className);
    return (
      compareClassSortValue(leftClass, rightClass, direction) ||
      compareValues(left.player_name, right.player_name, "asc")
    );
  }

  if (key === "trophy_score") {
    return (
      compareValues(left.trophy_score, right.trophy_score, direction) ||
      compareValues(left.gold, right.gold, direction) ||
      compareValues(left.silver, right.silver, direction) ||
      compareValues(left.bronze, right.bronze, direction) ||
      compareValues(left.player_name, right.player_name, "asc")
    );
  }

  return (
    compareValues(left[key], right[key], direction) ||
    compareValues(left.player_name, right.player_name, "asc")
  );
}

function compareDuoStats(left, right, key, direction) {
  const leftValue = key === "index" ? left.default_rank : left[key];
  const rightValue = key === "index" ? right.default_rank : right[key];
  return (
    compareValues(leftValue, rightValue, direction) ||
    compareValues(left.duo_name, right.duo_name, "asc")
  );
}

function compareClassSortValue(leftClass, rightClass, direction) {
  const leftGames = leftClass.wins + leftClass.losses;
  const rightGames = rightClass.wins + rightClass.losses;
  const leftValid = leftGames >= CLASS_SORT_MIN_GAMES;
  const rightValid = rightGames >= CLASS_SORT_MIN_GAMES;
  if (!leftValid && !rightValid) {
    return (
      compareValues(leftGames, rightGames, "desc") ||
      compareValues(leftClass.wins, rightClass.wins, "desc")
    );
  }
  if (!leftValid) return 1;
  if (!rightValid) return -1;

  return (
    compareValues(adjustedClassRate(leftClass), adjustedClassRate(rightClass), direction) ||
    compareValues(leftGames, rightGames, direction) ||
    compareValues(leftClass.wins, rightClass.wins, direction)
  );
}

function adjustedClassRate(classStat) {
  const games = classStat.wins + classStat.losses;
  if (games === 0) return null;
  return ((classStat.wins + 2.5) / (games + 5)) * 100;
}

function compareValues(leftValue, rightValue, direction) {
  const leftEmpty = leftValue === null || leftValue === undefined || leftValue === "";
  const rightEmpty = rightValue === null || rightValue === undefined || rightValue === "";
  if (leftEmpty && rightEmpty) return 0;
  if (leftEmpty) return 1;
  if (rightEmpty) return -1;

  const multiplier = direction === "asc" ? 1 : -1;
  if (typeof leftValue === "string" || typeof rightValue === "string") {
    return String(leftValue).localeCompare(String(rightValue), "ko-KR") * multiplier;
  }
  if (leftValue === rightValue) return 0;
  return (leftValue > rightValue ? 1 : -1) * multiplier;
}

function getClassStat(row, className) {
  return (
    row.class_stats.find((item) => item.class_name === className) ?? {
      class_name: className,
      wins: 0,
      losses: 0,
      win_rate: null,
    }
  );
}

function updateSortIndicators(tableName) {
  const selector = tableName === "player" ? "[data-player-sort]" : "[data-duo-sort]";
  const sort = state.statSorts[tableName];
  document.querySelectorAll(selector).forEach((button) => {
    const key = tableName === "player" ? button.dataset.playerSort : button.dataset.duoSort;
    const isActive = key === sort.key;
    button.classList.toggle("active", isActive);
    button.dataset.direction = isActive ? sort.direction : "";
    button.setAttribute("aria-sort", isActive ? sort.direction : "none");
  });
}

async function openPlayerDetail(playerId) {
  const panel = document.querySelector("#player-detail-panel");
  panel.hidden = false;
  panel.innerHTML = `<div class="detail-loading">플레이어 상세를 조회하는 중입니다...</div>`;

  const params = new URLSearchParams();
  if (state.selectedSeasonId) params.set("season_id", state.selectedSeasonId);
  const response = await fetch(`/api/players/${playerId}/detail?${params.toString()}`);
  if (!response.ok) {
    panel.innerHTML = `<div class="error-text">플레이어 상세 조회에 실패했습니다.</div>`;
    return;
  }

  const detail = await response.json();
  renderPlayerDetail(detail);
}

function renderPlayerDetail(detail) {
  const panel = document.querySelector("#player-detail-panel");
  const stats = detail.season_stats;
  panel.hidden = false;
  panel.innerHTML = `
    <div class="detail-header">
      <div>
        <p class="eyebrow">Player Detail</p>
        <h3>${escapeHtml(detail.player_name)}</h3>
        <div class="detail-tier">${renderTierBadge(detail.tier, "large")}</div>
      </div>
      <button type="button" class="close-detail">닫기</button>
    </div>
    ${
      stats
        ? `
          <div class="detail-grid">
            <article>
              <span>순위</span>
              <strong>${stats.rank ?? "-"}</strong>
            </article>
            <article>
              <span>점수</span>
              <strong>${stats.rating ?? "-"}</strong>
            </article>
            <article>
              <span>총 전적</span>
              <strong>${stats.wins}승 ${stats.losses}패</strong>
            </article>
            <article>
              <span>승률</span>
              <strong>${formatRate(stats.win_rate)}</strong>
            </article>
          </div>
          <div class="mini-table">
            ${stats.class_stats.map(renderClassPill).join("")}
          </div>
        `
        : `<p class="muted">해당 시즌의 개인전적이 없습니다.</p>`
    }
    <div class="detail-columns">
      <section>
        <h4>최근 5경기</h4>
        ${renderRecentGames(detail.recent_games)}
      </section>
      <section>
        <h4>Good</h4>
        ${renderDuoList(detail.best_duos)}
      </section>
      <section>
        <h4>Bad</h4>
        ${renderDuoList(detail.worst_duos)}
      </section>
    </div>
  `;
  panel.querySelector(".close-detail").addEventListener("click", hidePlayerDetail);
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function hidePlayerDetail() {
  const panel = document.querySelector("#player-detail-panel");
  panel.hidden = true;
  panel.innerHTML = "";
}

function renderClassPill(row) {
  return `
    <div class="class-pill">
      <span>${escapeHtml(row.class_name)}</span>
      <strong>${row.wins}/${row.losses}</strong>
      <small>${formatRate(row.win_rate)}</small>
    </div>
  `;
}

function renderRecentGames(games) {
  if (!games.length) return `<p class="muted">최근 경기 데이터가 없습니다.</p>`;
  return `
    <ul class="plain-list">
      ${games
        .map(
          (game) => `
            <li>
              <span>${formatKoreaDate(game.played_at)}</span>
              <strong class="${game.result === "승" ? "win-text" : "lose-text"}">
                ${game.result}
              </strong>
              <span>${escapeHtml(game.class_name ?? "-")} · ${escapeHtml(game.score)}</span>
            </li>
          `
        )
        .join("")}
    </ul>
  `;
}

function renderDuoList(duos) {
  if (!duos.length) return `<p class="muted">듀오 데이터가 없습니다.</p>`;
  return `
    <ul class="plain-list">
      ${duos
        .map(
          (duo) => `
            <li>
              <span>${escapeHtml(duo.duo_name)}</span>
              <strong>${duo.wins}/${duo.losses}</strong>
              <span>${formatRate(duo.win_rate)}</span>
            </li>
          `
        )
        .join("")}
    </ul>
  `;
}

async function searchDuoMatchup() {
  const user1 = document.querySelector("#duo-player-1").value.trim();
  const user2 = document.querySelector("#duo-player-2").value.trim();
  const result = document.querySelector("#duo-matchup-result");
  if (!user1 || !user2) {
    result.innerHTML = `<div class="error-text">플레이어 2명을 모두 입력해주세요.</div>`;
    return;
  }

  const allSeasons = document.querySelector("#duo-search-all-seasons")?.checked ?? false;
  const params = new URLSearchParams({
    user1,
    user2,
    all_seasons: String(allSeasons),
  });
  if (!allSeasons && state.selectedSeasonId) params.set("season_id", state.selectedSeasonId);

  result.innerHTML = `<div class="detail-loading">듀오 전적을 조회하는 중입니다...</div>`;
  const response = await fetch(`/api/duo-matchup?${params.toString()}`);
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    result.innerHTML = `<div class="error-text">${
      escapeHtml(detail?.detail ?? "듀오 검색에 실패했습니다.")
    }</div>`;
    return;
  }

  const matchup = await response.json();
  renderDuoMatchup(matchup);
}

function renderDuoMatchup(matchup) {
  const result = document.querySelector("#duo-matchup-result");
  const classes = matchup.class_head_to_head.classes;
  result.innerHTML = `
    <div class="matchup-summary">
      <article>
        <span>같은 팀 전적</span>
        <strong>${formatPairRecord(matchup.team_up)}</strong>
      </article>
      <article>
        <span>상대 전적</span>
        <strong>${formatPairRecord(matchup.vs)}</strong>
      </article>
    </div>
    <div class="table-wrap compact-table h2h-table">
      <table>
        <thead>
          <tr>
            <th>${escapeHtml(matchup.user1)} \\ ${escapeHtml(matchup.user2)}</th>
            ${classes.map((className) => `<th>${escapeHtml(className)}</th>`).join("")}
          </tr>
        </thead>
        <tbody>
          ${classes
            .map(
              (leftClass) => `
                <tr>
                  <th>${escapeHtml(leftClass)}</th>
                  ${classes
                    .map((rightClass) => {
                      const record = matchup.class_head_to_head.matrix[leftClass][rightClass];
                      return `<td>${formatPairRecord(record)}</td>`;
                    })
                    .join("")}
                </tr>
              `
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function showAdminPanel(panelName) {
  if (panelName === "user" && !state.me?.is_super) panelName = "season";
  if (panelName === "mmr" && !hasPermission("mmr:manage")) panelName = "season";
  document.querySelectorAll("[data-admin-tab]").forEach((button) => {
    const active = button.dataset.adminTab === panelName;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  });

  document.querySelectorAll("[data-admin-panel]").forEach((panel) => {
    const active = panel.dataset.adminPanel === panelName;
    panel.hidden = !active;
    panel.classList.toggle("active", active);
  });

  if (panelName === "season" && state.adminSeasons.length === 0) loadAdminSeasons();
  if (panelName === "notice" && state.adminNotices.length === 0) loadAdminNotices();
  if (panelName === "player" && state.adminPlayers.length === 0) loadAdminPlayers();
  if (panelName === "user" && state.adminUsers.length === 0) loadAdminUsers();
  if (panelName === "mmr" && !state.adminScoringRule) loadAdminScoringRule();
  if (panelName === "setting") loadAdminSettings();
}

function renderSuperAdminControls() {
  document.querySelectorAll("[data-super-admin-only]").forEach((element) => {
    if (element.matches("[data-admin-panel]")) return;
    element.hidden = !state.me?.is_super;
  });
}

function renderPermissionControls() {
  document.querySelectorAll("[data-permission-required]").forEach((element) => {
    element.hidden = !hasPermission(element.dataset.permissionRequired);
  });
}

async function loadNotices() {
  const list = document.querySelector("#notice-list");
  list.innerHTML = `<div class="notice-card"><p class="muted">공지사항을 조회하는 중입니다...</p></div>`;
  try {
    const response = await fetch("/api/notices");
    if (!response.ok) throw new Error(await readErrorMessage(response, "공지사항 조회에 실패했습니다."));
    state.notices = await response.json();
    renderNotices();
  } catch (error) {
    console.error(error);
    list.innerHTML = `<div class="notice-card"><p class="error-text">${escapeHtml(error.message)}</p></div>`;
  }
}

function renderNotices() {
  const list = document.querySelector("#notice-list");
  if (!state.notices.length) {
    list.innerHTML = `<div class="notice-card"><p class="muted">등록된 공지사항이 없습니다.</p></div>`;
    return;
  }

  list.innerHTML = state.notices.map(renderNoticeCard).join("");
}

function renderNoticeCard(notice) {
  return `
    <article class="notice-card ${notice.is_pinned ? "pinned" : ""}">
      ${notice.is_pinned ? `<span class="notice-pin">상단 고정</span>` : ""}
      <div class="notice-card-header">
        <h3>${escapeHtml(notice.title)}</h3>
        <span class="notice-meta">${formatSeasonDate(notice.published_at ?? notice.created_at)}</span>
      </div>
      <div class="notice-body">${escapeHtml(notice.body)}</div>
    </article>
  `;
}

async function loadAdminNotices() {
  const body = document.querySelector("#admin-notice-body-list");
  body.innerHTML = `<tr><td colspan="4" class="muted">공지사항 목록을 조회하는 중입니다...</td></tr>`;
  try {
    const response = await fetch("/api/admin/notices");
    if (!response.ok) throw new Error(await readErrorMessage(response, "공지사항 목록 조회에 실패했습니다."));
    state.adminNotices = await response.json();
    renderAdminNotices();
  } catch (error) {
    console.error(error);
    body.innerHTML = `<tr><td colspan="4" class="error-text">${escapeHtml(error.message)}</td></tr>`;
    setAdminNoticeMessage(error.message, true);
  }
}

function renderAdminNotices() {
  const body = document.querySelector("#admin-notice-body-list");
  document.querySelector("#admin-notice-count").textContent =
    `${state.adminNotices.length.toLocaleString("ko-KR")}개`;

  if (!state.adminNotices.length) {
    body.innerHTML = `<tr><td colspan="4" class="muted">등록된 공지사항이 없습니다.</td></tr>`;
    return;
  }

  body.innerHTML = state.adminNotices
    .map(
      (notice) => `
        <tr>
          <td>
            <strong>${escapeHtml(notice.title)}</strong>
            <small class="muted">${escapeHtml(notice.body.slice(0, 60))}${notice.body.length > 60 ? "..." : ""}</small>
          </td>
          <td>
            <span class="status-pill ${notice.is_published ? "active" : "inactive"}">
              ${notice.is_published ? "게시" : "미게시"}
            </span>
            ${notice.is_pinned ? `<span class="status-pill in-progress">고정</span>` : ""}
          </td>
          <td>${formatSeasonDate(notice.published_at)}</td>
          <td>
            <div class="row-actions">
              <button type="button" data-admin-edit-notice="${notice.id}">수정</button>
              <button type="button" class="danger-button" data-admin-delete-notice="${notice.id}">삭제</button>
            </div>
          </td>
        </tr>
      `
    )
    .join("");
}

async function saveAdminNotice(event) {
  event.preventDefault();
  const noticeId = state.currentEditingNoticeId;
  const title = document.querySelector("#admin-notice-title").value.trim();
  const body = document.querySelector("#admin-notice-body").value.trim();
  const isPublished = document.querySelector("#admin-notice-published").checked;
  const isPinned = document.querySelector("#admin-notice-pinned").checked;

  if (!title || !body) {
    setAdminNoticeMessage("제목과 내용을 입력해주세요.", true);
    return;
  }

  const method = noticeId ? "PUT" : "POST";
  const url = noticeId ? `/api/admin/notices/${noticeId}` : "/api/admin/notices";
  try {
    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title,
        body,
        is_published: isPublished,
        is_pinned: isPinned,
      }),
    });
    if (!response.ok) throw new Error(await readErrorMessage(response, "공지사항 저장에 실패했습니다."));
    resetAdminNoticeForm();
    setAdminNoticeMessage(noticeId ? "공지사항을 수정했습니다." : "공지사항을 등록했습니다.", false);
    await loadAdminNotices();
    if (window.location.hash === "#notice") await loadNotices();
  } catch (error) {
    console.error(error);
    setAdminNoticeMessage(error.message, true);
  }
}

function editAdminNotice(noticeId) {
  const notice = state.adminNotices.find((item) => item.id === noticeId);
  if (!notice) return;
  state.currentEditingNoticeId = notice.id;
  document.querySelector("#admin-notice-id").value = String(notice.id);
  document.querySelector("#admin-notice-title").value = notice.title;
  document.querySelector("#admin-notice-body").value = notice.body;
  document.querySelector("#admin-notice-published").checked = notice.is_published;
  document.querySelector("#admin-notice-pinned").checked = notice.is_pinned;
  document.querySelector("#admin-notice-submit").textContent = "수정";
  setAdminNoticeMessage("공지사항을 수정 중입니다.", false);
  document.querySelector("#admin-notice-title").focus();
}

async function deleteAdminNotice(noticeId) {
  const notice = state.adminNotices.find((item) => item.id === noticeId);
  const title = notice?.title ?? "선택한 공지사항";
  if (!window.confirm(`${title} 공지사항을 삭제할까요?`)) return;

  try {
    const response = await fetch(`/api/admin/notices/${noticeId}`, { method: "DELETE" });
    if (!response.ok) throw new Error(await readErrorMessage(response, "공지사항 삭제에 실패했습니다."));
    if (state.currentEditingNoticeId === noticeId) resetAdminNoticeForm();
    setAdminNoticeMessage("공지사항을 삭제했습니다.", false);
    await loadAdminNotices();
    if (window.location.hash === "#notice") await loadNotices();
  } catch (error) {
    console.error(error);
    setAdminNoticeMessage(error.message, true);
  }
}

function resetAdminNoticeForm() {
  state.currentEditingNoticeId = null;
  document.querySelector("#admin-notice-form").reset();
  document.querySelector("#admin-notice-id").value = "";
  document.querySelector("#admin-notice-published").checked = true;
  document.querySelector("#admin-notice-pinned").checked = false;
  document.querySelector("#admin-notice-submit").textContent = "등록";
  setAdminNoticeMessage("", false);
}

function setAdminNoticeMessage(message, isError = false) {
  const element = document.querySelector("#admin-notice-message");
  element.textContent = message;
  element.classList.toggle("error-text", isError);
}

async function loadAdminSeasons() {
  const body = document.querySelector("#admin-season-body");
  body.innerHTML = `<tr><td colspan="5" class="muted">시즌 목록을 조회하는 중입니다...</td></tr>`;
  try {
    const includeDisabled = document.querySelector("#admin-include-disabled-seasons")?.checked ?? false;
    const response = await fetch(`/api/admin/seasons?include_disabled=${includeDisabled}`);
    if (!response.ok) throw new Error(await readErrorMessage(response, "시즌 목록 조회에 실패했습니다."));
    state.adminSeasons = await response.json();
    renderAdminSeasons();
  } catch (error) {
    console.error(error);
    body.innerHTML = `<tr><td colspan="5" class="error-text">시즌 목록 조회에 실패했습니다.</td></tr>`;
    setAdminSeasonMessage(error.message, true);
  }
}

function renderAdminSeasons() {
  const body = document.querySelector("#admin-season-body");
  const openSeason = state.adminSeasons.find((season) => season.status === "OPEN");
  const latestEnabledSeason = state.adminSeasons.find((season) => !season.disabled_at);
  document.querySelector("#admin-open-season").textContent = openSeason?.name ?? "없음";
  document.querySelector("#admin-season-count").textContent =
    `${state.adminSeasons.length.toLocaleString("ko-KR")}개`;
  const nextName = suggestNextSeasonName();
  const seasonNameInput = document.querySelector("#admin-season-name");
  const createSeasonButton = document.querySelector("#admin-create-season-button");
  if (seasonNameInput) seasonNameInput.placeholder = `자동: ${nextName}`;
  if (createSeasonButton) {
    createSeasonButton.disabled = Boolean(openSeason);
    createSeasonButton.title = openSeason
      ? "현재 진행중 시즌을 먼저 마감해야 신규 시즌을 시작할 수 있습니다."
      : "";
  }

  if (!state.adminSeasons.length) {
    body.innerHTML = `<tr><td colspan="5" class="muted">등록된 시즌이 없습니다.</td></tr>`;
    return;
  }

  body.innerHTML = state.adminSeasons
    .map((season) => {
      const isOpen = season.status === "OPEN";
      const isDisabled = Boolean(season.disabled_at);
      const hasAnotherOpen = Boolean(openSeason && openSeason.id !== season.id);
      const canReopen = latestEnabledSeason?.id === season.id;
      return `
        <tr class="${isDisabled ? "inactive-row" : ""}">
          <td>
            <strong>${escapeHtml(season.name)}</strong>
            <small class="muted">#${season.sort_order}</small>
          </td>
          <td>
            <span class="status-pill ${seasonStatusClass(season.status)}">
              ${isDisabled ? "비활성" : formatSeasonStatus(season.status)}
            </span>
          </td>
          <td>${formatSeasonDate(season.starts_at)}</td>
          <td>${formatSeasonDate(season.ends_at)}</td>
          <td>
            <div class="row-actions">
              ${isDisabled ? "" : isOpen
                  ? `<button type="button" class="danger-button" data-admin-close-season="${season.id}">마감</button>`
                  : `<button type="button" class="primary" data-admin-open-season="${season.id}" ${
                      hasAnotherOpen || !canReopen ? "disabled" : ""
                    } title="${hasAnotherOpen ? "진행중 시즌은 1개만 허용됩니다." : !canReopen ? "가장 최근 시즌만 재개할 수 있습니다." : ""}">
                      시작/재개
                    </button>`
              }
              ${!isDisabled && state.me?.is_super && !isOpen
                ? `<button type="button" class="danger-button" data-admin-disable-season="${season.id}">비활성화</button>`
                : ""}
              ${season.scoring_rule_version_id
                ? `<button type="button" data-admin-season-rule="${season.id}">적용 규칙</button>`
                : ""}
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
}

async function createAdminSeason(event) {
  event.preventDefault();
  const openSeason = state.adminSeasons.find((season) => season.status === "OPEN");
  if (openSeason) {
    setAdminSeasonMessage(
      `현재 진행중 시즌(${openSeason.name})을 먼저 마감해야 신규 시즌을 시작할 수 있습니다.`,
      true
    );
    return;
  }

  const input = document.querySelector("#admin-season-name");
  const name = input.value.trim();
  const seasonName = name || suggestNextSeasonName();
  const confirmed = window.confirm(`${seasonName}을(를) 신규 시즌으로 시작할까요?`);
  if (!confirmed) return;

  try {
    const response = await fetch("/api/admin/seasons", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name || null, open_immediately: true }),
    });
    if (!response.ok) throw new Error(await readErrorMessage(response, "신규 시즌 시작에 실패했습니다."));
    const season = await response.json();
    input.value = "";
    setAdminSeasonMessage(`${season.name} 시즌을 시작했습니다.`, false);
    await refreshSeasonsAfterAdminChange(season.id);
  } catch (error) {
    setAdminSeasonMessage(error.message, true);
  }
}

async function openAdminSeason(seasonId) {
  const season = state.adminSeasons.find((item) => item.id === seasonId);
  if (!season) return;
  const confirmed = window.confirm(
    `${season.name}을(를) 진행중 시즌으로 시작/재개할까요?\n진행중 시즌은 1개만 허용됩니다.`
  );
  if (!confirmed) return;
  await changeAdminSeasonStatus(seasonId, "open", `${season.name} 시즌을 시작/재개했습니다.`);
}

async function closeAdminSeason(seasonId) {
  const season = state.adminSeasons.find((item) => item.id === seasonId);
  if (!season) return;
  const confirmed = window.confirm(
    `${season.name}을(를) 마감할까요?\n실수로 마감한 경우 열린 시즌이 없을 때 다시 시작/재개할 수 있습니다.`
  );
  if (!confirmed) return;
  await changeAdminSeasonStatus(seasonId, "close", `${season.name} 시즌을 마감했습니다.`);
}

async function disableAdminSeason(seasonId) {
  const season = state.adminSeasons.find((item) => item.id === seasonId);
  if (!season) return;
  const confirmed = window.confirm(
    `${season.name}을(를) 비활성화할까요?\n공개 화면에서 숨겨지며 다시 활성화할 수 없습니다.`
  );
  if (!confirmed) return;
  await changeAdminSeasonStatus(seasonId, "disable", `${season.name} 시즌을 비활성화했습니다.`);
}

async function openSeasonRuleModal(seasonId) {
  const season = state.adminSeasons.find((item) => item.id === seasonId);
  const modal = document.querySelector("#season-rule-modal");
  const content = document.querySelector("#season-rule-content");
  document.querySelector("#season-rule-title").textContent = `${season?.name ?? "시즌"} MMR 규칙`;
  document.querySelector("#season-rule-subtitle").textContent = "이 시즌에 확정되어 실제 경기 계산에 사용되는 값입니다.";
  content.innerHTML = `<p class="muted">규칙을 불러오는 중입니다...</p>`;
  modal.hidden = false;
  document.body.classList.add("modal-open");
  try {
    const response = await fetch(`/api/admin/seasons/${seasonId}/scoring-rule`);
    if (!response.ok) throw new Error(await readErrorMessage(response, "시즌 규칙 조회에 실패했습니다."));
    const rule = await response.json();
    content.innerHTML = renderSeasonRuleSummary(rule.config);
  } catch (error) {
    content.innerHTML = `<p class="error-text">${escapeHtml(error.message)}</p>`;
  }
}

function closeSeasonRuleModal() {
  document.querySelector("#season-rule-modal").hidden = true;
  document.body.classList.remove("modal-open");
}

function renderSeasonRuleSummary(config) {
  const entries = [
    ["최초 점수", config.initial_score, "점"],
    ["배치 경기", config.placement_game_count, "판"],
    ["배치 승리 점수", config.placement_win_points, "점"],
    ["승리 K값", config.winner_k, ""],
    ["패배 K값", config.loser_k, ""],
    ["승리 기대값 상수", config.winner_expected_score_constant, ""],
    ["패배 기대값 상수", config.loser_expected_score_constant, ""],
    ["패배 보정", Number(config.loss_scale).toFixed(2), "배"],
    ["올캐릭 보너스", `${(Number(config.all_character_bonus_ratio) * 100).toFixed(0)}%`, ""],
  ];
  return `
    <div class="season-rule-grid">
      ${entries.map(([label, value, unit]) => `
        <div><span>${label}</span><strong>${value}${unit}</strong></div>
      `).join("")}
    </div>
    <div class="season-tier-summary">
      <span>티어 기준</span>
      ${TIER_THRESHOLD_NAMES.map((name) => `<b>${name} ${Number(config.tier_thresholds?.[name] ?? 0).toLocaleString("ko-KR")}</b>`).join("")}
    </div>
  `;
}

async function changeAdminSeasonStatus(seasonId, action, successMessage) {
  try {
    const response = await fetch(`/api/admin/seasons/${seasonId}/${action}`, { method: "POST" });
    if (!response.ok) throw new Error(await readErrorMessage(response, "시즌 상태 변경에 실패했습니다."));
    const changedSeason = await response.json();
    setAdminSeasonMessage(successMessage, false);
    await refreshSeasonsAfterAdminChange(changedSeason.id);
  } catch (error) {
    setAdminSeasonMessage(error.message, true);
  }
}

function suggestNextSeasonName() {
  const maxSortOrder = state.adminSeasons.reduce(
    (maxValue, season) => Math.max(maxValue, Number(season.sort_order) || 0),
    0
  );
  return `시즌${maxSortOrder + 1}`;
}

async function refreshSeasonsAfterAdminChange(preferredSeasonId) {
  const seasonSelect = document.querySelector("#season-select");
  const response = await fetch("/api/seasons");
  state.seasons = await response.json();
  renderSeasons(seasonSelect);
  const preferredValue = String(preferredSeasonId ?? state.selectedSeasonId ?? "");
  if ([...seasonSelect.options].some((option) => option.value === preferredValue)) {
    seasonSelect.value = preferredValue;
  }
  await loadSeasonData(seasonSelect.value);
  await loadAdminSeasons();
}

function setAdminSeasonMessage(message, isError = false) {
  const element = document.querySelector("#admin-season-message");
  element.textContent = message;
  element.classList.toggle("error-text", isError);
}

async function loadAdminScoringRule() {
  if (!hasPermission("mmr:manage")) return;
  setAdminMmrMessage("MMR 설정을 조회하는 중입니다...", false);
  try {
    const response = await fetch("/api/admin/scoring-rule");
    if (!response.ok) throw new Error(await readErrorMessage(response, "MMR 설정 조회에 실패했습니다."));
    state.adminScoringRule = await response.json();
    renderAdminScoringRule();
    setAdminMmrMessage("", false);
  } catch (error) {
    console.error(error);
    setAdminMmrMessage(error.message, true);
  }
}

function renderAdminScoringRule() {
  const rule = state.adminScoringRule;
  if (!rule) return;
  const config = rule.config ?? {};
  document.querySelector("#admin-mmr-status").textContent = rule.editable
    ? "다음 시즌 적용 예정"
    : "수정 불가";
  document.querySelector("#admin-mmr-lock-message").textContent =
    "여기서 저장한 규칙은 다음 시즌을 시작할 때 확정됩니다. 진행중·마감 시즌의 규칙은 바뀌지 않습니다.";

  document.querySelectorAll("[data-scoring-field]").forEach((input) => {
    input.value = config[input.dataset.scoringField] ?? "";
    input.disabled = !rule.editable;
  });
  document.querySelectorAll("[data-tier-field]").forEach((input) => {
    input.value = config.tier_thresholds?.[input.dataset.tierField] ?? "";
    input.disabled = !rule.editable;
  });
  document.querySelector("#admin-mmr-save").disabled = !rule.editable;
}

async function saveAdminScoringRule(event) {
  event.preventDefault();
  const payload = collectScoringConfigFromForm();
  const tierError = validateTierThresholds(payload.tier_thresholds);
  if (tierError) {
    setAdminMmrMessage(tierError, true);
    return;
  }

  try {
    const response = await fetch("/api/admin/scoring-rule", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await readErrorMessage(response, "MMR 설정 저장에 실패했습니다."));
    state.adminScoringRule = await response.json();
    renderAdminScoringRule();
    setAdminMmrMessage("MMR 설정을 저장했습니다.", false);
  } catch (error) {
    console.error(error);
    setAdminMmrMessage(error.message, true);
  }
}

function collectScoringConfigFromForm() {
  const config = {};
  document.querySelectorAll("[data-scoring-field]").forEach((input) => {
    const value = Number(input.value);
    config[input.dataset.scoringField] = Number.isFinite(value) ? value : 0;
  });
  config.tier_thresholds = {};
  document.querySelectorAll("[data-tier-field]").forEach((input) => {
    const value = Number(input.value);
    config.tier_thresholds[input.dataset.tierField] = Number.isFinite(value) ? value : 0;
  });
  return config;
}

function validateTierThresholds(thresholds) {
  for (let index = 0; index < TIER_THRESHOLD_NAMES.length - 1; index += 1) {
    const higher = TIER_THRESHOLD_NAMES[index];
    const lower = TIER_THRESHOLD_NAMES[index + 1];
    if (Number(thresholds[higher]) <= Number(thresholds[lower])) {
      return `${higher} 기준은 ${lower} 기준보다 높아야 합니다.`;
    }
  }
  return "";
}

function setAdminMmrMessage(message, isError = false) {
  const element = document.querySelector("#admin-mmr-message");
  element.textContent = message;
  element.classList.toggle("error-text", isError);
}

async function loadAdminSettings() {
  if (!hasPermission("admin:manage")) return;
  try {
    const response = await fetch("/api/admin/settings");
    if (!response.ok) throw new Error(await readErrorMessage(response, "설정 조회에 실패했습니다."));
    state.appSettings = await response.json();
    document.querySelector("#admin-discord-url").value = state.appSettings.discord_url ?? "";
    setAdminSettingMessage("", false);
  } catch (error) {
    console.error(error);
    setAdminSettingMessage(error.message, true);
  }
}

async function saveAdminSettings(event) {
  event.preventDefault();
  const discordUrl = document.querySelector("#admin-discord-url").value.trim() || null;
  try {
    const response = await fetch("/api/admin/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ discord_url: discordUrl }),
    });
    if (!response.ok) throw new Error(await readErrorMessage(response, "설정 저장에 실패했습니다."));
    state.appSettings = await response.json();
    document.querySelector("#admin-discord-url").value = state.appSettings.discord_url ?? "";
    renderCurrentGames();
    setAdminSettingMessage("설정을 저장했습니다.", false);
  } catch (error) {
    console.error(error);
    setAdminSettingMessage(error.message, true);
  }
}

function setAdminSettingMessage(message, isError = false) {
  const element = document.querySelector("#admin-setting-message");
  element.textContent = message;
  element.classList.toggle("error-text", isError);
}

function showMmrSection(sectionName) {
  document.querySelectorAll("[data-mmr-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.mmrTab === sectionName);
  });
  document.querySelectorAll("[data-mmr-section]").forEach((section) => {
    section.classList.toggle("active", section.dataset.mmrSection === sectionName);
  });
}

function openMmrSimulator() {
  if (!state.adminScoringRule) {
    setAdminMmrMessage("MMR 설정을 먼저 조회해주세요.", true);
    return;
  }
  populateMmrSimulatorConfig(state.adminScoringRule.config ?? {});
  renderMmrSimulation();
  document.querySelector("#mmr-simulator-modal").hidden = false;
  document.body.classList.add("modal-open");
}

function closeMmrSimulator() {
  document.querySelector("#mmr-simulator-modal").hidden = true;
  document.body.classList.remove("modal-open");
}

function populateMmrSimulatorConfig(config) {
  document.querySelectorAll("[data-sim-config-field]").forEach((input) => {
    input.value = config[input.dataset.simConfigField] ?? "";
  });
}

function collectScoringConfigFromSimulator() {
  const config = {};
  document.querySelectorAll("[data-sim-config-field]").forEach((input) => {
    const value = Number(input.value);
    config[input.dataset.simConfigField] = Number.isFinite(value) ? value : 0;
  });
  return config;
}

function renderMmrSimulation() {
  const config = collectScoringConfigFromSimulator();
  const myScore = Number(document.querySelector("#sim-my-score").value || 0);
  const opponentAverage = Number(document.querySelector("#sim-opponent-score").value || 0);
  const winnerScore = Number(document.querySelector("#sim-winner-score").value || 0);
  const loserScore = Number(document.querySelector("#sim-loser-score").value || 0);
  const isAllCharacterBonus = document.querySelector("#sim-all-character").checked;
  const result = document.querySelector("#mmr-simulator-result");

  if (config.winner_k <= 0 || config.loser_k <= 0 || config.winner_expected_score_constant <= 0 || config.loser_expected_score_constant <= 0) {
    result.innerHTML = `<p class="error-text">K값과 기대값 상수는 0보다 커야 합니다.</p>`;
    return;
  }

  if (winnerScore <= loserScore) {
    result.innerHTML = `<p class="error-text">승리팀 스코어는 패배팀 스코어보다 높아야 합니다.</p>`;
    return;
  }

  const win = simulateMmrWin({
    myScore,
    opponentAverage,
    winnerK: config.winner_k,
    winnerExpectedConstant: config.winner_expected_score_constant,
    allCharacterBonusRatio: config.all_character_bonus_ratio,
    isAllCharacterBonus,
  });
  const loss = simulateMmrLoss({
    myScore,
    opponentAverage,
    winnerScore,
    loserScore,
    loserK: config.loser_k,
    loserExpectedConstant: config.loser_expected_score_constant,
    lossScale: config.loss_scale,
  });

  result.innerHTML = `
    <article class="mmr-result-card win">
      <span>승리 시</span>
      <strong>${formatSignedNumber(win.delta)}점</strong>
      <small>예상 점수 ${win.afterScore.toLocaleString("ko-KR")} · 기대 승률 ${formatPercent(win.expectedRate)}</small>
    </article>
    <article class="mmr-result-card loss">
      <span>패배 시</span>
      <strong>${formatSignedNumber(loss.delta)}점</strong>
      <small>예상 점수 ${loss.afterScore.toLocaleString("ko-KR")} · 기대값 ${formatPercent(loss.expectedRate)}</small>
    </article>
  `;
}

function simulateMmrWin({
  myScore,
  opponentAverage,
  winnerK,
  winnerExpectedConstant,
  allCharacterBonusRatio,
  isAllCharacterBonus,
}) {
  const expectedRate = expectedMmrRate(myScore, opponentAverage, winnerExpectedConstant);
  const baseDelta = winnerK * (1 - expectedRate);
  const bonusDelta = isAllCharacterBonus ? baseDelta * allCharacterBonusRatio : 0;
  const afterScore = Math.ceil(myScore + baseDelta + bonusDelta);
  return { expectedRate, afterScore, delta: afterScore - myScore };
}

function simulateMmrLoss({
  myScore,
  opponentAverage,
  winnerScore,
  loserScore,
  loserK,
  loserExpectedConstant,
  lossScale,
}) {
  const expectedRate = expectedMmrRate(myScore, opponentAverage, loserExpectedConstant);
  const scoreFactor = 1 - loserScore / winnerScore / 2;
  const afterScore = googleRound(
    myScore + loserK * (0 - expectedRate) * lossScale * scoreFactor
  );
  return { expectedRate, afterScore, delta: afterScore - myScore };
}

function expectedMmrRate(myScore, opponentAverage, constant) {
  return 1 / (1 + 10 ** ((opponentAverage - myScore) / constant));
}

function googleRound(value) {
  return Math.floor(value + 0.5);
}

function formatSignedNumber(value) {
  return value > 0 ? `+${value.toLocaleString("ko-KR")}` : value.toLocaleString("ko-KR");
}

function formatPercent(value) {
  return `${(value * 100).toFixed(1)}%`;
}

async function loadAdminPlayers() {
  const includeInactive = document.querySelector("#admin-include-inactive")?.checked ?? true;
  const query = document.querySelector("#admin-player-search")?.value.trim() ?? "";
  const params = new URLSearchParams({
    include_inactive: String(includeInactive),
  });
  if (query) params.set("q", query);

  const body = document.querySelector("#admin-player-body");
  body.innerHTML = `<tr><td colspan="7" class="muted">유저 목록을 조회하는 중입니다...</td></tr>`;
  try {
    const response = await fetch(`/api/admin/players?${params.toString()}`);
    if (!response.ok) throw new Error(await response.text());
    state.adminPlayers = await response.json();
    renderAdminPlayers();
  } catch (error) {
    console.error(error);
    body.innerHTML = `<tr><td colspan="7" class="error-text">유저 목록 조회에 실패했습니다.</td></tr>`;
  }
}

async function loadAdminUsers() {
  if (!state.me?.is_super) return;
  const body = document.querySelector("#admin-user-body");
  body.innerHTML = `<tr><td colspan="4" class="muted">관리자 계정을 조회하는 중입니다...</td></tr>`;
  try {
    const response = await fetch("/api/admin/users");
    if (!response.ok) throw new Error(await readErrorMessage(response, "관리자 계정 조회에 실패했습니다."));
    state.adminUsers = await response.json();
    renderAdminUsers();
  } catch (error) {
    console.error(error);
    body.innerHTML = `<tr><td colspan="4" class="error-text">${escapeHtml(error.message)}</td></tr>`;
    setAdminUserMessage(error.message, true);
  }
}

function renderAdminUsers() {
  const body = document.querySelector("#admin-user-body");
  document.querySelector("#admin-user-count").textContent =
    `${state.adminUsers.length.toLocaleString("ko-KR")}명`;

  if (!state.adminUsers.length) {
    body.innerHTML = `<tr><td colspan="4" class="muted">Google 로그인 이력이 있는 계정이 없습니다.</td></tr>`;
    return;
  }

  body.innerHTML = state.adminUsers.map(renderAdminUserRow).join("");
}

function renderAdminUserRow(user) {
  const permissionSet = new Set(user.permissions ?? []);
  const isCurrentUser = user.email === state.me?.email;
  return `
    <tr class="${user.is_disabled ? "inactive-row" : ""}">
      <td>
        <strong>${escapeHtml(user.display_name || user.email)}</strong>
        <small class="muted">${escapeHtml(user.email)}</small>
      </td>
      <td>
        <span class="status-pill ${user.is_disabled ? "inactive" : user.is_super ? "in-progress" : permissionSet.size ? "active" : "inactive"}">
          ${user.is_disabled ? "비활성" : user.is_super ? "Super" : permissionSet.size ? "운영자" : "권한 없음"}
        </span>
      </td>
      <td>
        <div class="permission-grid" data-permission-group="${user.id}">
          <label class="inline-check">
            <input type="checkbox" data-permission-super="${user.id}" ${user.is_super ? "checked" : ""} ${isCurrentUser ? "disabled" : ""} />
            <span>Super</span>
          </label>
          ${ADMIN_PERMISSION_OPTIONS.map(
            ([value, label]) => `
              <label class="inline-check">
                <input type="checkbox" value="${escapeHtml(value)}" data-permission-value="${user.id}" ${
                  permissionSet.has(value) ? "checked" : ""
                } />
                <span>${escapeHtml(label)}</span>
              </label>
            `
          ).join("")}
        </div>
      </td>
      <td>
        <div class="row-actions">
          <button type="button" class="primary" data-admin-save-user="${user.id}">저장</button>
          ${
            user.is_disabled
              ? `<button type="button" data-admin-restore-user="${user.id}">복구</button>`
              : `<button type="button" class="danger-button" data-admin-disable-user="${user.id}" ${isCurrentUser ? "disabled" : ""}>비활성</button>`
          }
        </div>
      </td>
    </tr>
  `;
}

async function saveAdminUserPermissions(userId) {
  const user = state.adminUsers.find((item) => item.id === userId);
  if (!user) return;
  const isSuper = document.querySelector(`[data-permission-super="${userId}"]`)?.checked ?? false;
  const permissions = [...document.querySelectorAll(`[data-permission-value="${userId}"]:checked`)].map(
    (input) => input.value
  );

  try {
    const response = await fetch(`/api/admin/users/${userId}/permissions`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_super: isSuper, permissions }),
    });
    if (!response.ok) throw new Error(await readErrorMessage(response, "관리자 권한 저장에 실패했습니다."));
    setAdminUserMessage(`${user.email} 권한을 저장했습니다.`, false);
    await loadAdminUsers();
  } catch (error) {
    console.error(error);
    setAdminUserMessage(error.message, true);
  }
}

async function disableAdminUser(userId) {
  const user = state.adminUsers.find((item) => item.id === userId);
  if (!user || !window.confirm(`${user.email} 계정을 비활성화할까요?`)) return;
  try {
    const response = await fetch(`/api/admin/users/${userId}/disable`, { method: "POST" });
    if (!response.ok) throw new Error(await readErrorMessage(response, "관리자 계정 비활성화에 실패했습니다."));
    setAdminUserMessage(`${user.email} 계정을 비활성화했습니다.`, false);
    await loadAdminUsers();
  } catch (error) {
    console.error(error);
    setAdminUserMessage(error.message, true);
  }
}

async function restoreAdminUser(userId) {
  const user = state.adminUsers.find((item) => item.id === userId);
  if (!user) return;
  try {
    const response = await fetch(`/api/admin/users/${userId}/restore`, { method: "POST" });
    if (!response.ok) throw new Error(await readErrorMessage(response, "관리자 계정 복구에 실패했습니다."));
    setAdminUserMessage(`${user.email} 계정을 복구했습니다.`, false);
    await loadAdminUsers();
  } catch (error) {
    console.error(error);
    setAdminUserMessage(error.message, true);
  }
}

function setAdminUserMessage(message, isError = false) {
  const element = document.querySelector("#admin-user-message");
  element.textContent = message;
  element.classList.toggle("error-text", isError);
}

function setupAdminClassRankSelects() {
  document.querySelectorAll("[data-admin-character]").forEach((select) => {
    select.innerHTML = CLASS_RANKS.map(
      (rank) =>
        `<option value="${rank}" ${rank === DEFAULT_CLASS_RANK ? "selected" : ""}>${rank}</option>`
    ).join("");
  });
}

function normalizeClassRank(rank) {
  const normalized = String(rank || DEFAULT_CLASS_RANK).trim().toUpperCase();
  return CLASS_RANKS.includes(normalized) ? normalized : DEFAULT_CLASS_RANK;
}

function classRankFor(classRanks, job) {
  return normalizeClassRank(classRanks?.[job]);
}

function classRankScore(rank) {
  return CLASS_RANK_SCORES[normalizeClassRank(rank)] ?? CLASS_RANK_SCORES[DEFAULT_CLASS_RANK];
}

function renderClassRankOptions(selectedRank) {
  return CLASS_RANKS.map(
    (rank) => `<option value="${rank}" ${rank === normalizeClassRank(selectedRank) ? "selected" : ""}>${rank}</option>`
  ).join("");
}

function renderClassRankSummary(classRanks) {
  return `
    <div class="class-rank-summary">
      ${JOB_ORDER.map(
        (job) => `
          <span class="class-rank-pill">
            <b>${escapeHtml(job)}</b>
            <strong>${classRankFor(classRanks, job)}</strong>
          </span>
        `
      ).join("")}
    </div>
  `;
}

function renderAdminPlayers() {
  const body = document.querySelector("#admin-player-body");
  document.querySelector("#admin-player-count").textContent =
    `${state.adminPlayers.length.toLocaleString("ko-KR")}명`;

  if (!state.adminPlayers.length) {
    body.innerHTML = `<tr><td colspan="7" class="muted">등록된 유저가 없습니다.</td></tr>`;
    return;
  }

  body.innerHTML = state.adminPlayers
    .map(
      (player) => `
        <tr class="clickable-row ${player.is_active ? "" : "inactive-row"}" data-admin-player-row="${player.player_id}">
          <td>${escapeHtml(player.player_name)}</td>
          <td>${renderTierBadge(player.current_tier, "micro")}</td>
          <td>${renderClassRankSummary(player.class_ranks)}</td>
          <td>
            <span class="status-pill ${player.is_active ? "active" : "inactive"}">
              ${player.is_active ? "활성" : "비활성"}
            </span>
          </td>
          <td>${player.total_games}</td>
          <td>${player.game_refs + player.stats_refs}</td>
          <td>
            <div class="row-actions">
              <button type="button" data-admin-edit-player="${player.player_id}">수정</button>
              ${
                player.is_active
                  ? `<button type="button" class="danger-button" data-admin-delete-player="${player.player_id}">삭제</button>`
                  : `<button type="button" data-admin-restore-player="${player.player_id}">복구</button>`
              }
            </div>
          </td>
        </tr>
      `
    )
    .join("");
}

async function createAdminPlayer(event) {
  event.preventDefault();
  const message = document.querySelector("#admin-player-message");
  const form = document.querySelector("#admin-player-form");
  const displayName = document.querySelector("#admin-player-name").value.trim();
  const characters = [...document.querySelectorAll("[data-admin-character]")].map((select) => ({
    class_name: select.dataset.adminCharacter,
    class_rank: normalizeClassRank(select.value),
  }));

  if (!displayName) {
    setAdminPlayerMessage("닉네임을 입력해주세요.", true);
    return;
  }

  try {
    const isEditing = state.editingAdminPlayerId !== null;
    const response = await fetch(
      isEditing ? `/api/admin/players/${state.editingAdminPlayerId}` : "/api/admin/players",
      {
      method: isEditing ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: displayName, characters }),
      }
    );
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail ?? "유저 등록에 실패했습니다.");
    }
    resetAdminPlayerForm();
    message.classList.remove("error-text");
    setAdminPlayerMessage(isEditing ? "유저 정보를 수정했습니다." : "유저를 등록했습니다.", false);
    await refreshTeamPlayers();
    await loadAdminPlayers();
    await loadCurrentGames();
  } catch (error) {
    console.error(error);
    setAdminPlayerMessage(error.message || "유저 등록에 실패했습니다.", true);
  }
}

function loadAdminPlayerIntoForm(playerId) {
  const player = state.adminPlayers.find((item) => item.player_id === playerId);
  if (!player) return;

  state.editingAdminPlayerId = playerId;
  document.querySelector("#admin-player-form-title").textContent = "유저 수정";
  document.querySelector("#admin-player-submit").textContent = "수정 저장";
  document.querySelector("#admin-player-name").value = player.player_name;
  document.querySelectorAll("[data-admin-character]").forEach((select) => {
    select.value = classRankFor(player.class_ranks, select.dataset.adminCharacter);
  });
  setAdminPlayerMessage(`${player.player_name} 정보를 수정 중입니다.`, false);
}

function resetAdminPlayerForm() {
  state.editingAdminPlayerId = null;
  document.querySelector("#admin-player-form").reset();
  setupAdminClassRankSelects();
  document.querySelector("#admin-player-form-title").textContent = "유저 등록";
  document.querySelector("#admin-player-submit").textContent = "등록";
}

async function deleteAdminPlayer(playerId) {
  const player = state.adminPlayers.find((item) => item.player_id === playerId);
  const label = player?.player_name ?? "선택한 유저";
  if (!window.confirm(`${label} 유저를 삭제/비활성 처리할까요?`)) return;

  try {
    const response = await fetch(`/api/admin/players/${playerId}`, { method: "DELETE" });
    if (!response.ok) throw new Error("유저 삭제에 실패했습니다.");
    const result = await response.json();
    setAdminPlayerMessage(
      result.deleted
        ? "유저를 완전히 삭제했습니다."
        : "참조 기록이 있어 유저를 비활성 처리했습니다.",
      false
    );
    await refreshTeamPlayers();
    await loadAdminPlayers();
  } catch (error) {
    console.error(error);
    setAdminPlayerMessage(error.message || "유저 삭제에 실패했습니다.", true);
  }
}

async function restoreAdminPlayer(playerId) {
  try {
    const response = await fetch(`/api/admin/players/${playerId}/restore`, { method: "POST" });
    if (!response.ok) throw new Error("유저 복구에 실패했습니다.");
    setAdminPlayerMessage("유저를 활성화했습니다.", false);
    await refreshTeamPlayers();
    await loadAdminPlayers();
  } catch (error) {
    console.error(error);
    setAdminPlayerMessage(error.message || "유저 복구에 실패했습니다.", true);
  }
}

function setAdminPlayerMessage(message, isError) {
  const element = document.querySelector("#admin-player-message");
  element.textContent = message;
  element.classList.toggle("error-text", isError);
}

function renderTeamInputs() {
  document.querySelector("#team-input-grid").innerHTML = Array.from({ length: 8 }, (_, index) => {
    return `
      <article class="team-input-card">
        <label class="autocomplete-host">
          <span>P${index + 1}</span>
          <input class="input_text" type="text" id="id${index + 1}" autocomplete="off" />
          <div class="autocomplete-list" hidden></div>
        </label>
        <div class="job-checks" id="job${index + 1}">
          ${JOB_ORDER.map(
            (job) => `
              <label>
                <input type="checkbox" value="${job}" checked />
                <span>${job}</span>
              </label>
            `
          ).join("")}
        </div>
      </article>
    `;
  }).join("");

  document.querySelectorAll("#team-input-grid .input_text").forEach(setupNameAutocomplete);
}

function setupNameAutocomplete(input) {
  if (!input) return;
  const host = input.closest(".autocomplete-host");
  const list = host?.querySelector(".autocomplete-list");
  if (!host || !list) return;

  let activeIndex = -1;

  const render = () => {
    const term = input.value.trim().toLowerCase();
    if (!term) {
      hideAutocomplete(list);
      return;
    }
    const matches = state.teamPlayers
      .filter((player) => player.player_name.toLowerCase().includes(term))
      .slice(0, AUTOCOMPLETE_LIMIT);

    if (!matches.length) {
      hideAutocomplete(list);
      return;
    }

    activeIndex = -1;
    list.innerHTML = matches
      .map(
        (player, index) => `
          <button type="button" data-index="${index}" data-name="${escapeHtml(player.player_name)}">
            <span class="autocomplete-main">
              <strong>${escapeHtml(player.player_name)}</strong>
              ${renderTierBadge(player.current_tier, "micro")}
            </span>
          </button>
        `
      )
      .join("");
    list.hidden = false;
  };

  input.addEventListener("input", render);
  input.addEventListener("focus", () => {
    if (input.value.trim()) render();
  });
  input.addEventListener("keydown", (event) => {
    const buttons = [...list.querySelectorAll("button")];
    if (list.hidden || !buttons.length) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      activeIndex = Math.min(activeIndex + 1, buttons.length - 1);
      markActiveSuggestion(buttons, activeIndex);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
      markActiveSuggestion(buttons, activeIndex);
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      input.value = buttons[activeIndex].dataset.name;
      hideAutocomplete(list);
    } else if (event.key === "Escape") {
      hideAutocomplete(list);
    }
  });
  list.addEventListener("mousedown", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    event.preventDefault();
    input.value = button.dataset.name;
    hideAutocomplete(list);
  });
}

function markActiveSuggestion(buttons, activeIndex) {
  buttons.forEach((button, index) => {
    button.classList.toggle("active", index === activeIndex);
  });
}

function hideAutocomplete(list) {
  list.hidden = true;
  list.innerHTML = "";
}

function hideAllAutocomplete() {
  document.querySelectorAll(".autocomplete-list").forEach(hideAutocomplete);
}

function getPlayerData() {
  const players = [];
  for (let index = 1; index <= 8; index += 1) {
    const jobInputs = [...document.querySelectorAll(`#job${index} input:checked`)];
    const jobs = jobInputs.map((input) => input.value);
    const id = document.querySelector(`#id${index}`).value.trim();

    if (jobs.length === 0) {
      showTeamMessage("모든 유저의 직업을 선택해주세요.");
      return null;
    }
    if (id) players.push({ jobs, id });
  }

  const uniqueIds = new Set(players.map((player) => player.id));
  if (uniqueIds.size !== players.length) {
    showTeamMessage("중복된 플레이어 이름이 있습니다.");
    return null;
  }
  if (players.length !== 8) {
    showTeamMessage("8명의 플레이어 정보를 정확히 입력해주세요.");
    return null;
  }
  return players.map((player) => {
    const meta = state.teamPlayers.find((candidate) => candidate.player_name === player.id);
    return {
      ...player,
      classRanks: meta?.class_ranks ?? {},
    };
  });
}

function getAllCharPlayers() {
  const allCharPlayers = [];
  for (let index = 1; index <= 8; index += 1) {
    const jobs = [...document.querySelectorAll(`#job${index} input:checked`)];
    const id = document.querySelector(`#id${index}`).value.trim();
    if (jobs.length === 4 && id) allCharPlayers.push(id);
  }
  return allCharPlayers.join();
}

function shuffle(array) {
  const shuffled = [...array];
  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [shuffled[index], shuffled[swapIndex]] = [shuffled[swapIndex], shuffled[index]];
  }
  return shuffled;
}

function isValidTeam(team) {
  const teamJobs = team.map((player) => player.job);
  return JOB_ORDER.every((job) => teamJobs.includes(job));
}

function checkForbiddenCombination(team) {
  const teamIds = team.map((player) => player.id);
  const hasUserA = teamIds.includes(USER_A);
  const hasUserB = teamIds.some((id) => USERS_B.includes(id));
  return hasUserA && hasUserB;
}

function rankForPlayerJob(player, job) {
  return classRankFor(player.classRanks, job);
}

function teamRankScore(team) {
  return team.reduce((sum, player) => sum + classRankScore(player.rank), 0);
}

function teamBalanceDiff(team1, team2) {
  return Math.abs(teamRankScore(team1) - teamRankScore(team2));
}

function generateTeamsWithRules(players, lastTeam1, lastTeam2, isFirstRun, maxAttempts) {
  let attempts = 0;
  let bestTeam1 = null;
  let bestTeam2 = null;
  let bestDiff = Number.POSITIVE_INFINITY;
  let successful = false;

  while (attempts < maxAttempts) {
    attempts += 1;
    const assignedPlayers = [];
    const currentPlayersForAttempt = JSON.parse(JSON.stringify(players));
    const tempAssigned = [];

    JOB_ORDER.forEach((job) => {
      const eligiblePlayers = currentPlayersForAttempt.filter((player) => {
        return player.jobs.includes(job) && !tempAssigned.some((picked) => picked.id === player.id);
      });
      if (eligiblePlayers.length > 0) {
        const chosenPlayer = eligiblePlayers[Math.floor(Math.random() * eligiblePlayers.length)];
        tempAssigned.push({
          id: chosenPlayer.id,
          job,
          rank: rankForPlayerJob(chosenPlayer, job),
        });
        const playerIndex = currentPlayersForAttempt.findIndex(
          (player) => player.id === chosenPlayer.id
        );
        if (playerIndex > -1) currentPlayersForAttempt.splice(playerIndex, 1);
      }
    });

    assignedPlayers.push(...tempAssigned);
    players.forEach((player) => {
      if (assignedPlayers.some((assigned) => assigned.id === player.id)) return;
      const assignedJobs = assignedPlayers.map((assigned) => assigned.job);
      const unassignedJobs = player.jobs.filter((job) => !assignedJobs.includes(job));
      const jobPool = unassignedJobs.length > 0 ? unassignedJobs : player.jobs;
      const job = jobPool[Math.floor(Math.random() * jobPool.length)];
      assignedPlayers.push({
        id: player.id,
        job,
        rank: rankForPlayerJob(player, job),
      });
    });

    if (assignedPlayers.length !== 8) continue;

    const shuffledPlayers = shuffle(assignedPlayers);
    let team1 = shuffledPlayers.slice(0, 4);
    let team2 = shuffledPlayers.slice(4, 8);

    if (!isValidTeam(team1) || !isValidTeam(team2)) continue;

    if (!isFirstRun) {
      const commonInTeam1 = team1.filter((player) =>
        lastTeam1.some((lastPlayer) => lastPlayer.id === player.id)
      ).length;
      const commonInTeam2 = team2.filter((player) =>
        lastTeam2.some((lastPlayer) => lastPlayer.id === player.id)
      ).length;

      if (commonInTeam1 !== 2 || commonInTeam2 !== 2) continue;

      const allPreviousPlayersWithJobs = [...lastTeam1, ...lastTeam2];
      let jobRuleViolated = false;
      for (const player of [...team1, ...team2]) {
        const previousPlayerInfo = allPreviousPlayersWithJobs.find(
          (previousPlayer) => previousPlayer.id === player.id
        );
        if (!previousPlayerInfo) continue;
        const originalPlayer = players.find((candidate) => candidate.id === player.id);
        if (originalPlayer && originalPlayer.jobs.length > 1 && player.job === previousPlayerInfo.job) {
          jobRuleViolated = true;
          break;
        }
      }
      if (jobRuleViolated) continue;
    }

    const diff = teamBalanceDiff(team1, team2);
    if (diff > bestDiff) continue;

    team1 = team1.sort((a, b) => JOB_ORDER.indexOf(a.job) - JOB_ORDER.indexOf(b.job));
    team2 = team2.sort((a, b) => JOB_ORDER.indexOf(a.job) - JOB_ORDER.indexOf(b.job));
    bestTeam1 = team1;
    bestTeam2 = team2;
    bestDiff = diff;
    successful = true;
    if (bestDiff === 0) break;
  }

  return { team1: bestTeam1, team2: bestTeam2, successful, balanceDiff: bestDiff };
}

function createTeams() {
  const players = getPlayerData();
  if (players === null) return;

  const maxAttempts = 20000;
  const isFirstRun =
    state.lastGeneratedTeam1Players.length === 0 || state.lastGeneratedTeam2Players.length === 0;

  let result = generateTeamsWithRules(
    players,
    state.lastGeneratedTeam1Players,
    state.lastGeneratedTeam2Players,
    isFirstRun,
    maxAttempts
  );

  if (!result.successful) {
    result = generateTeamsWithRules(players, [], [], true, maxAttempts);
    if (!result.successful) {
      showTeamMessage("팀을 생성할 수 없습니다. 직업 선택을 다시 확인해주세요.");
      return;
    }
  }

  let finalTeam1 = result.team1;
  let finalTeam2 = result.team2;
  if (checkForbiddenCombination(finalTeam1) || checkForbiddenCombination(finalTeam2)) {
    const retryLastTeam1 = finalTeam1.map((player) => ({ id: player.id, job: player.job }));
    const retryLastTeam2 = finalTeam2.map((player) => ({ id: player.id, job: player.job }));
    const retryResult = generateTeamsWithRules(
      players,
      retryLastTeam1,
      retryLastTeam2,
      isFirstRun,
      maxAttempts
    );
    if (retryResult.successful) {
      finalTeam1 = retryResult.team1;
      finalTeam2 = retryResult.team2;
    }
  }

  const allCharacterIds = new Set(players.filter((player) => player.jobs.length === 4).map((player) => player.id));
  finalTeam1 = finalTeam1.map((player) => ({
    ...player,
    isAllCharacterBonus: allCharacterIds.has(player.id),
  }));
  finalTeam2 = finalTeam2.map((player) => ({
    ...player,
    isAllCharacterBonus: allCharacterIds.has(player.id),
  }));

  displayTeams(finalTeam1, finalTeam2, [...allCharacterIds].join());
  state.lastGeneratedTeam1Players = finalTeam1.map((player) => ({ id: player.id, job: player.job }));
  state.lastGeneratedTeam2Players = finalTeam2.map((player) => ({ id: player.id, job: player.job }));
}

function displayTeams(team1, team2, allPlayersString, options = {}) {
  const team1Info = `Team1 : ${team1.map((player) => `${player.id}(${player.job})`).join("  ")}`;
  const team2Info = `Team2 : ${team2.map((player) => `${player.id}(${player.job})`).join("  ")}`;
  state.lastGeneratedTextResult = `${team1Info}\nVS\n${team2Info}\n올캐릭:${allPlayersString}`;
  state.currentTeamBuilderGameId = options.gameId ?? null;
  state.currentTeamBuilderGameStatus = options.status ?? "draft";
  state.currentTeamBuilderTeams = { teamA: team1, teamB: team2 };

  document.querySelector("#team-result").innerHTML = `
    <div class="team-display-wrapper">
      ${renderGeneratedTeam("1팀", team1)}
      ${renderGeneratedTeam("2팀", team2)}
    </div>
    ${renderTeamMatchControls()}
  `;
  showTeamMessage("팀이 생성되었습니다.", false, false);
  flipGeneratedCards();
}

function renderTeamMatchControls() {
  if (!hasPermission("game:create")) return "";

  const status = state.currentTeamBuilderGameStatus;
  const isDraft = status === "draft";
  const isInProgress = status === "in_progress";
  const isFinished = status === "finished";
  const isCanceled = status === "canceled";
  const seasonOpen = state.selectedSeasonId && isSeasonOpen(state.selectedSeasonId);
  const statusText = {
    draft: "대기",
    in_progress: "진행중",
    finished: "결과 등록됨",
    canceled: "취소됨",
  }[status] ?? "대기";
  const statusClass = isInProgress ? "in-progress" : isFinished ? "active" : isCanceled ? "closed" : "inactive";
  const seasonNote = isCanceled
    ? "이 경기는 다른 화면에서 취소되었습니다. 결과입력은 할 수 없고, 이력 화면에서 취소 원복 후 다시 처리할 수 있습니다."
    : seasonOpen
      ? "미등록 플레이어가 포함되면 팀짜기는 가능하지만 경기 등록은 저장되지 않습니다."
      : "현재 선택한 시즌은 종료 상태입니다. 열린 시즌에서만 경기시작/결과입력이 가능합니다.";

  return `
    <section class="team-match-controls" id="team-match-controls">
      <div class="team-match-header">
        <div>
          <strong>경기 관리</strong>
          <span>팀짜기 화면에서 경기 시작과 결과 입력을 처리합니다.</span>
        </div>
        <span class="status-pill ${statusClass}">
          ${statusText}
        </span>
      </div>
      <div class="team-match-action-row">
        <button type="button" class="primary" id="start-game-button" ${!isDraft || !seasonOpen ? "disabled" : ""}>
          ${seasonOpen ? (isDraft ? "경기시작" : "경기시작 완료") : "열린 시즌 필요"}
        </button>
        <label>
          <span>승리팀</span>
          <select id="result-winner-side" ${!isInProgress ? "disabled" : ""}>
            <option value="A">1팀</option>
            <option value="B">2팀</option>
          </select>
        </label>
        <label>
          <span>1팀 점수</span>
          <input id="result-score-a" type="number" min="0" step="1" value="5" ${!isInProgress ? "disabled" : ""} />
        </label>
        <label>
          <span>2팀 점수</span>
          <input id="result-score-b" type="number" min="0" step="1" value="0" ${!isInProgress ? "disabled" : ""} />
        </label>
        <button type="button" id="submit-result-button" ${!isInProgress ? "disabled" : ""}>
          결과입력
        </button>
      </div>
      <p class="team-match-note">
        ${seasonNote}
      </p>
    </section>
  `;
}

function refreshTeamMatchControls() {
  const controls = document.querySelector("#team-match-controls");
  if (controls) controls.outerHTML = renderTeamMatchControls();
}

async function syncTeamBuilderGameStatus({ render = true } = {}) {
  if (!state.currentTeamBuilderGameId) return null;

  const response = await fetch(
    `/api/admin/games/${encodeURIComponent(state.currentTeamBuilderGameId)}`
  );
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, "진행중 경기 상태를 확인하지 못했습니다."));
  }

  const game = await response.json();
  if (game.status === "CANCELED") {
    state.currentTeamBuilderGameStatus = "canceled";
  } else if (game.status === "ACTIVE") {
    state.currentTeamBuilderGameStatus = "finished";
  } else if (game.status === "IN_PROGRESS") {
    state.currentTeamBuilderGameStatus = "in_progress";
  }
  if (render) refreshTeamMatchControls();
  return game;
}

async function startTeamBuilderGame() {
  if (!state.currentTeamBuilderTeams) {
    showTeamMessage("먼저 팀을 생성해주세요.");
    return;
  }
  if (!state.selectedSeasonId) {
    showTeamMessage("시즌을 먼저 선택해주세요.");
    return;
  }

  const startButton = document.querySelector("#start-game-button");
  if (startButton) startButton.disabled = true;

  try {
    const response = await fetch("/api/admin/games/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        season_id: Number(state.selectedSeasonId),
        source: "team_builder",
        team_a: state.currentTeamBuilderTeams.teamA.map(toGamePlayerPayload),
        team_b: state.currentTeamBuilderTeams.teamB.map(toGamePlayerPayload),
      }),
    });
    if (!response.ok) throw new Error(await readErrorMessage(response, "경기 시작에 실패했습니다."));

    const game = await response.json();
    state.currentTeamBuilderGameId = game.id;
    state.currentTeamBuilderGameStatus = "in_progress";
    refreshTeamMatchControls();
    showTeamMessage("경기가 시작되었습니다. 결과가 나오면 스코어와 승리팀을 입력해주세요.", false, false);
    await loadHistoryPage(1);
    await loadCurrentGames();
  } catch (error) {
    if (startButton) startButton.disabled = false;
    showTeamMessage(error.message);
  }
}

async function submitTeamBuilderResult() {
  if (!state.currentTeamBuilderGameId) {
    showTeamMessage("먼저 경기시작을 눌러 진행중 경기를 만들어주세요.");
    return;
  }

  try {
    const currentGame = await syncTeamBuilderGameStatus({ render: false });
    if (currentGame?.status === "CANCELED") {
      state.currentTeamBuilderGameStatus = "canceled";
      refreshTeamMatchControls();
      showTeamMessage(
        "이 경기는 다른 화면에서 취소되었습니다. 이력 화면에서 원복 후 다시 처리해주세요.",
        true,
        false
      );
      return;
    }
    if (currentGame?.status === "ACTIVE") {
      state.currentTeamBuilderGameStatus = "finished";
      refreshTeamMatchControls();
      showTeamMessage("이미 결과가 등록된 경기입니다.", true, false);
      return;
    }
  } catch (error) {
    showTeamMessage(error.message, true, false);
    return;
  }

  const winnerSide = document.querySelector("#result-winner-side")?.value ?? "A";
  const scoreA = Number(document.querySelector("#result-score-a")?.value ?? 0);
  const scoreB = Number(document.querySelector("#result-score-b")?.value ?? 0);
  if (!Number.isInteger(scoreA) || !Number.isInteger(scoreB) || scoreA < 0 || scoreB < 0) {
    showTeamMessage("스코어는 0 이상의 정수로 입력해주세요.");
    return;
  }

  const winnerScore = winnerSide === "A" ? scoreA : scoreB;
  const loserScore = winnerSide === "A" ? scoreB : scoreA;
  if (winnerScore <= loserScore) {
    showTeamMessage("승리팀 점수는 패배팀 점수보다 높아야 합니다.");
    return;
  }

  const resultButton = document.querySelector("#submit-result-button");
  if (resultButton) resultButton.disabled = true;

  try {
    const response = await fetch(
      `/api/admin/games/${encodeURIComponent(state.currentTeamBuilderGameId)}/result`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          winner_side: winnerSide,
          score_a: scoreA,
          score_b: scoreB,
        }),
      }
    );
    if (!response.ok) throw new Error(await readErrorMessage(response, "결과 입력에 실패했습니다."));

    state.currentTeamBuilderGameStatus = "finished";
    refreshTeamMatchControls();
    showTeamMessage("결과가 등록되었습니다.", false, false);
    await refreshAfterGameMutation(1);
  } catch (error) {
    if (resultButton) resultButton.disabled = false;
    showTeamMessage(error.message);
  }
}

function toGamePlayerPayload(player) {
  return {
    name: player.id,
    class_name: player.job,
    is_all_character_bonus: Boolean(player.isAllCharacterBonus),
  };
}

function renderGeneratedTeam(title, players) {
  return `
    <article class="visual-team-box">
      <h3>${escapeHtml(title)}</h3>
      <div class="visual-player-slots-container">
        ${players
          .map((player, index) => renderGeneratedPlayer(player, index))
          .join("")}
      </div>
    </article>
  `;
}

function renderGeneratedPlayer(player, order) {
  const metaData = state.playerMetaDataMap.get(player.id);
  const tierName = metaData?.tier ?? "";
  const tierCss = tierClass(tierName);
  const classes = ["visual-player-slot"];
  if (tierCss) classes.push(tierCss);

  return `
    <div class="${classes.join(" ")}" data-flip-order="${order}">
      <div class="flip-card-inner">
        <div class="flip-card-front">
          <strong>가즈아 드어넥슴</strong>
          <span>LEAGUE CARD</span>
        </div>
        <div class="flip-card-back">
          <span class="${jobClass(player.job)}">${escapeHtml(player.job)}</span>
          <strong>${escapeHtml(player.id)}</strong>
          ${renderTierBadge(tierName, "mini")}
        </div>
      </div>
    </div>
  `;
}

function flipGeneratedCards() {
  const cardsByOrder = [...document.querySelectorAll(".visual-player-slot")].reduce((groups, card) => {
    const order = Number(card.dataset.flipOrder);
    if (!groups.has(order)) groups.set(order, []);
    groups.get(order).push(card);
    return groups;
  }, new Map());

  [...cardsByOrder.keys()].sort((left, right) => left - right).forEach((order, index) => {
    setTimeout(() => {
      cardsByOrder.get(order).forEach((card) => {
        card.querySelector(".flip-card-inner")?.classList.add("flipped");
      });
    }, 220 + index * 1800);
  });
}

function resetTeams() {
  state.lastGeneratedTeam1Players = [];
  state.lastGeneratedTeam2Players = [];
  showTeamMessage("팀짜기 규칙이 초기화되었습니다.", false, false);
}

function clearTeamResultOnly() {
  state.lastGeneratedTextResult = "";
  state.currentTeamBuilderGameId = null;
  state.currentTeamBuilderGameStatus = "draft";
  state.currentTeamBuilderTeams = null;
  document.querySelector("#team-result").innerHTML = "";
  document.querySelector("#team-message").textContent = "";
}

async function copyResult() {
  if (!state.lastGeneratedTextResult) {
    showTeamMessage("먼저 팀을 생성해주세요.");
    return;
  }
  await navigator.clipboard.writeText(state.lastGeneratedTextResult);
  showTeamMessage("복사되었습니다.", false, false);
}

function showTeamMessage(message, isError = true, clearResult = true) {
  const messageElement = document.querySelector("#team-message");
  messageElement.textContent = message;
  messageElement.classList.toggle("error-text", isError);
  if (clearResult) document.querySelector("#team-result").innerHTML = "";
}

function renderTeam(players) {
  return players
    .map(
      (player) =>
        `<span>${escapeHtml(player.class_name ?? "-")} · ${escapeHtml(player.player_name)}</span>`
    )
    .join("");
}

function jobClass(className) {
  return {
    드루: "job-badge druid",
    어쎄: "job-badge assassin",
    네크: "job-badge necro",
    슴딘: "job-badge paladin",
  }[className] ?? "job-badge";
}

function tierClass(tierName) {
  return (
    {
      마스터: "tier-master",
      다이아: "tier-diamond",
      플래티넘: "tier-platinum",
      골드: "tier-gold",
      실버: "tier-silver",
      아이언: "tier-iron",
      "배치 중": "tier-placement",
    }[tierName] ?? ""
  );
}

function renderTierBadge(tierName, variant = "compact") {
  const normalizedTier = tierName ?? "";
  const tierCss = tierClass(normalizedTier);
  const safeVariant = ["large", "compact", "mini", "micro"].includes(variant)
    ? variant
    : "compact";

  if (!normalizedTier || !tierCss) {
    return `
      <span class="tier-badge tier-badge--empty tier-badge--${safeVariant}" title="티어 없음">
        <span class="tier-emblem" aria-hidden="true">${tierIconSvg("empty")}</span>
        <span class="tier-badge-label">-</span>
      </span>
    `;
  }

  return `
    <span class="tier-badge ${tierCss} tier-badge--${safeVariant}" title="${escapeHtml(
      normalizedTier
    )}">
      <span class="tier-emblem" aria-hidden="true">${tierIconSvg(normalizedTier)}</span>
      <span class="tier-badge-label">${escapeHtml(normalizedTier)}</span>
    </span>
  `;
}

function tierIconSvg(tierName) {
  const icons = {
    아이언: `
      <svg class="tier-svg" viewBox="0 0 64 64" focusable="false">
        <path class="tier-svg-shadow" d="M32 5 52 13v16c0 14.5-8 24.5-20 30-12-5.5-20-15.5-20-30V13L32 5Z" />
        <path class="tier-svg-base" d="M32 7 50 14.5v14.2c0 13-7 22-18 27.3-11-5.3-18-14.3-18-27.3V14.5L32 7Z" />
        <path class="tier-svg-glint" d="M22 18.5 32 14l10 4.5-10 4.2-10-4.2Z" />
        <path class="tier-svg-mark" d="M24 27h16M22 35h20M27 43h10" />
      </svg>
    `,
    실버: `
      <svg class="tier-svg" viewBox="0 0 64 64" focusable="false">
        <path class="tier-svg-ribbon" d="M24 41 18 57l12-6 2 8 2-8 12 6-6-16H24Z" />
        <circle class="tier-svg-base" cx="32" cy="27" r="20" />
        <circle class="tier-svg-glint" cx="25" cy="20" r="5" />
        <path class="tier-svg-mark" d="m32 15 3.8 7.6 8.4 1.2-6.1 5.9 1.5 8.3-7.6-4-7.6 4 1.5-8.3-6.1-5.9 8.4-1.2L32 15Z" />
      </svg>
    `,
    골드: `
      <svg class="tier-svg" viewBox="0 0 64 64" focusable="false">
        <path class="tier-svg-laurel" d="M16 35c-5-8-3-18 5-24M48 35c5-8 3-18-5-24" />
        <path class="tier-svg-base" d="M32 6 50 17 46 45 32 58 18 45 14 17 32 6Z" />
        <path class="tier-svg-glint" d="M23 18 32 12.5 41 18 32 22.5 23 18Z" />
        <path class="tier-svg-mark" d="m24 31 5.2 5.1L41 24" />
      </svg>
    `,
    플래티넘: `
      <svg class="tier-svg" viewBox="0 0 64 64" focusable="false">
        <path class="tier-svg-base" d="M32 5 53 18v27L32 59 11 45V18L32 5Z" />
        <path class="tier-svg-glint" d="M32 5v54M11 18l42 27M53 18 11 45" />
        <path class="tier-svg-mark" d="M22 26h20l-10 18-10-18Z" />
      </svg>
    `,
    다이아: `
      <svg class="tier-svg" viewBox="0 0 64 64" focusable="false">
        <path class="tier-svg-base" d="M20 9h24l12 15-24 31L8 24 20 9Z" />
        <path class="tier-svg-glint" d="M20 9 32 24 44 9M8 24h48M22 24l10 31 10-31" />
        <path class="tier-svg-mark" d="M32 15 38 24 32 33 26 24 32 15Z" />
      </svg>
    `,
    마스터: `
      <svg class="tier-svg" viewBox="0 0 64 64" focusable="false">
        <path class="tier-svg-base" d="M14 49h36l3-28-11 9-10-18-10 18-11-9 3 28Z" />
        <path class="tier-svg-glint" d="M18 43h28M22 30l10-18 10 18M14 21l8 9M50 21l-8 9" />
        <path class="tier-svg-mark" d="M32 24 36 34 47 35l-8.3 6.8L41.5 53 32 47.2 22.5 53l2.8-11.2L17 35l11-1 4-10Z" />
      </svg>
    `,
    empty: `
      <svg class="tier-svg" viewBox="0 0 64 64" focusable="false">
        <path class="tier-svg-base" d="M32 8 51 19v26L32 56 13 45V19L32 8Z" />
        <path class="tier-svg-mark" d="M22 32h20" />
      </svg>
    `,
  };
  return icons[tierName] ?? icons.empty;
}

function formatClassStats(row, className) {
  const classStat = row.class_stats.find((item) => item.class_name === className);
  if (!classStat) return "0/0/-";
  return `${classStat.wins}/${classStat.losses}/${formatRate(classStat.win_rate)}`;
}

function formatPairRecord(record) {
  if (!record || record.wins + record.losses === 0) return "-";
  return `${record.wins}/${record.losses} (${formatRate(record.win_rate)})`;
}

function formatHistoryScore(value) {
  return value === null || value === undefined ? "-" : value;
}

function formatGameStatus(status) {
  return (
    {
      ACTIVE: "완료",
      CANCELED: "취소됨",
      IN_PROGRESS: "진행중",
    }[status] ?? status
  );
}

function formatSeasonStatus(status) {
  return (
    {
      DRAFT: "준비",
      OPEN: "진행중",
      CLOSED: "마감",
    }[status] ?? status
  );
}

function seasonStatusClass(status) {
  return (
    {
      DRAFT: "draft",
      OPEN: "active",
      CLOSED: "closed",
    }[status] ?? "inactive"
  );
}

function formatSeasonDate(value) {
  if (!value) return "-";
  return formatKoreaDate(value);
}

function formatKoreaDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleDateString("ko-KR", { timeZone: KOREA_TIME_ZONE });
}

function formatKoreaTime(value) {
  if (!value) return "-";
  return new Date(value).toLocaleTimeString("ko-KR", {
    timeZone: KOREA_TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatKoreaDateTime(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("ko-KR", { timeZone: KOREA_TIME_ZONE });
}

function hasPermission(permission) {
  return Boolean(
    state.me?.is_authenticated
      && (state.me?.is_super
        || (Array.isArray(state.me?.permissions) && state.me.permissions.includes(permission)))
  );
}

function canManageGames() {
  return hasPermission("game:create");
}

function canAccessAdminPage() {
  if (state.me?.is_super) return true;
  const adminPagePermissions = [
    "game:create",
    "game:cancel",
    "game:restore",
    "admin:manage",
    "season:manage",
    "notice:manage",
    "player:manage",
    "mmr:manage",
  ];
  return adminPagePermissions.some((permission) => hasPermission(permission));
}

function renderAuthState() {
  const authArea = document.querySelector("#auth-area");
  const adminNavigation = document.querySelector("[data-admin-navigation]");
  if (adminNavigation) adminNavigation.hidden = !canAccessAdminPage();
  renderSuperAdminControls();
  renderPermissionControls();
  if (!authArea) return;

  if (state.me?.auth_mode !== "google") {
    authArea.hidden = false;
    authArea.innerHTML = `<span class="auth-dev">로컬 관리자 모드</span>`;
    return;
  }

  authArea.hidden = false;
  if (state.me?.is_authenticated) {
    const noAdminPermission = !canAccessAdminPage();
    authArea.innerHTML = `
      <span class="auth-email-group">
        <span class="auth-email" title="${escapeHtml(state.me.email ?? "")}">${escapeHtml(
          state.me.email ?? "Google 계정"
        )}</span>
        ${noAdminPermission ? `<span class="auth-no-permission">관리 권한 없음</span>` : ""}
      </span>
      <a class="auth-button" href="/api/auth/logout">로그아웃</a>
    `;
    return;
  }

  if (!state.me?.oauth_configured) {
    authArea.innerHTML = `<span class="auth-pending">로그인 설정 중</span>`;
    return;
  }

  const next = `${window.location.pathname}${window.location.hash || "#home"}`;
  authArea.innerHTML = `
    <a class="auth-button google-login" href="/api/auth/login/google?next=${encodeURIComponent(
      next
    )}">관리자 로그인</a>
  `;
}

function isSeasonOpen(seasonId) {
  const season = state.seasons.find((item) => String(item.id) === String(seasonId));
  return season?.status === "OPEN";
}

function normalizeWinnerSideInput(value) {
  const normalized = String(value).trim().toUpperCase();
  if (["1", "A", "1팀", "TEAM A"].includes(normalized)) return "A";
  if (["2", "B", "2팀", "TEAM B"].includes(normalized)) return "B";
  return null;
}

async function readErrorMessage(response, fallback) {
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") return translateApiMessage(payload.detail);
    if (Array.isArray(payload.detail)) {
      return payload.detail.map((item) => item.msg ?? fallback).join("\n");
    }
  } catch (error) {
    console.error(error);
  }
  return fallback;
}

function translateApiMessage(message) {
  if (message === "Season is not open") {
    return "열린 시즌에서만 경기 등록/수정이 가능합니다.";
  }
  if (message === "Only games in an open season can be changed") {
    return "열린 시즌의 경기만 변경할 수 있습니다.";
  }
  if (message === "Game is canceled") return "취소된 경기는 결과를 입력할 수 없습니다.";
  if (message === "Game is already finished") return "이미 결과가 등록된 경기입니다.";
  if (message.startsWith("이미 열린 시즌이 있습니다:")) return message;
  if (message.startsWith("이미 존재하는 시즌입니다:")) return message;
  if (message === "Season name is required") return "시즌명을 입력해주세요.";
  if (message.startsWith("Registered player not found:")) {
    return `등록되지 않은 플레이어가 포함되어 있습니다: ${message.replace("Registered player not found:", "").trim()}`;
  }
  if (message === "Winner score must be greater than loser score") {
    return "승리팀 점수는 패배팀 점수보다 높아야 합니다.";
  }
  return message;
}

function formatRate(value) {
  return value === null || value === undefined ? "-" : `${Number(value).toFixed(1)}%`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

loadStatus();
