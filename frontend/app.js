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
  diaryModalOpen: false,
  snoozeTarget: null,
  settingsConfirm: null,
  billFilters: {
    year: "",
    month: "",
    category: "",
    transaction_type: "",
    q: "",
  },
  taskFilters: {
    view: "today",
    category: "",
  },
  diaryFilters: {
    period: "today",
  },
  diaryDraft: null,
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

  if (event.target.closest("[data-diary-placeholder], [data-open-diary-modal]")) {
    state.diaryModalOpen = true;
    render();
    return;
  }

  if (event.target.closest("[data-voice-placeholder]")) {
    showToast("语音操作会在后续接入 AI 对话和识别流程。");
    return;
  }

  if (event.target.closest("[data-bill-photo-placeholder]")) {
    showToast("拍照记账会在后续接入图片上传和 OCR 识别。");
    return;
  }

  if (event.target.closest("[data-bill-filter-panel]")) {
    showToast("更细的筛选面板会在下一步补齐。");
    return;
  }

  const diaryPeriodButton = event.target.closest("[data-diary-period]");
  if (diaryPeriodButton) {
    state.diaryFilters.period = diaryPeriodButton.dataset.diaryPeriod || "today";
    render();
    return;
  }

  if (event.target.closest("[data-diary-calendar-placeholder]")) {
    showToast("日记日历会在后续接入完整日期选择。");
    return;
  }

  if (event.target.closest("[data-diary-photo-placeholder]")) {
    showToast("图片上传会在后续接入附件与相册能力。");
    return;
  }

  if (event.target.closest("[data-diary-ai-prompt]")) {
    showToast("AI 日记追问会在后续接入对话生成。");
    return;
  }

  if (event.target.closest("[data-profile-notification]")) {
    showToast("通知中心会在后续接入提醒聚合。");
    return;
  }

  if (event.target.closest("[data-profile-preferences]")) {
    showToast("个性化设置会在后续接入账号与偏好配置。");
    return;
  }

  if (event.target.closest("[data-profile-placeholder]")) {
    showToast("该个人工具会在后续接入详细配置页。");
    return;
  }

  const taskViewButton = event.target.closest("[data-task-view]");
  if (taskViewButton) {
    state.taskFilters.view = taskViewButton.dataset.taskView || "today";
    render();
    return;
  }

  const taskCategoryButton = event.target.closest("[data-task-category]");
  if (taskCategoryButton) {
    state.taskFilters.category = taskCategoryButton.dataset.taskCategory || "";
    render();
    return;
  }

  if (event.target.closest("[data-task-calendar-placeholder]")) {
    showToast("日历视图会在后续接入完整日期选择。");
    return;
  }

  if (event.target.closest("[data-task-sort-placeholder]")) {
    showToast("当前按时间优先展示提醒，排序面板会在后续补齐。");
    return;
  }

  if (event.target.closest("[data-repeat-task-placeholder]")) {
    showToast("重复提醒会在后续接入周期规则。");
    return;
  }

  if (event.target.closest("[data-view-all-tasks]")) {
    state.taskFilters.view = "today";
    state.taskFilters.category = "";
    showToast("已清除提醒分类筛选。");
    return;
  }

  const billPeriodButton = event.target.closest("[data-bill-period]");
  if (billPeriodButton) {
    if (billPeriodButton.dataset.billPeriod === "month") {
      const now = new Date();
      state.billFilters.year = String(now.getFullYear());
      state.billFilters.month = String(now.getMonth() + 1);
      state.billFilters.q = "";
      state.billListMeta.page = 1;
      loadData();
    } else {
      showToast("本周和自定义周期会在下一步接入日期筛选。");
    }
    return;
  }

  const billTypeButton = event.target.closest("[data-bill-type]");
  if (billTypeButton) {
    state.billFilters.transaction_type = billTypeButton.dataset.billType;
    state.billListMeta.page = 1;
    loadData();
    return;
  }

  const billCategoryButton = event.target.closest("[data-bill-category]");
  if (billCategoryButton) {
    state.billFilters.category = billCategoryButton.dataset.billCategory;
    state.billListMeta.page = 1;
    loadData();
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
    state.diaryModalOpen = false;
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
      || state.diaryModalOpen
      || state.snoozeTarget
      || state.settingsConfirm
    )
  ) {
    state.modalOpen = false;
    state.editingBill = null;
    state.deleteTarget = null;
    state.taskModalOpen = false;
    state.diaryModalOpen = false;
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

  if (event.target.matches("[data-diary-form]")) {
    event.preventDefault();
    saveDiaryDraft(new FormData(event.target));
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

function saveDiaryDraft(formData) {
  state.diaryDraft = {
    title: String(formData.get("title") || "今天的日记").trim(),
    content: String(formData.get("content") || "").trim(),
    mood: String(formData.get("mood") || "happy"),
    weather: String(formData.get("weather") || "晴天").trim(),
    created_at: new Date().toISOString(),
  };
  state.diaryModalOpen = false;
  showToast("日记草稿已保存到本次前端体验。");
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
  const hasCustomHeader = ["dashboard", "bills", "tasks", "diary", "settings"].includes(state.route);
  app.innerHTML = `
    <div class="app-shell mobile-shell">
      <main class="main mobile-main">
        ${hasCustomHeader ? "" : renderTopbar(route, primaryAction)}
        ${renderPage()}
        ${renderMobileTabbar()}
      </main>
      ${state.modalOpen ? renderBillModal() : ""}
      ${state.deleteTarget ? renderDeleteBillModal() : ""}
      ${state.taskModalOpen ? renderTaskModal() : ""}
      ${state.diaryModalOpen ? renderDiaryModal() : ""}
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
  if (state.route === "diary") return renderDiaryMobilePage();
  if (state.route === "settings") return renderProfilePage();
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
  const overview = state.billOverview ?? {};
  const monthly = overview.monthly_statistics ?? state.bootstrap?.dashboard?.monthly_statistics ?? {};
  const categories = monthly.category_breakdown ?? [];
  const trend = overview.monthly_trend ?? [];
  const previousMonth = trend.length > 1 ? trend[trend.length - 2] : null;
  const expense = Number(monthly.total_expense ?? 0);
  const income = Number(monthly.total_income ?? 0);
  const netAmount = Number(monthly.net_amount ?? income - expense);

  return `
    <div class="mobile-page bills-mobile-page ledger-page">
      <section class="ledger-hero">
        <div>
          <h1 class="ledger-title">记账</h1>
          <p class="ledger-subtitle">轻松记录每一笔收支</p>
        </div>
        <div class="ledger-hero-art" aria-hidden="true">
          <span class="ledger-leaf leaf-a"></span>
          <span class="ledger-leaf leaf-b"></span>
          <span class="ledger-calendar-art"></span>
          <span class="ledger-mascot"></span>
          <span class="ledger-coin"></span>
        </div>
      </section>

      <section class="surface ledger-overview-panel">
        ${renderBillControls()}
        <section class="ledger-summary" aria-label="本月账单摘要">
          ${ledgerMetric("本月结余", money(netAmount), metricTrend(netAmount, previousMonth?.net_amount), "balance", "eye")}
          ${ledgerMetric("本月收入", money(income), metricTrend(income, previousMonth?.total_income), "income")}
          ${ledgerMetric("本月支出", money(expense), metricTrend(expense, previousMonth?.total_expense, true), "expense")}
        </section>
        <div class="ledger-insights">
          ${renderBillCategoryPanel(categories, expense)}
          ${renderBillTrendPanel(overview.daily_breakdown ?? [])}
        </div>
      </section>

      <section class="surface bill-feed-panel ledger-feed-panel">
        <div class="ledger-feed-header">
          <h2 class="section-title">最近账单</h2>
          ${renderBillCategoryFilters(categories)}
        </div>
        ${state.bills.length ? renderBillFeed(state.bills) : empty("还没有账单，可以先新增一条手动记录。")}
      </section>
      ${renderBillActionDock()}
    </div>
  `;
}

function renderBillControls() {
  const activeType = state.billFilters.transaction_type || "expense";
  return `
    <div class="ledger-controls">
      <div class="ledger-period-tabs" aria-label="时间范围">
        <button class="ledger-tab is-active" type="button" data-bill-period="month">本月</button>
        <button class="ledger-tab" type="button" data-bill-period="week">本周</button>
        <button class="ledger-tab" type="button" data-bill-period="custom">自定义</button>
        <button class="ledger-icon-tab" type="button" data-bill-period="custom" aria-label="选择日期">
          ${icon("calendar")}
        </button>
      </div>
      <div class="ledger-type-toggle" aria-label="收支类型">
        <button class="ledger-type ${activeType !== "income" ? "is-active" : ""}" type="button" data-bill-type="expense">支出</button>
        <button class="ledger-type ${activeType === "income" ? "is-active" : ""}" type="button" data-bill-type="income">收入</button>
      </div>
    </div>
  `;
}

function ledgerMetric(label, value, hint, tone, iconName = "") {
  return `
    <div class="ledger-metric">
      <span class="ledger-metric-label">
        ${label}${iconName ? icon(iconName) : ""}
      </span>
      <strong class="${tone}">${value}</strong>
      <small class="${hint.tone}">${hint.text}</small>
    </div>
  `;
}

function metricTrend(currentValue, previousValue, invertTone = false) {
  const current = Number(currentValue ?? 0);
  const previous = Number(previousValue ?? 0);
  if (!previous) {
    return { text: "较上月 0%", tone: "neutral" };
  }
  const delta = ((current - previous) / Math.abs(previous)) * 100;
  const isUp = delta >= 0;
  const isGood = invertTone ? !isUp : isUp;
  return {
    text: `较上月 ${isUp ? "↑" : "↓"} ${Math.abs(delta).toFixed(1)}%`,
    tone: isGood ? "positive" : "negative",
  };
}

function renderBillCategoryPanel(categories, totalExpense) {
  const topCategories = categories.slice(0, 5);
  return `
    <section class="ledger-insight-panel">
      <div class="ledger-panel-header">
        <h2 class="section-title">支出分类</h2>
        <button class="button ghost" type="button" data-bill-filter-panel>查看全部</button>
      </div>
      ${
        topCategories.length
          ? `
            <div class="ledger-category-body">
              ${renderCategoryDonut(topCategories, totalExpense)}
              <div class="ledger-category-list">
                ${topCategories
                  .map(
                    (item, index) => `
                      <button class="category-row" type="button" data-bill-category="${escapeHtml(item.category)}">
                        <span class="category-dot dot-${index + 1}"></span>
                        <span>${escapeHtml(item.category)}</span>
                        <strong>${Number(item.percentage ?? 0).toFixed(0)}%</strong>
                        <small>${money(item.amount)}</small>
                      </button>
                    `,
                  )
                  .join("")}
              </div>
            </div>
          `
          : empty("暂无分类数据。")
      }
    </section>
  `;
}

function renderCategoryDonut(categories, totalExpense) {
  const circumference = 2 * Math.PI * 42;
  const colors = ["#10b98f", "#43c7b4", "#8edfd0", "#c7e6e2", "#c5d3ef"];
  let offset = 0;
  const segments = categories
    .map((item, index) => {
      const percent = Number(item.percentage ?? 0);
      const length = Math.max(0, Math.min(circumference, (percent / 100) * circumference));
      const segment = `
        <circle class="ledger-donut-segment" cx="60" cy="60" r="42"
          stroke="${colors[index % colors.length]}"
          stroke-dasharray="${length.toFixed(2)} ${(circumference - length).toFixed(2)}"
          stroke-dashoffset="${(-offset).toFixed(2)}"></circle>
      `;
      offset += length;
      return segment;
    })
    .join("");

  return `
    <div class="ledger-donut" aria-label="总支出 ${money(totalExpense)}">
      <svg viewBox="0 0 120 120" aria-hidden="true">
        <circle class="ledger-donut-track" cx="60" cy="60" r="42"></circle>
        ${segments}
      </svg>
      <div class="ledger-donut-center">
        <span>总支出</span>
        <strong>${money(totalExpense)}</strong>
      </div>
    </div>
  `;
}

function renderBillTrendPanel(items) {
  const days = items.length ? items : [];
  const maxValue = Math.max(
    ...days.map((item) => Math.max(Number(item.total_expense ?? 0), Number(item.total_income ?? 0))),
    0,
  );
  const max = maxValue > 0 ? maxValue : 1500;
  const mid = max / 2;
  const expensePoints = trendLinePoints(days, max, "total_expense");
  const incomePoints = trendLinePoints(days, max, "total_income");
  const highlight = days[Math.min(19, Math.max(0, days.length - 1))];
  return `
    <section class="ledger-insight-panel">
      <div class="ledger-panel-header">
        <div>
          <h2 class="section-title">本月收支趋势</h2>
          <div class="trend-legend" aria-hidden="true">
            <span><i class="expense"></i>支出</span>
            <span><i class="income"></i>收入</span>
          </div>
        </div>
        <button class="button ghost" type="button" data-route="bills">查看全部</button>
      </div>
      <div class="ledger-trend-chart">
        <div class="trend-scale" aria-hidden="true">
          <span>${compactMoney(max)}</span>
          <span>${compactMoney(mid)}</span>
          <span>0</span>
        </div>
        <div class="trend-plot">
          <div class="trend-bars" role="list" aria-label="每日收支">
            ${days
              .map((item) => {
                const expense = Number(item.total_expense ?? 0);
                const income = Number(item.total_income ?? 0);
                return `
                  <button class="trend-day" type="button" role="listitem"
                    aria-label="${formatMonthDay(item.date)} 收入 ${money(income)} 支出 ${money(expense)}">
                    <span class="chart-tooltip">
                      <span class="tooltip-title">${formatMonthDay(item.date)}</span>
                      <span class="tooltip-value">收入 ${money(income)}</span>
                      <span class="tooltip-value">支出 ${money(expense)}</span>
                    </span>
                    <span class="trend-bar income" style="height:${Math.max(5, Math.round((income / max) * 90))}px"></span>
                    <span class="trend-bar expense" style="height:${Math.max(5, Math.round((expense / max) * 90))}px"></span>
                  </button>
                `;
              })
              .join("")}
          </div>
          <svg class="trend-line" viewBox="0 0 300 110" preserveAspectRatio="none" aria-hidden="true">
            <polyline class="expense" points="${expensePoints}" />
            <polyline class="income" points="${incomePoints}" />
          </svg>
          ${
            highlight
              ? `<span class="trend-badge">${formatMonthDay(highlight.date)}</span>`
              : ""
          }
        </div>
        <div class="trend-axis" aria-hidden="true">
          <span>${days[0] ? formatMonthDay(days[0].date) : ""}</span>
          <span>${days[9] ? formatMonthDay(days[9].date) : ""}</span>
          <span>${days[19] ? formatMonthDay(days[19].date) : ""}</span>
          <span>${days.length ? formatMonthDay(days[days.length - 1].date) : ""}</span>
        </div>
      </div>
    </section>
  `;
}

function trendLinePoints(items, max, field) {
  if (!items.length) {
    return "";
  }
  return items
    .map((item, index) => {
      const x = items.length === 1 ? 150 : (index / (items.length - 1)) * 300;
      const value = Number(item[field] ?? 0);
      const y = 100 - (value / max) * 86;
      return `${x.toFixed(2)},${Math.max(8, y).toFixed(2)}`;
    })
    .join(" ");
}

function renderBillCategoryFilters(categories) {
  const activeCategory = state.billFilters.category;
  const chips = [["", "全部"], ...categories.slice(0, 3).map((item) => [item.category, item.category])];
  return `
    <div class="ledger-filter-chips" aria-label="账单分类筛选">
      ${chips
        .map(
          ([value, label]) => `
            <button class="ledger-chip ${activeCategory === value ? "is-active" : ""}" type="button"
              data-bill-category="${escapeHtml(value)}">
              ${escapeHtml(label)}
            </button>
          `,
        )
        .join("")}
      <button class="ledger-filter-icon" type="button" data-bill-filter-panel aria-label="更多筛选">
        ${icon("filter")}
      </button>
    </div>
  `;
}

function renderBillActionDock() {
  return `
    <section class="bill-action-dock" aria-label="记账方式">
      <button class="bill-dock-side" type="button" data-voice-placeholder>
        ${icon("mic")}语音记账
      </button>
      <button class="bill-dock-main" type="button" data-open-bill-modal>
        ${icon("plus")}记一笔
      </button>
      <button class="bill-dock-side" type="button" data-bill-photo-placeholder>
        ${icon("camera")}拍照记账
      </button>
    </section>
  `;
}

function renderTasksPage() {
  const groups = getReminderTaskGroups();
  const visibleTasks = getVisibleReminderTasks(groups);
  const totalForProgress = groups.pending.length + groups.done.length;
  const progress = totalForProgress ? Math.round((groups.done.length / totalForProgress) * 100) : 0;

  return `
    <div class="mobile-page reminders-mobile-page reminder-page">
      <section class="reminder-hero">
        <div>
          <h1 class="reminder-title">提醒</h1>
          <p class="reminder-subtitle">安排好今天，每件事都不遗漏</p>
        </div>
        <div class="reminder-hero-art" aria-hidden="true">
          <span class="reminder-leaf reminder-leaf-left"></span>
          <span class="reminder-leaf reminder-leaf-right"></span>
          <span class="reminder-bell-art"></span>
          <span class="reminder-mascot"></span>
          <span class="reminder-calendar-art"></span>
        </div>
      </section>

      <section class="surface reminder-overview-panel">
        ${renderReminderViewTabs()}
        ${renderReminderCategoryTabs()}
        <section class="reminder-summary" aria-label="今日提醒摘要">
          ${reminderStat("今日待办", groups.today.length, "待完成事项")}
          ${reminderStat("已完成", groups.done.length, "已完成事项", "success")}
          ${reminderStat("重要事项", groups.important.length, "需要优先处理", "danger")}
          <div class="reminder-progress-summary">
            <span>今日完成进度</span>
            ${renderTaskProgressRing(progress)}
            <strong>${groups.done.length}/${totalForProgress || 0} 已完成</strong>
          </div>
        </section>
      </section>

      <section class="surface reminder-list-panel">
        <div class="reminder-list-header">
          <h2 class="section-title">${reminderListTitle()}</h2>
          <button class="reminder-sort-button" type="button" data-task-sort-placeholder>
            ${icon("list-filter")}按时间排序
          </button>
        </div>
        ${visibleTasks.length ? renderReminderTaskList(visibleTasks) : renderReminderEmpty()}
        <button class="reminder-more-button" type="button" data-view-all-tasks>
          查看全部 ${icon("chevron-right")}
        </button>
      </section>

      ${renderAiReminderAdvice(groups)}
      ${renderReminderActionDock()}
    </div>
  `;
}

function getReminderTaskGroups() {
  const sorted = [...state.tasks].sort(compareReminderTasks);
  const pending = sorted.filter((task) => task.status === "pending");
  const done = sorted.filter((task) => task.status === "done");
  const today = pending.filter(isTodayTask);
  return {
    all: sorted,
    pending,
    done,
    today: today.length ? today : pending,
    upcoming: pending.filter((task) => !isTodayTask(task)),
    important: pending.filter((task) => task.priority === "high"),
  };
}

function getVisibleReminderTasks(groups) {
  const view = state.taskFilters.view;
  let tasks = groups.today;
  if (view === "upcoming") {
    tasks = groups.upcoming.length ? groups.upcoming : groups.pending;
  } else if (view === "done") {
    tasks = groups.done;
  }

  if (state.taskFilters.category) {
    tasks = tasks.filter((task) => matchesTaskCategory(task, state.taskFilters.category));
  }
  return tasks.slice(0, 5);
}

function renderReminderViewTabs() {
  const tabs = [
    ["today", "今天"],
    ["upcoming", "即将到来"],
    ["done", "已完成"],
  ];
  return `
    <div class="reminder-view-tabs" aria-label="提醒状态">
      ${tabs
        .map(
          ([value, label]) => `
            <button class="reminder-view-tab ${state.taskFilters.view === value ? "is-active" : ""}"
              type="button" data-task-view="${value}">
              ${label}
            </button>
          `,
        )
        .join("")}
      <button class="reminder-calendar-button" type="button" data-task-calendar-placeholder aria-label="选择日期">
        ${icon("calendar")}
      </button>
    </div>
  `;
}

function renderReminderCategoryTabs() {
  const tabs = [
    ["", "全部", "check-circle"],
    ["学习", "学习", "book"],
    ["生活", "生活", "coffee"],
    ["工作", "工作", "briefcase"],
  ];
  return `
    <div class="reminder-category-tabs" aria-label="提醒分类">
      ${tabs
        .map(
          ([value, label, iconName]) => `
            <button class="reminder-category-tab ${state.taskFilters.category === value ? "is-active" : ""}"
              type="button" data-task-category="${escapeHtml(value)}">
              ${icon(iconName)}${label}
            </button>
          `,
        )
        .join("")}
    </div>
  `;
}

function reminderStat(label, value, hint, tone = "") {
  return `
    <div class="reminder-stat ${tone}">
      <span>${label}</span>
      <strong>${value}</strong>
      <small>${hint}</small>
    </div>
  `;
}

function renderTaskProgressRing(percent) {
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;
  return `
    <div class="progress-figure reminder-progress-figure" aria-label="今日完成进度 ${percent}%">
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

function reminderListTitle() {
  return {
    today: "今日提醒",
    upcoming: "即将到来",
    done: "已完成",
  }[state.taskFilters.view] ?? "今日提醒";
}

function renderReminderTaskList(tasks) {
  return `
    <div class="reminder-list">
      ${tasks.map((task) => renderReminderTaskItem(task)).join("")}
    </div>
  `;
}

function renderReminderTaskItem(task) {
  const done = task.status === "done";
  const tone = reminderTaskTone(task);
  const chip = reminderTaskChip(task);
  const priorityBadge = task.priority === "high" && !done
    ? '<span class="reminder-badge danger">重要</span>'
    : "";
  return `
    <article class="reminder-item ${done ? "is-done" : ""}">
      <span class="reminder-item-icon ${tone}">${icon(iconForTask(task))}</span>
      <div class="reminder-item-main">
        <div class="reminder-item-title-line">
          <h3>${escapeHtml(task.title)}</h3>
          ${priorityBadge}
        </div>
        <p>${shortTaskTime(task)}</p>
      </div>
      <span class="reminder-tag ${chip.tone}">${escapeHtml(chip.label)}</span>
      <button class="reminder-check ${done ? "is-done" : ""}" type="button"
        data-complete-task="${task.id}"
        aria-label="完成 ${escapeHtml(task.title)}"
        ${done || state.saving ? "disabled" : ""}>
        ${done ? icon("check") : ""}
      </button>
    </article>
  `;
}

function renderReminderEmpty() {
  return `
    <div class="reminder-empty">
      <span class="reminder-item-icon life">${icon("bell")}</span>
      <div>
        <p class="item-title">当前筛选下还没有提醒</p>
        <p class="item-meta">可以先添加一条，页面会立即使用真实后端数据刷新。</p>
      </div>
      <button class="button ghost" type="button" data-open-task-modal>${icon("plus")}添加</button>
    </div>
  `;
}

function renderAiReminderAdvice(groups) {
  const nextTask = groups.pending[0];
  const importantTask = groups.important[0];
  const advice = [
    nextTask
      ? `建议优先安排「${nextTask.title}」，时间是 ${shortTaskTime(nextTask)}。`
      : "今天还没有待处理提醒，可以安排一个轻量目标。",
    importantTask
      ? `「${importantTask.title}」标记为重要，适合放在精力最稳定的时间段。`
      : "暂无重要事项，今天的安排可以保持轻松节奏。",
    groups.pending.length > 3
      ? "待处理事项较多，建议预留一段缓冲时间。"
      : "当前事项不多，处理完后记得留出休息时间。",
  ];

  return `
    <section class="ai-reminder-panel" aria-label="AI 提醒建议">
      <div class="ai-reminder-title">
        <span class="panel-icon blue">${icon("spark")}</span>
        <h2 class="section-title">AI 提醒建议</h2>
      </div>
      <div class="ai-reminder-body">
        <div class="ai-reminder-rows">
          ${advice
            .map(
              (item, index) => `
                <p class="ai-reminder-row">
                  ${icon(index === 0 ? "send" : index === 1 ? "clock" : "moon")}
                  <span>${escapeHtml(item)}</span>
                </p>
              `,
            )
            .join("")}
        </div>
        <div class="ai-reminder-bot" aria-hidden="true">
          <span class="bot-ear left"></span>
          <span class="bot-ear right"></span>
          <span class="bot-head"><span></span></span>
          <span class="bot-body"></span>
        </div>
      </div>
    </section>
  `;
}

function renderReminderActionDock() {
  return `
    <section class="reminder-action-dock" aria-label="提醒操作">
      <button class="reminder-dock-side" type="button" data-voice-placeholder>
        ${icon("mic")}语音添加
      </button>
      <button class="reminder-dock-main" type="button" data-open-task-modal>
        ${icon("plus")}添加提醒
      </button>
      <button class="reminder-dock-side" type="button" data-repeat-task-placeholder>
        ${icon("refresh")}重复提醒
      </button>
    </section>
  `;
}

function compareReminderTasks(a, b) {
  const statusWeight = (task) => (task.status === "done" ? 1 : 0);
  const priorityWeight = (task) => ({ high: 0, medium: 1, low: 2 }[task.priority] ?? 1);
  const aTime = taskTargetDate(a)?.getTime() ?? Number.MAX_SAFE_INTEGER;
  const bTime = taskTargetDate(b)?.getTime() ?? Number.MAX_SAFE_INTEGER;
  return statusWeight(a) - statusWeight(b)
    || aTime - bTime
    || priorityWeight(a) - priorityWeight(b)
    || String(a.title ?? "").localeCompare(String(b.title ?? ""), "zh-CN");
}

function taskTargetDate(task) {
  const target = task?.task_type === "reminder"
    ? task.remind_at || task.due_at
    : task?.due_at || task?.remind_at;
  if (!target) {
    return null;
  }
  const date = new Date(target);
  return Number.isNaN(date.getTime()) ? null : date;
}

function isTodayTask(task) {
  const target = taskTargetDate(task);
  if (!target) {
    return task.status === "pending";
  }
  const now = new Date();
  return target.getFullYear() === now.getFullYear()
    && target.getMonth() === now.getMonth()
    && target.getDate() === now.getDate();
}

function shortTaskTime(task) {
  const target = taskTargetDate(task);
  if (!target) {
    return "未设置时间";
  }
  const time = target.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  if (isTodayTask(task)) {
    return `今天 ${time}`;
  }
  if (
    target.getFullYear() === tomorrow.getFullYear()
    && target.getMonth() === tomorrow.getMonth()
    && target.getDate() === tomorrow.getDate()
  ) {
    return `明天 ${time}`;
  }
  return `${formatMonthDay(target)} ${time}`;
}

function matchesTaskCategory(task, selectedCategory) {
  if (!selectedCategory) {
    return true;
  }
  return reminderTaskCategory(task) === selectedCategory;
}

function reminderTaskCategory(task) {
  const text = `${task?.category ?? ""} ${task?.title ?? ""}`.toLowerCase();
  if (text.includes("学") || text.includes("作业") || text.includes("study")) return "学习";
  if (text.includes("工") || text.includes("会议") || text.includes("项目") || text.includes("work")) return "工作";
  if (text.includes("个人") || text.includes("日记") || text.includes("心情")) return "个人";
  return "生活";
}

function reminderTaskTone(task) {
  return {
    学习: "study",
    工作: "work",
    个人: "personal",
    生活: "life",
  }[reminderTaskCategory(task)] ?? "life";
}

function reminderTaskChip(task) {
  if (task.status === "done") {
    return { label: "已完成", tone: "done" };
  }
  if (task.priority === "high" && isTodayTask(task)) {
    return { label: "今天截止", tone: "urgent" };
  }
  const category = reminderTaskCategory(task);
  return { label: category, tone: reminderTaskTone(task) };
}

function iconForTask(task) {
  const text = `${task?.category ?? ""} ${task?.title ?? ""}`.toLowerCase();
  if (text.includes("会议") || text.includes("团队") || text.includes("meeting")) return "users";
  if (text.includes("信用") || text.includes("账单") || text.includes("card")) return "card";
  if (text.includes("购物") || text.includes("超市") || text.includes("shop")) return "shopping";
  if (text.includes("学习") || text.includes("作业") || text.includes("study")) return "book";
  if (text.includes("日记") || text.includes("心情")) return "notebook";
  if (text.includes("工作") || text.includes("项目") || text.includes("work")) return "briefcase";
  return task?.task_type === "reminder" ? "bell" : "check-circle";
}

function renderDiaryMobilePage() {
  const diary = getDiarySnapshot();
  return `
    <div class="mobile-page diary-mobile-page diary-page">
      <section class="diary-hero">
        <div>
          <h1 class="diary-title">日记</h1>
          <p class="diary-subtitle">记录生活点滴，收藏今天的心情</p>
        </div>
        <div class="diary-hero-art" aria-hidden="true">
          <span class="diary-window-art"></span>
          <span class="diary-plant diary-plant-left"></span>
          <span class="diary-plant diary-plant-right"></span>
          <span class="diary-cup-art"></span>
          <span class="diary-mascot-art"></span>
          <span class="diary-book-art-hero"></span>
          <span class="diary-pencil-art"></span>
        </div>
      </section>

      <section class="surface diary-period-panel">
        ${renderDiaryPeriodTabs()}
      </section>

      ${renderDiaryMoodSummary(diary)}
      ${renderDiaryEntry(diary)}
      ${renderDiaryGallery()}
      ${renderDiaryAiAssistant()}
      ${renderDiaryActionDock()}
    </div>
  `;
}

function getDiarySnapshot() {
  const draft = state.diaryDraft;
  const recentBills = state.bills.slice(0, 2).map((bill) => bill.merchant).filter(Boolean);
  const pendingTasks = state.tasks.filter((task) => task.status === "pending").length;
  return {
    title: draft?.title || "今天的日记",
    mood: draft?.mood || "happy",
    moodLabel: diaryMoodLabel(draft?.mood || "happy"),
    moodScore: draft?.mood === "calm" ? 78 : draft?.mood === "tired" ? 52 : 86,
    weather: draft?.weather || "晴天",
    createdAt: draft?.created_at || new Date().toISOString(),
    streakDays: 7,
    monthEntries: Math.max(12, Number(state.bootstrap?.data_summary?.task_count ?? 0) + 12),
    body: draft?.content || [
      "今天是充实又安稳的一天。",
      recentBills.length
        ? `记录了 ${recentBills.join("、")} 相关的小事，生活节奏正在慢慢变清楚。`
        : "完成了一些重要安排，也给自己留了片刻安静时间。",
      pendingTasks
        ? `还有 ${pendingTasks} 件提醒待处理，晚上可以简单收个尾。`
        : "今晚没有太多挂念，可以轻轻松松结束这一天。",
      "希望明天也能保持这样的好状态。",
    ].join("\n"),
  };
}

function renderDiaryPeriodTabs() {
  const tabs = [
    ["today", "今天"],
    ["week", "本周"],
    ["month", "本月"],
  ];
  return `
    <div class="diary-period-tabs" aria-label="日记时间范围">
      ${tabs
        .map(
          ([value, label]) => `
            <button class="diary-period-tab ${state.diaryFilters.period === value ? "is-active" : ""}"
              type="button" data-diary-period="${value}">
              ${label}
            </button>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderDiaryMoodSummary(diary) {
  return `
    <section class="surface diary-mood-section">
      <div class="diary-section-header">
        <div class="diary-section-title">
          <span class="panel-icon">${icon("smile")}</span>
          <h2 class="section-title">今日心情</h2>
        </div>
        <button class="diary-icon-button" type="button" data-diary-calendar-placeholder aria-label="选择日记日期">
          ${icon("calendar")}
        </button>
      </div>
      <div class="diary-mood-body">
        <div class="diary-mood-card">
          <span class="diary-face ${escapeHtml(diary.mood)}" aria-hidden="true"></span>
          <div class="diary-mood-copy">
            <div>
              <strong>${escapeHtml(diary.moodLabel)}</strong>
              <span class="diary-quality-pill">很好</span>
            </div>
            <p>${diary.mood === "tired" ? "今天有点累，适合早点休息。" : "阳光正好，心情很棒。"}</p>
          </div>
        </div>
        ${diaryMiniStat("连续记录", diary.streakDays, "天")}
        ${diaryMiniStat("本月已写", diary.monthEntries, "篇")}
        <div class="diary-index">
          <span>心情指数</span>
          ${renderDiaryMoodRing(diary.moodScore)}
          <small>${diary.moodScore >= 80 ? "很好" : diary.moodScore >= 60 ? "平稳" : "需休息"}</small>
        </div>
      </div>
    </section>
  `;
}

function diaryMiniStat(label, value, unit) {
  return `
    <div class="diary-mini-stat">
      <span>${label}</span>
      <strong>${value}</strong>
      <small>${unit}</small>
    </div>
  `;
}

function renderDiaryMoodRing(percent) {
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;
  return `
    <div class="diary-ring" aria-label="心情指数 ${percent}%">
      <svg viewBox="0 0 92 92" aria-hidden="true">
        <circle class="ring-track" cx="46" cy="46" r="${radius}"></circle>
        <circle class="ring-value" cx="46" cy="46" r="${radius}"
          stroke-dasharray="${circumference.toFixed(2)}"
          stroke-dashoffset="${offset.toFixed(2)}"></circle>
      </svg>
      <strong>${percent}%</strong>
    </div>
  `;
}

function renderDiaryEntry(diary) {
  const lines = diary.body.split("\n").filter(Boolean);
  return `
    <section class="surface diary-entry-section">
      <div class="diary-entry-header">
        <div class="diary-section-title">
          <span class="panel-icon">${icon("notebook")}</span>
          <h2 class="section-title">${escapeHtml(diary.title)}</h2>
        </div>
        <div class="diary-entry-meta">
          <span>${icon("clock")}${formatDiaryTime(diary.createdAt)}</span>
          <span>${icon("sun")}${escapeHtml(diary.weather)}</span>
          <span class="is-soft">${icon("smile")}${escapeHtml(diary.moodLabel)}</span>
          <button class="diary-more" type="button" data-diary-placeholder aria-label="编辑日记">
            ${icon("more-horizontal")}
          </button>
        </div>
      </div>
      <div class="diary-entry-body">
        ${lines.map((line) => `<p>${escapeHtml(line)}</p>`).join("")}
      </div>
    </section>
  `;
}

function renderDiaryGallery() {
  const photos = [
    ["coffee", "晨间咖啡"],
    ["window", "窗边时刻"],
    ["desk", "夜晚书桌"],
  ];
  return `
    <section class="surface diary-gallery-section">
      <div class="diary-section-header">
        <div class="diary-section-title">
          <span class="panel-icon">${icon("image")}</span>
          <h2 class="section-title">今日片段</h2>
        </div>
        <button class="button ghost" type="button" data-diary-photo-placeholder>
          查看全部 ${icon("chevron-right")}
        </button>
      </div>
      <div class="diary-photo-grid">
        ${photos.map(([tone, label]) => renderDiaryPhotoCard(tone, label)).join("")}
      </div>
    </section>
  `;
}

function renderDiaryPhotoCard(tone, label) {
  return `
    <button class="diary-photo-card ${tone}" type="button" data-diary-photo-placeholder aria-label="${escapeHtml(label)}">
      <span class="photo-scene" aria-hidden="true"></span>
      <span>${escapeHtml(label)}</span>
    </button>
  `;
}

function renderDiaryAiAssistant() {
  const prompts = [
    ["heart", "今天最开心的事是什么？"],
    ["users", "有没有想感谢的人？"],
    ["lightbulb", "记录一下今天学到的新东西。"],
  ];
  return `
    <section class="ai-diary-panel" aria-label="AI 日记助手">
      <div class="ai-diary-title">
        <span class="panel-icon blue">${icon("spark")}</span>
        <h2 class="section-title">AI 日记助手</h2>
      </div>
      <div class="ai-diary-body">
        <div class="ai-diary-prompts">
          ${prompts
            .map(
              ([iconName, text]) => `
                <button class="ai-diary-prompt" type="button" data-diary-ai-prompt>
                  ${icon(iconName)}
                  <span>${escapeHtml(text)}</span>
                  ${icon("chevron-right")}
                </button>
              `,
            )
            .join("")}
        </div>
        <div class="ai-diary-bot" aria-hidden="true">
          <span class="bot-ear left"></span>
          <span class="bot-ear right"></span>
          <span class="bot-head"><span></span></span>
          <span class="bot-body"></span>
        </div>
      </div>
    </section>
  `;
}

function renderDiaryActionDock() {
  return `
    <section class="diary-action-dock" aria-label="日记操作">
      <button class="diary-dock-side" type="button" data-voice-placeholder>
        ${icon("mic")}语音日记
      </button>
      <button class="diary-dock-main" type="button" data-open-diary-modal>
        ${icon("plus")}写日记
      </button>
      <button class="diary-dock-side" type="button" data-diary-photo-placeholder>
        ${icon("image")}添加图片
      </button>
    </section>
  `;
}

function diaryMoodLabel(value) {
  return {
    happy: "开心",
    calm: "平静",
    tired: "疲惫",
  }[value] ?? "开心";
}

function formatDiaryTime(value) {
  const date = value ? new Date(value) : new Date();
  if (Number.isNaN(date.getTime())) {
    return "今天";
  }
  return `今天 ${date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
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

function renderProfilePage() {
  const overview = state.billOverview ?? {};
  const monthly = overview.monthly_statistics ?? state.bootstrap?.dashboard?.monthly_statistics ?? {};
  const summary = state.bootstrap?.data_summary ?? {};
  const expense = Number(monthly.total_expense ?? 0);
  const income = Number(monthly.total_income ?? 0);
  const netAmount = Number(monthly.net_amount ?? income - expense);
  const completedTasks = state.tasks.filter((task) => task.status === "done").length;
  const diaryCount = state.diaryDraft ? 1 : 0;

  return `
    <div class="mobile-page profile-mobile-page profile-page">
      <section class="profile-hero">
        <div class="profile-topline">
          <h1 class="profile-title">我的</h1>
          <div class="profile-top-actions">
            <button class="profile-icon-button" type="button" data-profile-notification aria-label="通知中心">
              ${icon("bell")}
            </button>
            <button class="profile-icon-button" type="button" data-profile-preferences aria-label="个人设置">
              ${icon("settings")}
            </button>
          </div>
        </div>
        <div class="profile-greeting">
          <span class="profile-avatar" aria-hidden="true">
            <span class="avatar-face"></span>
          </span>
          <div class="profile-greeting-copy">
            <h2>Hi，今天也要加油呀</h2>
            <p>记录生活，遇见更好的自己</p>
          </div>
          <button class="profile-link-button" type="button" data-profile-placeholder aria-label="查看个人资料">
            ${icon("chevron-right")}
          </button>
        </div>
        <div class="profile-landscape" aria-hidden="true">
          <span class="profile-cloud cloud-a"></span>
          <span class="profile-cloud cloud-b"></span>
          <span class="profile-mountain mountain-a"></span>
          <span class="profile-mountain mountain-b"></span>
          <span class="profile-field"></span>
          <span class="profile-person"></span>
          <span class="profile-leaves"></span>
        </div>
      </section>

      ${renderProfileFinanceCard(expense, income, netAmount, monthly)}
      ${renderProfileQuickLinks()}
      ${renderProfileTools()}
      ${renderProfileDataPanel(summary, completedTasks, diaryCount)}
      ${renderProfileSafetyPanel()}
    </div>
  `;
}

function renderProfileFinanceCard(expense, income, netAmount, monthly) {
  const categories = profileFinanceCategories(monthly, expense);
  return `
    <section class="surface profile-finance-card">
      <div class="profile-finance-copy">
        <p class="profile-card-label">本月总支出 ${icon("eye")}</p>
        <strong>${money(expense)}</strong>
        <span>本月收入 <b class="income">${money(income)}</b></span>
        <span>结余 <b class="${netAmount >= 0 ? "income" : "expense"}">${money(netAmount)}</b></span>
      </div>
      <div class="profile-finance-chart">
        ${renderProfileDonut(categories)}
        <div class="profile-category-legend">
          ${categories
            .map(
              (item, index) => `
                <button class="profile-legend-row" type="button" aria-label="${escapeHtml(item.category)} ${item.percent}%">
                  <i class="profile-dot dot-${(index % 5) + 1}"></i>
                  <span>${escapeHtml(item.category)}</span>
                  <strong>${item.percent}%</strong>
                  <span class="chart-tooltip">
                    <span class="tooltip-title">${escapeHtml(item.category)}</span>
                    <span class="tooltip-value">${money(item.amount)}</span>
                  </span>
                </button>
              `,
            )
            .join("")}
        </div>
      </div>
    </section>
  `;
}

function profileFinanceCategories(monthly, expense) {
  const source = (monthly.category_breakdown ?? [])
    .map((item) => ({
      category: item.category,
      amount: Number(item.amount ?? item.total ?? 0),
    }))
    .filter((item) => item.amount > 0)
    .slice(0, 4);

  if (!source.length) {
    return [{ category: "暂无记录", amount: 0, percent: 100, empty: true }];
  }

  const total = expense > 0 ? expense : source.reduce((sum, item) => sum + item.amount, 0);
  return source.map((item) => ({
    ...item,
    percent: total > 0 ? Math.max(1, Math.round((item.amount / total) * 100)) : 0,
  }));
}

function renderProfileDonut(categories) {
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return `
    <div class="profile-donut" aria-label="本月支出分类占比">
      <svg viewBox="0 0 112 112" aria-hidden="true">
        <circle class="profile-donut-track" cx="56" cy="56" r="${radius}"></circle>
        ${categories
          .map((item, index) => {
            const length = ((item.empty ? 100 : item.percent) / 100) * circumference;
            const segment = `
              <circle class="profile-donut-segment segment-${(index % 5) + 1} ${item.empty ? "empty" : ""}"
                cx="56" cy="56" r="${radius}"
                stroke-dasharray="${length.toFixed(2)} ${circumference.toFixed(2)}"
                stroke-dashoffset="${(-offset).toFixed(2)}"></circle>
            `;
            offset += length;
            return segment;
          })
          .join("")}
      </svg>
    </div>
  `;
}

function renderProfileQuickLinks() {
  return `
    <section class="surface profile-shortcuts" aria-label="个人快捷入口">
      ${profileShortcut("wallet", "记账本", "记录每一笔收支", "data-route=\"bills\"", "mint")}
      ${profileShortcut("spark", "智能助手", "语音对话操作", "data-voice-placeholder", "blue")}
      ${profileShortcut("calendar-check", "待办提醒", "查看事项安排", "data-route=\"tasks\"", "gold")}
      ${profileShortcut("notebook", "日记本", "记录心情日常", "data-route=\"diary\"", "rose")}
    </section>
  `;
}

function profileShortcut(iconName, title, note, attribute, tone) {
  return `
    <button class="profile-shortcut ${tone}" type="button" ${attribute}>
      <span>${icon(iconName)}</span>
      <strong>${title}</strong>
      <small>${note}</small>
    </button>
  `;
}

function renderProfileTools() {
  return `
    <section class="surface profile-tools-panel">
      <div class="profile-section-header">
        <h2 class="section-title">我的工具</h2>
        <button class="button ghost" type="button" data-profile-placeholder>
          全部工具 ${icon("chevron-right")}
        </button>
      </div>
      <div class="profile-tool-grid">
        ${profileTool("pie-chart", "预算管理", "data-profile-placeholder", "mint")}
        ${profileTool("file-text", "账单导出", "data-export-json", "blue")}
        ${profileTool("grid", "分类管理", "data-profile-placeholder", "orange")}
        ${profileTool("tag", "标签管理", "data-profile-placeholder", "mint")}
        ${profileTool("cloud", "数据备份", "data-snapshot-save", "blue")}
      </div>
    </section>
  `;
}

function profileTool(iconName, label, attribute, tone) {
  return `
    <button class="profile-tool ${tone}" type="button" ${attribute} ${state.saving ? "disabled" : ""}>
      ${icon(iconName)}
      <span>${label}</span>
    </button>
  `;
}

function renderProfileDataPanel(summary, completedTasks, diaryCount) {
  const billCount = Number(summary.bill_count ?? state.bills.length ?? 0);
  const attachmentCount = Number(summary.attachment_count ?? 0);
  return `
    <section class="surface profile-data-panel">
      <div class="profile-section-header">
        <h2 class="section-title">我的数据</h2>
        <button class="button ghost" type="button" data-profile-placeholder>
          查看全部 ${icon("chevron-right")}
        </button>
      </div>
      <div class="profile-data-grid">
        ${profileDataCard("calendar", "记账天数", billCount, "天", "坚持记录", "mint")}
        ${profileDataCard("notebook", "日记篇数", diaryCount, "篇", "记录心情", "blue")}
        ${profileDataCard("check-circle", "完成事项", completedTasks, "个", "高效生活", "orange")}
        ${profileDataCard("image", "附件片段", attachmentCount, "个", "生活素材", "rose")}
      </div>
    </section>
  `;
}

function profileDataCard(iconName, label, value, unit, note, tone) {
  return `
    <div class="profile-data-card ${tone}">
      <span>${icon(iconName)}</span>
      <p>${label}</p>
      <strong>${value}<small>${unit}</small></strong>
      <em>${note}</em>
    </div>
  `;
}

function renderProfileSafetyPanel() {
  const privacy = state.bootstrap?.privacy_settings ?? {};
  const snapshot = state.snapshotStatus;
  return `
    <section class="surface profile-safety-panel">
      <div>
        <h2 class="section-title">数据与隐私</h2>
        <p>${privacy.local_only_mode ? "本地体验已开启" : "本地体验未开启"} · ${escapeHtml(snapshotText(snapshot))}</p>
      </div>
      <div class="profile-safety-actions">
        <button class="button ghost" type="button" data-settings-action="loadSnapshot"
          ${!snapshot?.exists || state.saving ? "disabled" : ""}>
          ${icon("upload")}加载快照
        </button>
        <button class="button danger" type="button" data-settings-action="clear" ${state.saving ? "disabled" : ""}>
          ${icon("trash")}清除数据
        </button>
      </div>
    </section>
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
            <button class="bill-feed-item ledger-feed-item" type="button" data-edit-bill="${bill.id}">
              <span class="bill-feed-icon">${icon(iconForBill(bill))}</span>
              <div class="bill-feed-main">
                <div class="bill-feed-topline">
                  <h2>${escapeHtml(bill.merchant)}</h2>
                  <span class="amount ${bill.transaction_type}">${signedMoney(bill)}</span>
                </div>
                <p class="item-meta">
                  ${escapeHtml(bill.category)}
                  · ${formatDate(bill.paid_at)}
                </p>
                ${bill.note ? `<p class="bill-note">${escapeHtml(bill.note)}</p>` : ""}
              </div>
              <span class="ledger-payment">${escapeHtml(bill.payment_method || labelTransaction(bill.transaction_type))}</span>
            </button>
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

function renderDiaryModal() {
  const diary = getDiarySnapshot();
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal" role="dialog" aria-modal="true" aria-labelledby="diary-modal-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="diary-modal-title">写日记</h2>
            <p class="section-note">当前先保存为本次前端体验草稿，后续接入真实日记存储。</p>
          </div>
          <button class="button ghost" type="button" data-close-modal aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <form class="form" data-diary-form>
          <div class="form-grid">
            <div class="field full">
              <label for="diary_title">标题</label>
              <input id="diary_title" name="title" required maxlength="80" placeholder="今天的日记"
                value="${escapeHtml(diary.title)}" />
            </div>
            <div class="field">
              <label for="diary_mood">心情</label>
              <select id="diary_mood" name="mood">
                <option value="happy" ${diary.mood === "happy" ? "selected" : ""}>开心</option>
                <option value="calm" ${diary.mood === "calm" ? "selected" : ""}>平静</option>
                <option value="tired" ${diary.mood === "tired" ? "selected" : ""}>疲惫</option>
              </select>
            </div>
            <div class="field">
              <label for="diary_weather">天气</label>
              <input id="diary_weather" name="weather" maxlength="20" placeholder="晴天"
                value="${escapeHtml(diary.weather)}" />
            </div>
            <div class="field full">
              <label for="diary_content">内容</label>
              <textarea id="diary_content" name="content" required maxlength="800"
                placeholder="记录今天发生的小事、心情和想法。">${escapeHtml(diary.body)}</textarea>
            </div>
          </div>
          <div class="form-actions">
            <button class="button ghost" type="button" data-close-modal>取消</button>
            <button class="button primary" type="submit">
              ${icon("save")}保存草稿
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

function signedMoney(bill) {
  const prefix = bill.transaction_type === "expense" ? "-" : "+";
  return `${prefix}${money(bill.amount)}`;
}

function compactMoney(value) {
  const number = Number(value ?? 0);
  if (number >= 10000) {
    return `${(number / 10000).toFixed(1)}万`;
  }
  if (number >= 1000) {
    return `${Math.round(number).toLocaleString("zh-CN")}`;
  }
  return String(Math.round(number));
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

function formatMonthDay(value) {
  if (!value) return "";
  const date = new Date(value);
  return `${date.getMonth() + 1}/${date.getDate()}`;
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
    filter: '<path d="M4 5h16"></path><path d="M7 12h10"></path><path d="M10 19h4"></path>',
    reset: '<path d="M4 7h11a5 5 0 1 1-3.5 8.5"></path><path d="M4 7l4-4"></path><path d="M4 7l4 4"></path>',
    edit: '<path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17v3z"></path><path d="M13.5 6.5l4 4"></path>',
    eye: '<path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6z"></path><circle cx="12" cy="12" r="3"></circle>',
    calendar: '<rect x="4" y="5" width="16" height="15" rx="2"></rect><path d="M8 3v4"></path><path d="M16 3v4"></path><path d="M4 10h16"></path>',
    "calendar-check": '<rect x="4" y="5" width="16" height="15" rx="2"></rect><path d="M8 3v4"></path><path d="M16 3v4"></path><path d="M4 10h16"></path><path d="M8 15l2.5 2.5L16 12"></path>',
    camera: '<path d="M5 7h3l1.5-2h5L16 7h3a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2z"></path><circle cx="12" cy="13" r="4"></circle>',
    image: '<rect x="4" y="5" width="16" height="14" rx="2"></rect><circle cx="9" cy="10" r="2"></circle><path d="M4 16l4-4 4 4 2-2 6 5"></path>',
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
    notebook: '<path d="M7 4h10a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"></path><path d="M9 4v16"></path><path d="M12 8h4"></path><path d="M12 12h4"></path>',
    briefcase: '<path d="M10 6V4h4v2"></path><rect x="4" y="6" width="16" height="13" rx="2"></rect><path d="M4 12h16"></path><path d="M10 12v2h4v-2"></path>',
    coffee: '<path d="M5 8h11v5a5 5 0 0 1-5 5H10a5 5 0 0 1-5-5V8z"></path><path d="M16 9h2a3 3 0 0 1 0 6h-2"></path><path d="M7 4v1"></path><path d="M11 4v1"></path>',
    users: '<path d="M16 19a4 4 0 0 0-8 0"></path><circle cx="12" cy="9" r="4"></circle><path d="M20 19a3 3 0 0 0-3-3"></path><path d="M4 19a3 3 0 0 1 3-3"></path>',
    card: '<rect x="4" y="6" width="16" height="12" rx="2"></rect><path d="M4 10h16"></path><path d="M8 15h4"></path>',
    "list-filter": '<path d="M4 6h12"></path><path d="M4 12h9"></path><path d="M4 18h6"></path><path d="M18 9v9"></path><path d="M15 15l3 3 3-3"></path>',
    "chevron-right": '<path d="M9 6l6 6-6 6"></path>',
    send: '<path d="M21 3 10 14"></path><path d="M21 3l-7 18-4-7-7-4 18-7z"></path>',
    moon: '<path d="M20 15.5A8 8 0 0 1 8.5 4 7 7 0 1 0 20 15.5z"></path>',
    smile: '<circle cx="12" cy="12" r="9"></circle><path d="M8 10h.01"></path><path d="M16 10h.01"></path><path d="M8 14a5 5 0 0 0 8 0"></path>',
    sun: '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="M4.9 4.9l1.4 1.4"></path><path d="M17.7 17.7l1.4 1.4"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="M4.9 19.1l1.4-1.4"></path><path d="M17.7 6.3l1.4-1.4"></path>',
    "more-horizontal": '<circle cx="5" cy="12" r="1"></circle><circle cx="12" cy="12" r="1"></circle><circle cx="19" cy="12" r="1"></circle>',
    heart: '<path d="M20.8 8.6a5 5 0 0 0-8.1-3.9L12 5.4l-.7-.7a5 5 0 0 0-7.1 7.1L12 19l7.8-7.2a5 5 0 0 0 1-3.2z"></path>',
    lightbulb: '<path d="M9 18h6"></path><path d="M10 22h4"></path><path d="M8 14a6 6 0 1 1 8 0c-1 1-1 2-1 4h-6c0-2 0-3-1-4z"></path>',
    "pie-chart": '<path d="M12 3v9h9"></path><path d="M19.1 15A8 8 0 1 1 9 4.6"></path><path d="M14 3.3A8 8 0 0 1 20.7 10H14V3.3z"></path>',
    "file-text": '<path d="M6 3h9l3 3v15H6V3z"></path><path d="M14 3v4h4"></path><path d="M9 11h6"></path><path d="M9 15h6"></path><path d="M9 19h4"></path>',
    grid: '<rect x="4" y="4" width="6" height="6" rx="1"></rect><rect x="14" y="4" width="6" height="6" rx="1"></rect><rect x="4" y="14" width="6" height="6" rx="1"></rect><rect x="14" y="14" width="6" height="6" rx="1"></rect>',
    tag: '<path d="M20 13 13 20l-9-9V4h7l9 9z"></path><circle cx="8.5" cy="8.5" r="1"></circle>',
    cloud: '<path d="M7 18h10a4 4 0 0 0 .5-8A6 6 0 0 0 6.2 8.8 4.5 4.5 0 0 0 7 18z"></path>',
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
