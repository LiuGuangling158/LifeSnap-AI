const routes = [
  {
    id: "dashboard",
    label: "首页看板",
    icon: "layout",
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

  if (event.target.closest("[data-refresh]")) {
    loadData();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && (state.modalOpen || state.deleteTarget)) {
    state.modalOpen = false;
    state.editingBill = null;
    state.deleteTarget = null;
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
  }
});

loadData();

async function loadData() {
  state.loading = true;
  state.error = "";
  render();

  try {
    const [bootstrap, billOverview, billList, taskList] = await Promise.all([
      api("/app/bootstrap?recent_bill_limit=6&candidate_limit=5"),
      api("/bills/statistics/overview?trend_months=6&top_merchant_limit=6"),
      api(buildBillListPath()),
      api("/tasks?page_size=8"),
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

function getRoute() {
  const id = window.location.hash.replace("#", "");
  return routes.some((route) => route.id === id) ? id : "dashboard";
}

function render() {
  const route = routes.find((item) => item.id === state.route) ?? routes[0];
  app.innerHTML = `
    <div class="app-shell">
      ${renderSidebar()}
      <main class="main">
        <header class="topbar">
          <div>
            <p class="eyebrow">${route.eyebrow}</p>
            <h1 class="page-title">${route.title}</h1>
            <p class="page-subtitle">${route.subtitle}</p>
          </div>
          <div class="action-row">
            <button class="button primary" type="button" data-open-bill-modal>
              ${icon("plus")}新增记录
            </button>
            <button class="button ghost" type="button" data-refresh>
              ${icon("refresh")}刷新
            </button>
          </div>
        </header>
        ${renderPage()}
      </main>
      ${state.modalOpen ? renderBillModal() : ""}
      ${state.deleteTarget ? renderDeleteBillModal() : ""}
      ${state.toast ? `<div class="toast" role="status">${escapeHtml(state.toast)}</div>` : ""}
    </div>
  `;
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
  if (state.route === "settings") return renderSettingsPage();
  return renderDashboard();
}

function renderDashboard() {
  const dashboard = state.bootstrap?.dashboard ?? {};
  const monthly = dashboard.monthly_statistics ?? {};
  const dataSummary = state.bootstrap?.data_summary ?? {};

  return `
    <div class="stack">
      <section class="surface">
        <div class="section-header">
          <div>
            <h2 class="section-title">本月概览</h2>
            <p class="section-note">用于前端联调的真实接口数据，新增账单后会刷新。</p>
          </div>
          <span class="pill">${state.bootstrap?.capabilities?.storage_backend ?? "local"}</span>
        </div>
        <div class="metrics">
          ${metric("本月支出", money(monthly.total_expense), "expense")}
          ${metric("本月收入", money(monthly.total_income), "income")}
          ${metric("今日待办", dashboard.today_task_count ?? 0, "small")}
          ${metric("候选记录", pendingCandidateCount(dashboard), "small")}
        </div>
      </section>
      <div class="content-grid">
        <section class="surface">
          <div class="section-header">
            <div>
              <h2 class="section-title">本月每日支出</h2>
              <p class="section-note">悬停柱形查看日期和金额。</p>
            </div>
          </div>
          ${renderDailyChart(state.billOverview?.daily_breakdown ?? [])}
        </section>
        <section class="surface">
          <div class="section-header">
            <div>
              <h2 class="section-title">最近账单</h2>
              <p class="section-note">${dataSummary.bill_count ?? 0} 条活跃账单</p>
            </div>
          </div>
          ${renderBillList(dashboard.recent_bills ?? state.bills)}
        </section>
      </div>
    </div>
  `;
}

function renderBillsPage() {
  return `
    <section class="surface">
      <div class="section-header">
        <div>
          <h2 class="section-title">账单记录</h2>
          <p class="section-note">支持按月份、分类、交易类型和关键词筛选；删除会进入软删除。</p>
        </div>
        <span class="pill">${state.billListMeta.total} 条</span>
      </div>
      ${renderBillFilters()}
      ${state.bills.length ? renderBillsTable(state.bills) : empty("还没有账单，可以先新增一条手动记录。")}
    </section>
  `;
}

function renderTasksPage() {
  return `
    <section class="surface">
      <div class="section-header">
        <div>
          <h2 class="section-title">待办提醒</h2>
          <p class="section-note">后端待办列表已接入，下一轮可继续补新增、完成和延后。</p>
        </div>
      </div>
      ${state.tasks.length ? renderTaskList(state.tasks) : empty("还没有待办。")}
    </section>
  `;
}

function renderSettingsPage() {
  const caps = state.bootstrap?.capabilities ?? {};
  const privacy = state.bootstrap?.privacy_settings ?? {};
  return `
    <section class="surface">
      <div class="section-header">
        <div>
          <h2 class="section-title">本地与隐私</h2>
          <p class="section-note">先展示后端能力，后续补全可操作的数据清理和快照入口。</p>
        </div>
      </div>
      <div class="list">
        ${settingRow("本地模式", privacy.local_only_mode ? "开启" : "关闭")}
        ${settingRow("OCR", caps.ocr_provider ?? "unknown")}
        ${settingRow("AI 解析", caps.ai_text_parser ?? "unknown")}
        ${settingRow("持久化数据库", caps.feature_flags?.persistent_database ? "已接入" : "未接入")}
      </div>
    </section>
  `;
}

function renderDailyChart(items) {
  if (!items.length) {
    return empty("暂无统计数据。");
  }
  const values = items.map((item) => Number(item.total_expense ?? 0));
  const max = Math.max(...values, 1);
  return `
    <div class="chart" role="list" aria-label="本月每日支出">
      ${items
        .map((item, index) => {
          const value = Number(item.total_expense ?? 0);
          const height = Math.max(8, Math.round((value / max) * 170));
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
    <form class="filter-form" data-bill-filter>
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
        <button class="button" type="submit">${icon("search")}筛选</button>
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

function renderTaskList(tasks) {
  return `
    <div class="list">
      ${tasks
        .map(
          (task) => `
            <div class="list-item">
              <div>
                <p class="item-title">${escapeHtml(task.title)}</p>
                <p class="item-meta">${escapeHtml(task.category)} · ${labelTaskStatus(task.status)}</p>
              </div>
              <span class="pill">${labelTaskType(task.task_type)}</span>
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

function metric(label, value, tone = "") {
  return `
    <div class="metric">
      <div class="metric-label">${label}</div>
      <div class="metric-value ${tone}">${value}</div>
    </div>
  `;
}

function settingRow(label, value) {
  return `
    <div class="list-item">
      <div>
        <p class="item-title">${escapeHtml(label)}</p>
      </div>
      <span class="pill">${escapeHtml(String(value))}</span>
    </div>
  `;
}

function empty(message) {
  return `<p class="empty">${escapeHtml(message)}</p>`;
}

function pendingCandidateCount(dashboard) {
  return Number(dashboard.pending_bill_candidate_count ?? 0)
    + Number(dashboard.pending_task_candidate_count ?? 0);
}

function money(value) {
  const number = Number(value ?? 0);
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    maximumFractionDigits: 2,
  }).format(number);
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

function icon(name) {
  const paths = {
    layout: '<rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="3" y="14" width="18" height="7"></rect>',
    receipt: '<path d="M6 3h12v18l-2-1.2-2 1.2-2-1.2-2 1.2-2-1.2L6 21V3z"></path><path d="M9 8h6"></path><path d="M9 12h6"></path><path d="M9 16h4"></path>',
    check: '<path d="M4 12l5 5L20 6"></path>',
    settings: '<circle cx="12" cy="12" r="3"></circle><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1a7 7 0 0 0-1.7-1L14.5 3h-5l-.4 3.1a7 7 0 0 0-1.7 1l-2.4-1-2 3.4 2 1.5a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a7 7 0 0 0 1.7 1l.4 3.1h5l.4-3.1a7 7 0 0 0 1.7-1l2.4 1 2-3.4-2-1.5c.1-.3.1-.7.1-1z"></path>',
    plus: '<path d="M12 5v14"></path><path d="M5 12h14"></path>',
    refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7"></path><path d="M20 16v-5h-5"></path>',
    search: '<circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path>',
    reset: '<path d="M4 7h11a5 5 0 1 1-3.5 8.5"></path><path d="M4 7l4-4"></path><path d="M4 7l4 4"></path>',
    edit: '<path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17v3z"></path><path d="M13.5 6.5l4 4"></path>',
    trash: '<path d="M4 7h16"></path><path d="M10 11v6"></path><path d="M14 11v6"></path><path d="M6 7l1 14h10l1-14"></path><path d="M9 7V4h6v3"></path>',
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
