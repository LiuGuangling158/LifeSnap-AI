const routes = [
  {
    id: "dashboard",
    label: "首页",
    icon: "home",
    eyebrow: "本地体验",
    title: "今天先把账记顺",
    subtitle: "查看本月支出、最近账单和待办提醒；数据来自当前 FastAPI 后端。",
  },
  {
    id: "bills",
    label: "账单",
    icon: "receipt",
    eyebrow: "手动记录",
    title: "账单列表",
    subtitle: "第一步先支持手动新增、列表查看，后续接入截图识别候选确认。",
  },
  {
    id: "tasks",
    label: "待办",
    icon: "check",
    eyebrow: "提醒辅助",
    title: "待办提醒",
    subtitle: "展示后端已有待办数据；新增和编辑会在后续增量接入。",
  },
  {
    id: "diary",
    label: "日记",
    icon: "book",
    eyebrow: "生活记录",
    title: "日记",
    subtitle: "记录生活点滴的入口先占位，后续接入真实日记数据。",
  },
  {
    id: "settings",
    label: "设置",
    icon: "settings",
    eyebrow: "隐私与数据",
    title: "设置",
    subtitle: "先展示本地模式和后端能力，后续接入清除、导出、快照操作。",
  },
];

const state = {
  route: getRoute(),
  loading: true,
  saving: false,
  error: "",
  toast: "",
  modalOpen: false,
  editingBill: null,
  deleteTarget: null,
  taskModalOpen: false,
  snoozeTarget: null,
  settingsConfirm: null,
  billFilters: {
    year: "",
    month: "",
    category: "",
    transaction_type: "",
    q: "",
  },
  billListMeta: {
    total: 0,
    page: 1,
    page_size: 12,
    total_pages: 0,
  },
  bootstrap: null,
  billOverview: null,
  snapshotStatus: null,
  bills: [],
  tasks: [],
};

const app = document.querySelector("#app");

window.addEventListener("hashchange", () => {
  state.route = getRoute();
  render();
});

document.addEventListener("click", (event) => {
  const routeButton = event.target.closest("[data-route]");
  if (routeButton) {
    window.location.hash = routeButton.dataset.route;
    return;
  }

  if (event.target.closest("[data-open-bill-modal]")) {
    state.editingBill = null;
    state.modalOpen = true;
    render();
    return;
  }

  if (event.target.closest("[data-open-task-modal]")) {
    state.taskModalOpen = true;
    render();
    return;
  }

  if (event.target.closest("[data-snapshot-save]")) {
    saveSnapshot();
    return;
  }

  if (event.target.closest("[data-diary-placeholder]")) {
    showToast("日记功能会在下一步接入，当前先保留入口。");
    return;
  }

  if (event.target.closest("[data-voice-placeholder]")) {
    showToast("语音操作会在后续接入 AI 对话和识别流程。");
    return;
  }

  const editButton = event.target.closest("[data-edit-bill]");
  if (editButton) {
    state.editingBill = state.bills.find((bill) => bill.id === editButton.dataset.editBill) ?? null;
    state.modalOpen = Boolean(state.editingBill);
    render();
    return;
  }

  const deleteButton = event.target.closest("[data-delete-bill]");
  if (deleteButton) {
    state.deleteTarget = state.bills.find((bill) => bill.id === deleteButton.dataset.deleteBill) ?? null;
    render();
    return;
  }

  if (event.target.closest("[data-close-modal]")) {
    state.modalOpen = false;
    state.editingBill = null;
    state.taskModalOpen = false;
    state.snoozeTarget = null;
    state.settingsConfirm = null;
    render();
    return;
  }

  const completeTaskButton = event.target.closest("[data-complete-task]");
  if (completeTaskButton) {
    completeTask(completeTaskButton.dataset.completeTask);
    return;
  }

  const snoozeTaskButton = event.target.closest("[data-snooze-task]");
  if (snoozeTaskButton) {
    state.snoozeTarget = state.tasks.find((task) => task.id === snoozeTaskButton.dataset.snoozeTask) ?? null;
    render();
    return;
  }

  if (event.target.closest("[data-cancel-delete]")) {
    state.deleteTarget = null;
    render();
    return;
  }

  if (event.target.closest("[data-confirm-delete]")) {
    deleteBill();
    return;
  }

  if (event.target.closest("[data-reset-bill-filters]")) {
    state.billFilters = {
      year: "",
      month: "",
      category: "",
      transaction_type: "",
      q: "",
    };
    loadData();
    return;
  }

  if (event.target.closest("[data-export-json]")) {
    exportJson();
    return;
  }

  const settingsActionButton = event.target.closest("[data-settings-action]");
  if (settingsActionButton) {
    openSettingsConfirm(settingsActionButton.dataset.settingsAction);
    return;
  }

  if (event.target.closest("[data-cancel-settings-action]")) {
    state.settingsConfirm = null;
    render();
    return;
  }

  if (event.target.closest("[data-confirm-settings-action]")) {
    runSettingsConfirm();
    return;
  }

  if (event.target.closest("[data-refresh]")) {
    loadData();
  }
});

document.addEventListener("keydown", (event) => {
  if (
    event.key === "Escape"
    && (
      state.modalOpen
      || state.deleteTarget
      || state.taskModalOpen
      || state.snoozeTarget
      || state.settingsConfirm
    )
  ) {
    state.modalOpen = false;
    state.editingBill = null;
    state.deleteTarget = null;
    state.taskModalOpen = false;
    state.snoozeTarget = null;
    state.settingsConfirm = null;
    render();
  }
});

document.addEventListener("submit", async (event) => {
  if (event.target.matches("[data-bill-filter]")) {
    event.preventDefault();
    applyBillFilters(new FormData(event.target));
    return;
  }

  if (event.target.matches("[data-bill-form]")) {
    event.preventDefault();
    await submitBill(new FormData(event.target));
    return;
  }

  if (event.target.matches("[data-task-form]")) {
    event.preventDefault();
    await submitTask(new FormData(event.target));
    return;
  }

  if (event.target.matches("[data-snooze-form]")) {
    event.preventDefault();
    await submitSnooze(new FormData(event.target));
  }
});

loadData();

async function loadData() {
  state.loading = true;
  state.error = "";
  render();

  try {
    const [bootstrap, billOverview, billList, taskList, snapshotStatus] = await Promise.all([
      api("/app/bootstrap?recent_bill_limit=6&candidate_limit=5"),
      api("/bills/statistics/overview?trend_months=6&top_merchant_limit=6"),
      api(buildBillListPath()),
      api("/tasks?page_size=8"),
      api("/data/snapshot/status"),
    ]);
    state.bootstrap = bootstrap;
    state.billOverview = billOverview;
    state.bills = billList.items ?? [];
    state.billListMeta = {
      total: billList.total ?? 0,
      page: billList.page ?? 1,
      page_size: billList.page_size ?? 12,
      total_pages: billList.total_pages ?? 0,
    };
    state.tasks = taskList.items ?? [];
    state.snapshotStatus = snapshotStatus;
  } catch (error) {
    state.error = error.message || "后端连接失败";
  } finally {
    state.loading = false;
    render();
  }
}

async function submitBill(formData) {
  const amount = Number(formData.get("amount"));
  const paidAt = formData.get("paid_at");
  const editingBill = state.editingBill;
  const payload = {
    amount,
    merchant: String(formData.get("merchant") || "").trim(),
    category: String(formData.get("category") || "General").trim(),
    payment_method: String(formData.get("payment_method") || "").trim() || null,
    transaction_type: formData.get("transaction_type"),
    paid_at: paidAt ? new Date(paidAt).toISOString() : null,
    note: String(formData.get("note") || "").trim() || null,
  };
  if (!editingBill) {
    payload.source = "manual";
  }

  state.saving = true;
  render();
  try {
    await api(editingBill ? `/bills/${editingBill.id}` : "/bills", {
      method: editingBill ? "PATCH" : "POST",
      headers: {
        "Content-Type": "application/json",
        ...(editingBill ? {} : { "Idempotency-Key": `web-bill-${crypto.randomUUID()}` }),
      },
      body: JSON.stringify(payload),
    });
    state.modalOpen = false;
    state.editingBill = null;
    state.toast = editingBill ? "账单已更新" : "账单已保存";
    await loadData();
    window.setTimeout(() => {
      state.toast = "";
      render();
    }, 2200);
  } catch (error) {
    state.toast = error.message || "保存失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

async function deleteBill() {
  if (!state.deleteTarget) {
    return;
  }
  const bill = state.deleteTarget;
  state.saving = true;
  render();
  try {
    await api(`/bills/${bill.id}`, { method: "DELETE" });
    state.deleteTarget = null;
    state.toast = "账单已删除";
    await loadData();
    window.setTimeout(() => {
      state.toast = "";
      render();
    }, 2200);
  } catch (error) {
    state.toast = error.message || "删除失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

async function submitTask(formData) {
  const taskType = String(formData.get("task_type") || "todo");
  const dueAt = formData.get("due_at");
  const remindAt = formData.get("remind_at");
  const payload = {
    title: String(formData.get("title") || "").trim(),
    description: String(formData.get("description") || "").trim() || null,
    category: String(formData.get("category") || "生活").trim(),
    task_type: taskType,
    due_at: taskType === "todo" && dueAt ? new Date(dueAt).toISOString() : null,
    remind_at: taskType === "reminder" && remindAt ? new Date(remindAt).toISOString() : null,
    priority: formData.get("priority"),
    source: "manual",
  };

  state.saving = true;
  render();
  try {
    await api("/tasks", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": `web-task-${crypto.randomUUID()}`,
      },
      body: JSON.stringify(payload),
    });
    state.taskModalOpen = false;
    state.toast = "待办已创建";
    await loadData();
    window.setTimeout(() => {
      state.toast = "";
      render();
    }, 2200);
  } catch (error) {
    state.toast = error.message || "创建失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

async function completeTask(taskId) {
  const task = state.tasks.find((item) => item.id === taskId);
  if (!task || task.status !== "pending") {
    return;
  }

  state.saving = true;
  render();
  try {
    await api(`/tasks/${taskId}/complete`, {
      method: "POST",
      headers: { "Idempotency-Key": `web-task-complete-${taskId}-${crypto.randomUUID()}` },
    });
    state.toast = "待办已完成";
    await loadData();
    window.setTimeout(() => {
      state.toast = "";
      render();
    }, 2200);
  } catch (error) {
    state.toast = error.message || "操作失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

async function submitSnooze(formData) {
  if (!state.snoozeTarget) {
    return;
  }
  const minutes = Number(formData.get("minutes") || 0);

  state.saving = true;
  render();
  try {
    await api(`/tasks/${state.snoozeTarget.id}/snooze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": `web-task-snooze-${state.snoozeTarget.id}-${crypto.randomUUID()}`,
      },
      body: JSON.stringify({ minutes }),
    });
    state.snoozeTarget = null;
    state.toast = "提醒时间已延后";
    await loadData();
    window.setTimeout(() => {
      state.toast = "";
      render();
    }, 2200);
  } catch (error) {
    state.toast = error.message || "延后失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

async function exportJson() {
  state.saving = true;
  render();
  try {
    const snapshot = await api("/data/export");
    downloadText(
      `lifesnap-export-${new Date().toISOString().slice(0, 10)}.json`,
      JSON.stringify(snapshot, null, 2),
      "application/json;charset=utf-8",
    );
    state.toast = "JSON 数据已导出";
  } catch (error) {
    state.toast = error.message || "导出失败";
  } finally {
    state.saving = false;
    render();
  }
}

async function saveSnapshot() {
  state.saving = true;
  render();
  try {
    const result = await api("/data/snapshot/save", { method: "POST" });
    state.snapshotStatus = result;
    state.toast = "本地快照已保存";
    await loadData();
  } catch (error) {
    state.toast = error.message || "保存快照失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

function openSettingsConfirm(action) {
  const configs = {
    clear: {
      action,
      title: "清除本地数据",
      message: "会清空账单、待办、附件和候选记录。建议先保存快照或导出数据。",
      confirmLabel: "确认清除",
      danger: true,
    },
    loadSnapshot: {
      action,
      title: "加载本地快照",
      message: "会用快照内容覆盖当前本地数据。当前未保存的内存数据可能被替换。",
      confirmLabel: "确认加载",
      danger: true,
    },
    deleteSnapshot: {
      action,
      title: "删除本地快照",
      message: "会删除 backend/data/local_snapshot.json。删除后无法通过快照恢复。",
      confirmLabel: "确认删除",
      danger: true,
    },
  };

  state.settingsConfirm = configs[action] ?? null;
  render();
}

async function runSettingsConfirm() {
  if (!state.settingsConfirm) {
    return;
  }
  const { action } = state.settingsConfirm;
  state.saving = true;
  render();

  try {
    if (action === "clear") {
      await api("/data/clear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: true }),
      });
      state.toast = "本地数据已清除";
    }

    if (action === "loadSnapshot") {
      await api("/data/snapshot/load", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: true, reset_existing: true }),
      });
      state.toast = "本地快照已加载";
    }

    if (action === "deleteSnapshot") {
      await api("/data/snapshot", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: true }),
      });
      state.toast = "本地快照已删除";
    }

    state.settingsConfirm = null;
    await loadData();
  } catch (error) {
    state.toast = error.message || "操作失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

function applyBillFilters(formData) {
  state.billFilters = {
    year: String(formData.get("year") || "").trim(),
    month: String(formData.get("month") || "").trim(),
    category: String(formData.get("category") || "").trim(),
    transaction_type: String(formData.get("transaction_type") || "").trim(),
    q: String(formData.get("q") || "").trim(),
  };
  loadData();
}

function buildBillListPath() {
  const params = new URLSearchParams({ page_size: String(state.billListMeta.page_size) });
  Object.entries(state.billFilters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  return `/bills?${params.toString()}`;
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const text = await response.text();
  const body = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(body?.detail || body?.error?.message || `请求失败：${response.status}`);
  }
  return body;
}

function showToast(message) {
  state.toast = message;
  render();
  window.setTimeout(() => {
    if (state.toast === message) {
      state.toast = "";
      render();
    }
  }, 2600);
}

function getRoute() {
  const id = window.location.hash.replace("#", "");
  return routes.some((route) => route.id === id) ? id : "dashboard";
}

function render() {
  const route = routes.find((item) => item.id === state.route) ?? routes[0];
  const primaryAction = getPrimaryAction();
  app.innerHTML = `
    <div class="app-shell mobile-shell">
      <main class="main mobile-main">
        ${state.route === "dashboard" ? "" : renderTopbar(route, primaryAction)}
        ${renderPage()}
        ${renderMobileTabbar()}
      </main>
      ${state.modalOpen ? renderBillModal() : ""}
      ${state.deleteTarget ? renderDeleteBillModal() : ""}
      ${state.taskModalOpen ? renderTaskModal() : ""}
      ${state.snoozeTarget ? renderSnoozeModal() : ""}
      ${state.settingsConfirm ? renderSettingsConfirmModal() : ""}
      ${state.toast ? `<div class="toast" role="status">${escapeHtml(state.toast)}</div>` : ""}
    </div>
  `;
}

function renderTopbar(route, primaryAction) {
  return `
    <header class="topbar">
      <div>
        <p class="eyebrow">${route.eyebrow}</p>
        <h1 class="page-title">${route.title}</h1>
        <p class="page-subtitle">${route.subtitle}</p>
      </div>
      <div class="action-row">
        <button class="button primary" type="button" ${primaryAction.modalAttribute}>
          ${icon("plus")}${primaryAction.label}
        </button>
        <button class="button ghost" type="button" data-refresh>
          ${icon("refresh")}刷新
        </button>
      </div>
    </header>
  `;
}

function getPrimaryAction() {
  if (state.route === "tasks") {
    return { label: "新增待办", modalAttribute: "data-open-task-modal" };
  }
  if (state.route === "diary") {
    return { label: "写日记", modalAttribute: "data-diary-placeholder" };
  }
  if (state.route === "settings") {
    return { label: "保存快照", modalAttribute: "data-snapshot-save" };
  }
  return { label: "新增记录", modalAttribute: "data-open-bill-modal" };
}

function renderSidebar() {
  return `
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">${icon("spark")}</div>
        <div>
          <p class="brand-title">LifeSnap AI</p>
          <p class="brand-subtitle">小事管家 MVP</p>
        </div>
      </div>
      <nav class="nav" aria-label="主导航">
        ${routes
          .map(
            (route) => `
              <button class="nav-button ${state.route === route.id ? "is-active" : ""}"
                type="button"
                data-route="${route.id}">
                ${icon(route.icon)}${route.label}
              </button>
            `,
          )
          .join("")}
      </nav>
      <div class="sidebar-footer">
        <strong>当前阶段</strong><br />
        阶段 3：页面骨架、本地体验、手动账单主路径。
      </div>
    </aside>
  `;
}

function renderPage() {
  if (state.loading) {
    return `<section class="surface"><p class="status-line">正在读取后端数据...</p></section>`;
  }

  if (state.error) {
    return `
      <section class="surface">
        <p class="error">${escapeHtml(state.error)}</p>
        <p class="status-line">请确认 FastAPI 后端正在运行，然后刷新页面。</p>
      </section>
    `;
  }

  if (state.route === "bills") return renderBillsPage();
  if (state.route === "tasks") return renderTasksPage();
  if (state.route === "diary") return renderDiaryPage();
  if (state.route === "settings") return renderSettingsPage();
  return renderDashboard();
}

function renderDashboard() {
  const dashboard = state.bootstrap?.dashboard ?? {};
  const monthly = dashboard.monthly_statistics ?? {};
  const expense = Number(monthly.total_expense ?? 0);
  const income = Number(monthly.total_income ?? 0);
  const netAmount = Number(monthly.net_amount ?? income - expense);
  const budgetRemaining = Math.max(0, netAmount);
  const progress = financeProgress(monthly);
  const remainingPercent = Math.max(0, 100 - progress);
  const homeTasks = [
    ...(dashboard.today_tasks ?? []),
    ...(dashboard.upcoming_reminders ?? []),
  ].slice(0, 3);

  return `
    <div class="home-page">
      <section class="home-hero">
        <div class="home-hero-copy">
          <h1 class="home-title">早安，<br />今天也要<span>轻松管理生活</span></h1>
          <p class="home-subtitle">每一个小习惯，成就更好的自己</p>
        </div>
        <div class="home-illustration" aria-hidden="true">
          <div class="home-window">
            <span class="home-sun"></span>
          </div>
          <div class="home-cup"></div>
          <div class="home-plant plant-left"></div>
          <div class="home-plant plant-right"></div>
          <div class="home-mascot"></div>
        </div>
      </section>

      <section class="surface finance-overview">
        <div class="finance-header">
          <div class="finance-title">
            <span class="panel-icon">${icon("wallet")}</span>
            <div>
              <h2 class="section-title">本月财务概览</h2>
            </div>
          </div>
          <button class="button ghost" type="button" data-route="bills">查看全部</button>
        </div>
        <div class="finance-body">
          <div class="finance-main">
            <div class="home-metrics">
              ${homeMetric("本月支出", money(expense), "expense", `支出占收入 ${progress}%`)}
              ${homeMetric("本月收入", money(income), "income", `净额 ${money(netAmount)}`)}
              ${homeMetric("预算剩余", money(budgetRemaining), "income", `剩余 ${remainingPercent}%`)}
            </div>
            <div class="home-chart-wrap">
              ${renderDailyChart(state.billOverview?.daily_breakdown ?? [], "home-chart")}
              <div class="chart-axis" aria-hidden="true">
                <span>1日</span>
                <span>10日</span>
                <span>20日</span>
                <span>30日</span>
              </div>
            </div>
          </div>
          <div class="finance-ring-wrap">
            ${renderProgressRing(progress)}
            <p class="ring-label">预算进度</p>
          </div>
        </div>
      </section>

      <section class="surface assistant-strip">
        <div class="assistant-copy">
          <div class="finance-title">
            <span class="panel-icon blue">${icon("spark")}</span>
            <h2 class="section-title">AI 助手</h2>
          </div>
          <span class="voice-pill">${icon("mic")}可语音输入</span>
          <p class="assistant-title">说一句话，我来帮你</p>
          <p class="assistant-note">记账、提醒、整理日程</p>
        </div>
        <button class="assistant-mic" type="button" data-voice-placeholder aria-label="语音操作">
          ${icon("mic")}
        </button>
        <div class="assistant-bot" aria-hidden="true">
          <span class="bot-ear left"></span>
          <span class="bot-ear right"></span>
          <span class="bot-head"><span></span></span>
          <span class="bot-body"></span>
        </div>
      </section>

      <div class="home-split">
        <section class="surface home-task-panel">
          <div class="section-header">
            <div class="finance-title">
              <span class="panel-icon">${icon("check")}</span>
              <h2 class="section-title">待办提醒</h2>
            </div>
            <button class="button ghost" type="button" data-route="tasks">查看全部</button>
          </div>
          ${renderHomeTasks(homeTasks)}
          <button class="text-action" type="button" data-open-task-modal>${icon("plus")}添加待办</button>
        </section>
        <section class="surface home-diary-panel">
          <div class="section-header">
            <div class="finance-title">
              <span class="panel-icon">${icon("book")}</span>
              <h2 class="section-title">日记</h2>
            </div>
            <button class="button ghost" type="button" data-route="diary">查看全部</button>
          </div>
          <div class="diary-preview">
            <p>记录生活点滴，<br />留住每一个美好瞬间</p>
            <div class="diary-book-art" aria-hidden="true">
              <span class="book-cover"></span>
              <span class="book-pen"></span>
            </div>
            <button class="button primary diary-button" type="button" data-diary-placeholder>
              ${icon("edit")}记录今天的心情
            </button>
          </div>
        </section>
      </div>

      <section class="quick-dock" aria-label="快捷操作">
        ${quickAction("edit", "记一笔", "快速记账", "data-open-bill-modal")}
        ${quickAction("check-circle", "添加待办", "新建任务", "data-open-task-modal")}
        ${quickAction("book", "写日记", "记录心情", "data-diary-placeholder")}
        ${quickAction("mic", "语音操作", "动口不动手", "data-voice-placeholder")}
      </section>
    </div>
  `;
}

function renderBillsPage() {
  return `
    <div class="mobile-page bills-mobile-page">
      <section class="mobile-page-head">
        <p class="eyebrow">账单</p>
        <h1 class="mobile-page-title">每一笔都清楚</h1>
        <p class="mobile-page-subtitle">${state.billListMeta.total} 条记录，支持按月份、分类和关键词筛选。</p>
      </section>
      ${renderBillFilters()}
      <section class="surface bill-feed-panel">
        ${state.bills.length ? renderBillFeed(state.bills) : empty("还没有账单，可以先新增一条手动记录。")}
      </section>
    </div>
  `;
}

function renderTasksPage() {
  return `
    <section class="surface">
      <div class="section-header">
        <div>
          <h2 class="section-title">待办提醒</h2>
          <p class="section-note">支持手动创建、完成待办和延后提醒；AI 对话创建会在后续增量接入。</p>
        </div>
        <span class="pill">${state.tasks.length} 条</span>
      </div>
      ${state.tasks.length ? renderTaskList(state.tasks) : empty("还没有待办。")}
    </section>
  `;
}

function renderDiaryPage() {
  return `
    <div class="mobile-page diary-mobile-page">
      <section class="surface diary-placeholder-panel">
        <div class="section-header">
          <div>
            <h2 class="section-title">日记</h2>
            <p class="section-note">先放入口和页面占位，后续增量接入日记列表、心情记录和本地存储。</p>
          </div>
          <button class="button primary" type="button" data-diary-placeholder>
            ${icon("edit")}写日记
          </button>
        </div>
        <div class="diary-placeholder-body">
          <div class="diary-book-art large" aria-hidden="true">
            <span class="book-cover"></span>
            <span class="book-pen"></span>
          </div>
          <p>今天先把首页入口做完整，日记正文能力会按你的增量节奏继续补。</p>
        </div>
      </section>
    </div>
  `;
}

function renderSettingsPage() {
  const caps = state.bootstrap?.capabilities ?? {};
  const privacy = state.bootstrap?.privacy_settings ?? {};
  const summary = state.bootstrap?.data_summary ?? {};
  const snapshot = state.snapshotStatus;
  return `
    <section class="surface">
      <div class="section-header">
        <div>
          <h2 class="section-title">数据与隐私</h2>
          <p class="section-note">本页只提供本地体验需要的关键数据入口；破坏性操作需要二次确认。</p>
        </div>
      </div>
      <div class="settings-summary">
        ${metric("账单", summary.bill_count ?? 0, "small")}
        ${metric("待办", summary.task_count ?? 0, "small")}
        ${metric("附件", summary.attachment_count ?? 0, "small")}
        ${metric("候选", Number(summary.bill_candidate_count ?? 0) + Number(summary.task_candidate_count ?? 0), "small")}
      </div>
      <div class="settings-list">
        ${settingsRow(
          "隐私模式",
          privacy.local_only_mode ? "本地体验已开启" : "本地体验未开启",
          `
            <span class="muted-value">OCR: ${escapeHtml(caps.ocr_provider ?? "unknown")}</span>
            <span class="muted-value">AI: ${escapeHtml(caps.ai_text_parser ?? "unknown")}</span>
          `,
        )}
        ${settingsRow(
          "数据导出",
          "导出当前活跃账单、待办、附件元数据和候选记录。",
          `
            <button class="button" type="button" data-export-json ${state.saving ? "disabled" : ""}>
              ${icon("download")}JSON
            </button>
            <a class="button ghost" href="/data/export/bills.csv" download>${icon("download")}账单 CSV</a>
            <a class="button ghost" href="/data/export/tasks.csv" download>${icon("download")}待办 CSV</a>
          `,
        )}
        ${settingsRow(
          "本地快照",
          snapshotText(snapshot),
          `
            <button class="button" type="button" data-snapshot-save ${state.saving ? "disabled" : ""}>
              ${icon("save")}保存
            </button>
            <button class="button ghost" type="button" data-settings-action="loadSnapshot"
              ${!snapshot?.exists || state.saving ? "disabled" : ""}>
              ${icon("upload")}加载
            </button>
            <button class="button danger" type="button" data-settings-action="deleteSnapshot"
              ${!snapshot?.exists || state.saving ? "disabled" : ""}>
              ${icon("trash")}删除
            </button>
          `,
        )}
        ${settingsRow(
          "清除本地数据",
          "清空当前内存中的账单、待办、附件和候选记录。建议先导出或保存快照。",
          `
            <button class="button danger" type="button" data-settings-action="clear" ${state.saving ? "disabled" : ""}>
              ${icon("trash")}清除数据
            </button>
          `,
        )}
      </div>
    </section>
  `;
}

function homeMetric(label, value, tone, hint = "") {
  return `
    <div class="home-metric">
      <span>${label}</span>
      <strong class="${tone}">${value}</strong>
      ${hint ? `<small>${hint}</small>` : ""}
    </div>
  `;
}

function financeProgress(monthly) {
  const expense = Number(monthly.total_expense ?? 0);
  const income = Number(monthly.total_income ?? 0);
  if (income <= 0) {
    return 0;
  }
  return Math.min(100, Math.round((expense / income) * 100));
}

function renderProgressRing(percent) {
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;
  return `
    <div class="progress-figure" aria-label="支出占收入 ${percent}%">
      <svg class="progress-ring" viewBox="0 0 112 112" aria-hidden="true">
        <circle class="ring-track" cx="56" cy="56" r="${radius}"></circle>
        <circle class="ring-value" cx="56" cy="56" r="${radius}"
          stroke-dasharray="${circumference.toFixed(2)}"
          stroke-dashoffset="${offset.toFixed(2)}"></circle>
      </svg>
      <strong>${percent}%</strong>
    </div>
  `;
}

function renderHomeTasks(tasks) {
  if (!tasks.length) {
    return empty("今天还没有待办提醒。");
  }
  return `
    <div class="home-task-list">
      ${tasks
        .map(
          (task) => `
            <div class="home-task-item">
              <span class="panel-icon soft">${icon(task.task_type === "reminder" ? "clock" : "check")}</span>
              <div>
                <p class="item-title">${escapeHtml(task.title)}</p>
                <p class="item-meta">${taskTargetText(task)} · ${labelTaskPriority(task.priority)}</p>
              </div>
              <button class="icon-button" type="button" data-complete-task="${task.id}"
                aria-label="完成 ${escapeHtml(task.title)}"
                ${task.status !== "pending" || state.saving ? "disabled" : ""}>
                ${icon("check-circle")}
              </button>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function quickAction(iconName, title, subtitle, attribute) {
  return `
    <button class="quick-action" type="button" ${attribute}>
      <span class="quick-icon">${icon(iconName)}</span>
      <span>
        <strong>${title}</strong>
        <small>${subtitle}</small>
      </span>
    </button>
  `;
}

function renderMobileTabbar() {
  const tabs = [
    ["dashboard", "首页", "home"],
    ["bills", "记账", "wallet"],
    ["tasks", "提醒", "bell"],
    ["diary", "日记", "book"],
    ["settings", "我的", "user"],
  ];
  return `
    <nav class="mobile-tabbar" aria-label="底部导航">
      ${tabs
        .map(
          ([route, label, iconName]) => `
            <button class="tab-button ${state.route === route ? "is-active" : ""}"
              type="button"
              data-route="${route}">
              ${icon(iconName)}
              <span>${label}</span>
            </button>
          `,
        )
        .join("")}
    </nav>
  `;
}

function renderDailyChart(items, extraClass = "") {
  if (!items.length) {
    return empty("暂无统计数据。");
  }
  const values = items.map((item) => Number(item.total_expense ?? 0));
  const max = Math.max(...values, 1);
  const maxHeight = extraClass.includes("home-chart") ? 54 : 170;
  return `
    <div class="chart ${extraClass}" role="list" aria-label="本月每日支出">
      ${items
        .map((item, index) => {
          const value = Number(item.total_expense ?? 0);
          const height = Math.max(8, Math.round((value / max) * maxHeight));
          const date = item.date ?? `第 ${index + 1} 天`;
          return `
            <button class="chart-bar" type="button" role="listitem" aria-label="${date} 支出 ${money(value)}">
              <span class="chart-tooltip">
                <span class="tooltip-title">${escapeHtml(date)}</span>
                <span class="tooltip-value">${money(value)}</span>
              </span>
              <span class="bar-fill" style="height:${height}px"></span>
            </button>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderBillList(bills) {
  if (!bills?.length) {
    return empty("还没有最近账单。");
  }
  return `
    <div class="list">
      ${bills
        .slice(0, 6)
        .map(
          (bill) => `
            <div class="list-item">
              <div>
                <p class="item-title">${escapeHtml(bill.merchant)}</p>
                <p class="item-meta">${escapeHtml(bill.category)} · ${formatDate(bill.paid_at)}</p>
              </div>
              <span class="amount ${bill.transaction_type}">${money(bill.amount)}</span>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderBillFilters() {
  const filters = state.billFilters;
  return `
    <form class="mobile-filter-form" data-bill-filter>
      <div class="field">
        <label for="filter_year">年份</label>
        <input id="filter_year" name="year" type="number" min="1970" max="2100" placeholder="全部"
          value="${escapeHtml(filters.year)}" />
      </div>
      <div class="field">
        <label for="filter_month">月份</label>
        <select id="filter_month" name="month">
          <option value="">全部</option>
          ${Array.from({ length: 12 }, (_, index) => {
            const month = String(index + 1);
            return `<option value="${month}" ${filters.month === month ? "selected" : ""}>${month} 月</option>`;
          }).join("")}
        </select>
      </div>
      <div class="field">
        <label for="filter_category">分类</label>
        <input id="filter_category" name="category" maxlength="40" placeholder="如 餐饮"
          value="${escapeHtml(filters.category)}" />
      </div>
      <div class="field">
        <label for="filter_transaction_type">类型</label>
        <select id="filter_transaction_type" name="transaction_type">
          <option value="">全部</option>
          ${transactionOptions(filters.transaction_type)}
        </select>
      </div>
      <div class="field filter-keyword">
        <label for="filter_q">关键词</label>
        <input id="filter_q" name="q" maxlength="80" placeholder="商户、分类、备注"
          value="${escapeHtml(filters.q)}" />
      </div>
      <div class="filter-actions">
        <button class="button primary" type="submit">${icon("search")}筛选</button>
        <button class="button ghost" type="button" data-reset-bill-filters>${icon("reset")}清空</button>
      </div>
    </form>
  `;
}

function renderBillsTable(bills) {
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>商户</th>
            <th>分类</th>
            <th>类型</th>
            <th>时间</th>
            <th>金额</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          ${bills
            .map(
              (bill) => `
                <tr>
                  <td>${escapeHtml(bill.merchant)}</td>
                  <td>${escapeHtml(bill.category)}</td>
                  <td>${labelTransaction(bill.transaction_type)}</td>
                  <td>${formatDate(bill.paid_at)}</td>
                  <td class="amount ${bill.transaction_type}">${money(bill.amount)}</td>
                  <td>
                    <div class="table-actions">
                      <button class="icon-button" type="button" data-edit-bill="${bill.id}" aria-label="编辑 ${escapeHtml(bill.merchant)}" title="编辑">
                        ${icon("edit")}
                      </button>
                      <button class="icon-button danger" type="button" data-delete-bill="${bill.id}" aria-label="删除 ${escapeHtml(bill.merchant)}" title="删除">
                        ${icon("trash")}
                      </button>
                    </div>
                  </td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderBillFeed(bills) {
  return `
    <div class="bill-feed">
      ${bills
        .map(
          (bill) => `
            <article class="bill-feed-item">
              <span class="bill-feed-icon">${icon(iconForBill(bill))}</span>
              <div class="bill-feed-main">
                <div class="bill-feed-topline">
                  <h2>${escapeHtml(bill.merchant)}</h2>
                  <span class="amount ${bill.transaction_type}">${money(bill.amount)}</span>
                </div>
                <p class="item-meta">
                  ${escapeHtml(bill.category)}
                  · ${labelTransaction(bill.transaction_type)}
                  · ${formatDate(bill.paid_at)}
                </p>
                ${bill.note ? `<p class="bill-note">${escapeHtml(bill.note)}</p>` : ""}
              </div>
              <div class="bill-feed-actions">
                <button class="icon-button" type="button" data-edit-bill="${bill.id}"
                  aria-label="编辑 ${escapeHtml(bill.merchant)}" title="编辑">
                  ${icon("edit")}
                </button>
                <button class="icon-button danger" type="button" data-delete-bill="${bill.id}"
                  aria-label="删除 ${escapeHtml(bill.merchant)}" title="删除">
                  ${icon("trash")}
                </button>
              </div>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderTaskList(tasks) {
  return `
    <div class="list">
      ${tasks
        .map(
          (task) => `
            <div class="list-item task-row">
              <div>
                <p class="item-title">${escapeHtml(task.title)}</p>
                <p class="item-meta">
                  ${escapeHtml(task.category)}
                  · ${labelTaskStatus(task.status)}
                  · ${labelTaskPriority(task.priority)}
                  · ${taskTargetText(task)}
                </p>
              </div>
              <div class="task-actions">
                <span class="pill">${labelTaskType(task.task_type)}</span>
                <button class="icon-button" type="button" data-complete-task="${task.id}"
                  aria-label="完成 ${escapeHtml(task.title)}" title="完成"
                  ${task.status !== "pending" || state.saving ? "disabled" : ""}>
                  ${icon("check-circle")}
                </button>
                <button class="icon-button" type="button" data-snooze-task="${task.id}"
                  aria-label="延后 ${escapeHtml(task.title)}" title="延后"
                  ${task.status !== "pending" || state.saving ? "disabled" : ""}>
                  ${icon("clock")}
                </button>
              </div>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderBillModal() {
  const bill = state.editingBill;
  const title = bill ? "编辑账单" : "新增账单";
  const description = bill ? "修改后会立即更新列表和首页统计。" : "先支持手动记录，后续接入截图识别候选。";
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal" role="dialog" aria-modal="true" aria-labelledby="bill-modal-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="bill-modal-title">${title}</h2>
            <p class="section-note">${description}</p>
          </div>
          <button class="button ghost" type="button" data-close-modal aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <form class="form" data-bill-form>
          <div class="form-grid">
            <div class="field">
              <label for="amount">金额</label>
              <input id="amount" name="amount" type="number" min="0.01" step="0.01" required placeholder="18.50"
                value="${escapeHtml(bill?.amount ?? "")}" />
            </div>
            <div class="field">
              <label for="transaction_type">类型</label>
              <select id="transaction_type" name="transaction_type">
                ${transactionOptions(bill?.transaction_type ?? "expense")}
              </select>
            </div>
            <div class="field">
              <label for="merchant">商户</label>
              <input id="merchant" name="merchant" required maxlength="120" placeholder="早餐店"
                value="${escapeHtml(bill?.merchant ?? "")}" />
            </div>
            <div class="field">
              <label for="category">分类</label>
              <input id="category" name="category" required maxlength="40" placeholder="餐饮"
                value="${escapeHtml(bill?.category ?? "")}" />
            </div>
            <div class="field">
              <label for="payment_method">支付方式</label>
              <input id="payment_method" name="payment_method" maxlength="40" placeholder="微信支付"
                value="${escapeHtml(bill?.payment_method ?? "")}" />
            </div>
            <div class="field">
              <label for="paid_at">时间</label>
              <input id="paid_at" name="paid_at" type="datetime-local"
                value="${escapeHtml(toDateTimeLocal(bill?.paid_at))}" />
            </div>
            <div class="field full">
              <label for="note">备注</label>
              <textarea id="note" name="note" maxlength="500" placeholder="可选">${escapeHtml(bill?.note ?? "")}</textarea>
            </div>
          </div>
          <div class="form-actions">
            <button class="button ghost" type="button" data-close-modal>取消</button>
            <button class="button primary" type="submit" ${state.saving ? "disabled" : ""}>
              ${icon("save")}${state.saving ? "保存中..." : (bill ? "更新账单" : "保存账单")}
            </button>
          </div>
        </form>
      </section>
    </div>
  `;
}

function renderDeleteBillModal() {
  const bill = state.deleteTarget;
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal compact-modal" role="dialog" aria-modal="true" aria-labelledby="delete-bill-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="delete-bill-title">删除账单</h2>
            <p class="section-note">这会将账单移入软删除状态，不会立即从后端存储中彻底移除。</p>
          </div>
          <button class="button ghost" type="button" data-cancel-delete aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <div class="confirm-body">
          <p class="item-title">${escapeHtml(bill?.merchant ?? "账单")}</p>
          <p class="item-meta">${escapeHtml(bill?.category ?? "")} · ${formatDate(bill?.paid_at)} · ${money(bill?.amount)}</p>
        </div>
        <div class="form-actions modal-actions">
          <button class="button ghost" type="button" data-cancel-delete>取消</button>
          <button class="button danger" type="button" data-confirm-delete ${state.saving ? "disabled" : ""}>
            ${icon("trash")}${state.saving ? "删除中..." : "确认删除"}
          </button>
        </div>
      </section>
    </div>
  `;
}

function renderTaskModal() {
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal" role="dialog" aria-modal="true" aria-labelledby="task-modal-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="task-modal-title">新增待办</h2>
            <p class="section-note">先支持手动创建，后续接入 AI 对话生成待确认事项。</p>
          </div>
          <button class="button ghost" type="button" data-close-modal aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <form class="form" data-task-form>
          <div class="form-grid">
            <div class="field full">
              <label for="task_title">标题</label>
              <input id="task_title" name="title" required maxlength="120" placeholder="明天交房租" />
            </div>
            <div class="field">
              <label for="task_type">类型</label>
              <select id="task_type" name="task_type">
                <option value="todo">待办</option>
                <option value="reminder">提醒</option>
              </select>
            </div>
            <div class="field">
              <label for="task_priority">优先级</label>
              <select id="task_priority" name="priority">
                <option value="medium">普通</option>
                <option value="high">高</option>
                <option value="low">低</option>
              </select>
            </div>
            <div class="field">
              <label for="task_category">分类</label>
              <input id="task_category" name="category" required maxlength="40" placeholder="生活" />
            </div>
            <div class="field">
              <label for="task_due_at">截止时间</label>
              <input id="task_due_at" name="due_at" type="datetime-local" />
            </div>
            <div class="field">
              <label for="task_remind_at">提醒时间</label>
              <input id="task_remind_at" name="remind_at" type="datetime-local" />
            </div>
            <div class="field full">
              <label for="task_description">备注</label>
              <textarea id="task_description" name="description" maxlength="500" placeholder="可选"></textarea>
            </div>
          </div>
          <p class="form-hint">待办优先使用截止时间，提醒优先使用提醒时间；留空也可以先创建。</p>
          <div class="form-actions">
            <button class="button ghost" type="button" data-close-modal>取消</button>
            <button class="button primary" type="submit" ${state.saving ? "disabled" : ""}>
              ${icon("save")}${state.saving ? "创建中..." : "创建待办"}
            </button>
          </div>
        </form>
      </section>
    </div>
  `;
}

function renderSnoozeModal() {
  const task = state.snoozeTarget;
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal compact-modal" role="dialog" aria-modal="true" aria-labelledby="snooze-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="snooze-title">延后提醒</h2>
            <p class="section-note">选择一个常用时间，后端会从当前目标时间或现在开始顺延。</p>
          </div>
          <button class="button ghost" type="button" data-close-modal aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <div class="confirm-body">
          <p class="item-title">${escapeHtml(task?.title ?? "待办")}</p>
          <p class="item-meta">${taskTargetText(task)} · ${labelTaskPriority(task?.priority)}</p>
        </div>
        <form class="form" data-snooze-form>
          <div class="field">
            <label for="snooze_minutes">延后时间</label>
            <select id="snooze_minutes" name="minutes">
              <option value="30">30 分钟</option>
              <option value="60">1 小时</option>
              <option value="180">3 小时</option>
              <option value="1440">明天</option>
              <option value="10080">下周</option>
            </select>
          </div>
          <div class="form-actions">
            <button class="button ghost" type="button" data-close-modal>取消</button>
            <button class="button primary" type="submit" ${state.saving ? "disabled" : ""}>
              ${icon("clock")}${state.saving ? "延后中..." : "确认延后"}
            </button>
          </div>
        </form>
      </section>
    </div>
  `;
}

function renderSettingsConfirmModal() {
  const confirm = state.settingsConfirm;
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal compact-modal" role="dialog" aria-modal="true" aria-labelledby="settings-confirm-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="settings-confirm-title">${escapeHtml(confirm.title)}</h2>
            <p class="section-note">${escapeHtml(confirm.message)}</p>
          </div>
          <button class="button ghost" type="button" data-cancel-settings-action aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <div class="form-actions modal-actions">
          <button class="button ghost" type="button" data-cancel-settings-action>取消</button>
          <button class="button ${confirm.danger ? "danger" : "primary"}" type="button"
            data-confirm-settings-action ${state.saving ? "disabled" : ""}>
            ${icon(confirm.danger ? "trash" : "save")}${state.saving ? "处理中..." : escapeHtml(confirm.confirmLabel)}
          </button>
        </div>
      </section>
    </div>
  `;
}

function metric(label, value, tone = "") {
  return `
    <div class="metric">
      <div class="metric-label">${label}</div>
      <div class="metric-value ${tone}">${value}</div>
    </div>
  `;
}

function settingsRow(label, value, actions) {
  return `
    <div class="settings-row">
      <div>
        <p class="item-title">${escapeHtml(label)}</p>
        <p class="item-meta">${escapeHtml(value)}</p>
      </div>
      <div class="settings-actions">${actions}</div>
    </div>
  `;
}

function snapshotText(snapshot) {
  if (!snapshot?.exists) {
    return "尚未保存本地快照。";
  }
  const summary = snapshot.snapshot_data_summary;
  const parts = [];
  if (summary) {
    parts.push(`${summary.bill_count} 条账单`);
    parts.push(`${summary.task_count} 条待办`);
    if (summary.deleted_bill_count || summary.deleted_task_count) {
      parts.push("含软删除记录");
    }
  }
  const updatedAt = snapshot.updated_at ? `更新于 ${formatDate(snapshot.updated_at)}` : "已保存";
  return `${updatedAt}${parts.length ? `，${parts.join("，")}` : ""}`;
}

function empty(message) {
  return `<p class="empty">${escapeHtml(message)}</p>`;
}

function money(value) {
  const number = Number(value ?? 0);
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    maximumFractionDigits: 2,
  }).format(number);
}

function downloadText(filename, content, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function formatDate(value) {
  if (!value) return "未设置";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function labelTransaction(value) {
  return {
    expense: "支出",
    income: "收入",
    refund: "退款",
    transfer: "转账",
    top_up: "充值",
  }[value] ?? value;
}

function iconForBill(bill) {
  if (bill.transaction_type === "income") return "income";
  if (bill.transaction_type === "refund") return "refresh";
  const category = String(bill.category ?? "").toLowerCase();
  if (category.includes("餐") || category.includes("饮") || category.includes("food")) return "utensils";
  if (category.includes("交通") || category.includes("transport")) return "transport";
  if (category.includes("购物") || category.includes("shop")) return "shopping";
  if (category.includes("医疗") || category.includes("medical")) return "medical";
  return "wallet";
}

function transactionOptions(selectedValue = "") {
  const options = [
    ["expense", "支出"],
    ["income", "收入"],
    ["refund", "退款"],
    ["transfer", "转账"],
    ["top_up", "充值"],
  ];
  return options
    .map(
      ([value, label]) =>
        `<option value="${value}" ${selectedValue === value ? "selected" : ""}>${label}</option>`,
    )
    .join("");
}

function toDateTimeLocal(value) {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset();
  const local = new Date(date.getTime() - offset * 60 * 1000);
  return local.toISOString().slice(0, 16);
}

function labelTaskStatus(value) {
  return {
    pending: "待处理",
    done: "已完成",
    cancelled: "已取消",
  }[value] ?? value;
}

function labelTaskType(value) {
  return {
    todo: "待办",
    reminder: "提醒",
  }[value] ?? value;
}

function labelTaskPriority(value) {
  return {
    low: "低优先级",
    medium: "普通优先级",
    high: "高优先级",
  }[value] ?? "普通优先级";
}

function taskTargetText(task) {
  if (!task) return "未设置时间";
  const target = task.task_type === "reminder"
    ? task.remind_at || task.due_at
    : task.due_at || task.remind_at;
  return target ? formatDate(target) : "未设置时间";
}

function icon(name) {
  const paths = {
    home: '<path d="M4 11.5 12 5l8 6.5V20a1 1 0 0 1-1 1h-5v-6h-4v6H5a1 1 0 0 1-1-1v-8.5z"></path>',
    layout: '<rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="3" y="14" width="18" height="7"></rect>',
    receipt: '<path d="M6 3h12v18l-2-1.2-2 1.2-2-1.2-2 1.2-2-1.2L6 21V3z"></path><path d="M9 8h6"></path><path d="M9 12h6"></path><path d="M9 16h4"></path>',
    check: '<path d="M4 12l5 5L20 6"></path>',
    settings: '<circle cx="12" cy="12" r="3"></circle><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1a7 7 0 0 0-1.7-1L14.5 3h-5l-.4 3.1a7 7 0 0 0-1.7 1l-2.4-1-2 3.4 2 1.5a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a7 7 0 0 0 1.7 1l.4 3.1h5l.4-3.1a7 7 0 0 0 1.7-1l2.4 1 2-3.4-2-1.5c.1-.3.1-.7.1-1z"></path>',
    plus: '<path d="M12 5v14"></path><path d="M5 12h14"></path>',
    refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7"></path><path d="M20 16v-5h-5"></path>',
    search: '<circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path>',
    reset: '<path d="M4 7h11a5 5 0 1 1-3.5 8.5"></path><path d="M4 7l4-4"></path><path d="M4 7l4 4"></path>',
    edit: '<path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17v3z"></path><path d="M13.5 6.5l4 4"></path>',
    wallet: '<path d="M4 7h14a2 2 0 0 1 2 2v10H4V7z"></path><path d="M4 7V5a2 2 0 0 1 2-2h10v4"></path><path d="M16 13h4"></path>',
    income: '<path d="M12 19V5"></path><path d="M5 12l7-7 7 7"></path><path d="M5 21h14"></path>',
    utensils: '<path d="M4 3v8"></path><path d="M8 3v8"></path><path d="M4 7h4"></path><path d="M6 11v10"></path><path d="M15 3v18"></path><path d="M15 3c3 2 4 5 2 8"></path>',
    transport: '<path d="M6 17h12l2-7H4l2 7z"></path><path d="M8 17v2"></path><path d="M16 17v2"></path><path d="M7 10l1.5-4h7L17 10"></path>',
    shopping: '<path d="M6 8h14l-2 11H8L6 8z"></path><path d="M6 8 5 4H3"></path><path d="M9 12h7"></path>',
    medical: '<path d="M10 4h4v6h6v4h-6v6h-4v-6H4v-4h6V4z"></path>',
    mic: '<path d="M12 4a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0V7a3 3 0 0 0-3-3z"></path><path d="M5 11a7 7 0 0 0 14 0"></path><path d="M12 18v3"></path>',
    trash: '<path d="M4 7h16"></path><path d="M10 11v6"></path><path d="M14 11v6"></path><path d="M6 7l1 14h10l1-14"></path><path d="M9 7V4h6v3"></path>',
    "check-circle": '<circle cx="12" cy="12" r="9"></circle><path d="M8 12l3 3 5-6"></path>',
    clock: '<circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path>',
    bell: '<path d="M6 10a6 6 0 0 1 12 0c0 4 2 5 2 7H4c0-2 2-3 2-7z"></path><path d="M10 21h4"></path>',
    book: '<path d="M5 4h8a3 3 0 0 1 3 3v13H8a3 3 0 0 0-3 3V4z"></path><path d="M16 7h3v13h-3"></path><path d="M8 8h4"></path><path d="M8 12h4"></path>',
    user: '<circle cx="12" cy="8" r="4"></circle><path d="M4 21a8 8 0 0 1 16 0"></path>',
    download: '<path d="M12 3v12"></path><path d="M7 10l5 5 5-5"></path><path d="M5 21h14"></path>',
    upload: '<path d="M12 21V9"></path><path d="M7 14l5-5 5 5"></path><path d="M5 3h14"></path>',
    close: '<path d="M6 6l12 12"></path><path d="M18 6L6 18"></path>',
    save: '<path d="M5 3h12l2 2v16H5V3z"></path><path d="M8 3v6h8"></path><path d="M8 17h8"></path>',
    spark: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z"></path>',
  };
  return `<span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24">${paths[name] ?? paths.layout}</svg></span>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
