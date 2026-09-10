const routes = [
  {
    id: "dashboard",
    label: "首页",
    icon: "home",
    eyebrow: "本地体验",
    title: "今天先把账记顺",
    subtitle: "记下收支，随时知道钱花在哪里。",
  },
  {
    id: "bills",
    label: "账单",
    icon: "receipt",
    eyebrow: "手动记录",
    title: "账单列表",
    subtitle: "查找、核对和修改每一笔收支。",
  },
  {
    id: "tasks",
    label: "待办",
    icon: "check",
    eyebrow: "提醒辅助",
    title: "待办提醒",
    subtitle: "把要做的事记下来。",
  },
  {
    id: "diary",
    label: "日记",
    icon: "book",
    eyebrow: "生活记录",
    title: "日记",
    subtitle: "留下一点今天的心情。",
  },
  {
    id: "assistant",
    label: "助手",
    icon: "spark",
    eyebrow: "帮你整理",
    title: "智能助手",
    subtitle: "把一句话、图片或语音整理成可确认的生活操作。",
  },
  {
    id: "settings",
    label: "设置",
    icon: "settings",
    eyebrow: "隐私与数据",
    title: "设置",
    subtitle: "管理个人偏好和数据备份。",
  },
];

const defaultCategorySettings = {
  bill_categories: ["餐饮", "交通", "购物", "日用", "医疗", "娱乐", "学习", "住房", "工资", "其他"],
  task_categories: ["生活", "工作", "学习", "个人", "财务", "健康"],
};

const defaultBudgetSettings = {
  monthly_budget: 5000,
  currency: "CNY",
  warning_threshold_percent: 80,
};

const defaultTagSettings = {
  tags: ["开心", "轻松", "成长", "工作", "学习", "健康", "朋友", "家庭", "旅行"],
};

const profileStorageKey = "lifesnap_profile_settings";
const assistantSessionStorageKey = "lifesnap_assistant_session";
const knownAssistantToolIds = [
  "knowledge_search",
  "bill_candidate",
  "bill_analysis",
  "task_candidate",
  "diary_candidate",
  "diary_reflection",
  "attachment_bill_recognition",
];

const defaultProfileSettings = {
  displayName: "今天也要加油呀",
  signature: "记录生活，遇见更好的自己",
  avatarTone: "warm",
};

const initialAssistantSession = loadAssistantSession();

const state = {
  route: getRoute(),
  loading: true,
  saving: false,
  error: "",
  toast: "",
  modalOpen: false,
  billRangeOpen: false,
  billDetailsOpen: false,
  notificationOpen: false,
  editingBill: null,
  billDraft: null,
  deleteTarget: null,
  billRestoreTarget: null,
  taskDeleteTarget: null,
  taskRestoreTarget: null,
  editingTask: null,
  taskModalOpen: false,
  repeatTaskModalOpen: false,
  taskCalendarOpen: false,
  diaryModalOpen: false,
  diaryCalendarOpen: false,
  diaryDeleteTarget: null,
  diaryRestoreTarget: null,
  snoozeTarget: null,
  settingsConfirm: null,
  dataImportPreview: null,
  profileModalOpen: false,
  privacySettingsOpen: false,
  categorySettingsOpen: false,
  budgetSettingsOpen: false,
  tagSettingsOpen: false,
  diagnosticsOpen: false,
  diagnosticsLoading: false,
  integrationProbeLoading: false,
  diagnostics: null,
  integrationDiagnostics: null,
  integrationProbe: null,
  auditLogOpen: false,
  auditLogLoading: false,
  auditLog: null,
  recycleBinOpen: false,
  recycleBinLoading: false,
  recycleBin: {
    bills: [],
    tasks: [],
    diaries: [],
  },
  chatMessages: initialAssistantSession.chatMessages,
  chatDraft: initialAssistantSession.chatDraft,
  chatAttachments: [],
  chatCandidateEditor: null,
  activeAssistantToolId: initialAssistantSession.activeAssistantToolId,
  voiceListening: false,
  billFilters: {
    period: "month",
    year: String(new Date().getFullYear()),
    month: String(new Date().getMonth() + 1),
    start_date: "",
    end_date: "",
    category: "",
    transaction_type: "",
    q: "",
  },
  taskFilters: {
    view: "all",
    category: "",
    sort: "time",
    dateKey: todayDateKey(),
  },
  taskSortOpen: false,
  taskCalendarMonthKey: monthKeyFromDate(new Date()),
  taskCalendarLoading: false,
  taskCalendarTasks: [],
  taskListExpanded: false,
  taskListMeta: {
    total: 0,
    page: 1,
    page_size: 20,
    total_pages: 0,
  },
  diaryFilters: {
    period: "today",
  },
  diarySelectedDateKey: todayDateKey(),
  diaryCalendarMonthKey: monthKeyFromDate(new Date()),
  diaryDraft: null,
  diaryEntries: [],
  diaryOverview: null,
  diaryListMeta: {
    total: 0,
    page: 1,
    page_size: 100,
    total_pages: 0,
  },
  billListMeta: {
    total: 0,
    page: 1,
    page_size: 12,
    total_pages: 0,
  },
  bootstrap: null,
  billOverview: null,
  taskOverview: null,
  snapshotStatus: null,
  categorySettings: null,
  budgetSettings: null,
  tagSettings: null,
  bills: [],
  tasks: [],
  profile: loadProfileSettings(),
};

const app = document.querySelector("#app");
let toastDismissTimer;
let timedToast = "";

window.addEventListener("hashchange", () => {
  state.route = getRoute();
  render();
  window.scrollTo({ top: 0, behavior: "instant" });
});

document.addEventListener("click", (event) => {
  const pageButton = event.target.closest("[data-bill-page]");
  if (pageButton) {
    state.billListMeta.page = Number(pageButton.dataset.billPage);
    loadData();
    return;
  }
  if (event.target.closest("[data-bill-all-time]")) {
    state.billFilters = { ...state.billFilters, period: "all", year: "", month: "", start_date: "", end_date: "" };
    state.billListMeta.page = 1;
    loadData();
    return;
  }
  if (event.target.closest("[data-clear-bill-search]")) {
    state.billFilters.q = "";
    state.billListMeta.page = 1;
    loadData();
    return;
  }
  const routeButton = event.target.closest("[data-route]");
  if (routeButton) {
    window.location.hash = routeButton.dataset.route;
    return;
  }

  if (event.target.closest("[data-open-bill-modal]")) {
    state.billDetailsOpen = false;
    state.editingBill = null;
    state.billDraft = null;
    state.modalOpen = true;
    render();
    return;
  }

  if (event.target.closest("[data-open-task-modal]")) {
    state.editingTask = null;
    state.taskModalOpen = true;
    render();
    return;
  }

  if (event.target.closest("[data-snapshot-save]")) {
    saveSnapshot();
    return;
  }

  const diaryModalButton = event.target.closest("[data-diary-placeholder], [data-open-diary-modal]");
  if (diaryModalButton) {
    openDiaryModal(diaryModalButton.dataset.diaryDate || null);
    return;
  }

  if (event.target.closest("[data-voice-placeholder]")) {
    openAssistantPage("", { startVoice: true });
    return;
  }

  const chatExampleButton = event.target.closest("[data-chat-example]");
  if (chatExampleButton) {
    const draft = chatExampleButton.dataset.chatExample || "";
    state.activeAssistantToolId = inferAssistantToolFromMessage(draft);
    saveAssistantSession();
    openAssistantPage(draft);
    return;
  }

  const assistantToolButton = event.target.closest("[data-assistant-tool]");
  if (assistantToolButton) {
    startAssistantTool(assistantToolButton.dataset.assistantTool || "");
    return;
  }

  if (event.target.closest("[data-assistant-voice]")) {
    toggleVoiceInput();
    return;
  }

  if (event.target.closest("[data-chat-clear]")) {
    resetChatSession();
    return;
  }

  const removeChatAttachmentButton = event.target.closest("[data-remove-chat-attachment]");
  if (removeChatAttachmentButton) {
    removeChatAttachment(removeChatAttachmentButton.dataset.removeChatAttachment);
    return;
  }

  const chatEditButton = event.target.closest("[data-chat-edit]");
  if (chatEditButton) {
    openChatCandidateEditor(chatEditButton.dataset.candidateId);
    return;
  }

  if (event.target.closest("[data-close-chat-candidate-editor]")) {
    state.chatCandidateEditor = null;
    render();
    return;
  }

  const chatConfirmButton = event.target.closest("[data-chat-confirm]");
  if (chatConfirmButton) {
    confirmChatAction(chatConfirmButton.dataset.actionType, chatConfirmButton.dataset.candidateId);
    return;
  }

  const chatDiscardButton = event.target.closest("[data-chat-discard]");
  if (chatDiscardButton) {
    discardChatAction(chatDiscardButton.dataset.actionType, chatDiscardButton.dataset.candidateId);
    return;
  }

  if (event.target.closest("[data-bill-photo-placeholder]")) {
    app.querySelector("[data-bill-image-input]")?.click();
    return;
  }

  if (event.target.closest("[data-bill-filter-panel]")) {
    state.billRangeOpen = true;
    render();
    return;
  }

  const diaryPeriodButton = event.target.closest("[data-diary-period]");
  if (diaryPeriodButton) {
    state.diaryFilters.period = diaryPeriodButton.dataset.diaryPeriod || "today";
    render();
    return;
  }

  if (event.target.closest("[data-open-diary-calendar], [data-diary-calendar-placeholder]")) {
    openDiaryCalendar();
    return;
  }

  const diaryCalendarNavButton = event.target.closest("[data-diary-calendar-nav]");
  if (diaryCalendarNavButton) {
    shiftDiaryCalendarMonth(Number(diaryCalendarNavButton.dataset.diaryCalendarNav || 0));
    return;
  }

  const diaryDateButton = event.target.closest("[data-diary-date]");
  if (diaryDateButton) {
    selectDiaryDate(diaryDateButton.dataset.diaryDate);
    return;
  }

  if (event.target.closest("[data-diary-calendar-today]")) {
    selectDiaryToday();
    return;
  }

  if (event.target.closest("[data-diary-calendar-write]")) {
    openDiaryModal(state.diarySelectedDateKey || todayDateKey());
    return;
  }

  if (event.target.closest("[data-diary-calendar-done]")) {
    state.diaryCalendarOpen = false;
    render();
    return;
  }

  const diaryPhotoRemoveButton = event.target.closest("[data-diary-photo-remove]");
  if (diaryPhotoRemoveButton) {
    event.preventDefault();
    event.stopPropagation();
    removeDiaryImage(diaryPhotoRemoveButton.dataset.attachmentId);
    return;
  }

  if (event.target.closest("[data-diary-photo-placeholder]")) {
    app.querySelector("[data-diary-image-input]")?.click();
    return;
  }

  const diaryAiPromptButton = event.target.closest("[data-diary-ai-prompt]");
  if (diaryAiPromptButton) {
    openDiaryAssistantPrompt(diaryAiPromptButton.dataset.diaryAiPrompt || "");
    return;
  }

  if (event.target.closest("[data-profile-notification]")) {
    state.notificationOpen = true;
    render();
    return;
  }

  if (event.target.closest("[data-profile-preferences], [data-open-privacy-settings]")) {
    state.privacySettingsOpen = true;
    render();
    return;
  }

  if (event.target.closest("[data-open-category-settings]")) {
    state.categorySettingsOpen = true;
    render();
    return;
  }

  if (event.target.closest("[data-open-budget-settings]")) {
    state.budgetSettingsOpen = true;
    render();
    return;
  }

  if (event.target.closest("[data-open-tag-settings]")) {
    state.tagSettingsOpen = true;
    render();
    return;
  }

  if (event.target.closest("[data-profile-placeholder]")) {
    state.profileModalOpen = true;
    render();
    return;
  }

  const taskViewButton = event.target.closest("[data-task-view]");
  if (taskViewButton) {
    state.taskFilters.view = taskViewButton.dataset.taskView || "today";
    state.taskListExpanded = false;
    state.taskListMeta.page = 1;
    loadData();
    return;
  }

  const taskCategoryButton = event.target.closest("[data-task-category]");
  if (taskCategoryButton) {
    state.taskFilters.category = taskCategoryButton.dataset.taskCategory || "";
    state.taskListExpanded = false;
    state.taskListMeta.page = 1;
    loadData();
    return;
  }

  if (event.target.closest("[data-open-task-calendar]")) {
    openTaskCalendar();
    return;
  }

  const taskCalendarNavButton = event.target.closest("[data-task-calendar-nav]");
  if (taskCalendarNavButton) {
    shiftTaskCalendarMonth(Number(taskCalendarNavButton.dataset.taskCalendarNav || 0));
    return;
  }

  const taskDateButton = event.target.closest("[data-task-date]");
  if (taskDateButton) {
    selectTaskDate(taskDateButton.dataset.taskDate);
    return;
  }

  if (event.target.closest("[data-task-calendar-today]")) {
    selectTaskToday();
    return;
  }

  if (event.target.closest("[data-task-calendar-done]")) {
    state.taskCalendarOpen = false;
    render();
    return;
  }

  if (event.target.closest("[data-open-task-sort]")) {
    state.taskSortOpen = true;
    render();
    return;
  }

  if (event.target.closest("[data-close-task-sort]")) {
    state.taskSortOpen = false;
    render();
    return;
  }

  const taskSortButton = event.target.closest("[data-task-sort]");
  if (taskSortButton) {
    state.taskFilters.sort = taskSortButton.dataset.taskSort || "time";
    state.taskSortOpen = false;
    render();
    return;
  }

  if (event.target.closest("[data-open-repeat-task-modal]")) {
    state.repeatTaskModalOpen = true;
    render();
    return;
  }

  if (event.target.closest("[data-view-all-tasks]")) {
    state.taskListExpanded = true;
    render();
    return;
  }

  const billPeriodButton = event.target.closest("[data-bill-period]");
  if (billPeriodButton) {
    const period = billPeriodButton.dataset.billPeriod || "month";
    if (period === "month") {
      applyBillPeriodMonth();
    } else if (period === "week") {
      applyBillPeriodWeek();
    } else {
      state.billRangeOpen = true;
      render();
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
    state.billDetailsOpen = false;    state.editingBill = [...state.bills, ...(state.bootstrap?.dashboard?.recent_bills ?? [])].find((bill) => bill.id === editButton.dataset.editBill) ?? null;
    state.billDraft = null;
    state.modalOpen = Boolean(state.editingBill);
    render();
    return;
  }

  const deleteButton = event.target.closest("[data-delete-bill]");
  if (deleteButton) {
    state.deleteTarget = state.editingBill ?? state.bills.find((bill) => bill.id === deleteButton.dataset.deleteBill) ?? null;
    state.modalOpen = false;
    render();
    return;
  }

  const taskDeleteButton = event.target.closest("[data-delete-task]");
  if (taskDeleteButton) {
    state.taskDeleteTarget = findTaskById(taskDeleteButton.dataset.deleteTask);
    render();
    return;
  }

  const taskEditButton = event.target.closest("[data-edit-task]");
  if (taskEditButton) {
    state.editingTask = findTaskById(taskEditButton.dataset.editTask);
    state.notificationOpen = false;
    state.taskModalOpen = Boolean(state.editingTask);
    render();
    return;
  }

  const diaryDeleteButton = event.target.closest("[data-delete-diary]");
  if (diaryDeleteButton) {
    state.diaryDeleteTarget = state.diaryEntries.find(
      (entry) => entry.dateKey === diaryDeleteButton.dataset.deleteDiary,
    ) ?? null;
    state.diaryModalOpen = false;
    render();
    return;
  }

  if (event.target.closest("[data-close-modal]")) {
    if (state.saving) return;
    state.modalOpen = false;
    state.billRangeOpen = false;
    state.notificationOpen = false;
    state.editingBill = null;
    state.billDraft = null;
    state.taskDeleteTarget = null;
    state.taskSortOpen = false;
    state.taskCalendarOpen = false;
    state.taskModalOpen = false;
    state.repeatTaskModalOpen = false;
    state.editingTask = null;
    state.diaryModalOpen = false;
    state.diaryCalendarOpen = false;
    state.diaryDeleteTarget = null;
    state.snoozeTarget = null;
    state.settingsConfirm = null;
    state.dataImportPreview = null;
    state.profileModalOpen = false;
    state.privacySettingsOpen = false;
    state.categorySettingsOpen = false;
    state.budgetSettingsOpen = false;
    state.tagSettingsOpen = false;
    state.diagnosticsOpen = false;
    state.auditLogOpen = false;
    state.recycleBinOpen = false;
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
    state.snoozeTarget = findTaskById(snoozeTaskButton.dataset.snoozeTask);
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

  if (event.target.closest("[data-restore-bill]")) {
    restoreDeletedBill();
    return;
  }

  if (event.target.closest("[data-cancel-task-delete]")) {
    state.taskDeleteTarget = null;
    render();
    return;
  }

  if (event.target.closest("[data-confirm-task-delete]")) {
    deleteTask();
    return;
  }

  if (event.target.closest("[data-cancel-diary-delete]")) {
    state.diaryDeleteTarget = null;
    render();
    return;
  }

  if (event.target.closest("[data-confirm-diary-delete]")) {
    deleteDiary();
    return;
  }

  if (event.target.closest("[data-restore-diary]")) {
    restoreDeletedDiary();
    return;
  }

  if (event.target.closest("[data-restore-task]")) {
    restoreDeletedTask();
    return;
  }

  if (event.target.closest("[data-reset-bill-filters]")) {
    state.billFilters = defaultBillFilters();
    state.billListMeta.page = 1;
    state.billRangeOpen = false;
    loadData();
    return;
  }

  if (event.target.closest("[data-export-json]")) {
    exportJson();
    return;
  }

  if (event.target.closest("[data-import-json]")) {
    if (!state.saving) {
      app.querySelector("[data-import-json-input]")?.click();
    }
    return;
  }

  if (event.target.closest("[data-open-recycle-bin]")) {
    openRecycleBin();
    return;
  }

  if (event.target.closest("[data-close-recycle-bin]")) {
    state.recycleBinOpen = false;
    render();
    return;
  }

  if (event.target.closest("[data-refresh-recycle-bin]")) {
    refreshRecycleBin();
    return;
  }

  const recycleRestoreButton = event.target.closest("[data-restore-recycle]");
  if (recycleRestoreButton) {
    restoreRecycleItem(
      recycleRestoreButton.dataset.restoreRecycle,
      recycleRestoreButton.dataset.recycleId,
    );
    return;
  }

  const settingsActionButton = event.target.closest("[data-settings-action]");
  if (settingsActionButton) {
    openSettingsConfirm(settingsActionButton.dataset.settingsAction);
    return;
  }

  if (event.target.closest("[data-cancel-data-import]")) {
    state.dataImportPreview = null;
    render();
    return;
  }

  if (event.target.closest("[data-confirm-data-import]")) {
    importPreviewedData();
    return;
  }

  if (event.target.closest("[data-close-privacy-settings]")) {
    state.privacySettingsOpen = false;
    render();
    return;
  }

  if (event.target.closest("[data-close-category-settings]")) {
    state.categorySettingsOpen = false;
    render();
    return;
  }

  if (event.target.closest("[data-close-budget-settings]")) {
    state.budgetSettingsOpen = false;
    render();
    return;
  }

  if (event.target.closest("[data-close-tag-settings]")) {
    state.tagSettingsOpen = false;
    render();
    return;
  }

  if (event.target.closest("[data-close-profile-settings]")) {
    state.profileModalOpen = false;
    render();
    return;
  }

  if (event.target.closest("[data-open-diagnostics]")) {
    openDiagnostics();
    return;
  }

  if (event.target.closest("[data-close-diagnostics]")) {
    state.diagnosticsOpen = false;
    render();
    return;
  }

  if (event.target.closest("[data-refresh-diagnostics]")) {
    refreshDiagnostics();
    return;
  }

  if (event.target.closest("[data-run-integration-probe]")) {
    runIntegrationProbe();
    return;
  }

  const copyMockCommandButton = event.target.closest("[data-copy-mock-command]");
  if (copyMockCommandButton) {
    copyIntegrationGuideText(copyMockCommandButton.dataset.copyMockCommand);
    return;
  }

  const copyIntegrationGuideButton = event.target.closest("[data-copy-integration-guide]");
  if (copyIntegrationGuideButton) {
    event.preventDefault();
    copyIntegrationGuideText(copyIntegrationGuideButton.dataset.copyIntegrationGuide);
    return;
  }

  if (event.target.closest("[data-open-audit-log]")) {
    openAuditLog();
    return;
  }

  if (event.target.closest("[data-close-audit-log]")) {
    state.auditLogOpen = false;
    render();
    return;
  }

  if (event.target.closest("[data-refresh-audit-log]")) {
    refreshAuditLog();
    return;
  }

  const privacyToggleButton = event.target.closest("[data-privacy-toggle]");
  if (privacyToggleButton) {
    updatePrivacySetting(privacyToggleButton.dataset.privacyToggle);
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
  if (event.key === "Escape" && state.saving) return;
  if (event.key === "Tab") {
    const dialogs = app.querySelectorAll('[role="dialog"]');
    const dialog = dialogs[dialogs.length - 1];
    const focusable = dialog ? [...dialog.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex="0"]')].filter(node => node.getClientRects().length) : [];
    if (focusable.length && ((event.shiftKey && document.activeElement === focusable[0]) || (!event.shiftKey && document.activeElement === focusable[focusable.length - 1]))) {
      event.preventDefault();
      focusable[event.shiftKey ? focusable.length - 1 : 0].focus();
    }
  }
  if (
    event.target.matches("[data-chat-input]")
    && event.key === "Enter"
    && !event.shiftKey
    && !event.isComposing
  ) {
    event.preventDefault();
    event.target.closest("form")?.requestSubmit();
    return;
  }

  if (
    event.key === "Escape"
    && (
      state.modalOpen
      || state.billRangeOpen
      || state.notificationOpen
      || state.deleteTarget
      || state.taskDeleteTarget
      || state.taskSortOpen
      || state.taskCalendarOpen
      || state.taskModalOpen
      || state.repeatTaskModalOpen
      || state.diaryModalOpen
      || state.diaryCalendarOpen
      || state.diaryDeleteTarget
      || state.snoozeTarget
      || state.settingsConfirm
      || state.dataImportPreview
      || state.profileModalOpen
      || state.privacySettingsOpen
      || state.categorySettingsOpen
      || state.budgetSettingsOpen
      || state.tagSettingsOpen
      || state.diagnosticsOpen
      || state.auditLogOpen
      || state.recycleBinOpen
      || state.chatCandidateEditor
    )
  ) {
    state.modalOpen = false;
    state.billRangeOpen = false;
    state.notificationOpen = false;
    state.editingBill = null;
    state.billDraft = null;
    state.deleteTarget = null;
    state.taskDeleteTarget = null;
    state.taskSortOpen = false;
    state.taskCalendarOpen = false;
    state.taskModalOpen = false;
    state.repeatTaskModalOpen = false;
    state.editingTask = null;
    state.diaryModalOpen = false;
    state.diaryCalendarOpen = false;
    state.diaryDeleteTarget = null;
    state.snoozeTarget = null;
    state.settingsConfirm = null;
    state.dataImportPreview = null;
    state.profileModalOpen = false;
    state.privacySettingsOpen = false;
    state.categorySettingsOpen = false;
    state.budgetSettingsOpen = false;
    state.tagSettingsOpen = false;
    state.diagnosticsOpen = false;
    state.auditLogOpen = false;
    state.recycleBinOpen = false;
    state.chatCandidateEditor = null;
    render();
  }
});

document.addEventListener("input", (event) => {
  const billForm = event.target.closest("[data-bill-form]");
  if (billForm && !state.saving) {
    const draft = Object.fromEntries(new FormData(billForm));
    state.billDraft = { ...(state.billDraft ?? state.editingBill ?? {}), ...draft };
    state.billDetailsOpen = Boolean(billForm.querySelector("[data-bill-details]")?.open);
  }
  if (event.target.matches("[data-chat-input]")) {
    state.chatDraft = event.target.value;
    saveAssistantSession();
  }
});

document.addEventListener("change", async (event) => {
  if (event.target.matches("[data-chat-image-input]")) {
    await addChatImages(event.target.files);
    event.target.value = "";
  }

  if (event.target.matches("[data-bill-image-input]")) {
    await importBillImage(event.target.files?.[0]);
    event.target.value = "";
  }

  if (event.target.matches("[data-diary-image-input]")) {
    await uploadDiaryImages(event.target.files);
    event.target.value = "";
  }

  if (event.target.matches("[data-import-json-input]")) {
    await previewDataImport(event.target.files?.[0]);
    event.target.value = "";
  }
});

document.addEventListener("submit", async (event) => {
  if (event.target.matches("[data-bill-search-form]")) {
    event.preventDefault();
    state.billFilters.q = String(new FormData(event.target).get("q") || "").trim();
    state.billListMeta.page = 1;
    loadData();
    return;
  }
  if (event.target.matches("[data-bill-filter]")) {
    event.preventDefault();
    applyBillFilters(new FormData(event.target));
    return;
  }

  if (event.target.matches("[data-bill-range-form]")) {
    event.preventDefault();
    applyBillRangeFilters(new FormData(event.target));
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

  if (event.target.matches("[data-repeat-task-form]")) {
    event.preventDefault();
    await submitRepeatTask(new FormData(event.target));
    return;
  }

  if (event.target.matches("[data-diary-form]")) {
    event.preventDefault();
    await submitDiary(new FormData(event.target));
    return;
  }

  if (event.target.matches("[data-chat-form]")) {
    event.preventDefault();
    await submitChatMessage(new FormData(event.target));
    return;
  }

  if (event.target.matches("[data-chat-candidate-editor-form]")) {
    event.preventDefault();
    await submitChatCandidateEdit(new FormData(event.target));
    return;
  }

  if (event.target.matches("[data-profile-form]")) {
    event.preventDefault();
    submitProfileSettings(new FormData(event.target));
    return;
  }

  if (event.target.matches("[data-category-settings-form]")) {
    event.preventDefault();
    await submitCategorySettings(new FormData(event.target));
    return;
  }

  if (event.target.matches("[data-budget-settings-form]")) {
    event.preventDefault();
    await submitBudgetSettings(new FormData(event.target));
    return;
  }

  if (event.target.matches("[data-tag-settings-form]")) {
    event.preventDefault();
    await submitTagSettings(new FormData(event.target));
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
    const [
      bootstrap,
      billOverview,
      billList,
      taskList,
      taskOverview,
      diaryList,
      diaryOverview,
      snapshotStatus,
      categorySettings,
      budgetSettings,
      tagSettings,
    ] = await Promise.all([
      api("/app/bootstrap?recent_bill_limit=6&candidate_limit=5"),
      api("/bills/statistics/overview?trend_months=6&top_merchant_limit=6"),
      api(buildBillListPath()),
      api(buildTaskListPath()),
      api("/tasks/statistics/overview?upcoming_days=7&item_limit=10"),
      api(buildDiaryListPath()),
      api("/diaries/statistics/overview"),
      api("/data/snapshot/status"),
      api("/settings/categories"),
      api("/settings/budget"),
      api("/settings/tags"),
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
    state.taskListMeta = {
      total: taskList.total ?? 0,
      page: taskList.page ?? 1,
      page_size: taskList.page_size ?? 20,
      total_pages: taskList.total_pages ?? 0,
    };
    state.taskOverview = taskOverview;
    state.diaryEntries = normalizeDiaryEntries(diaryList.items ?? []);
    state.diaryListMeta = {
      total: diaryList.total ?? 0,
      page: diaryList.page ?? 1,
      page_size: diaryList.page_size ?? 100,
      total_pages: diaryList.total_pages ?? 0,
    };
    state.diaryOverview = diaryOverview;
    state.diaryDraft = null;
    state.snapshotStatus = snapshotStatus;
    state.categorySettings = categorySettings;
    state.budgetSettings = budgetSettings;
    state.tagSettings = tagSettings;
  } catch (error) {
    state.error = error.message || "后端连接失败";
  } finally {
    state.loading = false;
    render();
  }
}

async function submitBill(formData) {
  if (state.saving) return;
  const amount = Number(formData.get("amount"));
  const paidAt = formData.get("paid_at");
  const editingBill = state.editingBill;
  const isEditing = Boolean(editingBill?.id);
  const defaultBillCategory = "其他";
  const payload = {
    amount,
    merchant: String(formData.get("merchant") || "").trim() || null,
    category: String(formData.get("category") || defaultBillCategory).trim(),
    payment_method: String(formData.get("payment_method") || "").trim() || null,
    transaction_type: formData.get("transaction_type"),
    paid_at: paidAt ? new Date(paidAt).toISOString() : new Date().toISOString(),
    note: String(formData.get("note") || "").trim() || null,
  };
  if (!isEditing) {
    payload.source = state.billDraft?.source || "manual";
  }

  const requestPayload = JSON.stringify(payload);
  const requestKey = state.billDraft?.request_payload === requestPayload ? state.billDraft.request_key : crypto.randomUUID();
  state.billDraft = { ...state.billDraft, ...payload, request_key: requestKey, request_payload: requestPayload };
  state.billDetailsOpen = Boolean(app.querySelector("[data-bill-details]")?.open);
  state.billRestoreTarget = null;
  state.saving = true;
  render();
  try {
    await api(isEditing ? `/bills/${editingBill.id}` : "/bills", {
      method: isEditing ? "PATCH" : "POST",
      headers: {
        "Content-Type": "application/json",
        ...(isEditing ? {} : { "Idempotency-Key": `web-bill-${state.billDraft.request_key}` }),
      },
      body: JSON.stringify(payload),
    });
    state.modalOpen = false;
    state.editingBill = null;
    state.billDraft = null;
    state.toast = isEditing ? "账单已更新" : "账单已保存";
    await loadData();
    scheduleToastDismissal();
  } catch (error) {
    state.toast = error.message || "保存失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

async function importBillImage(file) {
  if (!file) {
    return;
  }
  if (!file.type.startsWith("image/")) {
    showToast("请选择支付截图或票据图片。");
    return;
  }

  state.billRestoreTarget = null;
  state.saving = true;
  render();
  try {
    const payload = new FormData();
    payload.append("file", file);
    payload.append("source", "album");
    const uploaded = await api("/attachments/upload", {
      method: "POST",
      body: payload,
    });
    const result = await api(`/attachments/${uploaded.id}/recognize-and-parse-bill`, {
      method: "POST",
    });

    state.editingBill = null;
    if (result.status === "candidate_created" && result.candidate) {
      state.billDraft = billDraftFromCandidate(result.candidate, uploaded);
      state.toast = "已读出账单，请核对金额后保存";
    } else {
      state.billDraft = fallbackBillDraftFromAttachment(uploaded, result);
      state.toast = "暂时没能读出图片内容，请填写金额和商家";
    }
    state.billDetailsOpen = false;
    state.modalOpen = true;
  } catch (error) {
    state.toast = error.message || "图片导入失败";
  } finally {
    state.saving = false;
    render();
  }
}

function billDraftFromCandidate(candidate, attachment) {
  const data = candidate.data ?? {};
  return {
    amount: data.amount ?? "",
    merchant: data.merchant || "",
    category: data.category || "其他",
    payment_method: data.payment_method || "",
    transaction_type: data.transaction_type || "expense",
    paid_at: data.paid_at || new Date().toISOString(),
    note: billDraftNote(candidate, attachment),
    source: "album",
    candidate_id: candidate.candidate_id,
    confidence: candidate.confidence,
    warnings: candidate.warnings ?? [],
  };
}

function fallbackBillDraftFromAttachment(attachment, result) {
  return { amount: "", merchant: "", category: "其他", payment_method: "", transaction_type: "expense", paid_at: new Date().toISOString(), note: "", source: "album", attachment_id: attachment.id, warnings: result?.warnings ?? [], needs_manual_entry: true };
}

function billDraftNote(candidate, attachment) {
  return candidate.data?.note || "";
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
    state.billRestoreTarget = {
      id: bill.id,
      merchant: bill.merchant,
      amount: bill.amount,
    };
    state.toast = "账单已删除";
    await loadData();
    window.setTimeout(() => {
      if (
        !state.saving
        && state.billRestoreTarget?.id === bill.id
        && state.toast === "账单已删除"
      ) {
        state.billRestoreTarget = null;
        state.toast = "";
        app.querySelector(".toast")?.remove();
      }
    }, 2200);
  } catch (error) {
    state.billRestoreTarget = null;
    state.toast = error.message || "删除失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

async function restoreDeletedBill() {
  if (!state.billRestoreTarget?.id || state.saving) {
    return;
  }

  const bill = state.billRestoreTarget;
  state.saving = true;
  render();
  try {
    await api(`/bills/${bill.id}/restore`, {
      method: "POST",
      headers: {
        "Idempotency-Key": `web-bill-restore-${bill.id}-${crypto.randomUUID()}`,
      },
    });
    state.billRestoreTarget = null;
    state.toast = "账单已恢复";
    await loadData();
    window.setTimeout(() => {
      if (state.toast === "账单已恢复") {
        state.toast = "";
        app.querySelector(".toast")?.remove();
      }
    }, 2200);
  } catch (error) {
    state.billRestoreTarget = null;
    state.toast = error.message || "账单恢复失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

async function deleteDiary() {
  if (!state.diaryDeleteTarget?.id) {
    return;
  }

  const diary = state.diaryDeleteTarget;
  state.saving = true;
  render();
  try {
    await api(`/diaries/${diary.id}`, { method: "DELETE" });
    state.diaryDeleteTarget = null;
    state.diaryModalOpen = false;
    state.diaryDraft = null;
    state.diaryRestoreTarget = {
      id: diary.id,
      dateKey: diary.dateKey,
      title: diary.title,
    };
    state.toast = "日记已删除";
    await loadData();
    window.setTimeout(() => {
      if (
        !state.saving
        && state.diaryRestoreTarget?.id === diary.id
        && state.toast === "日记已删除"
      ) {
        state.diaryRestoreTarget = null;
        state.toast = "";
        app.querySelector(".toast")?.remove();
      }
    }, 2200);
  } catch (error) {
    state.diaryRestoreTarget = null;
    state.toast = error.message || "日记删除失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

async function deleteTask() {
  if (!state.taskDeleteTarget?.id) {
    return;
  }

  const task = state.taskDeleteTarget;
  state.saving = true;
  render();
  try {
    await api(`/tasks/${task.id}`, { method: "DELETE" });
    state.taskDeleteTarget = null;
    state.taskRestoreTarget = {
      id: task.id,
      title: task.title,
    };
    state.toast = "待办已删除";
    await loadData();
    window.setTimeout(() => {
      if (
        !state.saving
        && state.taskRestoreTarget?.id === task.id
        && state.toast === "待办已删除"
      ) {
        state.taskRestoreTarget = null;
        state.toast = "";
        app.querySelector(".toast")?.remove();
      }
    }, 2200);
  } catch (error) {
    state.taskRestoreTarget = null;
    state.toast = error.message || "待办删除失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

async function restoreDeletedDiary() {
  if (!state.diaryRestoreTarget?.id || state.saving) {
    return;
  }

  const diary = state.diaryRestoreTarget;
  state.saving = true;
  render();
  try {
    const restored = await api(`/diaries/${diary.id}/restore`, {
      method: "POST",
      headers: {
        "Idempotency-Key": `web-diary-restore-${diary.id}-${crypto.randomUUID()}`,
      },
    });
    state.diaryRestoreTarget = null;
    state.diarySelectedDateKey = restored.entry_date || diary.dateKey || todayDateKey();
    state.diaryCalendarMonthKey = monthKeyFromDate(dateFromDateKey(state.diarySelectedDateKey));
    state.toast = "日记已恢复";
    await loadData();
    window.setTimeout(() => {
      if (state.toast === "日记已恢复") {
        state.toast = "";
        app.querySelector(".toast")?.remove();
      }
    }, 2200);
  } catch (error) {
    state.diaryRestoreTarget = null;
    state.toast = error.message || "日记恢复失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

async function restoreDeletedTask() {
  if (!state.taskRestoreTarget?.id || state.saving) {
    return;
  }

  const task = state.taskRestoreTarget;
  state.saving = true;
  render();
  try {
    await api(`/tasks/${task.id}/restore`, {
      method: "POST",
      headers: {
        "Idempotency-Key": `web-task-restore-${task.id}-${crypto.randomUUID()}`,
      },
    });
    state.taskRestoreTarget = null;
    state.toast = "待办已恢复";
    await loadData();
    window.setTimeout(() => {
      if (state.toast === "待办已恢复") {
        state.toast = "";
        app.querySelector(".toast")?.remove();
      }
    }, 2200);
  } catch (error) {
    state.taskRestoreTarget = null;
    state.toast = error.message || "待办恢复失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

async function openRecycleBin() {
  if (state.saving) {
    return;
  }
  state.recycleBinOpen = true;
  state.recycleBin = emptyRecycleBin();
  await refreshRecycleBin();
}

async function refreshRecycleBin() {
  state.recycleBinLoading = true;
  render();
  try {
    const [billList, taskList, diaryList] = await Promise.all([
      api("/bills?deleted_only=true&page_size=50"),
      api("/tasks?deleted_only=true&page_size=50"),
      api("/diaries?deleted_only=true&page_size=50"),
    ]);
    state.recycleBin = {
      bills: billList.items ?? [],
      tasks: taskList.items ?? [],
      diaries: diaryList.items ?? [],
    };
  } catch (error) {
    state.toast = error.message || "回收站加载失败";
  } finally {
    state.recycleBinLoading = false;
    render();
  }
}

async function restoreRecycleItem(type, id) {
  if (!id || state.saving) {
    return;
  }

  const config = recycleRestoreConfig(type);
  if (!config) {
    return;
  }

  state.saving = true;
  render();
  try {
    const restored = await api(`/${config.collection}/${id}/restore`, {
      method: "POST",
      headers: {
        "Idempotency-Key": `web-recycle-${type}-${id}-${crypto.randomUUID()}`,
      },
    });
    if (type === "diary") {
      state.diarySelectedDateKey = restored.entry_date || todayDateKey();
      state.diaryCalendarMonthKey = monthKeyFromDate(dateFromDateKey(state.diarySelectedDateKey));
    }
    state.toast = `${config.label}已恢复`;
    await loadData();
    await refreshRecycleBin();
  } catch (error) {
    state.toast = error.message || `${config.label}恢复失败`;
    render();
  } finally {
    state.saving = false;
    render();
  }
}

function emptyRecycleBin() {
  return {
    bills: [],
    tasks: [],
    diaries: [],
  };
}

function recycleRestoreConfig(type) {
  return {
    bill: { collection: "bills", label: "账单" },
    task: { collection: "tasks", label: "待办" },
    diary: { collection: "diaries", label: "日记" },
  }[type] ?? null;
}

async function submitTask(formData) {
  const editingTask = state.editingTask;
  const isEditing = Boolean(editingTask?.id);
  const taskType = String(formData.get("task_type") || "todo");
  const dueAt = formData.get("due_at");
  const remindAt = formData.get("remind_at");
  const defaultTaskCategory = getCategorySettings().task_categories[0] || "生活";
  const payload = {
    title: String(formData.get("title") || "").trim(),
    description: String(formData.get("description") || "").trim() || null,
    category: String(formData.get("category") || defaultTaskCategory).trim(),
    task_type: taskType,
    due_at: taskType === "todo" && dueAt ? new Date(dueAt).toISOString() : null,
    remind_at: taskType === "reminder" && remindAt ? new Date(remindAt).toISOString() : null,
    priority: formData.get("priority"),
  };

  state.taskRestoreTarget = null;
  state.saving = true;
  render();
  try {
    await api(isEditing ? `/tasks/${editingTask.id}` : "/tasks", {
      method: isEditing ? "PATCH" : "POST",
      headers: {
        "Content-Type": "application/json",
        ...(isEditing ? {} : { "Idempotency-Key": `web-task-${crypto.randomUUID()}` }),
      },
      body: JSON.stringify(payload),
    });
    state.taskModalOpen = false;
    state.editingTask = null;
    state.toast = isEditing ? "待办已更新" : "待办已创建";
    await loadData();
    scheduleToastDismissal();
  } catch (error) {
    state.toast = error.message || "创建失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

async function submitRepeatTask(formData) {
  const title = String(formData.get("title") || "").trim();
  const defaultTaskCategory = getCategorySettings().task_categories[0] || "生活";
  const category = String(formData.get("category") || defaultTaskCategory).trim() || defaultTaskCategory;
  const description = String(formData.get("description") || "").trim();
  const frequency = String(formData.get("frequency") || "weekly");
  const priority = String(formData.get("priority") || "medium");
  const startAtValue = String(formData.get("start_at") || "");
  const startAt = startAtValue ? new Date(startAtValue) : null;
  const count = clampRepeatCount(Number(formData.get("count") || 0));

  if (!title) {
    showToast("请先填写重复提醒标题。");
    return;
  }
  if (!startAt || Number.isNaN(startAt.getTime())) {
    showToast("请选择有效的首次提醒时间。");
    return;
  }

  const payloads = buildRepeatReminderPayloads({
    title,
    category,
    description,
    frequency,
    priority,
    startAt,
    count,
  });
  let createdCount = 0;

  state.taskRestoreTarget = null;
  state.repeatTaskModalOpen = true;
  state.saving = true;
  render();
  try {
    for (const [index, payload] of payloads.entries()) {
      await api("/tasks", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": `web-repeat-task-${index}-${crypto.randomUUID()}`,
        },
        body: JSON.stringify(payload),
      });
      createdCount += 1;
    }
    state.repeatTaskModalOpen = false;
    state.toast = `已创建 ${createdCount} 条重复提醒`;
    await loadData();
    scheduleToastDismissal();
  } catch (error) {
    if (createdCount) {
      state.toast = `已创建 ${createdCount} 条，后续创建失败：${error.message || "请稍后重试"}`;
      await loadData();
    } else {
      state.toast = error.message || "重复提醒创建失败";
      render();
    }
  } finally {
    state.saving = false;
    render();
  }
}

function buildRepeatReminderPayloads({
  title,
  category,
  description,
  frequency,
  priority,
  startAt,
  count,
}) {
  return Array.from({ length: count }, (_, index) => {
    const remindAt = addRepeatInterval(startAt, frequency, index);
    const noteParts = [
      description,
      `重复提醒：${repeatFrequencyLabel(frequency)}，第 ${index + 1}/${count} 次。`,
    ].filter(Boolean);
    return {
      title,
      description: noteParts.join("\n"),
      category,
      task_type: "reminder",
      due_at: null,
      remind_at: remindAt.toISOString(),
      priority,
      source: "manual",
    };
  });
}

function addRepeatInterval(startAt, frequency, index) {
  const next = new Date(startAt);
  if (frequency === "daily") {
    next.setDate(startAt.getDate() + index);
  } else if (frequency === "biweekly") {
    next.setDate(startAt.getDate() + index * 14);
  } else if (frequency === "monthly") {
    next.setMonth(startAt.getMonth() + index);
  } else {
    next.setDate(startAt.getDate() + index * 7);
  }
  return next;
}

function clampRepeatCount(value) {
  if (!Number.isFinite(value)) {
    return 2;
  }
  return Math.max(2, Math.min(30, Math.round(value)));
}

function repeatFrequencyLabel(value) {
  return {
    daily: "每天",
    weekly: "每周",
    biweekly: "每两周",
    monthly: "每月",
  }[value] ?? "每周";
}

async function submitDiary(formData) {
  const dateKey = state.diarySelectedDateKey || todayDateKey();
  const content = String(formData.get("content") || "").trim();
  const title = String(formData.get("title") || "").trim() || `${diaryDateLabel(dateKey)}的日记`;
  const hadEntry = Boolean(diaryEntryForDate(dateKey)?.id);
  if (!content) {
    showToast("请先写一点日记内容。");
    return;
  }

  const payload = {
    entry_date: dateKey,
    title,
    content,
    mood: String(formData.get("mood") || "happy"),
    weather: String(formData.get("weather") || "").trim() || null,
    source: "manual",
    attachment_ids: diaryAttachmentIdsForDate(dateKey),
    tags: parseLabelInput(formData.get("tags"), 20),
  };

  state.diaryRestoreTarget = null;
  state.saving = true;
  render();
  try {
    const saved = await api(`/diaries/by-date/${dateKey}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.diaryEntries = upsertDiaryEntry(state.diaryEntries, normalizeDiaryEntry(saved));
    state.diaryModalOpen = false;
    state.diaryDraft = null;
    state.toast = hadEntry ? "日记已更新" : "日记已保存";
    await loadData();
    scheduleToastDismissal();
  } catch (error) {
    state.toast = error.message || "日记保存失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

async function uploadDiaryImages(fileList) {
  const files = Array.from(fileList || []).filter((file) => file.type.startsWith("image/"));
  if (!files.length) {
    showToast("请选择日记图片。");
    return;
  }

  const dateKey = state.diarySelectedDateKey || todayDateKey();
  const existing = diaryEntryForDate(dateKey);
  const currentAttachmentIds = diaryAttachmentIdsForDate(dateKey);

  state.diaryRestoreTarget = null;
  state.saving = true;
  render();
  try {
    const uploadedIds = [];
    for (const file of files) {
      const payload = new FormData();
      payload.append("file", file);
      payload.append("source", "album");
      payload.append("save_original", "true");
      const uploaded = await api("/attachments/upload", {
        method: "POST",
        body: payload,
      });
      uploadedIds.push(uploaded.id);
    }

    const attachmentIds = uniqueValues([...currentAttachmentIds, ...uploadedIds]);
    const saved = await api(`/diaries/by-date/${dateKey}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        entry_date: dateKey,
        title: existing?.title || `${diaryDateLabel(dateKey)}的图片日记`,
        content: existing?.content || `保存了 ${files.length} 张生活片段。`,
        mood: existing?.mood || "happy",
        weather: existing?.weather || null,
        source: existing?.source || "manual",
        attachment_ids: attachmentIds,
      }),
    });

    state.diaryEntries = upsertDiaryEntry(state.diaryEntries, normalizeDiaryEntry(saved));
    state.toast = `已添加 ${uploadedIds.length} 张日记图片`;
    await loadData();
    scheduleToastDismissal();
  } catch (error) {
    state.toast = error.message || "日记图片上传失败";
  } finally {
    state.saving = false;
    render();
  }
}

async function removeDiaryImage(attachmentId) {
  if (!attachmentId || state.saving) {
    return;
  }

  const dateKey = state.diarySelectedDateKey || todayDateKey();
  const existing = diaryEntryForDate(dateKey);
  const remainingAttachmentIds = diaryAttachmentIdsForDate(dateKey).filter((id) => id !== String(attachmentId));
  const isReferencedElsewhere = isAttachmentReferencedOutsideDiaryDate(attachmentId, dateKey);

  state.diaryRestoreTarget = null;
  state.saving = true;
  render();
  try {
    if (existing) {
      const saved = await api(`/diaries/by-date/${dateKey}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entry_date: dateKey,
          title: existing.title || `${diaryDateLabel(dateKey)}的日记`,
          content: existing.content || "这一天的图片已经调整，可以继续记录新的生活片段。",
          mood: existing.mood || "happy",
          weather: existing.weather || null,
          source: existing.source || "manual",
          attachment_ids: remainingAttachmentIds,
        }),
      });
      state.diaryEntries = upsertDiaryEntry(state.diaryEntries, normalizeDiaryEntry(saved));
    }

    let cleanupFailed = false;
    if (!isReferencedElsewhere) {
      try {
        await api(`/attachments/${encodeURIComponent(attachmentId)}`, { method: "DELETE" });
      } catch {
        cleanupFailed = true;
      }
    }

    state.toast = cleanupFailed ? "图片已移除，附件清理稍后重试" : "日记图片已移除";
    await loadData();
    scheduleToastDismissal();
  } catch (error) {
    state.toast = error.message || "图片移除失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

function openDiaryModal(dateKey = null) {
  const resolvedDateKey = dateKey === "today" ? todayDateKey() : dateKey;
  if (resolvedDateKey) {
    state.diarySelectedDateKey = resolvedDateKey;
    state.diaryCalendarMonthKey = monthKeyFromDate(dateFromDateKey(resolvedDateKey));
  }
  state.diaryCalendarOpen = false;
  state.diaryModalOpen = true;
  render();
}

function isAttachmentReferencedOutsideDiaryDate(attachmentId, dateKey) {
  return state.diaryEntries.some(
    (entry) => entry.dateKey !== dateKey && (entry.attachment_ids || []).map(String).includes(String(attachmentId)),
  );
}

function openDiaryCalendar() {
  state.diaryCalendarOpen = true;
  state.diaryCalendarMonthKey = monthKeyFromDate(dateFromDateKey(state.diarySelectedDateKey || todayDateKey()));
  render();
}

function shiftDiaryCalendarMonth(delta) {
  state.diaryCalendarMonthKey = shiftMonthKey(state.diaryCalendarMonthKey, delta);
  render();
}

function selectDiaryDate(dateKey) {
  if (!dateKey) {
    return;
  }
  state.diarySelectedDateKey = dateKey;
  state.diaryCalendarMonthKey = monthKeyFromDate(dateFromDateKey(dateKey));
  render();
}

function selectDiaryToday() {
  selectDiaryDate(todayDateKey());
}

function ensureChatIntro() {
  if (state.chatMessages.length) {
    return;
  }
  state.chatMessages = [
    {
      role: "assistant",
      text: "你可以直接说一句账单或提醒，我会先整理成候选记录，确认后再保存。",
    },
  ];
}

function openChatModal(draft = "") {
  openAssistantPage(draft);
}

function openAssistantPage(draft = "", options = {}) {
  if (draft) {
    state.chatDraft = draft;
    saveAssistantSession();
  }
  ensureChatIntro();
  if (state.route !== "assistant") {
    window.location.hash = "assistant";
  } else {
    render();
  }
  if (options.startVoice) {
    window.setTimeout(() => startVoiceInput(), 80);
  }
}

function startAssistantTool(toolId) {
  state.activeAssistantToolId = toolId || null;
  saveAssistantSession();
  if (toolId === "attachment_bill_recognition") {
    openAssistantPage();
    window.setTimeout(() => {
      const input = app.querySelector("[data-chat-image-input]");
      if (input) {
        input.click();
      } else {
        showToast("图片入口暂时没有准备好，请稍后再试。");
      }
    }, 80);
    return;
  }

  const drafts = {
    bill_candidate: "记一笔：",
    task_candidate: "提醒我：",
    diary_candidate: "写日记：",
    diary_reflection: "日记追问：帮我整理今天的心情。",
  };
  openAssistantPage(drafts[toolId] || "");
}

function inferAssistantToolFromMessage(message = "", attachments = []) {
  if (attachments.length) {
    return "attachment_bill_recognition";
  }
  const text = String(message || "");
  if (text.includes("日记") || text.includes("心情") || text.includes("感谢") || text.includes("学到")) {
    return text.includes("追问") || text.includes("整理")
      ? "diary_reflection"
      : "diary_candidate";
  }
  if (text.includes("提醒") || text.includes("待办") || text.includes("任务") || text.includes("明天")) {
    return "task_candidate";
  }
  if (
    text.includes("记账")
    || text.includes("记一笔")
    || text.includes("收入")
    || text.includes("支出")
    || /\d+(?:\.\d{1,2})?\s*(元|块|rmb|cny|¥)/i.test(text)
  ) {
    return "bill_candidate";
  }
  return null;
}

function resetChatSession() {
  stopVoiceInput(false);
  state.chatMessages = [];
  state.chatDraft = "";
  state.chatAttachments = [];
  state.activeAssistantToolId = null;
  clearAssistantSessionStorage();
  ensureChatIntro();
  showToast("已清空当前助手会话。");
}

async function submitChatMessage(formData) {
  if (state.saving) return;
  const message = String(formData.get("message") || "").trim();
  const attachments = state.chatAttachments.filter((attachment) => attachment.status === "uploaded");
  const hasUploading = state.chatAttachments.some((attachment) => attachment.status === "uploading");
  const hasFailedAttachments = state.chatAttachments.some((attachment) => attachment.status === "failed");

  if (hasUploading) {
    showToast("图片还在上传，稍等一下再发送。");
    return;
  }

  if (!message && hasFailedAttachments && !attachments.length) {
    showToast("图片上传失败，请移除后重试或补充文字再发送。");
    return;
  }

  if (!message && !attachments.length) {
    return;
  }

  const displayText = message || "发送了一张图片";
  state.activeAssistantToolId = inferAssistantToolFromMessage(message, attachments)
    || state.activeAssistantToolId;
  state.chatMessages = [
    ...state.chatMessages,
    {
      role: "user",
      text: displayText,
      attachments: attachments.map(toChatMessageAttachment),
    },
  ];
  state.chatDraft = "";
  state.chatAttachments = [];
  state.saving = true;
  saveAssistantSession();
  render();

  try {
    const imageMessages = attachments.length ? await analyzeChatAttachments(attachments) : [];
    const shouldSendTextToChat = Boolean(message);

    if (imageMessages.length) {
      state.chatMessages = [...state.chatMessages, ...imageMessages];
      saveAssistantSession();
    }

    if (shouldSendTextToChat) {
      const context = activeChatCandidateContext();
      const backendMessage = context ? message : buildChatBackendMessage(message, attachments);
      const response = await api("/chat/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(chatMessageRequestBody(backendMessage, context)),
      });
      applyChatAgentResponseSideEffects(response);
      state.chatMessages = [
        ...state.chatMessages,
        { role: "assistant", text: response.reply, response: chatTranscriptResponse(response) },
      ];
      state.activeAssistantToolId = response.assistant_tool_id || state.activeAssistantToolId;
      saveAssistantSession();
    }
  } catch (error) {
    state.chatMessages = [
      ...state.chatMessages,
      { role: "assistant", text: error.message || "AI 助手暂时没有响应。" },
    ];
    saveAssistantSession();
  } finally {
    state.saving = false;
    render();
  }
}

async function analyzeChatAttachments(attachments) {
  const messages = [];
  for (const attachment of attachments) {
    if (!attachment.backendId) {
      messages.push({
        role: "assistant",
        text: `图片「${attachment.name}」还没有上传成功，暂时无法识别。`,
        response: {
          intent: "create_bill",
          confidence: 0,
          assistant_tool_id: "attachment_bill_recognition",
          action_type: "none",
          warnings: ["attachment_upload_missing"],
          need_user_confirmation: false,
          agent_steps: attachmentAgentSteps("blocked"),
        },
      });
      continue;
    }

    try {
      const result = await api(`/attachments/${attachment.backendId}/recognize-and-parse-bill`, {
        method: "POST",
      });
      messages.push(chatMessageFromAttachmentResult(attachment, result));
    } catch (error) {
      messages.push({
        role: "assistant",
        text: `图片「${attachment.name}」已上传，但识别时遇到问题：${error.message || "请稍后再试"}`,
        response: {
          intent: "create_bill",
          confidence: 0,
          assistant_tool_id: "attachment_bill_recognition",
          action_type: "none",
          warnings: ["attachment_recognition_failed"],
          need_user_confirmation: false,
          agent_steps: attachmentAgentSteps("blocked"),
        },
      });
    }
  }
  return messages;
}

function chatMessageFromAttachmentResult(attachment, result) {
  if (result.status === "candidate_created" && result.candidate) {
    return {
      role: "assistant",
      text: `我尝试识别了图片「${attachment.name}」，先整理成一个待确认账单。`,
      response: {
        reply: "我从图片里整理出一个待确认账单，你确认后再保存。",
        intent: "create_bill",
        confidence: result.candidate.confidence ?? 0.7,
        assistant_tool_id: "attachment_bill_recognition",
        action_type: "bill_candidate",
        candidate_id: result.candidate.candidate_id,
        candidate: result.candidate,
        warnings: result.warnings ?? [],
        agent_steps: attachmentAgentSteps("needs_confirmation"),
        need_user_confirmation: true,
      },
    };
  }

  return {
    role: "assistant",
    text: `图片「${attachment.name}」已上传，但暂时没能读出内容。可以输入商家、金额或要记录的事项。`,
    response: {
      intent: "create_bill",
      confidence: result.confidence ?? 0,
      assistant_tool_id: "attachment_bill_recognition",
      action_type: "none",
      warnings: result.warnings ?? [],
      need_user_confirmation: false,
      agent_steps: attachmentAgentSteps("blocked"),
    },
  };
}

function attachmentAgentSteps(finalStatus) {
  const isBlocked = finalStatus === "blocked";
  return [
    {
      title: "读取图片",
      detail: "已接收上传图片并尝试识别内容。",
      status: "completed",
    },
    {
      title: isBlocked ? "停止执行" : "整理候选",
      detail: isBlocked
        ? "暂时没有足够信息生成可确认账单。"
        : "已从识别结果中整理金额、收支类型和可识别信息。",
      status: isBlocked ? "blocked" : "completed",
    },
    ...(isBlocked
      ? []
      : [{
          title: "等待确认",
          detail: "保存前需要你确认候选账单。",
          status: finalStatus,
        }]),
  ];
}

async function addChatImages(fileList) {
  const files = Array.from(fileList || []).filter((file) => file.type.startsWith("image/"));
  if (!files.length) {
    showToast("请选择图片文件。");
    return;
  }

  const slots = Math.max(0, 4 - state.chatAttachments.length);
  const selectedFiles = files.slice(0, slots);
  if (!selectedFiles.length) {
    showToast("一次最多保留 4 张待发送图片。");
    return;
  }

  const pendingItems = selectedFiles.map((file) => ({
    id: crypto.randomUUID(),
    name: file.name || "图片",
    type: file.type,
    size: file.size,
    previewUrl: URL.createObjectURL(file),
    status: "uploading",
  }));
  state.chatAttachments = [...state.chatAttachments, ...pendingItems];
  render();

  await Promise.all(
    pendingItems.map(async (item, index) => {
      const file = selectedFiles[index];
      const payload = new FormData();
      payload.append("file", file);
      payload.append("source", "upload");

      try {
        const uploaded = await api("/attachments/upload", {
          method: "POST",
          body: payload,
        });
        updateChatAttachment(item.id, {
          status: "uploaded",
          backendId: uploaded.id,
          name: uploaded.filename || item.name,
          type: uploaded.content_type || item.type,
          size: uploaded.file_size ?? item.size,
        });
      } catch (error) {
        updateChatAttachment(item.id, {
          status: "failed",
          error: error.message || "上传失败",
        });
      }
    }),
  );
  render();
}

function updateChatAttachment(id, updates) {
  state.chatAttachments = state.chatAttachments.map((attachment) =>
    attachment.id === id ? { ...attachment, ...updates } : attachment,
  );
}

function removeChatAttachment(id) {
  state.chatAttachments = state.chatAttachments.filter((attachment) => attachment.id !== id);
  render();
}

function toChatMessageAttachment(attachment) {
  return {
    id: attachment.id,
    backendId: attachment.backendId,
    name: attachment.name,
    type: attachment.type,
    size: attachment.size,
    previewUrl: attachment.previewUrl,
    status: attachment.status,
  };
}

function buildChatBackendMessage(message, attachments) {
  if (!attachments.length) {
    return message;
  }
  const attachmentLines = attachments.map(
    (attachment) => `图片附件：${attachment.name}，附件ID：${attachment.backendId || "未上传"}`,
  );
  return [
    message || "请根据图片附件判断是否需要生成账单、提醒或日记操作。",
    ...attachmentLines,
  ].join("\n");
}

function chatMessageRequestBody(message, context = activeChatCandidateContext()) {
  const body = { message };
  if (context) {
    body.context_action_type = context.context_action_type;
    body.context_candidate_id = context.context_candidate_id;
  }
  return body;
}

function activeChatCandidateContext() {
  for (let index = state.chatMessages.length - 1; index >= 0; index -= 1) {
    const message = state.chatMessages[index];
    if (message?.role !== "assistant" || message.handled) {
      continue;
    }
    const response = message.response;
    const actionType = response?.action_type;
    const candidateId = getChatCandidateId(response);
    if (["bill_candidate", "task_candidate", "diary_candidate"].includes(actionType) && candidateId) {
      return {
        context_action_type: actionType,
        context_candidate_id: candidateId,
      };
    }
  }
  return null;
}

function applyChatAgentResponseSideEffects(response) {
  if (!response) {
    return;
  }
  const candidateId = getChatCandidateId(response);
  if (response.updated_existing_candidate && response.candidate && candidateId) {
    updateChatCandidateInMessages(candidateId, response.candidate);
  }
  if ((response.created_bill || response.created_task || response.created_diary) && candidateId) {
    markChatCandidate(candidateId, "confirmed");
  }
  if (response.discarded && candidateId) {
    markChatCandidate(candidateId, "discarded");
  }
}

function chatTranscriptResponse(response) {
  if (!response?.updated_existing_candidate) {
    return response;
  }
  return {
    ...response,
    action_type: "none",
    candidate: null,
  };
}

function toggleVoiceInput() {
  if (state.voiceListening) {
    stopVoiceInput();
    return;
  }
  startVoiceInput();
}

function startVoiceInput() {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    showToast("当前浏览器暂不支持语音输入，可以先手动输入。");
    return;
  }

  stopVoiceInput(false);
  const recognition = new Recognition();
  const initialDraft = state.chatDraft.trim();
  let spokenText = "";

  recognition.lang = "zh-CN";
  recognition.interimResults = true;
  recognition.continuous = false;

  recognition.onresult = (event) => {
    let interimText = "";
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const transcript = event.results[index][0]?.transcript?.trim() || "";
      if (event.results[index].isFinal) {
        spokenText = `${spokenText}${spokenText && transcript ? " " : ""}${transcript}`.trim();
      } else {
        interimText = transcript;
      }
    }
    const currentSpeech = [spokenText, interimText].filter(Boolean).join(" ");
    state.chatDraft = [initialDraft, currentSpeech].filter(Boolean).join(initialDraft && currentSpeech ? " " : "");
    saveAssistantSession();
    render();
  };

  recognition.onerror = () => {
    state.voiceListening = false;
    render();
    showToast("语音输入没有成功，可以再试一次。");
  };

  recognition.onend = () => {
    state.voiceListening = false;
    render();
  };

  window.chatSpeechRecognition = recognition;
  state.voiceListening = true;
  render();
  try {
    recognition.start();
  } catch (error) {
    state.voiceListening = false;
    render();
    showToast("语音输入启动失败，可以再试一次。");
  }
}

function stopVoiceInput(shouldRender = true) {
  if (window.chatSpeechRecognition) {
    window.chatSpeechRecognition.onend = null;
    window.chatSpeechRecognition.onerror = null;
    try {
      window.chatSpeechRecognition.stop();
    } catch (error) {
      // Speech recognition can already be stopped by the browser.
    }
    window.chatSpeechRecognition = null;
  }
  state.voiceListening = false;
  if (shouldRender) {
    render();
  }
}

function openChatCandidateEditor(candidateId) {
  const message = state.chatMessages.find((item) => getChatCandidateId(item.response) === String(candidateId));
  if (!message?.response?.candidate) {
    showToast("没找到这条待保存记录，请重新整理。");
    return;
  }
  if (message.handled) {
    showToast("这条记录已处理。已保存的内容可以在对应列表中修改。");
    return;
  }
  state.chatCandidateEditor = {
    candidateId: String(candidateId),
    actionType: message.response.action_type,
    candidate: message.response.candidate,
  };
  render();
}

async function submitChatCandidateEdit(formData) {
  const editor = state.chatCandidateEditor;
  if (!editor?.candidateId || !editor.actionType) {
    return;
  }

  const endpoint = chatCandidateEndpoint(editor.actionType, editor.candidateId);
  const payload = chatCandidateUpdatePayload(editor.actionType, formData);
  if (!endpoint || !payload) {
    showToast("这条记录暂时无法修改，请重新整理。");
    return;
  }

  state.saving = true;
  render();
  try {
    const candidate = await api(endpoint, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    updateChatCandidateInMessages(editor.candidateId, candidate);
    state.chatCandidateEditor = null;
    state.toast = "信息已修改，请核对后保存";
  } catch (error) {
    state.toast = error.message || "修改失败，请重试";
  } finally {
    state.saving = false;
    saveAssistantSession();
    render();
  }
}

function chatCandidateEndpoint(actionType, candidateId) {
  return {
    bill_candidate: `/agent/bill-candidates/${candidateId}`,
    task_candidate: `/agent/task-candidates/${candidateId}`,
    diary_candidate: `/agent/diary-candidates/${candidateId}`,
  }[actionType] || "";
}

function chatCandidateUpdatePayload(actionType, formData) {
  if (actionType === "bill_candidate") {
    const amount = Number(formData.get("amount") || 0);
    return {
      amount: amount > 0 ? amount : null,
      merchant: textOrNull(formData.get("merchant")),
      category: textOrDefault(formData.get("category"), "其他"),
      payment_method: textOrNull(formData.get("payment_method")),
      paid_at: dateTimeValueOrNull(formData.get("paid_at")),
      transaction_type: textOrDefault(formData.get("transaction_type"), "expense"),
      note: textOrNull(formData.get("note")),
    };
  }

  if (actionType === "task_candidate") {
    return {
      title: textOrNull(formData.get("title")),
      description: textOrNull(formData.get("description")),
      category: textOrDefault(formData.get("category"), "生活"),
      task_type: textOrDefault(formData.get("task_type"), "todo"),
      due_at: dateTimeValueOrNull(formData.get("due_at")),
      remind_at: dateTimeValueOrNull(formData.get("remind_at")),
      priority: textOrDefault(formData.get("priority"), "medium"),
    };
  }

  if (actionType === "diary_candidate") {
    return {
      entry_date: textOrNull(formData.get("entry_date")),
      title: textOrNull(formData.get("title")),
      content: textOrNull(formData.get("content")),
      mood: textOrDefault(formData.get("mood"), "calm"),
      weather: textOrNull(formData.get("weather")),
      tags: splitLabels(formData.get("tags")),
    };
  }

  return null;
}

function updateChatCandidateInMessages(candidateId, candidate) {
  state.chatMessages = state.chatMessages.map((message) => {
    if (getChatCandidateId(message.response) !== String(candidateId)) {
      return message;
    }
    const response = message.response || {};
    return {
      ...message,
      response: {
        ...response,
        candidate,
        candidate_id: candidate.candidate_id || response.candidate_id,
        confidence: candidate.confidence ?? response.confidence,
        warnings: candidate.warnings ?? response.warnings,
        need_user_confirmation: candidate.need_user_confirmation ?? response.need_user_confirmation,
      },
    };
  });
}

function textOrNull(value) {
  const text = String(value ?? "").trim();
  return text || null;
}

function textOrDefault(value, fallback) {
  return String(value ?? "").trim() || fallback;
}

function dateTimeValueOrNull(value) {
  const text = String(value ?? "").trim();
  if (!text) {
    return null;
  }
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}
async function confirmChatAction(actionType, candidateId) {
  if (state.saving || !actionType || !candidateId) {
    return;
  }

  state.saving = true;
  render();
  try {
    const response = await api("/chat/confirm-action", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": `web-chat-confirm-${actionType}-${candidateId}`,
      },
      body: JSON.stringify({ action_type: actionType, candidate_id: candidateId }),
    });
    markChatCandidate(candidateId, "confirmed");
    state.chatMessages = [
      ...state.chatMessages,
      { role: "assistant", text: response.reply || "已确认保存。", response },
    ];
    saveAssistantSession();
    state.toast = {
      bill_candidate: "AI 账单已保存",
      task_candidate: "AI 待办已保存",
      diary_candidate: "AI 日记已保存",
    }[actionType] || "记录已保存";
    await loadData();
  } catch (error) {
    state.chatMessages = [
      ...state.chatMessages,
      { role: "assistant", text: error.message || "确认保存失败。" },
    ];
    saveAssistantSession();
    render();
  } finally {
    state.saving = false;
    render();
  }
}

async function discardChatAction(actionType, candidateId) {
  if (state.saving || !actionType || !candidateId) {
    return;
  }

  state.saving = true;
  render();
  try {
    const response = await api("/chat/discard-action", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": `web-chat-discard-${actionType}-${candidateId}`,
      },
      body: JSON.stringify({ action_type: actionType, candidate_id: candidateId }),
    });
    markChatCandidate(candidateId, "discarded");
    state.chatMessages = [
      ...state.chatMessages,
      { role: "assistant", text: response.reply || "这条记录没有保存。" },
    ];
    saveAssistantSession();
    await loadData();
  } catch (error) {
    state.chatMessages = [
      ...state.chatMessages,
      { role: "assistant", text: error.message || "丢弃失败。" },
    ];
    saveAssistantSession();
    render();
  } finally {
    state.saving = false;
    render();
  }
}

function markChatCandidate(candidateId, status) {
  const targetId = String(candidateId || "");
  state.chatMessages = state.chatMessages.map((message) => {
    const responseCandidateId = getChatCandidateId(message.response);
    return responseCandidateId === targetId ? { ...message, handled: status } : message;
  });
  saveAssistantSession();
}

async function completeTask(taskId) {
  const task = state.tasks.find((item) => item.id === taskId);
  if (!task || task.status !== "pending") {
    return;
  }

  state.taskRestoreTarget = null;
  state.saving = true;
  render();
  try {
    await api(`/tasks/${taskId}/complete`, {
      method: "POST",
      headers: { "Idempotency-Key": `web-task-complete-${taskId}-${crypto.randomUUID()}` },
    });
    state.toast = "待办已完成";
    await loadData();
    scheduleToastDismissal();
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

  state.taskRestoreTarget = null;
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
    scheduleToastDismissal();
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
    state.toast = "本机备份已保存";
    await loadData();
  } catch (error) {
    state.toast = error.message || "备份失败，请重试";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

async function previewDataImport(file) {
  if (!file || state.saving) {
    return;
  }

  state.saving = true;
  state.dataImportPreview = null;
  render();

  try {
    const text = await file.text();
    const snapshot = JSON.parse(text);
    const result = await api("/data/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dry_run: true,
        reset_existing: true,
        snapshot,
      }),
    });
    state.dataImportPreview = {
      fileName: file.name || "lifesnap-export.json",
      snapshot,
      result,
    };
    state.toast = "导入预览已生成";
  } catch (error) {
    state.toast = error instanceof SyntaxError
      ? "JSON 文件格式不正确"
      : error.message || "导入预览失败";
  } finally {
    state.saving = false;
    render();
  }
}

async function importPreviewedData() {
  if (!state.dataImportPreview?.snapshot || state.saving) {
    return;
  }

  const { snapshot } = state.dataImportPreview;
  state.saving = true;
  render();

  try {
    await api("/data/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        confirm: true,
        reset_existing: true,
        snapshot,
      }),
    });
    state.dataImportPreview = null;
    state.toast = "JSON 数据已导入";
    await loadData();
  } catch (error) {
    state.toast = error.message || "导入失败";
    render();
  } finally {
    state.saving = false;
    render();
  }
}

async function updatePrivacySetting(key) {
  const allowedKeys = new Set([
    "local_only_mode",
    "allow_ai_text_processing",
    "save_original_attachments_by_default",
    "keep_ocr_text",
  ]);
  if (!allowedKeys.has(key) || state.saving) {
    return;
  }

  const current = Boolean(state.bootstrap?.privacy_settings?.[key]);
  state.saving = true;
  render();

  try {
    const updated = await api("/settings/privacy", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [key]: !current }),
    });
    state.bootstrap = {
      ...(state.bootstrap ?? {}),
      privacy_settings: updated,
    };
    state.toast = "隐私设置已更新";
  } catch (error) {
    state.toast = error.message || "隐私设置更新失败";
  } finally {
    state.saving = false;
    render();
  }
}

async function submitCategorySettings(formData) {
  if (state.saving) {
    return;
  }
  const billCategories = parseCategoryInput(formData.get("bill_categories"));
  const taskCategories = parseCategoryInput(formData.get("task_categories"));
  if (!billCategories.length || !taskCategories.length) {
    showToast("账单和待办分类都至少保留一项。");
    return;
  }

  state.saving = true;
  render();
  try {
    const updated = await api("/settings/categories", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        bill_categories: billCategories,
        task_categories: taskCategories,
      }),
    });
    state.categorySettings = updated;
    state.categorySettingsOpen = false;
    state.toast = "分类设置已保存";
  } catch (error) {
    state.toast = error.message || "分类设置保存失败";
  } finally {
    state.saving = false;
    render();
  }
}

async function submitBudgetSettings(formData) {
  if (state.saving) {
    return;
  }
  const monthlyBudget = Number(formData.get("monthly_budget"));
  const warningThreshold = Number(formData.get("warning_threshold_percent"));
  if (!Number.isFinite(monthlyBudget) || monthlyBudget < 0) {
    showToast("请输入有效的月预算金额。");
    return;
  }
  if (!Number.isFinite(warningThreshold) || warningThreshold < 1 || warningThreshold > 100) {
    showToast("预警比例需要在 1 到 100 之间。");
    return;
  }

  state.saving = true;
  render();
  try {
    const updated = await api("/settings/budget", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        monthly_budget: monthlyBudget,
        warning_threshold_percent: Math.round(warningThreshold),
      }),
    });
    state.budgetSettings = updated;
    state.budgetSettingsOpen = false;
    state.toast = "预算设置已保存";
    await loadData();
  } catch (error) {
    state.toast = error.message || "预算设置保存失败";
  } finally {
    state.saving = false;
    render();
  }
}

async function submitTagSettings(formData) {
  if (state.saving) {
    return;
  }
  const tags = parseLabelInput(formData.get("tags"), 30);
  if (!tags.length) {
    showToast("请至少保留一个标签。");
    return;
  }

  state.saving = true;
  render();
  try {
    const updated = await api("/settings/tags", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tags }),
    });
    state.tagSettings = updated;
    state.tagSettingsOpen = false;
    state.toast = "标签设置已保存";
  } catch (error) {
    state.toast = error.message || "标签设置保存失败";
  } finally {
    state.saving = false;
    render();
  }
}

function submitProfileSettings(formData) {
  const profile = normalizeProfileSettings({
    displayName: formData.get("display_name"),
    signature: formData.get("signature"),
    avatarTone: formData.get("avatar_tone"),
  });
  state.profile = profile;
  state.profileModalOpen = false;
  const persisted = saveProfileSettings(profile);
  showToast(persisted ? "个人资料已保存" : "个人资料已更新，本地保存受限");
}

async function openDiagnostics() {
  if (state.saving) {
    return;
  }
  state.diagnosticsOpen = true;
  await refreshDiagnostics();
}

async function refreshDiagnostics() {
  if (state.diagnosticsLoading) {
    return;
  }
  state.diagnosticsLoading = true;
  render();
  try {
    const [dataQuality, integrations] = await Promise.all([
      api("/diagnostics/data-quality?issue_limit=20"),
      api("/diagnostics/integrations"),
    ]);
    state.diagnostics = dataQuality;
    state.integrationDiagnostics = integrations;
  } catch (error) {
    state.toast = error.message || "系统自检失败";
  } finally {
    state.diagnosticsLoading = false;
    render();
  }
}

async function runIntegrationProbe() {
  if (state.integrationProbeLoading) {
    return;
  }
  state.integrationProbeLoading = true;
  render();
  try {
    state.integrationProbe = await api("/diagnostics/integrations/probe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true }),
    });
    state.toast = "真实连通性探测已完成";
  } catch (error) {
    state.toast = error.message || "真实连通性探测失败";
  } finally {
    state.integrationProbeLoading = false;
    render();
  }
}

async function copyIntegrationGuideText(commandKey) {
  const text = integrationGuideText(commandKey);
  if (!text) {
    showToast("没有可复制的内容");
    return;
  }
  try {
    await copyText(text);
    showToast("已复制接入说明");
  } catch (error) {
    showToast(error.message || "复制失败，请手动选择内容");
  }
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.append(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) {
    throw new Error("当前浏览器不允许自动复制");
  }
}

function integrationGuideText(commandKey) {
  return {
    start: [
      "cd backend",
      ".\\.venv\\Scripts\\python.exe scripts\\mock_ai_provider.py --host 127.0.0.1 --port 8787",
    ].join("\n"),
    env: [
      "$env:LIFESNAP_OCR_ENDPOINT = \"http://127.0.0.1:8787/recognize\"",
      "$env:LIFESNAP_OCR_PROVIDER = \"lifesnap_mock_ocr\"",
      "$env:LIFESNAP_AI_PARSE_ENDPOINT = \"http://127.0.0.1:8787/parse\"",
      "$env:LIFESNAP_AI_PARSE_PROVIDER = \"lifesnap_mock_ai\"",
      "uvicorn app.main:app --reload",
    ].join("\n"),
    privacy: [
      "{",
      "  \"local_only_mode\": false,",
      "  \"allow_ai_text_processing\": true,",
      "  \"save_original_attachments_by_default\": true",
      "}",
    ].join("\n"),
    realEnv: [
      "$env:LIFESNAP_OCR_ENDPOINT = \"https://your-ocr-service.example.com/recognize\"",
      "$env:LIFESNAP_OCR_API_KEY = \"optional-secret\"",
      "$env:LIFESNAP_OCR_PROVIDER = \"external_http\"",
      "$env:LIFESNAP_OCR_TIMEOUT_SECONDS = \"15\"",
      "$env:DEEPSEEK_API_KEY = \"your-deepseek-api-key\"",
      "$env:LIFESNAP_LLM_PROVIDER = \"deepseek\"",
      "$env:LIFESNAP_LLM_MODEL = \"deepseek-v4-flash\"",
      "$env:LIFESNAP_LLM_BASE_URL = \"https://api.deepseek.com\"",
      "$env:LIFESNAP_LLM_REASONING_EFFORT = \"none\"",
      "$env:LIFESNAP_LLM_FINE_TUNED_MODEL = \"optional-fine-tuned-model-id\"",
      "$env:LIFESNAP_LLM_FINE_TUNING_JOB_ID = \"optional-training-job-id\"",
      "$env:LIFESNAP_LLM_TIMEOUT_SECONDS = \"20\"",
      "$env:LIFESNAP_LLM_RESPONSE_FORMAT = \"json_object\"",
      "# 也可以继续使用通用 OpenAI-compatible 配置：LIFESNAP_LLM_API_KEY / LIFESNAP_LLM_MODEL / LIFESNAP_LLM_BASE_URL",
      "# 如果你已有自建解析服务，也可以继续使用旧协议：",
      "$env:LIFESNAP_AI_PARSE_ENDPOINT = \"https://your-ai-service.example.com/parse\"",
      "$env:LIFESNAP_AI_PARSE_API_KEY = \"optional-secret\"",
      "$env:LIFESNAP_AI_PARSE_PROVIDER = \"external_http\"",
      "$env:LIFESNAP_AI_PARSE_TIMEOUT_SECONDS = \"20\"",
      "uvicorn app.main:app --reload",
    ].join("\n"),
    aiContract: [
      "POST /parse",
      "request:",
      "{",
      "  \"schema_version\": \"lifesnap.ai.parse.v1\",",
      "  \"kind\": \"bill | task | chat_intent\",",
      "  \"text\": \"用户输入或 OCR 文本\",",
      "  \"source\": \"ai_chat | screenshot | album | upload\",",
      "  \"locale\": \"zh-CN\",",
      "  \"current_datetime\": \"2026-09-01T10:00:00+08:00\"",
      "}",
      "",
      "bill response:",
      "{",
      "  \"confidence\": 0.9,",
      "  \"data\": {",
      "    \"amount\": \"18.50\",",
      "    \"currency\": \"CNY\",",
      "    \"merchant\": \"瑞幸咖啡\",",
      "    \"category\": \"餐饮\",",
      "    \"payment_method\": \"微信支付\",",
      "    \"transaction_type\": \"expense\"",
      "  },",
      "  \"warnings\": []",
      "}",
      "",
      "chat_intent response:",
      "{",
      "  \"intent\": \"create_bill | create_task | create_diary | diary_reflection | analyze_bills | knowledge_answer | unsupported\",",
      "  \"confidence\": 0.88,",
      "  \"reply\": \"我先整理成一个待确认事项。\",",
      "  \"warnings\": []",
      "}",
    ].join("\n"),
    ocrContract: [
      "POST /recognize",
      "request:",
      "{",
      "  \"attachment_id\": \"00000000-0000-0000-0000-000000000000\",",
      "  \"filename\": \"payment.png\",",
      "  \"content_type\": \"image/png\",",
      "  \"content_base64\": \"...\"",
      "}",
      "",
      "response:",
      "{",
      "  \"text\": \"瑞幸咖啡\\n微信支付\\n实付 18.50 元\",",
      "  \"confidence\": 0.93,",
      "  \"provider\": \"your_ocr_provider\",",
      "  \"warnings\": []",
      "}",
    ].join("\n"),
    probe: [
      "Invoke-RestMethod -Method Post \\",
      "  -Uri http://127.0.0.1:8010/diagnostics/integrations/probe \\",
      "  -ContentType \"application/json\" \\",
      "  -Body '{\"confirm\": true}'",
    ].join("\n"),
  }[commandKey] ?? "";
}

function mockProviderCommandText(commandKey) {
  return integrationGuideText(commandKey);
}

async function openAuditLog() {
  if (state.saving) {
    return;
  }
  state.auditLogOpen = true;
  await refreshAuditLog();
}

async function refreshAuditLog() {
  if (state.auditLogLoading) {
    return;
  }
  state.auditLogLoading = true;
  render();
  try {
    state.auditLog = await api("/audit/events?page_size=20");
  } catch (error) {
    state.toast = error.message || "操作记录加载失败";
  } finally {
    state.auditLogLoading = false;
    render();
  }
}

function openSettingsConfirm(action) {
  const configs = {
    clear: {
      action,
      title: "清除本地数据",
      message: "会清空账单、待办、日记、图片和未保存记录。建议先导出备份文件。",
      confirmLabel: "确认清除",
      danger: true,
    },
    loadSnapshot: {
      action,
      title: "恢复本机备份",
      message: "恢复后，当前记录会被这份备份替换。建议先导出当前数据，再继续恢复。",
      confirmLabel: "确认恢复",
      danger: true,
    },
    deleteSnapshot: {
      action,
      title: "删除本地快照",
      message: "会删除这份本机备份。删除后无法再从这份备份恢复记录。",
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
      state.toast = "本机备份已恢复";
    }

    if (action === "deleteSnapshot") {
      await api("/data/snapshot", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: true }),
      });
      state.toast = "本机备份已删除";
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
    period: "custom",
    year: String(formData.get("year") || "").trim(),
    month: String(formData.get("month") || "").trim(),
    start_date: String(formData.get("start_date") || "").trim(),
    end_date: String(formData.get("end_date") || "").trim(),
    category: String(formData.get("category") || "").trim(),
    transaction_type: String(formData.get("transaction_type") || "").trim(),
    q: String(formData.get("q") || "").trim(),
  };
  state.billListMeta.page = 1;
  loadData();
}

function applyBillRangeFilters(formData) {
  const startDate = String(formData.get("start_date") || "").trim();
  const endDate = String(formData.get("end_date") || "").trim();
  if (startDate && endDate && startDate > endDate) {
    showToast("开始日期不能晚于结束日期。");
    return;
  }

  state.billFilters = {
    ...state.billFilters,
    period: "custom",
    year: "",
    month: "",
    start_date: startDate,
    end_date: endDate,
    category: String(formData.get("category") || "").trim(),
    transaction_type: String(formData.get("transaction_type") || "").trim(),
    q: String(formData.get("q") || "").trim(),
  };
  state.billRangeOpen = false;
  state.billListMeta.page = 1;
  loadData();
}

function defaultBillFilters() {
  const now = new Date();
  return {
    period: "month",
    year: String(now.getFullYear()),
    month: String(now.getMonth() + 1),
    start_date: "",
    end_date: "",
    category: "",
    transaction_type: "",
    q: "",
  };
}

function applyBillPeriodMonth() {
  const current = defaultBillFilters();
  state.billFilters = {
    ...state.billFilters,
    ...current,
    transaction_type: state.billFilters.transaction_type,
    category: state.billFilters.category,
    q: state.billFilters.q,
  };
  state.billListMeta.page = 1;
  loadData();
}

function applyBillPeriodWeek() {
  const { start, end } = localWeekRange(new Date());
  state.billFilters = {
    ...state.billFilters,
    period: "week",
    year: "",
    month: "",
    start_date: dateKeyFromDate(start),
    end_date: dateKeyFromDate(end),
  };
  state.billListMeta.page = 1;
  loadData();
}

function buildBillListPath() {
  const params = new URLSearchParams({ page: String(state.billListMeta.page), page_size: String(state.billListMeta.page_size) });
  Object.entries(state.billFilters).forEach(([key, value]) => {
    if (["period", "start_date", "end_date"].includes(key)) {
      return;
    }
    if (value) {
      params.set(key, value);
    }
  });
  if (state.billFilters.start_date) {
    params.set("paid_from", localDayRange(dateFromDateKey(state.billFilters.start_date)).start.toISOString());
  }
  if (state.billFilters.end_date) {
    params.set("paid_to", localDayRange(dateFromDateKey(state.billFilters.end_date)).end.toISOString());
  }
  return `/bills?${params.toString()}`;
}

function buildTaskListPath() {
  const params = new URLSearchParams({
    page: String(state.taskListMeta.page),
    page_size: String(state.taskListMeta.page_size),
  });
  const view = state.taskFilters.view || "today";
  if (state.taskFilters.category) {
    params.set("category", state.taskFilters.category);
  }

  if (view === "done") {
    params.set("status", "done");
    return `/tasks?${params.toString()}`;
  }

  params.set("status", "pending");
  if (view === "today") {
    const { start, end } = localDayRange(dateFromDateKey(taskSelectedDateKey()));
    params.set("due_from", start.toISOString());
    params.set("due_to", end.toISOString());
  }
  if (view === "upcoming") {
    const { start, end } = upcomingRange(7);
    params.set("due_from", start.toISOString());
    params.set("due_to", end.toISOString());
  }
  return `/tasks?${params.toString()}`;
}

function buildDiaryListPath() {
  const params = new URLSearchParams({
    page: String(state.diaryListMeta.page),
    page_size: String(state.diaryListMeta.page_size),
  });
  return `/diaries?${params.toString()}`;
}

function normalizeDiaryEntries(items) {
  return items
    .map(normalizeDiaryEntry)
    .filter(Boolean)
    .sort((left, right) => right.dateKey.localeCompare(left.dateKey));
}

function normalizeDiaryEntry(item) {
  if (!item?.entry_date) {
    return null;
  }
  return {
    id: item.id,
    dateKey: item.entry_date,
    title: item.title || "今天的日记",
    content: item.content || "",
    mood: item.mood || "happy",
    weather: item.weather || "晴天",
    created_at: item.created_at,
    updated_at: item.updated_at,
    source: item.source || "manual",
    attachment_ids: uniqueValues(item.attachment_ids || []),
    tags: normalizeLabels(item.tags || [], []),
  };
}

function diaryAttachmentIdsForDate(dateKey) {
  return uniqueValues(diaryEntryForDate(dateKey)?.attachment_ids || []);
}

function uniqueValues(values) {
  return Array.from(new Set(values.filter(Boolean).map(String)));
}

function upsertDiaryEntry(entries, entry) {
  if (!entry) {
    return entries;
  }
  return [
    entry,
    ...entries.filter((item) => item.dateKey !== entry.dateKey),
  ].sort((left, right) => right.dateKey.localeCompare(left.dateKey));
}

function localDayRange(value = new Date()) {
  const start = new Date(value);
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(start.getDate() + 1);
  end.setMilliseconds(-1);
  return { start, end };
}

function localWeekRange(value = new Date()) {
  const start = new Date(value);
  const mondayOffset = (start.getDay() + 6) % 7;
  start.setDate(start.getDate() - mondayOffset);
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  end.setHours(23, 59, 59, 999);
  return { start, end };
}

function localMonthRange(year, month) {
  const fallback = new Date();
  const resolvedYear = Number(year) || fallback.getFullYear();
  const resolvedMonth = Number(month) || fallback.getMonth() + 1;
  const start = new Date(resolvedYear, resolvedMonth - 1, 1);
  start.setHours(0, 0, 0, 0);
  const end = new Date(resolvedYear, resolvedMonth, 0);
  end.setHours(23, 59, 59, 999);
  return { start, end };
}

function upcomingRange(days) {
  const start = new Date();
  const end = new Date(start);
  end.setDate(start.getDate() + days);
  end.setHours(23, 59, 59, 999);
  return { start, end };
}

function taskSelectedDateKey() {
  return state.taskFilters.dateKey || todayDateKey();
}

async function openTaskCalendar() {
  state.taskCalendarOpen = true;
  state.taskCalendarMonthKey = monthKeyFromDate(dateFromDateKey(taskSelectedDateKey()));
  render();
  await refreshTaskCalendarMonth();
}

async function shiftTaskCalendarMonth(delta) {
  state.taskCalendarMonthKey = shiftMonthKey(state.taskCalendarMonthKey, delta);
  render();
  await refreshTaskCalendarMonth();
}

function selectTaskDate(dateKey) {
  if (!dateKey) {
    return;
  }
  state.taskFilters.view = "today";
  state.taskFilters.dateKey = dateKey;
  state.taskListExpanded = false;
  state.taskListMeta.page = 1;
  state.taskCalendarMonthKey = monthKeyFromDate(dateFromDateKey(dateKey));
  state.taskCalendarOpen = false;
  loadData();
}

function selectTaskToday() {
  selectTaskDate(todayDateKey());
}

async function refreshTaskCalendarMonth() {
  if (state.taskCalendarLoading) {
    return;
  }
  state.taskCalendarLoading = true;
  render();
  try {
    const { start, end } = monthRange(state.taskCalendarMonthKey);
    const params = new URLSearchParams({
      status: "pending",
      due_from: start.toISOString(),
      due_to: end.toISOString(),
      page_size: "100",
    });
    if (state.taskFilters.category) {
      params.set("category", state.taskFilters.category);
    }
    const result = await api(`/tasks?${params.toString()}`);
    state.taskCalendarTasks = result.items ?? [];
  } catch (error) {
    state.toast = error.message || "提醒日历加载失败";
  } finally {
    state.taskCalendarLoading = false;
    render();
  }
}

function monthRange(monthKey) {
  const start = dateFromMonthKey(monthKey || monthKeyFromDate(new Date()));
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setMonth(start.getMonth() + 1);
  end.setMilliseconds(-1);
  return { start, end };
}

function loadProfileSettings() {
  try {
    const stored = window.localStorage?.getItem(profileStorageKey);
    return normalizeProfileSettings(stored ? JSON.parse(stored) : {});
  } catch (error) {
    return { ...defaultProfileSettings };
  }
}

function saveProfileSettings(profile) {
  try {
    window.localStorage?.setItem(profileStorageKey, JSON.stringify(profile));
    return true;
  } catch (error) {
    return false;
  }
}

function loadAssistantSession() {
  try {
    const stored = window.localStorage?.getItem(assistantSessionStorageKey);
    return normalizeAssistantSession(stored ? JSON.parse(stored) : {});
  } catch (error) {
    return normalizeAssistantSession({});
  }
}

function saveAssistantSession() {
  try {
    window.localStorage?.setItem(assistantSessionStorageKey, JSON.stringify({
      chatMessages: state.chatMessages.map(toStoredChatMessage).filter(Boolean).slice(-30),
      chatDraft: state.chatDraft,
      activeAssistantToolId: state.activeAssistantToolId,
    }));
    return true;
  } catch (error) {
    return false;
  }
}

function clearAssistantSessionStorage() {
  try {
    window.localStorage?.removeItem(assistantSessionStorageKey);
  } catch (error) {
    // Clearing a local draft is best-effort only.
  }
}

function normalizeAssistantSession(value) {
  const input = value && typeof value === "object" ? value : {};
  return {
    chatMessages: Array.isArray(input.chatMessages)
      ? input.chatMessages.map(normalizeStoredChatMessage).filter(Boolean).slice(-30)
      : [],
    chatDraft: String(input.chatDraft ?? "").slice(0, 5000),
    activeAssistantToolId: isKnownAssistantTool(input.activeAssistantToolId)
      ? input.activeAssistantToolId
      : null,
  };
}

function normalizeStoredChatMessage(message) {
  if (!message || typeof message !== "object") {
    return null;
  }
  const role = message.role === "user" ? "user" : "assistant";
  const text = String(message.text ?? "").slice(0, 5000);
  const response = normalizeStoredChatResponse(message.response);
  if (!text && !response) {
    return null;
  }
  return {
    role,
    text,
    response,
    handled: ["confirmed", "discarded"].includes(message.handled) ? message.handled : undefined,
  };
}

function normalizeStoredChatResponse(response) {
  if (!response || typeof response !== "object") {
    return null;
  }
  return {
    reply: String(response.reply ?? "").slice(0, 5000),
    intent: String(response.intent ?? "unsupported"),
    confidence: Number.isFinite(Number(response.confidence)) ? Number(response.confidence) : 0,
    assistant_tool_id: isKnownAssistantTool(response.assistant_tool_id) ? response.assistant_tool_id : null,
    action_type: String(response.action_type ?? "none"),
    candidate_id: response.candidate_id ? String(response.candidate_id) : null,
    candidate: response.candidate ?? null,
    analysis: normalizeChatAnalysis(response.analysis),
    warnings: Array.isArray(response.warnings) ? response.warnings.map(String).slice(0, 20) : [],
    need_user_confirmation: Boolean(response.need_user_confirmation),
    updated_existing_candidate: Boolean(response.updated_existing_candidate),
    discarded: Boolean(response.discarded),
    created_bill: response.created_bill ?? null,
    created_task: response.created_task ?? null,
    created_diary: response.created_diary ?? null,
    knowledge_hits: Array.isArray(response.knowledge_hits)
      ? response.knowledge_hits.map(normalizeKnowledgeHit).filter(Boolean).slice(0, 5)
      : [],
    function_calls: Array.isArray(response.function_calls)
      ? response.function_calls.map(normalizeFunctionCallTrace).filter(Boolean).slice(0, 8)
      : [],
    model_trace: normalizeModelTrace(response.model_trace),
    agent_steps: Array.isArray(response.agent_steps)
      ? response.agent_steps.map(normalizeStoredAgentStep).filter(Boolean).slice(0, 6)
      : [],
  };
}

function normalizeChatAnalysis(analysis) {
  if (!analysis || typeof analysis !== "object") {
    return null;
  }
  return {
    period_label: String(analysis.period_label ?? "本期").slice(0, 40),
    category: analysis.category ? String(analysis.category).slice(0, 40) : null,
    bill_count: Number.isFinite(Number(analysis.bill_count)) ? Number(analysis.bill_count) : 0,
    total_expense: analysis.total_expense ?? 0,
    total_income: analysis.total_income ?? 0,
    total_refund: analysis.total_refund ?? 0,
    net_amount: analysis.net_amount ?? 0,
    category_amount: analysis.category_amount ?? null,
    category_count: analysis.category_count ?? null,
    category_percentage: analysis.category_percentage ?? null,
    previous_period_label: String(analysis.previous_period_label ?? "上期").slice(0, 40),
    previous_total_expense: analysis.previous_total_expense ?? 0,
    expense_delta: analysis.expense_delta ?? 0,
    expense_delta_percentage: analysis.expense_delta_percentage ?? null,
    previous_category_amount: analysis.previous_category_amount ?? null,
    category_delta: analysis.category_delta ?? null,
    category_delta_percentage: analysis.category_delta_percentage ?? null,
    budget_amount: analysis.budget_amount ?? 0,
    budget_usage_percentage: analysis.budget_usage_percentage ?? 0,
    budget_remaining: analysis.budget_remaining ?? 0,
    budget_warning_threshold_percent: Number(analysis.budget_warning_threshold_percent ?? 80),
    top_category: analysis.top_category ? String(analysis.top_category).slice(0, 40) : null,
    top_category_amount: analysis.top_category_amount ?? null,
    top_merchant: analysis.top_merchant ? String(analysis.top_merchant).slice(0, 80) : null,
    top_merchant_amount: analysis.top_merchant_amount ?? null,
    top_day: analysis.top_day ? String(analysis.top_day) : null,
    top_day_expense: analysis.top_day_expense ?? null,
  };
}

function normalizeKnowledgeHit(hit) {
  if (!hit || typeof hit !== "object") return null;
  return {
    source_id: String(hit.source_id ?? "knowledge").slice(0, 80),
    title: String(hit.title ?? "知识命中").slice(0, 80),
    snippet: String(hit.snippet ?? "").slice(0, 240),
    score: Number.isFinite(Number(hit.score)) ? Number(hit.score) : 0,
    tags: Array.isArray(hit.tags) ? hit.tags.map(String).slice(0, 6) : [],
  };
}

function normalizeFunctionCallTrace(call) {
  if (!call || typeof call !== "object") return null;
  return {
    name: String(call.name ?? "tool").slice(0, 80),
    label: String(call.label ?? call.name ?? "函数调用").slice(0, 80),
    arguments: call.arguments && typeof call.arguments === "object" ? call.arguments : {},
    result: String(call.result ?? "completed").slice(0, 180),
    status: String(call.status ?? "completed").slice(0, 40),
  };
}

function normalizeModelTrace(trace) {
  if (!trace || typeof trace !== "object") return null;
  return {
    provider: String(trace.provider ?? "rule_based").slice(0, 80),
    strategy: String(trace.strategy ?? "rule_based_local_fallback").slice(0, 80),
    runtime_model: trace.runtime_model ? String(trace.runtime_model).slice(0, 160) : null,
    base_model: trace.base_model ? String(trace.base_model).slice(0, 160) : null,
    fine_tuned_model: trace.fine_tuned_model ? String(trace.fine_tuned_model).slice(0, 160) : null,
    fine_tuning_status: String(trace.fine_tuning_status ?? "training_dataset_ready").slice(0, 80),
    response_format: trace.response_format ? String(trace.response_format).slice(0, 80) : null,
    reasoning_effort: trace.reasoning_effort ? String(trace.reasoning_effort).slice(0, 40) : null,
    external_model_configured: Boolean(trace.external_model_configured),
    external_model_ready: Boolean(trace.external_model_ready),
    local_fallback_active: trace.local_fallback_active !== false,
    endpoint_configured: Boolean(trace.endpoint_configured),
    api_key_configured: Boolean(trace.api_key_configured),
    privacy_blockers: Array.isArray(trace.privacy_blockers) ? trace.privacy_blockers.map(String).slice(0, 6) : [],
    credential_blockers: Array.isArray(trace.credential_blockers) ? trace.credential_blockers.map(String).slice(0, 6) : [],
    next_action: trace.next_action ? String(trace.next_action).slice(0, 220) : null,
    function_calling_mode: String(trace.function_calling_mode ?? "local_trace_only").slice(0, 80),
    rag_enabled: Boolean(trace.rag_enabled),
    function_calling_enabled: Boolean(trace.function_calling_enabled),
  };
}

function normalizeStoredAgentStep(step) {
  if (!step || typeof step !== "object") {
    return null;
  }
  return {
    title: String(step.title ?? "执行步骤").slice(0, 40),
    detail: String(step.detail ?? "").slice(0, 160),
    status: ["completed", "needs_confirmation", "blocked"].includes(step.status) ? step.status : "completed",
  };
}

function toStoredChatMessage(message) {
  return normalizeStoredChatMessage({
    role: message.role,
    text: message.text,
    response: message.response,
    handled: message.handled,
  });
}

function isKnownAssistantTool(toolId) {
  return knownAssistantToolIds.includes(toolId);
}

function normalizeProfileSettings(value) {
  const input = value && typeof value === "object" ? value : {};
  const displayName = String(input.displayName ?? input.display_name ?? "")
    .trim()
    .slice(0, 18);
  const signature = String(input.signature ?? "")
    .trim()
    .slice(0, 36);
  const avatarTone = ["warm", "mint", "blue", "rose"].includes(input.avatarTone ?? input.avatar_tone)
    ? String(input.avatarTone ?? input.avatar_tone)
    : defaultProfileSettings.avatarTone;

  return {
    displayName: displayName || defaultProfileSettings.displayName,
    signature: signature || defaultProfileSettings.signature,
    avatarTone,
  };
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
  state.billRestoreTarget = null;
  state.taskRestoreTarget = null;
  state.diaryRestoreTarget = null;
  state.toast = message;
  render();
  window.setTimeout(() => {
    if (state.toast === message) {
      state.toast = "";
      app.querySelector(".toast")?.remove();
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
  const hasCustomHeader = ["dashboard", "bills", "tasks", "diary", "assistant", "settings"].includes(state.route);
  app.innerHTML = `
    <div class="app-shell mobile-shell simple-shell">
      ${renderSidebar()}
      <main class="main mobile-main" id="main-content">
        ${hasCustomHeader ? "" : renderTopbar(route, primaryAction)}
        ${renderPage()}
        ${renderMobileTabbar()}
      </main>
      <input type="file" accept="image/*" data-bill-image-input hidden />
      <input type="file" accept="image/*" data-diary-image-input multiple hidden />
      <input type="file" accept="application/json,.json" data-import-json-input hidden />
      ${renderCategoryDatalists()}
      ${state.modalOpen ? renderBillModal() : ""}
      ${state.billRangeOpen ? renderBillRangeModal() : ""}
      ${state.notificationOpen ? renderNotificationModal() : ""}
      ${state.deleteTarget ? renderDeleteBillModal() : ""}
      ${state.taskDeleteTarget ? renderDeleteTaskModal() : ""}
      ${state.taskSortOpen ? renderTaskSortModal() : ""}
      ${state.taskCalendarOpen ? renderTaskCalendarModal() : ""}
      ${state.taskModalOpen ? renderTaskModal() : ""}
      ${state.repeatTaskModalOpen ? renderRepeatTaskModal() : ""}
      ${state.diaryModalOpen ? renderDiaryModal() : ""}
      ${state.diaryDeleteTarget ? renderDeleteDiaryModal() : ""}
      ${state.diaryCalendarOpen ? renderDiaryCalendarModal() : ""}
      ${state.snoozeTarget ? renderSnoozeModal() : ""}
      ${state.settingsConfirm ? renderSettingsConfirmModal() : ""}
      ${state.dataImportPreview ? renderDataImportModal() : ""}
      ${state.profileModalOpen ? renderProfileSettingsModal() : ""}
      ${state.privacySettingsOpen ? renderPrivacySettingsModal() : ""}
      ${state.categorySettingsOpen ? renderCategorySettingsModal() : ""}
      ${state.budgetSettingsOpen ? renderBudgetSettingsModal() : ""}
      ${state.tagSettingsOpen ? renderTagSettingsModal() : ""}
      ${state.diagnosticsOpen ? renderDiagnosticsModal() : ""}
      ${state.auditLogOpen ? renderAuditLogModal() : ""}
      ${state.recycleBinOpen ? renderRecycleBinModal() : ""}
      ${state.chatCandidateEditor ? renderChatCandidateEditorModal() : ""}
      ${state.toast ? renderToast() : ""}
    </div>
  `;
  afterRender();
  scheduleToastDismissal();
}

function scheduleToastDismissal() {
  if (state.toast === timedToast) return;
  window.clearTimeout(toastDismissTimer);
  timedToast = state.toast;
  if (!timedToast) return;
  const message = timedToast;
  toastDismissTimer = window.setTimeout(() => {
    if (state.toast === message) {
      state.toast = "";
      app.querySelector(".toast")?.remove();
    }
    timedToast = "";
  }, 4200);
}

function renderToast() {
  const canRestoreBill = state.toast === "账单已删除" && state.billRestoreTarget?.id;
  const canRestoreDiary = state.toast === "日记已删除" && state.diaryRestoreTarget?.id;
  const canRestoreTask = state.toast === "待办已删除" && state.taskRestoreTarget?.id;
  const canRestore = canRestoreBill || canRestoreDiary || canRestoreTask;
  return `
    <div class="toast ${canRestore ? "has-action" : ""}" role="status" aria-live="polite">
      <span>${escapeHtml(state.toast)}</span>
      ${canRestore ? `
        <button class="toast-action" type="button"
          ${canRestoreBill ? `data-restore-bill="${escapeHtml(state.billRestoreTarget.id)}"` : ""}
          ${canRestoreDiary ? `data-restore-diary="${escapeHtml(state.diaryRestoreTarget.id)}"` : ""}
          ${canRestoreTask ? `data-restore-task="${escapeHtml(state.taskRestoreTarget.id)}"` : ""}
          ${state.saving ? "disabled" : ""}>
          ${state.saving ? "恢复中..." : "撤销"}
        </button>
      ` : ""}
    </div>
  `;
}

function renderCategoryDatalists() {
  const categories = getCategorySettings();
  const tags = getTagSettings().tags;
  return `
    <datalist id="bill_category_options">
      ${categories.bill_categories.map((item) => `<option value="${escapeHtml(item)}"></option>`).join("")}
    </datalist>
    <datalist id="task_category_options">
      ${categories.task_categories.map((item) => `<option value="${escapeHtml(item)}"></option>`).join("")}
    </datalist>
    <datalist id="diary_tag_options">
      ${tags.map((item) => `<option value="${escapeHtml(item)}"></option>`).join("")}
    </datalist>
  `;
}

function afterRender() {
  if (state.route === "assistant") {
    const thread = app.querySelector(".assistant-thread");
    if (thread) thread.scrollTop = thread.scrollHeight;
  }
  const dialogs = app.querySelectorAll('[role="dialog"]');
  const dialog = dialogs[dialogs.length - 1];
  app.querySelector("main")?.toggleAttribute("inert", Boolean(dialog));
  app.querySelector(".simple-sidebar")?.toggleAttribute("inert", Boolean(dialog));
  document.body.classList.toggle("has-dialog", Boolean(dialog));
  if (dialog) {
    const target = dialog.querySelector('input:not([type="hidden"]), textarea, select') || dialog.querySelector("button");
    target?.focus({ preventScroll: true });
  }
}

function friendlyAssistantText(value) {
  const known = {
    "Bill candidate confirmed and saved.": "这笔账已保存，可以在账单里查看。",
    "Task candidate confirmed and saved.": "事项已保存，可以在待办里查看。",
    "Diary candidate confirmed and saved.": "日记已保存，可以在日记里查看。",
    "Bill candidate discarded.": "这笔账没有保存。",
    "Task candidate discarded.": "这件事没有保存。",
    "Diary candidate discarded.": "这篇日记没有保存。",
  };
  return String(known[value] || value).replaceAll("候选账单", "待核对账单").replaceAll("候选提醒", "待核对事项").replaceAll("候选记录", "待核对记录").replaceAll("候选日记", "待核对日记").replaceAll("候选结果", "待核对内容").replaceAll("字段", "信息").replaceAll("商户", "商家");
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
  const item = (id, label, symbol) => `<button class="nav-button ${state.route === id ? "is-active" : ""}" type="button" data-route="${id}" ${state.route === id ? 'aria-current="page"' : ""}>${icon(symbol)}<span>${label}</span></button>`;
  return `<aside class="sidebar simple-sidebar">
    <a class="brand" href="#dashboard" aria-label="LifeSnap 首页"><span class="brand-mark">${icon("wallet")}</span><span><strong class="brand-title">LifeSnap</strong><small class="brand-subtitle">把每一笔，记清楚</small></span></a>
    <nav class="nav" aria-label="主导航">
      ${item("dashboard", "首页", "home")}${item("bills", "账单", "receipt")}${item("assistant", "AI 帮记", "spark")}
      <p class="nav-group-label">生活小事</p>${item("tasks", "待办", "check")}${item("diary", "日记", "book")}
      <p class="nav-group-label">管理</p>${item("settings", "设置", "settings")}
    </nav><div class="simple-sidebar-note">${icon("check-circle")}每笔收支，由你确认。</div>
  </aside>`;
}

function renderPage() {
  if (state.loading) {
    return `<section class="surface"><p class="status-line">正在加载你的记录…</p></section>`;
  }

  if (state.error) {
    return `
      <section class="surface">
        <h1 class="section-title">暂时无法加载记录</h1><p class="status-line">连接可能中断了，请稍后重试。</p><button class="button primary" type="button" data-refresh>重新加载</button><details class="simple-details"><summary>查看原因</summary><p class="error">${escapeHtml(state.error)}</p></details>
      </section>
    `;
  }

  if (state.route === "bills") return renderBillsPage();
  if (state.route === "tasks") return renderTasksPage();
  if (state.route === "diary") return renderDiaryMobilePage();
  if (state.route === "assistant") return renderAssistantPage();
  if (state.route === "settings") return renderProfilePage();
  return renderDashboard();
}

function renderDashboard() {
  const dashboard = state.bootstrap?.dashboard ?? {};
  const monthly = dashboard.monthly_statistics ?? {};
  const expense = Number(monthly.total_expense ?? 0);
  const budget = Number(getBudgetSettings().monthly_budget ?? 0);
  const remaining = budget - expense;
  const recent = (dashboard.recent_bills ?? []).slice(0, 5);
  const now = new Date();
  const dateLabel = new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "long" }).format(now);
  const tasks = [...new Map([...(dashboard.today_tasks ?? []), ...(dashboard.upcoming_reminders ?? [])].map(task => [task.id, task])).values()].slice(0, 3);
  return `<div class="simple-home">
    <header class="simple-page-header"><div><p class="simple-kicker">${escapeHtml(dateLabel)}</p><h1>记好每一笔，心里更有数。</h1><p>花了多少、花在哪里，打开就知道。</p></div><button class="button primary" type="button" data-open-bill-modal>${icon("plus")}记一笔</button></header>
    <section class="entry-options" aria-label="选择记账方式">
      <button class="entry-option" type="button" data-bill-photo-placeholder ${state.saving ? "disabled" : ""}><span class="entry-icon">${icon("camera")}</span><span><strong>${state.saving ? "正在读取图片…" : "上传截图记账"}</strong><small>选择支付截图，核对后保存</small></span>${icon("chevron-right")}</button>
      <button class="entry-option" type="button" data-route="assistant"><span class="entry-icon blue">${icon("spark")}</span><span><strong>说一句，让 AI 帮记</strong><small>例如：今天午餐花了 28 元</small></span>${icon("chevron-right")}</button>
    </section>
    <section class="simple-finance" aria-label="本月收支">
      <div class="simple-finance-main"><span>${now.getMonth() + 1} 月支出</span><strong>${money(expense)}</strong><small>已记录 ${Number(monthly.bill_count ?? 0)} 笔收支</small></div>
      <div class="simple-finance-secondary"><span>本月收入</span><strong>${money(monthly.total_income)}</strong><span>本月退款 <b>${money(monthly.total_refund)}</b></span></div>
      <button class="simple-budget" type="button" data-open-budget-settings><span><strong>${budget > 0 ? (remaining < 0 ? "已超出预算" : "本月预算还剩") : "设置月预算"}</strong>${icon("chevron-right")}</span><b>${budget > 0 ? money(Math.abs(remaining)) : "给花销定个小目标"}</b><span class="simple-budget-track" aria-hidden="true"><i style="width:${budget > 0 ? Math.min(100, expense / budget * 100) : 0}%"></i></span><small>${budget > 0 ? `月预算 ${money(budget)}` : "点这里设置，方便留意支出"}</small></button>
    </section>
    <div class="simple-home-columns">
      <section class="surface simple-recent"><div class="simple-section-heading"><div><h2>最近账单</h2><p>点开一笔，就能查看和修改。</p></div><button class="button ghost" type="button" data-route="bills">全部账单 ${icon("chevron-right")}</button></div>
        ${recent.length ? renderBillFeed(recent) : renderSimpleEmpty("从第一笔开始", "填金额和用途，就能记好一笔账。", '<button class="button primary" type="button" data-open-bill-modal>记下第一笔</button>')}
      </section>
      <section class="surface simple-life"><div class="simple-section-heading"><div><h2>顺手记点小事</h2><p>账之外，也照顾好日常。</p></div></div>
        <div class="simple-life-links"><button type="button" data-route="tasks">${icon("check")}<span><strong>待办事项</strong><small>${tasks.length ? "看看接下来要做的事" : "把要做的事记下来"}</small></span>${icon("chevron-right")}</button><button type="button" data-route="diary">${icon("book")}<span><strong>我的日记</strong><small>留下一点今天的心情</small></span>${icon("chevron-right")}</button></div>
        ${tasks.length ? `<div class="simple-upcoming">${renderHomeTasks(tasks)}</div>` : '<p class="simple-note">生活记录随时可用，先从你需要的开始。</p>'}
      </section>
    </div>
  </div>`;
}

function renderSimpleEmpty(title, description, action = "") {
  return `<div class="simple-empty">${icon("receipt")}<h3>${escapeHtml(title)}</h3><p>${escapeHtml(description)}</p>${action}</div>`;
}

function renderBillsPage() {
  const overview = state.billOverview ?? {};
  const monthly = overview.monthly_statistics ?? {};
  const categories = monthly.category_breakdown ?? [];
  const meta = state.billListMeta;
  const extraFilters = [state.billFilters.category, state.billFilters.q].filter(Boolean);
  return `<div class="simple-bills">
    <header class="simple-page-header"><div><p class="simple-kicker">每一笔，都有记录</p><h1>账单</h1><p>查找收支，点开账单即可修改。</p></div><div class="action-row"><button class="button" type="button" data-bill-photo-placeholder ${state.saving ? "disabled" : ""}>${icon("camera")}上传截图</button><button class="button primary" type="button" data-open-bill-modal>${icon("plus")}记一笔</button></div></header>
    <section class="surface simple-ledger">
      ${renderBillControls()}
      <form class="simple-search" data-bill-search-form role="search">${icon("search")}<label class="sr-only" for="bill-search">搜索商家或备注</label><input id="bill-search" name="q" type="search" maxlength="80" placeholder="搜索商家、用途或备注" value="${escapeHtml(state.billFilters.q)}" />${state.billFilters.q ? '<button class="button ghost" type="button" data-clear-bill-search>清除</button>' : ""}<button class="button" type="submit">搜索</button></form>
      <div class="simple-list-caption"><span>${escapeHtml(billRangeLabel())} · ${meta.total} 笔${extraFilters.length ? ` · ${escapeHtml(extraFilters.join(" / "))}` : ""}</span>${extraFilters.length || state.billFilters.transaction_type || state.billFilters.period !== "month" ? '<button class="text-action" type="button" data-reset-bill-filters>重置筛选</button>' : ""}</div>
      ${state.bills.length ? renderBillFeed(state.bills) : renderSimpleEmpty("这里还没有账单", "可以换个时间范围，或记下一笔新的收支。", '<button class="button" type="button" data-bill-all-time>查看全部时间</button>')}
      ${meta.total_pages > 1 ? `<nav class="simple-pagination" aria-label="账单翻页"><button class="button" type="button" data-bill-page="${meta.page - 1}" ${meta.page <= 1 ? "disabled" : ""}>上一页</button><span>第 ${meta.page} / ${meta.total_pages} 页</span><button class="button" type="button" data-bill-page="${meta.page + 1}" ${meta.page >= meta.total_pages ? "disabled" : ""}>下一页</button></nav>` : ""}
    </section>
    <details class="surface simple-details simple-monthly"><summary><span>${icon("pie-chart")}本月花在哪里</span><small>展开统计 ${icon("chevron-right")}</small></summary><div class="simple-details-content">
      <p class="simple-note">${monthly.year ?? new Date().getFullYear()} 年 ${monthly.month ?? new Date().getMonth() + 1} 月的全部收支，独立于上方列表筛选。</p>
      <div class="simple-stat-row"><div><span>支出</span><strong>${money(monthly.total_expense)}</strong></div><div><span>收入</span><strong>${money(monthly.total_income)}</strong></div><div><span>退款</span><strong>${money(monthly.total_refund)}</strong></div></div>
      <div class="ledger-insights">${renderBillCategoryPanel(categories, Number(monthly.total_expense ?? 0))}${renderBillTrendPanel(overview.daily_breakdown ?? [])}</div>
    </div></details>
  </div>`;
}

function renderBillControls() {
  const type = state.billFilters.transaction_type;
  const period = state.billFilters.period;
  return `<div class="simple-filter-bar"><div class="simple-segments" role="group" aria-label="收支类型">${[["", "全部"], ["expense", "支出"], ["income", "收入"], ["refund", "退款"]].map(([value, label]) => `<button type="button" data-bill-type="${value}" aria-pressed="${type === value}" class="${type === value ? "is-active" : ""}">${label}</button>`).join("")}</div>
    <div class="simple-periods" role="group" aria-label="时间范围"><button class="button ${period === "month" ? "is-selected" : "ghost"}" type="button" data-bill-period="month" aria-pressed="${period === "month"}">本月</button><button class="button ${period === "week" ? "is-selected" : "ghost"}" type="button" data-bill-period="week" aria-pressed="${period === "week"}">本周</button><button class="button ${period === "all" ? "is-selected" : "ghost"}" type="button" data-bill-all-time aria-pressed="${period === "all"}">全部时间</button><button class="button" type="button" data-bill-filter-panel>${icon("filter")}筛选</button></div>
  </div>`;
}

function billRangeLabel() {
  const filters = state.billFilters;
  if (filters.period === "all") return "全部时间";
  if (filters.period === "week") {
    return `本周 ${diaryDateLabel(filters.start_date)} 至 ${diaryDateLabel(filters.end_date)}`;
  }
  if (filters.period === "custom") {
    const start = filters.start_date ? diaryDateLabel(filters.start_date) : "不限开始";
    const end = filters.end_date ? diaryDateLabel(filters.end_date) : "不限结束";
    return `${start} 至 ${end}`;
  }
  const year = filters.year || String(new Date().getFullYear());
  const month = filters.month || String(new Date().getMonth() + 1);
  return `${year} 年 ${month} 月`;
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
      <button class="bill-dock-side" type="button" data-bill-photo-placeholder ${state.saving ? "disabled" : ""}>
        ${icon("camera")}${state.saving ? "导入中..." : "拍照记账"}
      </button>
    </section>
  `;
}

function renderTasksPage() {
  const groups = getReminderTaskGroups();
  const visibleTasks = getVisibleReminderTasks(groups);
  const hasHiddenTasks = !state.taskListExpanded && state.taskListMeta.total > visibleTasks.length;
  return `<div class="simple-tasks">
    <header class="simple-page-header"><div><p class="simple-kicker">一件一件，慢慢完成</p><h1>待办事项</h1><p>写下要做的事，完成后勾选即可。</p></div><button class="button primary" type="button" data-open-task-modal>${icon("plus")}添加事项</button></header>
    <section class="surface simple-task-list">
      ${renderReminderViewTabs()}
      <div class="simple-section-heading"><h2>${reminderListTitle()}</h2><button class="button ghost" type="button" data-open-task-sort>${icon("list-filter")}排序</button></div>
      ${visibleTasks.length ? renderReminderTaskList(visibleTasks) : renderSimpleEmpty("这里暂时没有待办", "可以添加新事项，或切换日期查看。", '<button class="button" type="button" data-open-task-modal>添加一件事</button>')}
      ${hasHiddenTasks ? '<button class="reminder-more-button" type="button" data-view-all-tasks>显示更多事项</button>' : ""}
    </section>
    <details class="surface simple-details"><summary><span>分类与重复事项</span><small>需要时再设置 ${icon("chevron-right")}</small></summary><div class="simple-details-content">${renderReminderCategoryTabs()}<button class="button" type="button" data-open-repeat-task-modal>${icon("refresh")}添加重复事项</button></div></details>
    <p class="simple-note">这里用于查看和安排事项，目前不会在后台自动发送通知。</p>
  </div>`;
}

function getReminderTaskGroups() {
  const overview = state.taskOverview ?? {};
  const sorted = uniqueTasks([
    ...state.tasks,
    ...(overview.overdue_tasks ?? []),
    ...(overview.today_tasks ?? []),
    ...(overview.upcoming_reminders ?? []),
  ]).sort(compareReminderTasks);
  const pending = sorted.filter((task) => task.status === "pending");
  const done = sorted.filter((task) => task.status === "done");
  const selectedDateTasks = pending.filter((task) => isTaskOnDate(task, taskSelectedDateKey()));
  return {
    all: sorted,
    pending,
    done,
    today: selectedDateTasks,
    upcoming: pending.filter((task) => !isTodayTask(task)),
    important: pending.filter((task) => task.priority === "high"),
  };
}

function allLoadedTasks() {
  const overview = state.taskOverview ?? {};
  return uniqueTasks([
    ...state.tasks,
    ...(overview.overdue_tasks ?? []),
    ...(overview.today_tasks ?? []),
    ...(overview.upcoming_reminders ?? []),
  ]);
}

function findTaskById(taskId) {
  return allLoadedTasks().find((task) => task.id === taskId) ?? null;
}

function uniqueTasks(tasks) {
  const seen = new Set();
  return tasks.filter((task) => {
    if (!task?.id || seen.has(task.id)) {
      return false;
    }
    seen.add(task.id);
    return true;
  });
}

function getReminderSummary(groups) {
  const overview = state.taskOverview ?? {};
  const isSelectedToday = taskSelectedDateKey() === todayDateKey();
  return {
    pending: Number(overview.pending_count ?? groups.pending.length),
    done: Number(overview.done_count ?? groups.done.length),
    today: isSelectedToday ? Number(overview.due_today_count ?? groups.today.length) : groups.today.length,
    important: countOverviewPriority("high") || groups.important.length,
  };
}

function countOverviewPriority(priority) {
  const item = (state.taskOverview?.priority_breakdown ?? []).find((entry) => entry.priority === priority);
  return Number(item?.count ?? 0);
}

function getVisibleReminderTasks(groups) {
  const view = state.taskFilters.view;
  let tasks = view === "all" ? groups.pending : groups.today;
  if (view === "upcoming") {
    tasks = groups.upcoming.length ? groups.upcoming : groups.pending;
  } else if (view === "done") {
    tasks = groups.done;
  }

  if (state.taskFilters.category) {
    tasks = tasks.filter((task) => matchesTaskCategory(task, state.taskFilters.category));
  }
  return tasks.slice(0, state.taskListExpanded ? state.taskListMeta.page_size : 5);
}

function renderReminderViewTabs() {
  const tabs = [
    ["all", "待完成"],
    ["today", taskSelectedDateKey() === todayDateKey() ? "今天" : taskDateLabel(taskSelectedDateKey())],
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
      <button class="reminder-calendar-button" type="button" data-open-task-calendar aria-label="选择日期">
        ${icon("calendar")}
      </button>
    </div>
  `;
}

function renderTaskCalendarModal() {
  const monthDate = dateFromMonthKey(state.taskCalendarMonthKey || monthKeyFromDate(new Date()));
  const selectedKey = taskSelectedDateKey();
  const days = diaryCalendarDays(monthDate);
  const monthLabel = monthDate.toLocaleDateString("zh-CN", { year: "numeric", month: "long" });
  const selectedTasks = taskCalendarTasksForDate(selectedKey);
  const weekdays = ["一", "二", "三", "四", "五", "六", "日"];
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal diary-calendar-modal" role="dialog" aria-modal="true" aria-labelledby="task-calendar-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="task-calendar-title">提醒日历</h2>
            <p class="section-note">选择日期，查看当天的待办事项。</p>
          </div>
          <button class="button ghost" type="button" data-close-modal aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <div class="diary-calendar-toolbar">
          <button class="diary-calendar-nav is-prev" type="button" data-task-calendar-nav="-1" aria-label="上个月">
            ${icon("chevron-right")}
          </button>
          <strong>${escapeHtml(monthLabel)}</strong>
          <button class="diary-calendar-nav" type="button" data-task-calendar-nav="1" aria-label="下个月">
            ${icon("chevron-right")}
          </button>
        </div>
        <div class="diary-calendar-weekdays" aria-hidden="true">
          ${weekdays.map((day) => `<span>${day}</span>`).join("")}
        </div>
        <div class="diary-calendar-grid">
          ${days.map((day) => renderTaskCalendarDay(day, monthDate, selectedKey)).join("")}
        </div>
        ${state.taskCalendarLoading ? `<p class="task-calendar-note">正在读取本月提醒...</p>` : ""}
        <div class="diary-calendar-footer">
          <div>
            <strong>${escapeHtml(taskDateLabel(selectedKey))}</strong>
            <span>${selectedTasks.length ? `${selectedTasks.length} 条提醒` : "当前已加载日期暂无提醒"}</span>
          </div>
          <div class="diary-calendar-actions">
            <button class="button ghost" type="button" data-task-calendar-today>今天</button>
            <button class="button primary" type="button" data-task-calendar-done>完成</button>
          </div>
        </div>
      </section>
    </div>
  `;
}

function renderTaskCalendarDay(day, monthDate, selectedKey) {
  const key = dateKeyFromDate(day);
  const isCurrentMonth = day.getMonth() === monthDate.getMonth();
  const isSelected = key === selectedKey;
  const isToday = key === todayDateKey();
  const taskCount = taskCalendarTasksForDate(key).length;
  const hasTasks = taskCount > 0;
  return `
    <button class="diary-calendar-day task-calendar-day ${isCurrentMonth ? "" : "is-muted"} ${isSelected ? "is-selected" : ""} ${isToday ? "is-today" : ""} ${hasTasks ? "has-entry" : ""}"
      type="button" data-task-date="${key}" aria-label="选择 ${escapeHtml(taskDateLabel(key))}">
      <span>${day.getDate()}</span>
      ${hasTasks ? `<i></i><em>${taskCount}</em>` : ""}
    </button>
  `;
}

function taskCalendarTasksForDate(dateKey) {
  return state.taskCalendarTasks.filter((task) => isTaskOnDate(task, dateKey));
}

function renderReminderCategoryTabs() {
  const configuredCategories = getCategorySettings().task_categories.slice(0, 4);
  const selectedCategory = state.taskFilters.category;
  const visibleCategories = selectedCategory
    && selectedCategory !== ""
    && !configuredCategories.includes(selectedCategory)
    ? [...configuredCategories.slice(0, 3), selectedCategory]
    : configuredCategories;
  const tabs = [
    ["", "全部", "check-circle"],
    ...visibleCategories.map((category) => [
      category,
      category,
      iconForTask({ category }),
    ]),
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
    all: "待完成事项",
    today: `${taskDateLabel(taskSelectedDateKey())}待办`,
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
      <button class="reminder-edit" type="button" data-edit-task="${task.id}"
        aria-label="编辑 ${escapeHtml(task.title)}" ${state.saving ? "disabled" : ""}>
        ${icon("edit")}
      </button>
      <button class="reminder-check ${done ? "is-done" : ""}" type="button"
        data-complete-task="${task.id}"
        aria-label="完成 ${escapeHtml(task.title)}"
        ${done || state.saving ? "disabled" : ""}>
        ${done ? icon("check") : ""}
      </button>
      <button class="reminder-delete" type="button" data-delete-task="${task.id}"
        aria-label="删除 ${escapeHtml(task.title)}" ${state.saving ? "disabled" : ""}>
        ${icon("trash")}
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
        <p class="item-meta">添加一件要做的事，完成后就可以勾掉。</p>
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
      <button class="reminder-dock-side" type="button" data-open-repeat-task-modal>
        ${icon("refresh")}重复提醒
      </button>
    </section>
  `;
}

function compareReminderTasks(a, b) {
  const statusWeight = (task) => (task.status === "done" ? 1 : 0);
  return statusWeight(a) - statusWeight(b)
    || compareReminderTasksBySort(a, b)
    || String(a.title ?? "").localeCompare(String(b.title ?? ""), "zh-CN");
}

function compareReminderTasksBySort(a, b) {
  const sort = state.taskFilters.sort || "time";
  if (sort === "priority") {
    return priorityWeight(a) - priorityWeight(b)
      || targetTime(a) - targetTime(b)
      || createdTime(b) - createdTime(a);
  }
  if (sort === "created") {
    return createdTime(b) - createdTime(a)
      || targetTime(a) - targetTime(b)
      || priorityWeight(a) - priorityWeight(b);
  }
  return targetTime(a) - targetTime(b)
    || priorityWeight(a) - priorityWeight(b)
    || createdTime(b) - createdTime(a);
}

function priorityWeight(task) {
  return { high: 0, medium: 1, low: 2 }[task?.priority] ?? 1;
}

function targetTime(task) {
  return taskTargetDate(task)?.getTime() ?? Number.MAX_SAFE_INTEGER;
}

function createdTime(task) {
  const date = task?.created_at ? new Date(task.created_at) : null;
  return date && !Number.isNaN(date.getTime()) ? date.getTime() : 0;
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

function isTaskOnDate(task, dateKey) {
  const target = taskTargetDate(task);
  if (!target) {
    return task?.status === "pending" && dateKey === todayDateKey();
  }
  return dateKeyFromDate(target) === dateKey;
}

function isTodayTask(task) {
  return isTaskOnDate(task, todayDateKey());
}

function taskDateLabel(dateKey) {
  if (dateKey === todayDateKey()) {
    return "今日";
  }
  return diaryDateLabel(dateKey);
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
  return `<div class="simple-diary">
    <header class="simple-page-header"><div><p class="simple-kicker">给今天，留一点位置</p><h1>我的日记</h1><p>记下发生的小事，留住自己的感受。</p></div><button class="button primary" type="button" data-open-diary-modal data-diary-date="${escapeHtml(diary.dateKey)}">${icon("edit")}${diary.hasEntry ? "修改日记" : "写日记"}</button></header>
    <section class="surface simple-diary-date"><strong>${escapeHtml(diary.dateLabel)}</strong><div class="action-row"><button class="button ghost" type="button" data-diary-calendar-today>今天</button><button class="button" type="button" data-open-diary-calendar>${icon("calendar")}选择日期</button></div></section>
    ${diary.hasEntry ? renderDiaryEntry(diary) : `<section class="surface">${renderSimpleEmpty("这一天，还没写日记", "写一句话也可以，从此刻的心情开始。", `<button class="button" type="button" data-open-diary-modal data-diary-date="${escapeHtml(diary.dateKey)}">写下这一天</button>`)}</section>`}
    ${diary.hasEntry && diary.attachmentIds.length ? renderDiaryGallery(diary) : ""}
  </div>`;
}

function getDiarySnapshot() {
  const selectedDateKey = state.diarySelectedDateKey || todayDateKey();
  const entry = diaryEntryForDate(selectedDateKey);
  const mood = entry?.mood || "happy";
  const streakDays = Number(state.diaryOverview?.streak_days ?? diaryStreakDays());
  const recentBills = state.bills.slice(0, 2).map((bill) => bill.merchant).filter(Boolean);
  const pendingTasks = Number(
    state.taskOverview?.pending_count ?? state.tasks.filter((task) => task.status === "pending").length,
  );
  return {
    title: entry?.title || `${diaryDateLabel(selectedDateKey)}的日记`,
    mood,
    moodLabel: diaryMoodLabel(mood),
    moodScore: diaryMoodScore(mood),
    moodQuality: diaryMoodQuality(mood),
    moodText: diaryMoodText(mood),
    weather: entry?.weather || "晴天",
    createdAt: entry?.updated_at || entry?.created_at || diaryEntryTimestamp(selectedDateKey),
    dateKey: selectedDateKey,
    dateLabel: diaryDateLabel(selectedDateKey),
    hasEntry: Boolean(entry),
    streakDays,
    monthEntries: diaryEntriesInMonth(selectedDateKey),
    attachmentIds: diaryAttachmentIdsForDate(selectedDateKey),
    tags: normalizeLabels(entry?.tags || [], []),
    body: entry?.content || [
      `${diaryDateLabel(selectedDateKey)}还没有保存日记，可以先留下一点生活记录。`,
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

function openDiaryAssistantPrompt(promptText) {
  const diary = getDiarySnapshot();
  const existingContent = diary.hasEntry
    ? diary.body.slice(0, 800)
    : "今天还没有保存正文。";
  const tags = diary.tags?.length ? diary.tags.join("、") : "暂无";
  const prompt = promptText || "帮我补全今天的日记。";
  const draft = [
    `日记追问：${prompt}`,
    `日期：${diary.dateLabel}`,
    `当前心情：${diary.moodLabel}`,
    `天气：${diary.weather}`,
    `标签：${tags}`,
    `已有内容：${existingContent}`,
    "请先围绕这个问题追问我一个更具体的小问题，帮助我把今天的日记写得更完整。",
  ].join("\n");

  state.activeAssistantToolId = "diary_reflection";
  openAssistantPage(draft);
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
          <h2 class="section-title">${escapeHtml(diary.dateLabel)}心情</h2>
        </div>
        <button class="diary-icon-button" type="button" data-open-diary-calendar aria-label="选择日记日期">
          ${icon("calendar")}
        </button>
      </div>
      <div class="diary-mood-body">
        <div class="diary-mood-card">
          <span class="diary-face ${escapeHtml(diary.mood)}" aria-hidden="true"></span>
          <div class="diary-mood-copy">
            <div>
              <strong>${escapeHtml(diary.moodLabel)}</strong>
              <span class="diary-quality-pill">${escapeHtml(diary.moodQuality)}</span>
            </div>
            <p>${escapeHtml(diary.moodText)}</p>
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
  const attachmentCount = diary.attachmentIds?.length || 0;
  return `
    <section class="surface diary-entry-section">
      <div class="diary-entry-header">
        <div class="diary-section-title">
          <span class="panel-icon">${icon("notebook")}</span>
          <h2 class="section-title">${escapeHtml(diary.title)}</h2>
        </div>
        <div class="diary-entry-meta">
          <span>${icon("calendar")}${escapeHtml(diary.dateLabel)}</span>
          <span>${icon("clock")}${formatDiaryTime(diary.createdAt)}</span>
          <span>${icon("sun")}${escapeHtml(diary.weather)}</span>
          <span class="is-soft">${icon("smile")}${escapeHtml(diary.moodLabel)}</span>
          ${attachmentCount ? `<span>${icon("image")}${attachmentCount} 张图片</span>` : ""}
          <button class="diary-more" type="button" data-open-diary-modal
            data-diary-date="${escapeHtml(diary.dateKey)}" aria-label="${diary.hasEntry ? "编辑日记" : "写日记"}">
            ${icon("more-horizontal")}
          </button>
        </div>
      </div>
      <div class="diary-entry-body">
        ${lines.map((line) => `<p>${escapeHtml(line)}</p>`).join("")}
      </div>
      ${diary.tags?.length ? `
        <div class="diary-tag-list">
          ${diary.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}
        </div>
      ` : ""}
    </section>
  `;
}

function renderDiaryCalendarModal() {
  const monthDate = dateFromMonthKey(state.diaryCalendarMonthKey || monthKeyFromDate(new Date()));
  const selectedKey = state.diarySelectedDateKey || todayDateKey();
  const days = diaryCalendarDays(monthDate);
  const monthLabel = monthDate.toLocaleDateString("zh-CN", { year: "numeric", month: "long" });
  const selectedEntry = diaryEntryForDate(selectedKey);
  const weekdays = ["一", "二", "三", "四", "五", "六", "日"];
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal diary-calendar-modal" role="dialog" aria-modal="true" aria-labelledby="diary-calendar-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="diary-calendar-title">日记日历</h2>
            <p class="section-note">有标记的日期写过日记，点开即可查看。</p>
          </div>
          <button class="button ghost" type="button" data-close-modal aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <div class="diary-calendar-toolbar">
          <button class="diary-calendar-nav is-prev" type="button" data-diary-calendar-nav="-1" aria-label="上个月">
            ${icon("chevron-right")}
          </button>
          <strong>${escapeHtml(monthLabel)}</strong>
          <button class="diary-calendar-nav" type="button" data-diary-calendar-nav="1" aria-label="下个月">
            ${icon("chevron-right")}
          </button>
        </div>
        <div class="diary-calendar-weekdays" aria-hidden="true">
          ${weekdays.map((day) => `<span>${day}</span>`).join("")}
        </div>
        <div class="diary-calendar-grid">
          ${days.map((day) => renderDiaryCalendarDay(day, monthDate, selectedKey)).join("")}
        </div>
        <div class="diary-calendar-footer">
          <div>
            <strong>${escapeHtml(diaryDateLabel(selectedKey))}</strong>
            <span>${selectedEntry ? "已写日记" : "还没有保存日记"}</span>
          </div>
          <div class="diary-calendar-actions">
            <button class="button ghost" type="button" data-diary-calendar-today>今天</button>
            <button class="button ghost" type="button" data-diary-calendar-done>完成</button>
            <button class="button primary" type="button" data-diary-calendar-write>
              ${icon("edit")}写这天
            </button>
          </div>
        </div>
      </section>
    </div>
  `;
}

function renderDiaryCalendarDay(day, monthDate, selectedKey) {
  const key = dateKeyFromDate(day);
  const isCurrentMonth = day.getMonth() === monthDate.getMonth();
  const isSelected = key === selectedKey;
  const isToday = key === todayDateKey();
  const hasEntry = Boolean(diaryEntryForDate(key));
  return `
    <button class="diary-calendar-day ${isCurrentMonth ? "" : "is-muted"} ${isSelected ? "is-selected" : ""} ${isToday ? "is-today" : ""} ${hasEntry ? "has-entry" : ""}"
      type="button" data-diary-date="${key}" aria-label="选择 ${escapeHtml(diaryDateLabel(key))}">
      <span>${day.getDate()}</span>
      ${hasEntry ? "<i></i>" : ""}
    </button>
  `;
}

function renderDiaryGallery(diary) {
  const attachmentIds = diary.attachmentIds || [];
  const photos = attachmentIds.length
    ? attachmentIds.slice(0, 3).map((id, index) => ["saved", `已保存图片 ${index + 1}`, id])
    : [
        ["coffee", "晨间咖啡", ""],
        ["window", "窗边时刻", ""],
        ["desk", "夜晚书桌", ""],
      ];
  return `
    <section class="surface diary-gallery-section">
      <div class="diary-section-header">
        <div class="diary-section-title">
          <span class="panel-icon">${icon("image")}</span>
          <h2 class="section-title">今日片段</h2>
        </div>
        <button class="button ghost" type="button" data-diary-photo-placeholder ${state.saving ? "disabled" : ""}>
          ${state.saving ? "上传中..." : attachmentIds.length ? "继续添加" : "添加图片"} ${icon("chevron-right")}
        </button>
      </div>
      <div class="diary-photo-grid">
        ${photos.map(([tone, label, id]) => renderDiaryPhotoCard(tone, label, id)).join("")}
      </div>
    </section>
  `;
}

function renderDiaryPhotoCard(tone, label, attachmentId = "") {
  if (attachmentId) {
    const contentUrl = attachmentContentUrl(attachmentId);
    return `
      <div class="diary-photo-card saved" aria-label="${escapeHtml(label)}">
        <a class="diary-photo-link" href="${contentUrl}" target="_blank" rel="noopener"
          aria-label="查看${escapeHtml(label)}" title="查看已保存图片">
          <img src="${contentUrl}" alt="${escapeHtml(label)}" loading="lazy" />
          <span class="diary-photo-label">${escapeHtml(label)}</span>
        </a>
        <button class="diary-photo-remove" type="button" data-diary-photo-remove
          data-attachment-id="${escapeHtml(attachmentId)}" aria-label="移除${escapeHtml(label)}"
          ${state.saving ? "disabled" : ""}>
          ${icon("close")}
        </button>
      </div>
    `;
  }

  return `
    <button class="diary-photo-card ${tone}" type="button" data-diary-photo-placeholder
      aria-label="${escapeHtml(label)}" ${attachmentId ? `title="附件 ${escapeHtml(attachmentId)}"` : ""}>
      <span class="photo-scene" aria-hidden="true"></span>
      <span>${escapeHtml(label)}</span>
    </button>
  `;
}

function attachmentContentUrl(attachmentId) {
  return `/attachments/${encodeURIComponent(attachmentId)}/content`;
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
                <button class="ai-diary-prompt" type="button" data-diary-ai-prompt="${escapeHtml(text)}">
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

function renderDiaryActionDock(diary) {
  const actionLabel = diary?.hasEntry ? "编辑日记" : "写日记";
  const actionIcon = diary?.hasEntry ? "edit" : "plus";
  return `
    <section class="diary-action-dock" aria-label="日记操作">
      <button class="diary-dock-side" type="button" data-voice-placeholder>
        ${icon("mic")}语音日记
      </button>
      <button class="diary-dock-main" type="button" data-open-diary-modal
        data-diary-date="${escapeHtml(diary?.dateKey || todayDateKey())}">
        ${icon(actionIcon)}${actionLabel}
      </button>
      <button class="diary-dock-side" type="button" data-diary-photo-placeholder ${state.saving ? "disabled" : ""}>
        ${icon("image")}${state.saving ? "上传中..." : "添加图片"}
      </button>
    </section>
  `;
}

function diaryMoodLabel(value) {
  return {
    happy: "开心",
    calm: "平静",
    tired: "疲惫",
    anxious: "有压力",
    sad: "低落",
  }[value] ?? "开心";
}

function diaryMoodScore(value) {
  return {
    happy: 86,
    calm: 78,
    tired: 52,
    anxious: 58,
    sad: 46,
  }[value] ?? 80;
}

function diaryMoodQuality(value) {
  return {
    happy: "很好",
    calm: "平稳",
    tired: "需休息",
    anxious: "放慢点",
    sad: "抱抱自己",
  }[value] ?? "很好";
}

function diaryMoodText(value) {
  return {
    happy: "阳光正好，心情很棒。",
    calm: "今天节奏平稳，适合温柔收尾。",
    tired: "今天有点累，适合早点休息。",
    anxious: "事情有点多，可以先把最重要的一件放前面。",
    sad: "允许自己慢一点，记录下来也是一种照顾。",
  }[value] ?? "阳光正好，心情很棒。";
}

function formatDiaryTime(value) {
  const date = value ? new Date(value) : new Date();
  if (Number.isNaN(date.getTime())) {
    return "未设置";
  }
  const prefix = dateKeyFromDate(date) === todayDateKey() ? "今天" : formatMonthDay(date);
  return `${prefix} ${date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
}

function defaultRepeatStartDate() {
  const date = new Date();
  date.setHours(date.getHours() + 1, 0, 0, 0);
  return date;
}

function repeatPreviewDates(startAt, frequency, count) {
  return Array.from({ length: count }, (_, index) => addRepeatInterval(startAt, frequency, index));
}

function todayDateKey() {
  return dateKeyFromDate(new Date());
}

function dateKeyFromDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function dateFromDateKey(dateKey) {
  const [year, month, day] = String(dateKey || todayDateKey()).split("-").map(Number);
  return new Date(year, (month || 1) - 1, day || 1);
}

function monthKeyFromDate(date) {
  return dateKeyFromDate(date).slice(0, 7);
}

function dateFromMonthKey(monthKey) {
  const [year, month] = String(monthKey || monthKeyFromDate(new Date())).split("-").map(Number);
  return new Date(year, (month || 1) - 1, 1);
}

function shiftMonthKey(monthKey, delta) {
  const date = dateFromMonthKey(monthKey);
  date.setMonth(date.getMonth() + delta);
  return monthKeyFromDate(date);
}

function diaryCalendarDays(monthDate) {
  const first = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1);
  const mondayOffset = (first.getDay() + 6) % 7;
  const start = new Date(first);
  start.setDate(first.getDate() - mondayOffset);
  return Array.from({ length: 42 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return day;
  });
}

function diaryDateLabel(dateKey) {
  const date = dateFromDateKey(dateKey);
  if (dateKey === todayDateKey()) {
    return "今天";
  }
  return date.toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
}

function diaryEntryTimestamp(dateKey) {
  const date = dateFromDateKey(dateKey);
  const now = new Date();
  date.setHours(now.getHours(), now.getMinutes(), 0, 0);
  return date.toISOString();
}

function diaryEntryForDate(dateKey) {
  return state.diaryEntries.find((entry) => entry.dateKey === dateKey)
    ?? (state.diaryDraft?.dateKey === dateKey ? state.diaryDraft : null);
}

function diaryEntriesInMonth(dateKey) {
  const monthKey = String(dateKey || todayDateKey()).slice(0, 7);
  return state.diaryEntries.filter((entry) => entry.dateKey?.startsWith(monthKey)).length;
}

function diaryStreakDays() {
  const keys = new Set(state.diaryEntries.map((entry) => entry.dateKey));
  let cursor = dateFromDateKey(todayDateKey());
  let count = 0;
  while (keys.has(dateKeyFromDate(cursor))) {
    count += 1;
    cursor.setDate(cursor.getDate() - 1);
  }
  return count;
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
  const summary = state.bootstrap?.data_summary ?? {};
  const snapshot = state.snapshotStatus;
  const row = (symbol, title, note, attribute) => `<button class="simple-setting-row" type="button" ${attribute} ${state.saving ? "disabled" : ""}>${icon(symbol)}<span><strong>${title}</strong><small>${note}</small></span>${icon("chevron-right")}</button>`;
  return `<div class="simple-settings">
    <header class="simple-page-header"><div><p class="simple-kicker">按你的习惯来</p><h1>更多与设置</h1><p>日常工具、个人偏好和数据管理。</p></div></header>
    <section class="surface simple-settings-group"><h2>生活记录</h2>${row("check", "待办事项", "查看、新增和完成待办", 'data-route="tasks"')}${row("book", "我的日记", "记录文字、照片和心情", 'data-route="diary"')}</section>
    <section class="surface simple-settings-group"><h2>记账偏好</h2>${row("pie-chart", "月预算", `当前预算 ${money(getBudgetSettings().monthly_budget)}`, "data-open-budget-settings")}${row("grid", "收支分类", "调整餐饮、交通等常用分类", "data-open-category-settings")}${row("settings", "隐私设置", "选择图片和文字是否允许交给外部 AI 处理", "data-open-privacy-settings")}</section>
    <section class="surface simple-settings-group"><h2>我的数据</h2>${row("download", "导出备份文件", "下载账单、待办和日记，方便保留或迁移", "data-export-json")}${row("upload", "从备份文件恢复", "选择之前导出的文件，预览后再导入", "data-import-json")}${row("trash", "回收站", escapeHtml(recycleBinText(summary)), "data-open-recycle-bin")}</section>
    <details class="surface simple-details"><summary><span>更多设置</span><small>个人资料、备份与问题排查 ${icon("chevron-right")}</small></summary><div class="simple-details-content">
      ${row("user", "个人资料", "修改昵称和签名", "data-profile-placeholder")}${row("tag", "日记标签", "管理记录生活的常用标签", "data-open-tag-settings")}
      ${row("save", "保存本机备份", "在当前设备上保留一份可恢复的记录", "data-snapshot-save")}
      ${snapshot?.exists ? row("refresh", "恢复本机备份", escapeHtml(snapshotText(snapshot)), 'data-settings-action="loadSnapshot"') : ""}
      ${row("file-text", "最近操作", "查看记录的新增、修改和删除操作", "data-open-audit-log")}${row("check-circle", "连接与问题排查", "识别不可用时，在这里查看原因", "data-open-diagnostics")}
      <div class="simple-danger-zone">${row("trash", "清空所有记录", "清空前会再次确认，建议先导出备份", 'data-settings-action="clear"')}</div>
    </div></details>
  </div>`;
}

function renderProfileSettingsModal() {
  const profile = normalizeProfileSettings(state.profile);
  const avatarOptions = [
    ["warm", "暖阳"],
    ["mint", "薄荷"],
    ["blue", "天空"],
    ["rose", "粉桃"],
  ];
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal compact-modal profile-settings-modal" role="dialog" aria-modal="true" aria-labelledby="profile-settings-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="profile-settings-title">个人资料</h2>
            <p class="section-note">用于个人页问候展示，暂存在当前浏览器。</p>
          </div>
          <button class="button ghost" type="button" data-close-profile-settings aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <form class="form profile-settings-form" data-profile-form>
          <div class="profile-settings-preview">
            <span class="profile-avatar tone-${escapeHtml(profile.avatarTone)}" aria-hidden="true">
              <span class="avatar-face"></span>
            </span>
            <div>
              <strong>Hi，${escapeHtml(profile.displayName)}</strong>
              <span>${escapeHtml(profile.signature)}</span>
            </div>
          </div>
          <div class="form-grid">
            <div class="field full">
              <label for="profile_display_name">问候昵称</label>
              <input id="profile_display_name" name="display_name" maxlength="18" required
                value="${escapeHtml(profile.displayName)}" placeholder="今天也要加油呀" />
            </div>
            <div class="field full">
              <label for="profile_signature">生活签名</label>
              <input id="profile_signature" name="signature" maxlength="36" required
                value="${escapeHtml(profile.signature)}" placeholder="记录生活，遇见更好的自己" />
            </div>
            <div class="field full">
              <label for="profile_avatar_tone">头像色调</label>
              <select id="profile_avatar_tone" name="avatar_tone">
                ${avatarOptions
                  .map(([value, label]) => `
                    <option value="${escapeHtml(value)}" ${profile.avatarTone === value ? "selected" : ""}>
                      ${escapeHtml(label)}
                    </option>
                  `)
                  .join("")}
              </select>
            </div>
          </div>
          <div class="form-actions">
            <button class="button ghost" type="button" data-close-profile-settings>取消</button>
            <button class="button primary" type="submit">${icon("save")}保存资料</button>
          </div>
        </form>
      </section>
    </div>
  `;
}

function renderNotificationModal() {
  const groups = getNotificationGroups();
  const total = groups.overdue.length + groups.today.length + groups.upcoming.length;
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal notification-modal" role="dialog" aria-modal="true" aria-labelledby="notification-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="notification-title">通知中心</h2>
            <p class="section-note">看看今天和接下来有哪些待办事项。</p>
          </div>
          <button class="button ghost" type="button" data-close-modal aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <div class="notification-summary" aria-label="提醒摘要">
          ${notificationMetric("逾期", groups.overdue.length, "danger")}
          ${notificationMetric("今日", groups.today.length, "mint")}
          ${notificationMetric("即将到来", groups.upcoming.length, "blue")}
        </div>
        <div class="notification-body">
          ${total ? `
            ${renderNotificationSection("逾期待处理", groups.overdue, "danger")}
            ${renderNotificationSection("今天要处理", groups.today, "mint")}
            ${renderNotificationSection("未来提醒", groups.upcoming, "blue")}
          ` : renderNotificationEmpty()}
        </div>
      </section>
    </div>
  `;
}

function getProfileNotificationCount() {
  const overview = state.taskOverview ?? {};
  const overdue = Number(overview.overdue_count ?? 0);
  const today = Number(overview.due_today_count ?? 0);
  const upcoming = Number(overview.upcoming_reminder_count ?? 0);
  const total = overdue + today + upcoming;
  if (total) {
    return total;
  }
  return allLoadedTasks().filter((task) => task.status === "pending" && taskTargetDate(task)).length;
}

function getNotificationGroups() {
  const overview = state.taskOverview ?? {};
  const now = new Date();
  const seen = new Set();
  const take = (tasks) => uniqueTasks(tasks)
    .filter((task) => task.status === "pending")
    .filter((task) => {
      if (!task?.id || seen.has(task.id)) {
        return false;
      }
      seen.add(task.id);
      return true;
    })
    .sort(compareReminderTasks)
    .slice(0, 5);

  const overdue = take(overview.overdue_tasks ?? []);
  const today = take([...(overview.today_tasks ?? []), ...allLoadedTasks().filter(isTodayTask)]);
  const upcoming = take([
    ...(overview.upcoming_reminders ?? []),
    ...allLoadedTasks().filter((task) => {
      const target = taskTargetDate(task);
      return target && target > now && !isTodayTask(task);
    }),
  ]);

  return { overdue, today, upcoming };
}

function notificationMetric(label, value, tone) {
  return `
    <div class="notification-metric ${tone}">
      <span>${escapeHtml(label)}</span>
      <strong>${value}</strong>
    </div>
  `;
}

function renderNotificationSection(title, items, tone) {
  if (!items.length) {
    return "";
  }
  return `
    <section class="notification-section">
      <h3>${escapeHtml(title)}</h3>
      <div class="notification-list">
        ${items.map((task) => renderNotificationItem(task, tone)).join("")}
      </div>
    </section>
  `;
}

function renderNotificationItem(task, tone) {
  return `
    <article class="notification-item ${tone}">
      <span class="notification-icon">${icon(iconForTask(task))}</span>
      <div class="notification-main">
        <strong>${escapeHtml(task.title || "未命名提醒")}</strong>
        <small>${escapeHtml(task.category || "生活")} · ${shortTaskTime(task)} · ${labelTaskPriority(task.priority)}</small>
      </div>
      <div class="notification-actions">
        <button class="icon-button" type="button" data-edit-task="${escapeHtml(task.id)}"
          aria-label="编辑 ${escapeHtml(task.title || "提醒")}" ${state.saving ? "disabled" : ""}>
          ${icon("edit")}
        </button>
        <button class="icon-button" type="button" data-complete-task="${escapeHtml(task.id)}"
          aria-label="完成 ${escapeHtml(task.title || "提醒")}" ${state.saving ? "disabled" : ""}>
          ${icon("check-circle")}
        </button>
      </div>
    </article>
  `;
}

function renderNotificationEmpty() {
  return `
    <div class="notification-empty">
      <span>${icon("bell")}</span>
      <div>
        <strong>当前没有待处理提醒</strong>
        <small>新的待办、提醒和重复提醒会自动出现在这里。</small>
      </div>
      <button class="button ghost" type="button" data-close-modal>${icon("check")}知道了</button>
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
      backendPercent: Number(item.percentage ?? NaN),
    }))
    .filter((item) => item.amount > 0)
    .slice(0, 4);

  if (!source.length) {
    return [{ category: "暂无记录", amount: 0, percent: 100, empty: true }];
  }

  const total = expense > 0 ? expense : source.reduce((sum, item) => sum + item.amount, 0);
  return source.map((item) => {
    const computedPercent = total > 0 ? Math.max(1, Math.round((item.amount / total) * 100)) : 0;
    return {
      category: item.category,
      amount: item.amount,
      percent: Number.isFinite(item.backendPercent) ? Math.max(0, Math.round(item.backendPercent)) : computedPercent,
    };
  });
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
      ${profileShortcut("spark", "智能助手", "语音对话操作", "data-route=\"assistant\"", "blue")}
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
        <button class="button ghost" type="button" data-route="settings">
          全部工具 ${icon("chevron-right")}
        </button>
      </div>
      <div class="profile-tool-grid">
        ${profileTool("pie-chart", "预算管理", "data-open-budget-settings", "mint")}
        ${profileTool("file-text", "账单导出", "data-export-json", "blue")}
        ${profileTool("grid", "分类管理", "data-open-category-settings", "orange")}
        ${profileTool("tag", "标签管理", "data-open-tag-settings", "mint")}
        ${profileTool("cloud", "数据备份", "data-snapshot-save", "blue")}
        ${profileTool("upload", "数据导入", "data-import-json", "mint")}
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
        <button class="button ghost" type="button" data-route="settings">
          查看全部 ${icon("chevron-right")}
        </button>
      </div>
      <div class="profile-data-grid">
        ${profileDataCard("calendar", "记账笔数", billCount, "笔", "后端账单", "mint")}
        ${profileDataCard("notebook", "日记篇数", diaryCount, "篇", "后端日记", "blue")}
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
  const summary = state.bootstrap?.data_summary ?? {};
  const snapshot = state.snapshotStatus;
  const deletedCount = deletedDataCount(summary);
  return `
    <section class="surface profile-safety-panel">
      <div>
        <h2 class="section-title">数据与隐私</h2>
        <p>${privacy.local_only_mode ? "本地体验已开启" : "本地体验未开启"} · ${escapeHtml(snapshotText(snapshot))}</p>
        ${renderPrivacySummary(privacy)}
      </div>
      <div class="profile-safety-actions">
        <button class="button ghost" type="button" data-open-privacy-settings ${state.saving ? "disabled" : ""}>
          ${icon("settings")}隐私设置
        </button>
        <button class="button ghost" type="button" data-open-diagnostics ${state.saving ? "disabled" : ""}>
          ${icon("check-circle")}系统自检
        </button>
        <button class="button ghost" type="button" data-open-audit-log ${state.saving ? "disabled" : ""}>
          ${icon("file-text")}最近操作
        </button>
        <button class="button ghost" type="button" data-open-recycle-bin ${state.saving ? "disabled" : ""}>
          ${icon("refresh")}回收站${deletedCount ? ` ${deletedCount}` : ""}
        </button>
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

function renderPrivacySummary(privacy = {}) {
  return `
    <div class="privacy-summary" aria-label="隐私状态">
      ${privacySummaryChip("AI", Boolean(privacy.allow_ai_text_processing))}
      ${privacySummaryChip("原件", Boolean(privacy.save_original_attachments_by_default))}
      ${privacySummaryChip("OCR", Boolean(privacy.keep_ocr_text))}
    </div>
  `;
}

function privacySummaryChip(label, enabled) {
  return `
    <span class="privacy-chip ${enabled ? "is-on" : "is-off"}">
      ${escapeHtml(label)} ${enabled ? "开" : "关"}
    </span>
  `;
}

function privacySummaryText(privacy = {}) {
  const localText = privacy.local_only_mode ? "本地体验已开启" : "本地体验未开启";
  const aiText = privacy.allow_ai_text_processing ? "AI 解析开启" : "AI 解析关闭";
  const attachmentText = privacy.save_original_attachments_by_default ? "保留上传的原图" : "默认不保存原始附件";
  const ocrText = privacy.keep_ocr_text ? "保留图片识别出的文字" : "不保留图片识别出的文字";
  return `${localText}，${aiText}，${attachmentText}，${ocrText}。`;
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
        ${metric("日记", summary.diary_count ?? state.diaryEntries.length ?? 0, "small")}
        ${metric("附件", summary.attachment_count ?? 0, "small")}
        ${metric("候选", Number(summary.bill_candidate_count ?? 0) + Number(summary.task_candidate_count ?? 0) + Number(summary.diary_candidate_count ?? 0), "small")}
      </div>
      <div class="settings-list">
        ${settingsRow(
          "隐私模式",
          privacySummaryText(privacy),
          `
            <button class="button ghost" type="button" data-open-privacy-settings ${state.saving ? "disabled" : ""}>
              ${icon("settings")}隐私设置
            </button>
            <span class="muted-value">OCR: ${escapeHtml(caps.ocr_provider ?? "unknown")}</span>
            <span class="muted-value">AI: ${escapeHtml(caps.ai_text_parser ?? "unknown")}</span>
          `,
        )}
        ${settingsRow(
          "数据导出",
          "导出当前活跃账单、待办、日记、附件元数据和候选记录；也可导入此前导出的 JSON。",
          `
            <button class="button" type="button" data-export-json ${state.saving ? "disabled" : ""}>
              ${icon("download")}JSON
            </button>
            <button class="button ghost" type="button" data-import-json ${state.saving ? "disabled" : ""}>
              ${icon("upload")}导入 JSON
            </button>
            <a class="button ghost" href="/data/export/bills.csv" download>${icon("download")}账单 CSV</a>
            <a class="button ghost" href="/data/export/tasks.csv" download>${icon("download")}待办 CSV</a>
            <a class="button ghost" href="/data/export/diaries.csv" download>${icon("download")}日记 CSV</a>
            <a class="button ghost" href="/data/export/attachments.csv" download>${icon("download")}附件 CSV</a>
            <a class="button ghost" href="/data/export/bill-candidates.csv" download>${icon("download")}账单候选 CSV</a>
            <a class="button ghost" href="/data/export/task-candidates.csv" download>${icon("download")}待办候选 CSV</a>
            <a class="button ghost" href="/data/export/diary-candidates.csv" download>${icon("download")}日记候选 CSV</a>
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
          "回收站",
          recycleBinText(summary),
          `
            <button class="button ghost" type="button" data-open-recycle-bin ${state.saving ? "disabled" : ""}>
              ${icon("refresh")}查看回收站
            </button>
          `,
        )}
        ${settingsRow(
          "清除本地数据",
          "清空当前内存中的账单、待办、日记、附件和候选记录。建议先导出或保存快照。",
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

function financeProgress(monthly, budgetSettings = getBudgetSettings()) {
  const expense = Number(monthly.total_expense ?? 0);
  const monthlyBudget = Number(budgetSettings.monthly_budget ?? 0);
  if (monthlyBudget <= 0) {
    return 0;
  }
  return Math.min(100, Math.round((expense / monthlyBudget) * 100));
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
  const tabs = [["dashboard", "首页", "home"], ["bills", "账单", "receipt"], ["assistant", "AI 帮记", "spark"], ["settings", "更多", "grid"]];
  return `<nav class="mobile-tabbar" aria-label="底部导航">${tabs.map(([id, label, symbol]) => `<button class="tab-button ${state.route === id || (id === "settings" && ["tasks", "diary"].includes(state.route)) ? "is-active" : ""}" type="button" data-route="${id}" ${state.route === id ? 'aria-current="page"' : ""}>${icon(symbol)}<span>${label}</span></button>`).join("")}</nav>`;
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
                <p class="item-title">${escapeHtml(billDisplayName(bill))}</p>
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

function renderBillRangeModal() {
  const filters = state.billFilters;
  const defaultRange = filters.period === "month"
    ? localMonthRange(filters.year, filters.month)
    : localWeekRange(new Date());
  const startDate = filters.start_date || dateKeyFromDate(defaultRange.start);
  const endDate = filters.end_date || dateKeyFromDate(defaultRange.end);
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal compact-modal bill-range-modal" role="dialog" aria-modal="true" aria-labelledby="bill-range-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="bill-range-title">账单筛选</h2>
            <p class="section-note">选择时间、分类或收支类型，找到你要的账单。</p>
          </div>
          <button class="button ghost" type="button" data-close-modal aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <form class="form" data-bill-range-form>
          <div class="form-grid">
            <div class="field">
              <label for="bill_range_start">开始日期</label>
              <input id="bill_range_start" name="start_date" type="date"
                value="${escapeHtml(startDate)}" />
            </div>
            <div class="field">
              <label for="bill_range_end">结束日期</label>
              <input id="bill_range_end" name="end_date" type="date"
                value="${escapeHtml(endDate)}" />
            </div>
            <div class="field">
              <label for="bill_range_type">类型</label>
              <select id="bill_range_type" name="transaction_type">
                <option value="">全部</option>
                ${transactionOptions(filters.transaction_type)}
              </select>
            </div>
            <div class="field">
              <label for="bill_range_category">分类</label>
              <input id="bill_range_category" name="category" maxlength="40" list="bill_category_options" placeholder="如 餐饮"
                value="${escapeHtml(filters.category)}" />
            </div>
            <div class="field full">
              <label for="bill_range_q">关键词</label>
              <input id="bill_range_q" name="q" maxlength="80" placeholder="商家/用途、分类、支付方式或备注"
                value="${escapeHtml(filters.q)}" />
            </div>
          </div>
          <p class="form-hint">日期为空时表示不限制该方向；本月、本周按钮会快速切换范围。</p>
          <div class="form-actions">
            <button class="button ghost" type="button" data-reset-bill-filters>${icon("reset")}恢复本月</button>
            <button class="button primary" type="submit" ${state.saving ? "disabled" : ""}>
              ${icon("search")}应用筛选
            </button>
          </div>
        </form>
      </section>
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
        <input id="filter_category" name="category" maxlength="40" list="bill_category_options" placeholder="如 餐饮"
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
        <input id="filter_q" name="q" maxlength="80" placeholder="商家/用途、分类、备注"
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
            <th>商家/用途</th>
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
                  <td>${escapeHtml(billDisplayName(bill))}</td>
                  <td>${escapeHtml(bill.category)}</td>
                  <td>${labelTransaction(bill.transaction_type)}</td>
                  <td>${formatDate(bill.paid_at)}</td>
                  <td class="amount ${bill.transaction_type}">${money(bill.amount)}</td>
                  <td>
                    <div class="table-actions">
                      <button class="icon-button" type="button" data-edit-bill="${bill.id}" aria-label="编辑 ${escapeHtml(billDisplayName(bill))}" title="编辑">
                        ${icon("edit")}
                      </button>
                      <button class="icon-button danger" type="button" data-delete-bill="${bill.id}" aria-label="删除 ${escapeHtml(billDisplayName(bill))}" title="删除">
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
  return `<div class="bill-feed simple-bill-feed">${bills.map(bill => `<button class="bill-feed-item simple-bill-row" type="button" data-edit-bill="${escapeHtml(bill.id)}" aria-label="查看账单：${escapeHtml(billDisplayName(bill))}，${escapeHtml(labelTransaction(bill.transaction_type))} ${money(bill.amount)}">
    <span class="bill-feed-icon">${icon(iconForBill(bill))}</span><span class="simple-bill-description"><strong>${escapeHtml(billDisplayName(bill))}</strong><small>${escapeHtml(bill.category)} · ${formatDate(bill.paid_at)}${bill.payment_method ? ` · ${escapeHtml(bill.payment_method)}` : ""}</small></span>
    <span class="simple-bill-amount ${escapeHtml(bill.transaction_type)}"><strong>${signedMoney(bill)}</strong><small>${escapeHtml(labelTransaction(bill.transaction_type))}</small></span>${icon("chevron-right")}
  </button>`).join("")}</div>`;
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
                <button class="icon-button" type="button" data-edit-task="${task.id}"
                  aria-label="编辑 ${escapeHtml(task.title)}" title="编辑"
                  ${state.saving ? "disabled" : ""}>
                  ${icon("edit")}
                </button>
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
                <button class="icon-button danger" type="button" data-delete-task="${task.id}"
                  aria-label="删除 ${escapeHtml(task.title)}" title="删除"
                  ${state.saving ? "disabled" : ""}>
                  ${icon("trash")}
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
  const bill = state.billDraft ?? state.editingBill;
  const isEditing = Boolean(state.editingBill?.id);
  const fromImage = Boolean(bill?.source === "album" || bill?.source === "screenshot");
  const title = isEditing ? "修改账单" : fromImage ? "核对这笔账单" : "记一笔";
  const categories = [...new Set(["其他", ...getCategorySettings().bill_categories, bill?.category].filter(Boolean))];
  return `<div class="modal-backdrop" role="presentation"><section class="modal simple-bill-modal" role="dialog" aria-modal="true" aria-labelledby="bill-modal-title">
    <div class="modal-header"><div><h2 class="modal-title" id="bill-modal-title">${title}</h2><p class="section-note">${fromImage ? "请核对金额和收支类型，其他信息可以之后再补。" : "填好金额和收支类型，就能保存。"}</p></div><button class="button ghost" type="button" data-close-modal aria-label="关闭" ${state.saving ? "disabled" : ""}>${icon("close")}</button></div>
    ${bill?.needs_manual_entry ? '<p class="simple-notice">暂时没能读出图片内容。只要补上金额，就可以先保存。</p>' : ""}
    <form class="form" data-bill-form>
      <div class="simple-amount-field"><div class="field"><label for="amount">金额（元）</label><input id="amount" name="amount" type="number" inputmode="decimal" min="0.01" step="0.01" required placeholder="0.00" value="${escapeHtml(bill?.amount ?? "")}" /></div><div class="field"><label for="transaction_type">收支类型</label><select id="transaction_type" name="transaction_type">${transactionOptions(bill?.transaction_type ?? "expense")}</select></div></div>
      <div class="form-grid">
        <div class="field full"><label for="merchant">商家或用途 <small>选填</small></label><input id="merchant" name="merchant" maxlength="120" placeholder="例如：午餐、超市购物、工资" value="${escapeHtml(bill?.merchant ?? "")}" /></div>
        <div class="field"><label for="category">分类</label><select id="category" name="category">${categories.map(value => `<option value="${escapeHtml(value)}" ${value === (bill?.category || "其他") ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}</select></div>
        <div class="field"><label for="paid_at">记账时间 <small>选填</small></label><input id="paid_at" name="paid_at" type="datetime-local" value="${escapeHtml(toDateTimeLocal(bill?.paid_at || new Date().toISOString()))}" /></div>
      </div>
      <details class="simple-details simple-form-details" data-bill-details ${state.billDetailsOpen ? "open" : ""}><summary><span>支付方式和备注</span><small>选填 ${icon("chevron-right")}</small></summary><div class="simple-details-content form-grid">
        <div class="field full"><label for="payment_method">支付方式</label><input id="payment_method" name="payment_method" list="payment-method-options" maxlength="40" placeholder="例如：微信、支付宝、现金" value="${escapeHtml(bill?.payment_method ?? "")}" /><datalist id="payment-method-options"><option value="微信支付"></option><option value="支付宝"></option><option value="银行卡"></option><option value="现金"></option></datalist></div>
        <div class="field full"><label for="note">备注</label><textarea id="note" name="note" maxlength="500" placeholder="想补充的信息，留空也可以">${escapeHtml(bill?.note ?? "")}</textarea></div>
      </div></details>
      <div class="form-actions">${isEditing ? `<button class="button ghost danger simple-delete" type="button" data-delete-bill="${escapeHtml(state.editingBill.id)}" ${state.saving ? "disabled" : ""}>${icon("trash")}删除</button>` : ""}<button class="button ghost" type="button" data-close-modal ${state.saving ? "disabled" : ""}>取消</button><button class="button primary" type="submit" ${state.saving ? "disabled" : ""}>${icon("check")}${state.saving ? "正在保存…" : isEditing ? "保存修改" : "保存账单"}</button></div>
    </form>
  </section></div>`;
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
          <p class="item-title">${escapeHtml(billDisplayName(bill))}</p>
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

function renderDeleteTaskModal() {
  const task = state.taskDeleteTarget;
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal compact-modal" role="dialog" aria-modal="true" aria-labelledby="delete-task-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="delete-task-title">删除待办</h2>
            <p class="section-note">这会将待办移入软删除状态，删除后短时间内可以撤销。</p>
          </div>
          <button class="button ghost" type="button" data-cancel-task-delete aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <div class="confirm-body">
          <p class="item-title">${escapeHtml(task?.title ?? "待办")}</p>
          <p class="item-meta">${escapeHtml(task?.category ?? "生活")} · ${labelTaskStatus(task?.status)} · ${taskTargetText(task)}</p>
        </div>
        <div class="form-actions modal-actions">
          <button class="button ghost" type="button" data-cancel-task-delete>取消</button>
          <button class="button danger" type="button" data-confirm-task-delete ${state.saving ? "disabled" : ""}>
            ${icon("trash")}${state.saving ? "删除中..." : "确认删除"}
          </button>
        </div>
      </section>
    </div>
  `;
}

function renderDeleteDiaryModal() {
  const diary = state.diaryDeleteTarget;
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal compact-modal" role="dialog" aria-modal="true" aria-labelledby="delete-diary-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="delete-diary-title">删除日记</h2>
            <p class="section-note">这会将当前日记移入软删除状态，后续可通过后端恢复能力接回。</p>
          </div>
          <button class="button ghost" type="button" data-cancel-diary-delete aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <div class="confirm-body">
          <p class="item-title">${escapeHtml(diary?.title ?? "日记")}</p>
          <p class="item-meta">${escapeHtml(diaryDateLabel(diary?.dateKey || todayDateKey()))} · ${escapeHtml(diary?.mood ? diaryMoodLabel(diary.mood) : "未标记心情")}</p>
        </div>
        <div class="form-actions modal-actions">
          <button class="button ghost" type="button" data-cancel-diary-delete>取消</button>
          <button class="button danger" type="button" data-confirm-diary-delete ${state.saving ? "disabled" : ""}>
            ${icon("trash")}${state.saving ? "删除中..." : "确认删除"}
          </button>
        </div>
      </section>
    </div>
  `;
}

function renderTaskModal() {
  const task = state.editingTask;
  const isEditing = Boolean(task?.id);
  const taskType = task?.task_type || "todo";
  const priority = task?.priority || "medium";
  return `<div class="modal-backdrop" role="presentation"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="task-modal-title">
    <div class="modal-header"><div><h2 class="modal-title" id="task-modal-title">${isEditing ? "修改事项" : "添加事项"}</h2><p class="section-note">写下要做的事。还没定好时间，也可以先记下来。</p></div><button class="button ghost" type="button" data-close-modal aria-label="关闭">${icon("close")}</button></div>
    <form class="form" data-task-form>
      <div class="field"><label for="task_title">要做什么</label><input id="task_title" name="title" required maxlength="120" placeholder="例如：交房租、买牛奶" value="${escapeHtml(task?.title || "")}" /></div>
      <div class="field"><label for="task_due_at">计划完成时间 <small>选填</small></label><input id="task_due_at" name="due_at" type="datetime-local" value="${escapeHtml(toDateTimeLocal(task?.due_at))}" /></div>
      <details class="simple-details simple-form-details" ${isEditing ? "open" : ""}><summary><span>分类、重要程度和备注</span><small>选填 ${icon("chevron-right")}</small></summary><div class="simple-details-content form-grid">
        <div class="field"><label for="task_category">分类</label><input id="task_category" name="category" maxlength="40" list="task_category_options" value="${escapeHtml(task?.category || "生活")}" /></div>
        <div class="field"><label for="task_priority">重要程度</label><select id="task_priority" name="priority"><option value="medium" ${priority === "medium" ? "selected" : ""}>普通</option><option value="high" ${priority === "high" ? "selected" : ""}>重要</option><option value="low" ${priority === "low" ? "selected" : ""}>不着急</option></select></div>
        <div class="field"><label for="task_type">事项类型</label><select id="task_type" name="task_type"><option value="todo" ${taskType === "todo" ? "selected" : ""}>普通待办</option><option value="reminder" ${taskType === "reminder" ? "selected" : ""}>定时事项</option></select></div>
        <div class="field"><label for="task_remind_at">提醒时间 <small>仅用于页面查看</small></label><input id="task_remind_at" name="remind_at" type="datetime-local" value="${escapeHtml(toDateTimeLocal(task?.remind_at))}" /></div>
        <div class="field full"><label for="task_description">备注</label><textarea id="task_description" name="description" maxlength="500" placeholder="需要带什么，或其他想补充的信息">${escapeHtml(task?.description || "")}</textarea></div>
      </div></details>
      <div class="form-actions"><button class="button ghost" type="button" data-close-modal>取消</button><button class="button primary" type="submit" ${state.saving ? "disabled" : ""}>${icon("check")}${state.saving ? "正在保存…" : "保存事项"}</button></div>
    </form>
  </section></div>`;
}

function renderRepeatTaskModal() {
  const defaultStart = defaultRepeatStartDate();
  const previewDates = repeatPreviewDates(defaultStart, "weekly", 3);
  const defaultTaskCategory = getCategorySettings().task_categories[0] || "生活";
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal repeat-task-modal" role="dialog" aria-modal="true" aria-labelledby="repeat-task-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="repeat-task-title">重复提醒</h2>
            <p class="section-note">按规则生成多条独立提醒，真实保存到后端任务数据里。</p>
          </div>
          <button class="button ghost" type="button" data-close-modal aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <form class="form" data-repeat-task-form>
          <div class="form-grid">
            <div class="field full">
              <label for="repeat_task_title">提醒标题</label>
              <input id="repeat_task_title" name="title" required maxlength="120" placeholder="每周复盘" />
            </div>
            <div class="field">
              <label for="repeat_task_frequency">重复频率</label>
              <select id="repeat_task_frequency" name="frequency">
                <option value="daily">每天</option>
                <option value="weekly" selected>每周</option>
                <option value="biweekly">每两周</option>
                <option value="monthly">每月</option>
              </select>
            </div>
            <div class="field">
              <label for="repeat_task_count">生成次数</label>
              <input id="repeat_task_count" name="count" type="number" min="2" max="30" step="1" value="6" />
            </div>
            <div class="field">
              <label for="repeat_task_start_at">首次提醒</label>
              <input id="repeat_task_start_at" name="start_at" type="datetime-local"
                value="${escapeHtml(toDateTimeLocal(defaultStart))}" />
            </div>
            <div class="field">
              <label for="repeat_task_priority">优先级</label>
              <select id="repeat_task_priority" name="priority">
                <option value="medium">普通</option>
                <option value="high">高</option>
                <option value="low">低</option>
              </select>
            </div>
            <div class="field">
              <label for="repeat_task_category">分类</label>
              <input id="repeat_task_category" name="category" required maxlength="40" list="task_category_options"
                value="${escapeHtml(defaultTaskCategory)}" />
            </div>
            <div class="field full">
              <label for="repeat_task_description">备注</label>
              <textarea id="repeat_task_description" name="description" maxlength="500" placeholder="可选，比如提前准备材料。"></textarea>
            </div>
          </div>
          <div class="repeat-rule-note">
            <span>${icon("calendar-check")}</span>
            <div>
              <strong>默认预览</strong>
              <small>${previewDates.map((date) => formatDate(date)).join("、")}；提交后可单独完成、删除或稍后提醒。</small>
            </div>
          </div>
          <div class="form-actions">
            <button class="button ghost" type="button" data-close-modal>取消</button>
            <button class="button primary" type="submit" ${state.saving ? "disabled" : ""}>
              ${icon("refresh")}${state.saving ? "创建中..." : "创建重复提醒"}
            </button>
          </div>
        </form>
      </section>
    </div>
  `;
}

function renderDiaryModal() {
  const diary = getDiarySnapshot();
  const modalTitle = diary.hasEntry ? "编辑日记" : "写日记";
  const actionLabel = diary.hasEntry ? "更新日记" : "保存日记";
  const titleValue = diary.hasEntry ? diary.title : "";
  const weatherValue = diary.hasEntry ? diary.weather : "";
  const tagValue = diary.hasEntry ? diary.tags.join("，") : "";
  const bodyValue = diary.hasEntry ? diary.body : "";
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal" role="dialog" aria-modal="true" aria-labelledby="diary-modal-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="diary-modal-title">${modalTitle}</h2>
            <p class="section-note">记录在 ${escapeHtml(diary.dateLabel)}，保存后随时可以回来修改。</p>
          </div>
          <button class="button ghost" type="button" data-close-modal aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <form class="form" data-diary-form>
          <div class="form-grid">
            <div class="field full">
              <label for="diary_title">标题</label>
              <input id="diary_title" name="title" maxlength="80" placeholder="今天的日记"
                value="${escapeHtml(titleValue)}" />
            </div>
            <div class="field">
              <label for="diary_mood">心情</label>
              <select id="diary_mood" name="mood">
                <option value="happy" ${diary.mood === "happy" ? "selected" : ""}>开心</option>
                <option value="calm" ${diary.mood === "calm" ? "selected" : ""}>平静</option>
                <option value="tired" ${diary.mood === "tired" ? "selected" : ""}>疲惫</option>
                <option value="anxious" ${diary.mood === "anxious" ? "selected" : ""}>有压力</option>
                <option value="sad" ${diary.mood === "sad" ? "selected" : ""}>低落</option>
              </select>
            </div>
            <div class="field">
              <label for="diary_weather">天气</label>
              <input id="diary_weather" name="weather" maxlength="20" placeholder="晴天"
                value="${escapeHtml(weatherValue)}" />
            </div>
            <div class="field full">
              <label for="diary_tags">标签</label>
              <input id="diary_tags" name="tags" maxlength="400" list="diary_tag_options" placeholder="轻松，成长，朋友"
                value="${escapeHtml(tagValue)}" />
            </div>
            <div class="field full">
              <label for="diary_content">内容</label>
              <textarea id="diary_content" name="content" required maxlength="800"
                placeholder="记录今天发生的小事、心情和想法。">${escapeHtml(bodyValue)}</textarea>
            </div>
          </div>
          <div class="form-actions">
            ${diary.hasEntry ? `
              <button class="button danger" type="button" data-delete-diary="${escapeHtml(diary.dateKey)}"
                ${state.saving ? "disabled" : ""}>
                ${icon("trash")}删除日记
              </button>
            ` : ""}
            <button class="button ghost" type="button" data-close-modal>取消</button>
            <button class="button primary" type="submit" ${state.saving ? "disabled" : ""}>
              ${icon("save")}${state.saving ? "保存中..." : actionLabel}
            </button>
          </div>
        </form>
      </section>
    </div>
  `;
}

function renderAssistantPage() {
  const messages = state.chatMessages;
  const hasConversation = messages.some(message => message.role === "user");
  const voiceAvailable = Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
  return `<div class="assistant-page simple-assistant">
    <header class="simple-page-header"><div><p class="simple-kicker">${icon("spark")}省一点输入的时间</p><h1>AI 帮记</h1><p>说清楚要记什么，核对后再保存。</p></div>${hasConversation ? '<button class="button ghost" type="button" data-chat-clear>清空对话</button>' : ""}</header>
    <section class="assistant-chat-page" aria-label="和助手记账">
      ${renderAssistantRuntimePanel()}
      ${renderAssistantCapabilities()}
      <div class="assistant-thread chat-thread" aria-live="polite">
        ${hasConversation ? messages.map((message, index) => renderChatMessage(message, index)).join("") : `<div class="simple-assistant-welcome"><span class="entry-icon">${icon("spark")}</span><h2>这次想记点什么？</h2><p>输入一句话，或上传支付截图。<br />我会整理成一张记录卡，等你核对。</p>${renderAssistantQuickPrompts()}<small>也可以记录待办和日记。</small></div>`}
        ${state.saving ? `<div class="chat-message assistant" role="status"><span>${icon("spark")}</span><p>正在整理，请稍等…</p></div>` : ""}
      </div>
      <form class="assistant-composer" data-chat-form>
        ${renderChatAttachmentQueue()}
        <label class="sr-only" for="chat_message">想记录的内容</label><textarea id="chat_message" name="message" maxlength="5000" data-chat-input placeholder="例如：今天在沙县吃午餐，花了 28 元，用微信付的">${escapeHtml(state.chatDraft)}</textarea>
        <div class="assistant-composer-actions"><label class="assistant-tool-button">${icon("image")}<span>上传图片</span><input class="sr-only" type="file" accept="image/png,image/jpeg,image/webp" multiple data-chat-image-input /></label>
          ${voiceAvailable ? `<button class="assistant-tool-button ${state.voiceListening ? "is-listening" : ""}" type="button" data-assistant-voice>${icon("mic")}<span>${state.voiceListening ? "停止听写" : "语音输入"}</span></button>` : ""}
          <button class="assistant-send-button" type="submit" ${state.saving || state.chatAttachments.some(attachment => attachment.status === "uploading") ? "disabled" : ""}>${icon("send")}帮我整理</button>
        </div><p class="simple-composer-note">整理后请在记录卡上保存。需要补充时，点「修改信息」。</p>
      </form>
    </section>
  </div>`;
}

function renderAssistantRuntimePanel() {
  const runtime = state.bootstrap?.capabilities?.agent_runtime ?? {
    rag_enabled: true,
    function_calling_enabled: true,
    fine_tuning_ready: true,
    knowledge_sources: [],
    function_tools: [],
    model_profile: { strategy: "rule_based_local_fallback", fine_tuning_status: "training_dataset_ready" },
  };
  const model = runtime.model_profile ?? {};
  const knowledgeCount = (runtime.knowledge_sources ?? []).reduce((total, source) => total + Number(source.document_count ?? 0), 0);
  const toolCount = (runtime.function_tools ?? []).length;
  const runtimeStatus = assistantRuntimeStatus(model);
  return `
    <div class="assistant-runtime-panel" aria-label="Agent 架构状态">
      ${runtimeChip("search", "RAG 知识库", `${knowledgeCount} 条知识`, runtime.rag_enabled)}
      ${runtimeChip("settings", "Function Calling", `${toolCount} 个函数`, runtime.function_calling_enabled)}
      ${runtimeChip("spark", "模型策略", modelStrategyLabel(model.strategy), !model.external_model_configured || model.external_model_ready)}
      ${runtimeChip("file-text", "微调", fineTuningStatusLabel(model.fine_tuning_status), runtime.fine_tuning_ready)}
      <div class="assistant-runtime-status ${escapeHtml(runtimeStatus.tone)}">
        <span>${icon(runtimeStatus.icon)}</span>
        <strong>${escapeHtml(runtimeStatus.label)}</strong>
        <small>${escapeHtml(runtimeStatus.detail)}</small>
      </div>
    </div>
  `;
}

function assistantRuntimeStatus(model = {}) {
  const provider = providerLabel(model.provider);
  const blockers = [...(model.credential_blockers ?? []), ...(model.privacy_blockers ?? [])]
    .map(integrationCodeLabel)
    .join("、");
  if (model.external_model_ready) {
    return {
      icon: "check-circle",
      tone: "is-ready",
      label: `${provider} 已就绪`,
      detail: [model.runtime_model, functionCallingModeLabel(model.function_calling_mode), model.reasoning_effort ? `推理 ${model.reasoning_effort}` : null].filter(Boolean).join(" · "),
    };
  }
  if (model.external_model_configured) {
    return {
      icon: "alert-circle",
      tone: "is-blocked",
      label: `${provider} 未就绪`,
      detail: blockers || model.next_action || "检查模型连接配置",
    };
  }
  return {
    icon: "spark",
    tone: "is-local",
    label: "本地 Agent 可用",
    detail: model.next_action || "配置 DeepSeek 后可启用大模型解析",
  };
}

function runtimeChip(iconName, label, value, enabled) {
  return `
    <div class="assistant-runtime-chip ${enabled ? "is-on" : "is-off"}">
      <span>${icon(iconName)}</span>
      <div>
        <strong>${escapeHtml(label)}</strong>
        <small>${escapeHtml(value)}</small>
      </div>
    </div>
  `;
}

function renderAssistantCapabilities() {
  const preferredToolIds = ["bill_candidate", "bill_analysis", "task_candidate", "diary_candidate", "attachment_bill_recognition"];
  const toolsById = new Map(assistantTools().map((tool) => [tool.id, tool]));
  const tools = preferredToolIds.map((toolId) => toolsById.get(toolId)).filter(Boolean);
  if (!tools.length) {
    return "";
  }

  return `
    <div class="assistant-capabilities" aria-label="助手可执行能力">
      ${tools.map((tool) => `
        <button class="assistant-capability ${state.activeAssistantToolId === tool.id ? "is-active" : ""}" type="button"
          data-assistant-tool="${escapeHtml(tool.id)}"
          aria-pressed="${state.activeAssistantToolId === tool.id ? "true" : "false"}"
          aria-label="使用${escapeHtml(tool.label)}"
          title="${escapeHtml(tool.description || tool.label)}">
          <span>${icon(iconForAssistantTool(tool.id))}</span>
          <div>
            <strong>${escapeHtml(tool.label)}</strong>
            <small>${escapeHtml(tool.requires_confirmation ? "需要确认" : "只读执行")}</small>
          </div>
        </button>
      `).join("")}
    </div>
  `;
}

function assistantComposerPlaceholder() {
  return {
    bill_candidate: "例如：午餐 28 元 微信支付 餐饮",
    bill_analysis: "例如：这个月餐饮花了多少？",
    task_candidate: "例如：提醒我明天 10 点开会",
    diary_candidate: "例如：今天完成了项目复盘，心情很轻松，晴天",
    diary_reflection: "例如：今天有点累，但完成了一个重要任务",
    attachment_bill_recognition: "可以先选择图片，再补一句说明",
  }[state.activeAssistantToolId] ?? "例如：午餐 28 元 微信支付；或：提醒我明天 10 点开会。也可以先选图片再补一句说明。";
}

function assistantTools() {
  const tools = state.bootstrap?.capabilities?.assistant_tools;
  if (Array.isArray(tools) && tools.length) {
    return tools;
  }
  return [
    { id: "knowledge_search", label: "知识库检索", requires_confirmation: false },
    { id: "bill_candidate", label: "记账候选", requires_confirmation: true },
    { id: "bill_analysis", label: "账单分析", requires_confirmation: false },
    { id: "task_candidate", label: "提醒候选", requires_confirmation: true },
    { id: "diary_candidate", label: "日记候选", requires_confirmation: true },
    { id: "diary_reflection", label: "日记追问", requires_confirmation: false },
    { id: "attachment_bill_recognition", label: "图片记账", requires_confirmation: true },
  ];
}

function iconForAssistantTool(toolId) {
  return {
    knowledge_search: "search",
    bill_candidate: "wallet",
    bill_analysis: "pie-chart",
    task_candidate: "bell",
    diary_candidate: "book",
    diary_reflection: "book",
    attachment_bill_recognition: "image",
  }[toolId] ?? "spark";
}

function renderAssistantQuickPrompts() {
  return `<div class="assistant-prompts" aria-label="试试这些例子">
    <button type="button" data-chat-example="沙县小吃&#10;午餐 28 元 微信支付 餐饮">${icon("utensils")}记一笔午餐</button>
    <button type="button" data-chat-example="这个月餐饮花了多少？">${icon("pie-chart")}查消费</button>
    <button type="button" data-chat-example="这个月消费趋势和预算情况怎么样？">${icon("pie-chart")}看预算</button>
    <button type="button" data-chat-example="工资收入 6800 元">${icon("income")}记一笔收入</button>
    <button type="button" data-chat-example="你有 RAG 知识库和函数调用吗？">${icon("search")}问问 Agent 链路</button>
    <button type="button" data-chat-example="提醒我明天 10 点开会">${icon("bell")}记一个待办</button>
  </div>`;
}

function renderChatAttachmentQueue() {
  if (!state.chatAttachments.length) {
    return "";
  }
  return `
    <div class="assistant-attachment-queue" aria-label="待发送图片">
      ${state.chatAttachments.map((attachment) => `
        <div class="assistant-attachment">
          <img src="${escapeHtml(attachment.previewUrl)}" alt="${escapeHtml(attachment.name)}" />
          <div>
            <strong>${escapeHtml(attachment.name)}</strong>
            <span>${chatAttachmentStatus(attachment)}</span>
          </div>
          <button type="button" data-remove-chat-attachment="${escapeHtml(attachment.id)}"
            aria-label="移除 ${escapeHtml(attachment.name)}">
            ${icon("close")}
          </button>
        </div>
      `).join("")}
    </div>
  `;
}

function renderChatMessage(message, index) {
  const role = message.role === "user" ? "user" : "assistant";
  return `
    <article class="chat-message ${role}" data-chat-message="${index}">
      <span>${icon(role === "user" ? "user" : "spark")}</span>
      <div>
        <p>${escapeHtml(role === "assistant" ? friendlyAssistantText(message.text ?? "") : message.text ?? "")}</p>
        ${renderChatMessageAttachments(message.attachments)}
        ${role === "assistant" ? renderChatSelectedTool(message.response) : ""}
        ${role === "assistant" ? renderChatAgentSteps(message.response?.agent_steps) : ""}
        ${role === "assistant" ? renderChatAnalysis(message.response) : ""}
        ${role === "assistant" ? renderChatRuntimeTrace(message.response) : ""}
        ${renderChatCandidate(message)}
        ${renderChatResult(message)}
      </div>
    </article>
  `;
}

function renderChatSelectedTool(response) {
  if (!response?.assistant_tool_id) {
    return "";
  }
  const tool = assistantTools().find((item) => item.id === response.assistant_tool_id);
  const label = tool?.label || chatIntentDisplay(response.intent) || "助手能力";
  const note = response.need_user_confirmation
    ? "需确认后执行"
    : response.discarded
      ? "已取消"
      : "已执行";
  return `
    <div class="chat-selected-tool">
      ${icon(iconForAssistantTool(response.assistant_tool_id))}
      <span>${escapeHtml(label)}</span>
      <small>${escapeHtml(note)}</small>
    </div>
  `;
}

function renderChatAgentSteps(steps = []) {
  if (!steps.length) {
    return "";
  }

  return `
    <div class="chat-agent-steps" aria-label="助手执行步骤">
      ${steps
        .map((step) => {
          const status = String(step.status || "completed");
          return `
            <div class="chat-agent-step ${escapeHtml(status)}">
              <span>${icon(chatAgentStepIcon(status))}</span>
              <div>
                <strong>${escapeHtml(step.title || "执行步骤")}</strong>
                <small>${escapeHtml(step.detail || "")}</small>
              </div>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function chatAgentStepIcon(status) {
  if (status === "needs_confirmation") {
    return "clock";
  }
  if (status === "blocked") {
    return "alert-circle";
  }
  return "check-circle";
}

function renderChatRuntimeTrace(response) {
  if (!response) {
    return "";
  }
  const hits = response.knowledge_hits ?? [];
  const calls = response.function_calls ?? [];
  const model = response.model_trace;
  if (!hits.length && !calls.length && !model) {
    return "";
  }
  return `
    <details class="chat-runtime-trace">
      <summary>${icon("list-filter")}<span>Agent 工作链路</span><small>${escapeHtml(runtimeTraceSummary(hits, calls, model))}</small></summary>
      <div class="chat-runtime-body">
        ${model ? renderModelTrace(model) : ""}
        ${hits.length ? `<div class="chat-runtime-section"><strong>RAG 知识命中</strong>${hits.map(renderKnowledgeHit).join("")}</div>` : ""}
        ${calls.length ? `<div class="chat-runtime-section"><strong>Function Calling</strong>${calls.map(renderFunctionCall).join("")}</div>` : ""}
      </div>
    </details>
  `;
}

function runtimeTraceSummary(hits, calls, model) {
  const parts = [];
  if (hits.length) parts.push(`${hits.length} 条知识`);
  if (calls.length) parts.push(`${calls.length} 次函数调用`);
  if (model) parts.push(modelStrategyLabel(model.strategy));
  return parts.join(" · ") || "已记录";
}

function renderModelTrace(model) {
  const meta = [
    providerLabel(model.provider),
    modelStrategyLabel(model.strategy),
    fineTuningStatusLabel(model.fine_tuning_status),
    functionCallingModeLabel(model.function_calling_mode),
  ].filter(Boolean);
  return `
    <div class="chat-runtime-model">
      <span>${icon("spark")}</span>
      <div>
        <strong>${escapeHtml(modelTraceTitle(model))}</strong>
        <small>${escapeHtml(meta.join(" · "))}</small>
      </div>
    </div>
  `;
}

function modelTraceTitle(model = {}) {
  if (model.external_model_ready) {
    return model.runtime_model || providerLabel(model.provider);
  }
  if (model.external_model_configured) {
    return "本地规则解析兜底";
  }
  return "本地规则解析";
}

function renderKnowledgeHit(hit) {
  return `
    <article class="chat-knowledge-hit">
      <span>${escapeHtml(Math.round(Number(hit.score ?? 0) * 100))}%</span>
      <div>
        <strong>${escapeHtml(hit.title)}</strong>
        <small>${escapeHtml(hit.snippet)}</small>
      </div>
    </article>
  `;
}

function renderFunctionCall(call) {
  return `
    <article class="chat-function-call ${escapeHtml(call.status || "completed")}">
      <span>${icon(call.status === "blocked" ? "alert-circle" : "check-circle")}</span>
      <div>
        <strong>${escapeHtml(call.label || call.name)}</strong>
        <small>${escapeHtml([call.name, functionCallArgumentsText(call.arguments), call.result].filter(Boolean).join(" · "))}</small>
      </div>
    </article>
  `;
}

function functionCallArgumentsText(args = {}) {
  return Object.entries(args)
    .slice(0, 3)
    .map(([key, value]) => `${key}: ${String(value ?? "null").slice(0, 36)}`)
    .join("，");
}

function modelStrategyLabel(strategy) {
  return {
    fine_tuned_llm_with_local_fallback: "微调模型优先",
    base_llm_with_rag_and_function_calling: "基础模型增强",
    llm_configured_blocked_by_privacy: "大模型被隐私阻断",
    llm_configured_not_ready: "大模型待授权",
    external_parser_blocked_by_privacy: "外部解析被隐私阻断",
    external_parser_with_local_fallback: "外部解析服务",
    rule_based_local_fallback: "本地规则兜底",
  }[strategy] ?? (strategy || "本地规则兜底");
}

function providerLabel(provider) {
  return {
    deepseek: "DeepSeek",
    openai_compatible: "OpenAI Compatible",
    external_http: "外部解析服务",
    rule_based: "本地规则",
  }[provider] ?? (provider || "本地规则");
}

function functionCallingModeLabel(mode) {
  return {
    deepseek_native_tool_calls_with_local_execution: "DeepSeek tools",
    native_tool_calls_with_local_execution: "原生 tools",
    local_trace_only: "本地函数链路",
  }[mode] ?? mode;
}

function fineTuningStatusLabel(status) {
  return {
    serving_fine_tuned_model: "微调模型已接入",
    training_dataset_ready: "样本可导出",
  }[status] ?? (status || "样本可导出");
}

function renderChatMessageAttachments(attachments = []) {
  if (!attachments.length) {
    return "";
  }
  return `
    <div class="chat-message-attachments">
      ${attachments.map((attachment) => `
        <figure>
          <img src="${escapeHtml(attachment.previewUrl)}" alt="${escapeHtml(attachment.name)}" />
          <figcaption>${escapeHtml(attachment.name)}</figcaption>
        </figure>
      `).join("")}
    </div>
  `;
}

function chatAttachmentStatus(attachment) {
  if (attachment.status === "uploaded") {
    return "已上传，发送后识别";
  }
  if (attachment.status === "failed") {
    return attachment.error || "上传失败";
  }
  return "上传中";
}

function renderChatResult(message) {
  const response = message.response;
  if (response?.created_bill) {
    const bill = response.created_bill;
    return `
      <div class="chat-result-card">
        <div class="chat-result-head">
          <span>${icon("check-circle")}</span>
          <strong>账单已保存</strong>
        </div>
        <div class="chat-result-grid">
          <div>
            <small>金额</small>
            <b>${money(bill.amount)}</b>
          </div>
          <div>
            <small>商家/用途</small>
            <b>${escapeHtml(billDisplayName(bill))}</b>
          </div>
          <div>
            <small>分类</small>
            <b>${escapeHtml(bill.category || "其他")}</b>
          </div>
          <div>
            <small>时间</small>
            <b>${formatDate(bill.paid_at)}</b>
          </div>
        </div>
        <button class="button ghost" type="button" data-route="bills">
          ${icon("wallet")}查看记账
        </button>
      </div>
    `;
  }

  if (response?.created_task) {
    const task = response.created_task;
    return `
      <div class="chat-result-card">
        <div class="chat-result-head">
          <span>${icon("check-circle")}</span>
          <strong>提醒已保存</strong>
        </div>
        <div class="chat-result-grid">
          <div>
            <small>标题</small>
            <b>${escapeHtml(task.title || "未命名")}</b>
          </div>
          <div>
            <small>类型</small>
            <b>${escapeHtml(labelTaskType(task.task_type))}</b>
          </div>
          <div>
            <small>优先级</small>
            <b>${escapeHtml(labelTaskPriority(task.priority))}</b>
          </div>
          <div>
            <small>时间</small>
            <b>${escapeHtml(taskTargetText(task))}</b>
          </div>
        </div>
        <button class="button ghost" type="button" data-route="tasks">
          ${icon("bell")}查看提醒
        </button>
      </div>
    `;
  }

  if (response?.created_diary) {
    const diary = response.created_diary;
    return `
      <div class="chat-result-card">
        <div class="chat-result-head">
          <span>${icon("check-circle")}</span>
          <strong>日记已保存</strong>
        </div>
        <div class="chat-result-grid">
          <div>
            <small>标题</small>
            <b>${escapeHtml(diary.title || "今天的日记")}</b>
          </div>
          <div>
            <small>日期</small>
            <b>${escapeHtml(formatDateOnly(diary.entry_date))}</b>
          </div>
          <div>
            <small>心情</small>
            <b>${escapeHtml(diaryMoodLabel(diary.mood))}</b>
          </div>
          <div>
            <small>天气</small>
            <b>${escapeHtml(diary.weather || "未记录")}</b>
          </div>
        </div>
        <button class="button ghost" type="button" data-route="diary">
          ${icon("book")}查看日记
        </button>
      </div>
    `;
  }

  return "";
}

function renderChatAnalysis(response) {
  const analysis = response?.analysis;
  if (!analysis) {
    return "";
  }
  const spendValue = analysis.category ? analysis.category_amount : analysis.total_expense;
  const spendLabel = analysis.category ? `${analysis.category}支出` : "本期支出";
  const changeLabel = chatAnalysisChangeLabel(analysis);
  const budgetLabel = chatAnalysisBudgetLabel(analysis);
  const rows = [
    ["周期", analysis.category ? `${analysis.period_label} · ${analysis.category}` : analysis.period_label],
    [spendLabel, money(spendValue)],
    ["收入", money(analysis.total_income)],
    ["账单", `${Number(analysis.bill_count ?? 0)} 笔`],
  ];
  if (analysis.category) {
    rows.push(["分类占比", `${analysis.category_percentage ?? 0}%`]);
  } else if (analysis.top_category) {
    rows.push(["最高分类", `${analysis.top_category} · ${money(analysis.top_category_amount)}`]);
  }
  if (budgetLabel) {
    rows.push(["预算", budgetLabel]);
  }
  if (changeLabel) {
    rows.push(["环比", changeLabel]);
  }
  if (analysis.top_day && analysis.top_day_expense !== null) {
    rows.push(["单日最高", `${formatMonthDay(analysis.top_day)} · ${money(analysis.top_day_expense)}`]);
  }

  return `
    <div class="chat-result-card chat-analysis-card">
      <div class="chat-result-head">
        <span>${icon("pie-chart")}</span>
        <strong>账单分析摘要</strong>
      </div>
      <div class="chat-result-grid">
        ${rows.map(([label, value]) => `
          <div>
            <small>${escapeHtml(label)}</small>
            <b>${escapeHtml(String(value ?? ""))}</b>
          </div>
        `).join("")}
      </div>
      <button class="button ghost" type="button" data-route="bills">
        ${icon("wallet")}查看记账
      </button>
    </div>
  `;
}

function chatAnalysisChangeLabel(analysis) {
  const delta = Number(analysis.category ? analysis.category_delta : analysis.expense_delta);
  if (!Number.isFinite(delta)) {
    return null;
  }
  if (delta === 0) {
    return `较${analysis.previous_period_label}持平`;
  }
  return `较${analysis.previous_period_label}${delta > 0 ? "多" : "少"} ${money(Math.abs(delta))}`;
}

function chatAnalysisBudgetLabel(analysis) {
  const budget = Number(analysis.budget_amount ?? 0);
  if (!Number.isFinite(budget) || budget <= 0) {
    return null;
  }
  const remaining = Number(analysis.budget_remaining ?? 0);
  if (!Number.isFinite(remaining)) {
    return null;
  }
  return remaining >= 0 ? `剩余 ${money(remaining)}` : `超出 ${money(Math.abs(remaining))}`;
}

function renderChatCandidateEditorModal() {
  const editor = state.chatCandidateEditor;
  const actionType = editor?.actionType || "";
  const data = editor?.candidate?.data || {};
  const title = {
    bill_candidate: "修改账单信息",
    task_candidate: "修改待办信息",
    diary_candidate: "修改日记信息",
  }[actionType] || "编辑候选记录";

  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal" role="dialog" aria-modal="true" aria-labelledby="chat-candidate-editor-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="chat-candidate-editor-title">${title}</h2>
            <p class="section-note">修改完成后，回到记录卡确认保存。</p>
          </div>
          <button class="button ghost" type="button" data-close-chat-candidate-editor aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <form class="form" data-chat-candidate-editor-form>
          <div class="form-grid">
            ${renderChatCandidateEditorFields(actionType, data)}
          </div>
          <div class="form-actions">
            <button class="button ghost" type="button" data-close-chat-candidate-editor>取消</button>
            <button class="button primary" type="submit" ${state.saving ? "disabled" : ""}>
              ${icon("save")}${state.saving ? "保存中..." : "完成修改"}
            </button>
          </div>
        </form>
      </section>
    </div>
  `;
}

function renderChatCandidateEditorFields(actionType, data) {
  if (actionType === "bill_candidate") {
    const defaultBillCategory = getCategorySettings().bill_categories[0] || "其他";
    return `
      <div class="field">
        <label for="chat_candidate_amount">金额</label>
        <input id="chat_candidate_amount" name="amount" type="number" min="0.01" step="0.01"
          value="${escapeHtml(data.amount ?? "")}" />
      </div>
      <div class="field">
        <label for="chat_candidate_transaction_type">类型</label>
        <select id="chat_candidate_transaction_type" name="transaction_type">
          ${transactionOptions(data.transaction_type || "expense")}
        </select>
      </div>
      <div class="field">
        <label for="chat_candidate_merchant">商家或用途 <small>选填</small></label>
        <input id="chat_candidate_merchant" name="merchant" maxlength="120"
          value="${escapeHtml(data.merchant || "")}" />
      </div>
      <div class="field">
        <label for="chat_candidate_category">分类</label>
        <input id="chat_candidate_category" name="category" maxlength="40" list="bill_category_options"
          placeholder="${escapeHtml(defaultBillCategory)}" value="${escapeHtml(data.category || "")}" />
      </div>
      <div class="field">
        <label for="chat_candidate_payment_method">支付方式</label>
        <input id="chat_candidate_payment_method" name="payment_method" maxlength="40"
          value="${escapeHtml(data.payment_method || "")}" />
      </div>
      <div class="field">
        <label for="chat_candidate_paid_at">时间</label>
        <input id="chat_candidate_paid_at" name="paid_at" type="datetime-local"
          value="${escapeHtml(toDateTimeLocal(data.paid_at))}" />
      </div>
      <div class="field full">
        <label for="chat_candidate_note">备注</label>
        <textarea id="chat_candidate_note" name="note" maxlength="500">${escapeHtml(data.note || "")}</textarea>
      </div>
    `;
  }

  if (actionType === "task_candidate") {
    const defaultTaskCategory = getCategorySettings().task_categories[0] || "生活";
    return `
      <div class="field full">
        <label for="chat_candidate_title">标题</label>
        <input id="chat_candidate_title" name="title" maxlength="120" value="${escapeHtml(data.title || "")}" />
      </div>
      <div class="field">
        <label for="chat_candidate_task_type">类型</label>
        <select id="chat_candidate_task_type" name="task_type">
          <option value="todo" ${data.task_type === "todo" ? "selected" : ""}>待办</option>
          <option value="reminder" ${data.task_type === "reminder" ? "selected" : ""}>提醒</option>
        </select>
      </div>
      <div class="field">
        <label for="chat_candidate_priority">优先级</label>
        <select id="chat_candidate_priority" name="priority">
          <option value="medium" ${data.priority === "medium" ? "selected" : ""}>普通</option>
          <option value="high" ${data.priority === "high" ? "selected" : ""}>高</option>
          <option value="low" ${data.priority === "low" ? "selected" : ""}>低</option>
        </select>
      </div>
      <div class="field">
        <label for="chat_candidate_task_category">分类</label>
        <input id="chat_candidate_task_category" name="category" maxlength="40" list="task_category_options"
          placeholder="${escapeHtml(defaultTaskCategory)}" value="${escapeHtml(data.category || "")}" />
      </div>
      <div class="field">
        <label for="chat_candidate_due_at">截止时间</label>
        <input id="chat_candidate_due_at" name="due_at" type="datetime-local"
          value="${escapeHtml(toDateTimeLocal(data.due_at))}" />
      </div>
      <div class="field">
        <label for="chat_candidate_remind_at">提醒时间</label>
        <input id="chat_candidate_remind_at" name="remind_at" type="datetime-local"
          value="${escapeHtml(toDateTimeLocal(data.remind_at))}" />
      </div>
      <div class="field full">
        <label for="chat_candidate_description">备注</label>
        <textarea id="chat_candidate_description" name="description" maxlength="500">${escapeHtml(data.description || "")}</textarea>
      </div>
    `;
  }

  return `
    <div class="field">
      <label for="chat_candidate_entry_date">日期</label>
      <input id="chat_candidate_entry_date" name="entry_date" type="date"
        value="${escapeHtml(data.entry_date || todayDateKey())}" />
    </div>
    <div class="field">
      <label for="chat_candidate_mood">心情</label>
      <select id="chat_candidate_mood" name="mood">
        <option value="happy" ${data.mood === "happy" ? "selected" : ""}>开心</option>
        <option value="calm" ${data.mood === "calm" ? "selected" : ""}>平静</option>
        <option value="tired" ${data.mood === "tired" ? "selected" : ""}>疲惫</option>
        <option value="anxious" ${data.mood === "anxious" ? "selected" : ""}>有压力</option>
        <option value="sad" ${data.mood === "sad" ? "selected" : ""}>低落</option>
      </select>
    </div>
    <div class="field full">
      <label for="chat_candidate_diary_title">标题</label>
      <input id="chat_candidate_diary_title" name="title" maxlength="120" value="${escapeHtml(data.title || "")}" />
    </div>
    <div class="field">
      <label for="chat_candidate_weather">天气</label>
      <input id="chat_candidate_weather" name="weather" maxlength="40" value="${escapeHtml(data.weather || "")}" />
    </div>
    <div class="field">
      <label for="chat_candidate_tags">标签</label>
      <input id="chat_candidate_tags" name="tags" maxlength="400" list="diary_tag_options"
        value="${escapeHtml(Array.isArray(data.tags) ? data.tags.join("，") : "")}" />
    </div>
    <div class="field full">
      <label for="chat_candidate_content">正文</label>
      <textarea id="chat_candidate_content" name="content" maxlength="5000">${escapeHtml(data.content || "")}</textarea>
    </div>
  `;
}
function renderChatCandidate(message) {
  const response = message.response;
  if (!response || response.action_type === "none" || !response.candidate) {
    return "";
  }
  if (message.handled) {
    return `<p class="simple-handled">${message.handled === "confirmed" ? "这条记录已保存。" : "这条记录未保存。"}</p>`;
  }

  const candidateId = getChatCandidateId(response);
  const actionType = response.action_type;
  const candidate = response.candidate;
  const data = candidate.data ?? {};
  const confidence = Math.round(Number(candidate.confidence ?? response.confidence ?? 0) * 100);
  let rows = [];
  let candidateTitle = "核对待办";
  if (actionType === "bill_candidate") {
    candidateTitle = "核对这笔账";
    rows = [
        ["类型", labelTransaction(data.transaction_type)],
        ["金额", data.amount ? money(data.amount) : "待补充"],
        ["商家或用途", data.merchant || "未填写"],
        ["分类", data.category || "其他"],
        ["时间", data.paid_at ? formatDate(data.paid_at) : "保存时的时间"],
      ];
  } else if (actionType === "diary_candidate") {
    candidateTitle = "核对日记";
    rows = [
      ["标题", data.title || "待补充"],
      ["日期", data.entry_date ? formatDateOnly(data.entry_date) : "待补充"],
      ["心情", diaryMoodLabel(data.mood)],
      ["天气", data.weather || "未记录"],
      ["标签", Array.isArray(data.tags) && data.tags.length ? data.tags.join("，") : "未记录"],
    ];
  } else {
    rows = [
        ["类型", labelTaskType(data.task_type)],
        ["标题", data.title || "待补充"],
        ["分类", data.category || "生活"],
        ["优先级", labelTaskPriority(data.priority)],
        ["时间", formatChatTaskTime(data)],
      ];
  }
  const warnings = response.warnings?.length ? response.warnings : candidate.warnings ?? [];
  const canConfirm = isChatCandidateConfirmable(actionType, data);
  const warningText = chatCandidateWarningText(actionType, data, warnings);
  const handledLabel = {
    confirmed: "已保存",
    discarded: "未保存",
  }[message.handled];

  return `
    <div class="chat-candidate">
      <div class="chat-candidate-head">
        <strong>${candidateTitle}</strong>
        <span>${handledLabel || "尚未保存"}</span>
      </div>
      <div class="chat-candidate-grid">
        ${rows
          .map(
            ([label, value]) => `
              <div>
                <small>${escapeHtml(label)}</small>
                <b>${escapeHtml(String(value ?? ""))}</b>
              </div>
            `,
          )
          .join("")}
      </div>
      ${warningText ? `<p class="chat-warning">${escapeHtml(warningText)}</p>` : ""}
      <div class="chat-candidate-actions">
        ${
          handledLabel
            ? `<span class="chat-status">${handledLabel}</span>`
            : `
              <button class="button ghost" type="button"
                data-chat-edit
                data-candidate-id="${escapeHtml(candidateId)}"
                ${state.saving ? "disabled" : ""}>
                ${icon("edit")}修改信息
              </button>
              <button class="button primary" type="button"
                data-chat-confirm
                data-action-type="${escapeHtml(actionType)}"
                data-candidate-id="${escapeHtml(candidateId)}"
                ${state.saving || !canConfirm ? "disabled" : ""}>
                ${icon("check-circle")}${actionType === "bill_candidate" ? "保存这笔账" : "保存记录"}
              </button>
              <button class="button ghost" type="button"
                data-chat-discard
                data-action-type="${escapeHtml(actionType)}"
                data-candidate-id="${escapeHtml(candidateId)}"
                ${state.saving ? "disabled" : ""}>
                不保存
              </button>
            `
        }
      </div>
    </div>
  `;
}

function getChatCandidateId(response) {
  return String(response?.candidate_id || response?.candidate?.candidate_id || "");
}

function isChatCandidateConfirmable(actionType, data) {
  if (actionType === "bill_candidate") {
    return Boolean(data?.amount);
  }
  if (actionType === "task_candidate") {
    return Boolean(data?.title && (data.task_type !== "reminder" || data.remind_at));
  }
  if (actionType === "diary_candidate") {
    return Boolean(data?.entry_date && data?.title && data?.content);
  }
  return false;
}

function chatCandidateWarningText(actionType, data, warnings) {
  if (actionType === "bill_candidate" && !isChatCandidateConfirmable(actionType, data)) {
    return "还缺金额。点「修改信息」补齐后，就能保存。";
  }
  if (actionType === "task_candidate" && !isChatCandidateConfirmable(actionType, data)) {
    return "还缺事项名称或提醒时间。点「修改信息」补齐后，就能保存。";
  }
  if (actionType === "diary_candidate" && !isChatCandidateConfirmable(actionType, data)) {
    return "还缺日期、标题或正文。点「修改信息」补齐后，就能保存。";
  }
  return warnings.length ? "请核对上面的信息，有出入可以修改。" : "";
}

function formatChatTaskTime(data) {
  const target = data?.task_type === "reminder"
    ? data.remind_at || data.due_at
    : data?.due_at || data?.remind_at;
  return target ? formatDate(target) : "待补充";
}

function renderTaskSortModal() {
  const currentSort = state.taskFilters.sort || "time";
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal compact-modal" role="dialog" aria-modal="true" aria-labelledby="task-sort-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="task-sort-title">提醒排序</h2>
            <p class="section-note">调整当前提醒列表的展示顺序，不改变后端数据。</p>
          </div>
          <button class="button ghost" type="button" data-close-task-sort aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <div class="task-sort-list">
          ${taskSortOptions().map((option) => `
            <button class="task-sort-option ${currentSort === option.value ? "is-active" : ""}"
              type="button" data-task-sort="${escapeHtml(option.value)}">
              <span>${icon(option.iconName)}</span>
              <div>
                <strong>${escapeHtml(option.label)}</strong>
                <small>${escapeHtml(option.note)}</small>
              </div>
              ${currentSort === option.value ? icon("check") : ""}
            </button>
          `).join("")}
        </div>
      </section>
    </div>
  `;
}

function taskSortOptions() {
  return [
    {
      value: "time",
      label: "按时间排序",
      note: "越接近当前目标时间的提醒越靠前。",
      iconName: "clock",
    },
    {
      value: "priority",
      label: "按优先级排序",
      note: "重要事项优先，同级再按时间排列。",
      iconName: "check-circle",
    },
    {
      value: "created",
      label: "按创建时间排序",
      note: "最新添加的提醒优先展示。",
      iconName: "calendar",
    },
  ];
}

function taskSortLabel(value) {
  return taskSortOptions().find((option) => option.value === value)?.label ?? "按时间排序";
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

function renderDataImportModal() {
  const preview = state.dataImportPreview;
  const result = preview?.result ?? {};
  const before = result.before ?? {};
  const candidateCount = Number(result.imported_bill_candidate_count ?? 0)
    + Number(result.imported_task_candidate_count ?? 0)
    + Number(result.imported_diary_candidate_count ?? 0);
  const categoryCount = Number(preview?.snapshot?.category_settings?.bill_categories?.length ?? 0)
    + Number(preview?.snapshot?.category_settings?.task_categories?.length ?? 0);
  const importedBudget = Number(preview?.snapshot?.budget_settings?.monthly_budget ?? 0);
  const tagCount = Number(preview?.snapshot?.tag_settings?.tags?.length ?? 0);
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal compact-modal" role="dialog" aria-modal="true" aria-labelledby="data-import-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="data-import-title">确认导入 JSON</h2>
            <p class="section-note">
              ${escapeHtml(preview?.fileName ?? "lifesnap-export.json")} 已通过后端预览校验。导入会先清空当前本地数据，再写入文件内容。
            </p>
          </div>
          <button class="button ghost" type="button" data-cancel-data-import aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <div class="import-preview-grid">
          ${importPreviewMetric("账单", result.imported_bill_count ?? 0, `${before.bill_count ?? 0} 条当前记录`)}
          ${importPreviewMetric("待办", result.imported_task_count ?? 0, `${before.task_count ?? 0} 条当前记录`)}
          ${importPreviewMetric("日记", result.imported_diary_count ?? 0, `${before.diary_count ?? 0} 篇当前记录`)}
          ${importPreviewMetric("附件", result.imported_attachment_count ?? 0, `${before.attachment_count ?? 0} 个当前附件`)}
          ${importPreviewMetric("候选", candidateCount, "账单、待办与日记")}
          ${importPreviewMetric("分类", categoryCount, "账单与待办分类")}
          ${importPreviewMetric("预算", money(importedBudget), "月预算配置")}
          ${importPreviewMetric("标签", tagCount, "日记常用标签")}
        </div>
        <p class="import-warning">建议确认已有数据已导出或保存快照后再导入。</p>
        <div class="form-actions modal-actions">
          <button class="button ghost" type="button" data-cancel-data-import>取消</button>
          <button class="button danger" type="button" data-confirm-data-import ${state.saving ? "disabled" : ""}>
            ${icon("upload")}${state.saving ? "导入中..." : "确认导入"}
          </button>
        </div>
      </section>
    </div>
  `;
}

function renderPrivacySettingsModal() {
  const privacy = state.bootstrap?.privacy_settings ?? {};
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal compact-modal" role="dialog" aria-modal="true" aria-labelledby="privacy-settings-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="privacy-settings-title">隐私设置</h2>
            <p class="section-note">由你决定，哪些内容可以交给外部 AI 处理。</p>
          </div>
          <button class="button ghost" type="button" data-close-privacy-settings aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <div class="privacy-settings-list">
          ${privacySettingRow(
            "local_only_mode",
            "仅在本机处理",
            "开启后，不会调用外部图片识别或 AI 服务。",
            Boolean(privacy.local_only_mode),
          )}
          ${privacySettingRow(
            "allow_ai_text_processing",
            "允许外部 AI 整理文字",
            "关闭后不会把文字发给外部 AI；仅在本机处理开启时，此授权也不会生效。",
            Boolean(privacy.allow_ai_text_processing),
          )}
          ${privacySettingRow(
            "save_original_attachments_by_default",
            "保留上传的原图",
            "开启后，可保留并查看上传的图片原件。",
            Boolean(privacy.save_original_attachments_by_default),
          )}
          ${privacySettingRow(
            "keep_ocr_text",
            "保留图片识别出的文字",
            "关闭后，识别出的文字不会长期保留。",
            Boolean(privacy.keep_ocr_text),
          )}
        </div>
      </section>
    </div>
  `;
}

function renderCategorySettingsModal() {
  const categories = getCategorySettings();
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal category-settings-modal" role="dialog" aria-modal="true" aria-labelledby="category-settings-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="category-settings-title">分类管理</h2>
            <p class="section-note">分类会保存到后端本地 JSON，并用于记账、筛选和提醒表单。</p>
          </div>
          <button class="button ghost" type="button" data-close-category-settings aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <form class="form category-settings-form" data-category-settings-form>
          <div class="form-grid">
            <div class="field full">
              <label for="bill_categories">账单分类</label>
              <textarea id="bill_categories" name="bill_categories" maxlength="600" required>${escapeHtml(categories.bill_categories.join("\n"))}</textarea>
              ${renderCategoryPreview(categories.bill_categories)}
            </div>
            <div class="field full">
              <label for="task_categories">待办分类</label>
              <textarea id="task_categories" name="task_categories" maxlength="600" required>${escapeHtml(categories.task_categories.join("\n"))}</textarea>
              ${renderCategoryPreview(categories.task_categories)}
            </div>
          </div>
          <p class="form-hint">支持换行、逗号或分号分隔；会自动去重，单项最多 40 字，最多保留 30 项。</p>
          <div class="form-actions">
            <button class="button ghost" type="button" data-close-category-settings>取消</button>
            <button class="button primary" type="submit" ${state.saving ? "disabled" : ""}>
              ${icon("save")}${state.saving ? "保存中..." : "保存分类"}
            </button>
          </div>
        </form>
      </section>
    </div>
  `;
}

function renderBudgetSettingsModal() {
  const budget = getBudgetSettings();
  const monthlyBudget = Number(budget.monthly_budget ?? 0);
  const threshold = Number(budget.warning_threshold_percent ?? 80);
  const monthly = state.bootstrap?.dashboard?.monthly_statistics ?? {};
  const expense = Number(monthly.total_expense ?? 0);
  const progress = financeProgress(monthly, budget);
  const remaining = Math.max(0, monthlyBudget - expense);
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal compact-modal budget-settings-modal" role="dialog" aria-modal="true" aria-labelledby="budget-settings-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="budget-settings-title">预算管理</h2>
            <p class="section-note">设置本月预算，用于首页预算进度和个人页财务概览。</p>
          </div>
          <button class="button ghost" type="button" data-close-budget-settings aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <div class="budget-preview">
          <div>
            <span>本月已用</span>
            <strong>${money(expense)}</strong>
          </div>
          <div>
            <span>剩余预算</span>
            <strong>${money(remaining)}</strong>
          </div>
          <div>
            <span>使用进度</span>
            <strong class="${progress >= threshold ? "expense" : "income"}">${progress}%</strong>
          </div>
        </div>
        <form class="form" data-budget-settings-form>
          <div class="form-grid">
            <div class="field full">
              <label for="monthly_budget">月预算金额</label>
              <input id="monthly_budget" name="monthly_budget" type="number" min="0" step="0.01" required
                value="${escapeHtml(monthlyBudget)}" />
            </div>
            <div class="field full">
              <label for="warning_threshold_percent">预警比例</label>
              <input id="warning_threshold_percent" name="warning_threshold_percent" type="number" min="1" max="100" step="1" required
                value="${escapeHtml(threshold)}" />
            </div>
          </div>
          <p class="form-hint">当预算使用进度达到预警比例时，页面会用支出色提示；当前先支持全局月预算。</p>
          <div class="form-actions">
            <button class="button ghost" type="button" data-close-budget-settings>取消</button>
            <button class="button primary" type="submit" ${state.saving ? "disabled" : ""}>
              ${icon("save")}${state.saving ? "保存中..." : "保存预算"}
            </button>
          </div>
        </form>
      </section>
    </div>
  `;
}

function renderTagSettingsModal() {
  const tags = getTagSettings().tags;
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal compact-modal tag-settings-modal" role="dialog" aria-modal="true" aria-labelledby="tag-settings-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="tag-settings-title">标签管理</h2>
            <p class="section-note">设置写日记时可以选择的常用标签。</p>
          </div>
          <button class="button ghost" type="button" data-close-tag-settings aria-label="关闭">
            ${icon("close")}
          </button>
        </div>
        <form class="form tag-settings-form" data-tag-settings-form>
          <div class="field">
            <label for="tag_settings_tags">常用标签</label>
            <textarea id="tag_settings_tags" name="tags" maxlength="600" required>${escapeHtml(tags.join("\n"))}</textarea>
            ${renderCategoryPreview(tags)}
          </div>
          <p class="form-hint">支持换行、逗号或分号分隔；会自动去重，单项最多 40 字，最多保留 30 项。</p>
          <div class="form-actions">
            <button class="button ghost" type="button" data-close-tag-settings>取消</button>
            <button class="button primary" type="submit" ${state.saving ? "disabled" : ""}>
              ${icon("save")}${state.saving ? "保存中..." : "保存标签"}
            </button>
          </div>
        </form>
      </section>
    </div>
  `;
}

function renderDiagnosticsModal() {
  const diagnostics = state.diagnostics;
  const integrationDiagnostics = state.integrationDiagnostics;
  const issues = diagnostics?.issues ?? [];
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal diagnostics-modal" role="dialog" aria-modal="true" aria-labelledby="diagnostics-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="diagnostics-title">系统自检</h2>
            <p class="section-note">读取后端数据质量和 AI/OCR 接入状态，帮助定位配置、隐私和数据风险。</p>
          </div>
          <div class="diagnostics-modal-actions">
            <button class="button ghost" type="button" data-refresh-diagnostics
              ${state.diagnosticsLoading ? "disabled" : ""}>
              ${icon("refresh")}${state.diagnosticsLoading ? "刷新中..." : "刷新"}
            </button>
            <button class="button ghost" type="button" data-close-diagnostics aria-label="关闭">
              ${icon("close")}
            </button>
          </div>
        </div>
        <div class="diagnostics-body">
          ${state.diagnosticsLoading && !diagnostics && !integrationDiagnostics ? `<p class="diagnostics-empty">正在运行系统自检...</p>` : ""}
          ${integrationDiagnostics ? renderIntegrationDiagnostics(integrationDiagnostics) : ""}
          ${renderMockProviderGuide()}
          ${renderExternalProviderGuide()}
          ${diagnostics ? `
            <section class="diagnostics-section">
              <div class="diagnostics-section-head">
                <h3>数据质量</h3>
                <span>${escapeHtml(formatDate(diagnostics.generated_at))}</span>
              </div>
              <div class="diagnostics-summary">
                ${diagnosticMetric("状态", diagnosticsStatusLabel(diagnostics.status), diagnostics.status)}
                ${diagnosticMetric("需处理", diagnostics.action_required_count ?? 0, "action_required")}
                ${diagnosticMetric("警告", diagnostics.warning_count ?? 0, "warning")}
                ${diagnosticMetric("提示", diagnostics.info_count ?? 0, "info")}
              </div>
              ${issues.length ? `
                <div class="diagnostics-list">
                  ${issues.map(renderDiagnosticIssue).join("")}
                </div>
              ` : `<p class="diagnostics-empty">没有发现需要处理的问题。</p>`}
              ${diagnostics.truncated ? `<p class="diagnostics-note">问题较多，当前只展示前 ${diagnostics.issue_limit} 条。</p>` : ""}
            </section>
          ` : ""}
        </div>
      </section>
    </div>
  `;
}

function renderExternalProviderGuide() {
  const items = [
    ["realEnv", "外部服务环境变量", "替换 endpoint 和 key 后重启 FastAPI。"],
    ["aiContract", "AI /parse 契约", "账单、待办和聊天意图共用同一个解析入口。"],
    ["ocrContract", "OCR /recognize 契约", "图片文件会以 base64 传给外部 OCR 服务。"],
    ["probe", "真实探测命令", "配置完成后可直接验证四段链路。"],
  ];
  return `
    <section class="diagnostics-section external-provider-guide">
      <div class="diagnostics-section-head">
        <div>
          <h3>真实供应商接入</h3>
          <span>用于接入自建服务或第三方 OCR/AI 网关</span>
        </div>
      </div>
      <div class="external-guide-list">
        ${items.map(([key, title, note]) => renderExternalGuideItem(key, title, note)).join("")}
      </div>
    </section>
  `;
}

function renderExternalGuideItem(key, title, note) {
  const text = integrationGuideText(key);
  return `
    <details class="external-guide-item">
      <summary>
        <span>
          <strong>${escapeHtml(title)}</strong>
          <small>${escapeHtml(note)}</small>
        </span>
        <button class="button ghost compact-button" type="button" data-copy-integration-guide="${escapeHtml(key)}">
          ${icon("copy")}复制
        </button>
      </summary>
      <pre><code>${escapeHtml(text)}</code></pre>
    </details>
  `;
}

function renderMockProviderGuide() {
  const items = [
    ["start", "启动本地 mock Provider", "在单独终端运行，提供 /recognize 和 /parse。"],
    ["env", "配置后端外部服务", "在启动 FastAPI 前运行，让后端走 mock 外部链路。"],
    ["privacy", "隐私开关请求体", "关闭本地模式，并允许外部 AI 整理文字与原始附件保留。"],
  ];
  return `
    <section class="diagnostics-section mock-provider-guide">
      <div class="diagnostics-section-head">
        <h3>本地 mock 测试</h3>
        <span>无需真实供应商账号</span>
      </div>
      <p class="mock-provider-note">按顺序运行下面配置后，再刷新系统自检，应能看到 OCR、AI 解析和聊天意图路由进入外部服务链路。</p>
      <div class="mock-command-list">
        ${items.map(([key, title, note]) => renderMockCommand(key, title, note)).join("")}
      </div>
    </section>
  `;
}

function renderMockCommand(key, title, note) {
  const command = mockProviderCommandText(key);
  return `
    <article class="mock-command">
      <div class="mock-command-head">
        <div>
          <strong>${escapeHtml(title)}</strong>
          <span>${escapeHtml(note)}</span>
        </div>
        <button class="button ghost compact-button" type="button" data-copy-mock-command="${escapeHtml(key)}">
          ${icon("copy")}复制
        </button>
      </div>
      <pre><code>${escapeHtml(command)}</code></pre>
    </article>
  `;
}

function renderIntegrationDiagnostics(integrations) {
  const checks = integrations.checks ?? [];
  const probe = state.integrationProbe;
  return `
    <section class="diagnostics-section">
      <div class="diagnostics-section-head">
        <div>
          <h3>AI/OCR 接入状态</h3>
          <span>${escapeHtml(formatDate(integrations.generated_at))}</span>
        </div>
        <button class="button ghost compact-button" type="button" data-run-integration-probe
          ${state.integrationProbeLoading ? "disabled" : ""}>
          ${icon("refresh")}${state.integrationProbeLoading ? "探测中..." : "真实探测"}
        </button>
      </div>
      <div class="diagnostics-summary integration-summary">
        ${diagnosticMetric("状态", integrationStatusLabel(integrations.status), integrations.status)}
        ${diagnosticMetric("可用", integrations.ready_count ?? 0, "ok")}
        ${diagnosticMetric("回落", integrations.fallback_count ?? 0, "fallback")}
        ${diagnosticMetric("阻断", integrations.blocked_count ?? 0, "blocked")}
      </div>
      ${checks.length ? `
        <div class="integration-list">
          ${checks.map(renderIntegrationCheck).join("")}
        </div>
      ` : `<p class="diagnostics-empty">暂无集成检查结果。</p>`}
      ${probe ? renderIntegrationProbeResults(probe) : `
        <p class="diagnostics-note">真实探测会调用已配置的外部 OCR/AI 服务，并返回最近一次连通性结果；未配置或隐私阻断时会跳过。</p>
      `}
    </section>
  `;
}

function renderIntegrationProbeResults(probe) {
  const results = probe.results ?? [];
  return `
    <div class="integration-probe">
      <div class="integration-probe-head">
        <strong>真实探测结果</strong>
        <span>${escapeHtml(formatDate(probe.generated_at))}</span>
      </div>
      <div class="diagnostics-summary integration-summary probe-summary">
        ${diagnosticMetric("状态", integrationProbeStatusLabel(probe.status), probe.status)}
        ${diagnosticMetric("成功", probe.success_count ?? 0, "success")}
        ${diagnosticMetric("失败", probe.failed_count ?? 0, "failed")}
        ${diagnosticMetric("跳过", probe.skipped_count ?? 0, "skipped")}
      </div>
      ${results.length ? `
        <div class="integration-probe-list">
          ${results.map(renderIntegrationProbeResult).join("")}
        </div>
      ` : `<p class="diagnostics-empty">暂无真实探测结果。</p>`}
    </div>
  `;
}

function renderIntegrationProbeResult(result) {
  const status = result.status || "skipped";
  return `
    <article class="integration-probe-result ${escapeHtml(status)}">
      <span>${icon(integrationIcon(result.name))}</span>
      <div class="integration-check-main">
        <div class="integration-check-title">
          <strong>${escapeHtml(integrationNameLabel(result.name))}</strong>
          <small>${escapeHtml(result.provider || "unknown")}</small>
        </div>
        <p>${escapeHtml(integrationProbeDetailText(result))}</p>
        <small>${escapeHtml(integrationProbeMetaText(result))}</small>
      </div>
      <div class="integration-check-status">
        <strong>${escapeHtml(integrationProbeResultLabel(status))}</strong>
        <span>${escapeHtml(result.error || (result.attempted ? "已请求" : "未请求"))}</span>
      </div>
    </article>
  `;
}

function renderIntegrationCheck(check) {
  const status = check.status || "fallback";
  const warningText = integrationWarningText(check);
  return `
    <article class="integration-check ${escapeHtml(status)}">
      <span>${icon(integrationIcon(check.name))}</span>
      <div class="integration-check-main">
        <div class="integration-check-title">
          <strong>${escapeHtml(integrationNameLabel(check.name))}</strong>
          <small>${escapeHtml(check.provider || "unknown")}</small>
        </div>
        <p>${escapeHtml(warningText)}</p>
        <small>${escapeHtml(integrationMetaText(check))}</small>
      </div>
      <div class="integration-check-status">
        <strong>${escapeHtml(integrationCheckStatusLabel(status))}</strong>
        <span>${escapeHtml(integrationNextAction(check))}</span>
      </div>
    </article>
  `;
}

function integrationIcon(name) {
  return {
    ocr: "camera",
    ai_parser: "spark",
    ai_bill_parser: "receipt",
    ai_task_parser: "check",
    chat_intent: "send",
  }[name] ?? "settings";
}

function integrationNameLabel(name) {
  return {
    ocr: "OCR 文字识别",
    ai_parser: "AI 账单/待办解析",
    ai_bill_parser: "AI 账单解析",
    ai_task_parser: "AI 待办解析",
    chat_intent: "聊天意图识别",
  }[name] ?? name ?? "集成服务";
}

function integrationStatusLabel(status) {
  return {
    ready: "外部服务可用",
    blocked: "隐私阻断",
    fallback: "本地兜底",
  }[status] ?? "未知";
}

function integrationCheckStatusLabel(status) {
  return {
    ready: "可用",
    blocked: "阻断",
    fallback: "回落",
  }[status] ?? "未知";
}

function integrationProbeStatusLabel(status) {
  return {
    success: "探测通过",
    failed: "探测失败",
    skipped: "已跳过",
  }[status] ?? "未知";
}

function integrationProbeResultLabel(status) {
  return {
    success: "通过",
    failed: "失败",
    skipped: "跳过",
  }[status] ?? "未知";
}

function integrationWarningText(check) {
  const tokens = [
    ...(check.privacy_blockers ?? []),
    ...(check.warnings ?? []),
  ].map(integrationCodeLabel).filter(Boolean);
  if (!tokens.length) {
    return "当前配置可用，相关流程会优先使用外部服务。";
  }
  return tokens.join("；");
}

function integrationMetaText(check) {
  const endpointText = check.endpoint_configured ? "接口已配置" : "接口未配置";
  const keyText = check.api_key_configured ? "密钥已配置" : "密钥未配置";
  const capabilities = (check.capabilities ?? [])
    .map(integrationCapabilityLabel)
    .filter(Boolean)
    .join("、");
  return [endpointText, keyText, capabilities].filter(Boolean).join(" · ");
}

function integrationNextAction(check) {
  if (check.status === "ready") {
    return "当前流程可使用";
  }
  if ((check.privacy_blockers ?? []).length) {
    return "检查隐私设置";
  }
  return {
    ocr: "配置 OCR 服务",
    ai_parser: "配置 AI 解析服务",
    chat_intent: "配置 AI 解析服务",
  }[check.name] ?? "补充配置";
}

function integrationProbeDetailText(result) {
  const warnings = [
    ...(result.privacy_blockers ?? []),
    ...(result.warnings ?? []),
  ].map(integrationCodeLabel).filter(Boolean);
  if (warnings.length) {
    return warnings.join("；");
  }
  const preview = result.response_preview ?? {};
  if (result.name === "ocr" && preview.text_sample) {
    return `识别样例：${preview.text_sample}`;
  }
  if (result.name === "ai_bill_parser") {
    return [preview.merchant, preview.amount ? `¥${preview.amount}` : "", preview.category]
      .filter(Boolean)
      .join(" · ") || "账单解析链路正常";
  }
  if (result.name === "ai_task_parser") {
    return [preview.title, preview.category, preview.task_type]
      .filter(Boolean)
      .join(" · ") || "待办解析链路正常";
  }
  if (result.name === "chat_intent") {
    return preview.intent ? `识别意图：${preview.intent}` : "聊天意图链路正常";
  }
  return result.success ? "连通性正常" : "等待探测结果";
}

function integrationProbeMetaText(result) {
  const latency = result.latency_ms == null ? null : `${result.latency_ms}ms`;
  const configured = result.configured ? "已配置" : "未配置";
  const attempted = result.attempted ? "已调用" : "未调用";
  return [configured, attempted, latency].filter(Boolean).join(" · ");
}

function integrationCodeLabel(code) {
  return {
    local_only_mode_enabled: "本地模式开启，外部服务不会被调用",
    ai_text_processing_disabled: "AI 文本处理已关闭",
    ocr_engine_not_configured: "未配置外部 OCR，图片识别会使用手动兜底",
    original_attachment_required_for_external_ocr: "外部 OCR 需要保留原始附件文件",
    rule_based_parser_fallback: "未配置外部 AI 解析，账单/待办使用规则解析",
    keyword_router_fallback: "未配置外部聊天路由，助手使用关键词判断意图",
    external_processing_blocked: "隐私设置阻止外部处理",
    external_ocr_failed: "外部 OCR 请求失败",
    external_ocr_invalid_response: "外部 OCR 响应格式异常",
    external_ocr_empty_text: "外部 OCR 未返回文字",
    external_ai_parser_failed: "外部 AI 解析请求失败",
    external_ai_parser_invalid_response: "外部 AI 解析响应格式异常",
    external_chat_intent_invalid_response: "外部聊天意图响应格式异常",
    llm_agent_failed: "大模型 Agent 请求失败",
    llm_agent_invalid_response: "大模型 Agent 响应格式异常",
    llm_agent_function_calling_unavailable: "大模型工具调用不可用，已降级解析",
    deepseek_api_key_missing: "DeepSeek API Key 未配置",
  }[code] ?? code;
}

function integrationCapabilityLabel(value) {
  return {
    attachment_text_recognition: "附件识别",
    stored_text_fallback: "文本兜底",
    bill_candidate_parsing: "账单候选",
    task_candidate_parsing: "待办候选",
    chat_intent_routing: "聊天路由",
    chat_candidate_flow: "候选确认",
    llm_agent_reasoning: "大模型 Agent",
    llm_json_output: "严格 JSON 输出",
    llm_function_calling: "函数调用",
    deepseek_chat_completions: "DeepSeek Chat Completions",
  }[value] ?? value;
}

function diagnosticMetric(label, value, tone) {
  return `
    <div class="diagnostic-metric ${escapeHtml(tone)}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function renderDiagnosticIssue(issue) {
  const severity = issue.severity || "info";
  return `
    <article class="diagnostic-issue ${escapeHtml(severity)}">
      <span>${escapeHtml(diagnosticSeverityLabel(severity))}</span>
      <div>
        <strong>${escapeHtml(diagnosticIssueTitle(issue))}</strong>
        <p>${escapeHtml(diagnosticIssueMessage(issue))}</p>
        ${diagnosticIssueMeta(issue) ? `<small>${escapeHtml(diagnosticIssueMeta(issue))}</small>` : ""}
      </div>
    </article>
  `;
}

function diagnosticsStatusLabel(status) {
  return {
    ok: "状态良好",
    warning: "有风险提醒",
    action_required: "需要处理",
  }[status] ?? "未知";
}

function diagnosticSeverityLabel(severity) {
  return {
    action_required: "需处理",
    warning: "警告",
    info: "提示",
  }[severity] ?? "提示";
}

function diagnosticIssueTitle(issue) {
  return {
    ai_text_processing_disabled: "AI 文本处理已关闭",
    original_attachment_retention_enabled: "保留上传的原图",
    attachment_missing_ocr_text: "附件缺少 OCR 文本",
    duplicate_attachment: "发现重复附件",
    pending_bill_candidates: "有待确认账单候选",
    pending_task_candidates: "有待确认待办候选",
    pending_diary_candidates: "有待确认日记候选",
    bill_candidate_missing_required_fields: "账单候选缺少必要字段",
    task_candidate_missing_required_fields: "待办候选缺少必要字段",
    diary_candidate_missing_required_fields: "日记候选缺少必要字段",
    possible_duplicate_bill: "可能存在重复账单",
    unscheduled_pending_task: "待办未设置时间",
    overdue_task: "待办已逾期",
    deleted_bills_in_recycle_bin: "回收站中有已删除账单",
    deleted_tasks_in_recycle_bin: "回收站中有已删除待办",
  }[issue.code] ?? issue.code ?? "诊断问题";
}

function diagnosticIssueMessage(issue) {
  return {
    ai_text_processing_disabled: "聊天解析、图片识别后的 AI 解析会受限，可在隐私设置中重新开启。",
    original_attachment_retention_enabled: "这会增加本地存储占用，也会提高原始图片暴露风险。",
    attachment_missing_ocr_text: "该附件可能需要重新识别，或手动补充成账单/日记内容。",
    duplicate_attachment: "多个附件的校验值相同，可以后续清理重复文件。",
    pending_bill_candidates: "助手识别出的账单还没有确认保存。",
    pending_task_candidates: "助手识别出的待办还没有确认保存。",
    pending_diary_candidates: "助手整理出的日记还没有确认保存。",
    bill_candidate_missing_required_fields: "缺少金额，暂时不能确认保存。",
    task_candidate_missing_required_fields: "缺少标题或提醒时间，暂时不能确认保存。",
    diary_candidate_missing_required_fields: "缺少日期、标题或正文，暂时不能确认保存。",
    possible_duplicate_bill: "两条账单金额、类型、时间很接近，商家/用途也一致或都未填写，建议核对。",
    unscheduled_pending_task: "待办没有到期或提醒时间，可能难以及时触达。",
    overdue_task: "这条待办已经超过目标时间，需要处理或延后。",
    deleted_bills_in_recycle_bin: "可以在回收站查看并恢复误删账单。",
    deleted_tasks_in_recycle_bin: "可以在回收站查看并恢复误删待办。",
  }[issue.code] ?? issue.message ?? "";
}

function diagnosticIssueMeta(issue) {
  const metadata = issue.metadata ?? {};
  if (metadata.filename) return `文件：${metadata.filename}`;
  if (metadata.title) return `标题：${metadata.title}`;
  if (metadata.merchant) return `商家/用途：${metadata.merchant}，金额：${metadata.amount ?? "未知"}`;
  if (metadata.candidate_count) return `候选数量：${metadata.candidate_count}`;
  if (metadata.deleted_bill_count) return `已删除账单：${metadata.deleted_bill_count}`;
  if (metadata.deleted_task_count) return `已删除待办：${metadata.deleted_task_count}`;
  return issue.entity_type ? `类型：${issue.entity_type}` : "";
}

function renderAuditLogModal() {
  const log = state.auditLog;
  const events = log?.items ?? [];
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal audit-modal" role="dialog" aria-modal="true" aria-labelledby="audit-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="audit-title">最近操作</h2>
            <p class="section-note">查看最近的新增、修改、删除和恢复操作。</p>
          </div>
          <div class="audit-modal-actions">
            <button class="button ghost" type="button" data-refresh-audit-log
              ${state.auditLogLoading ? "disabled" : ""}>
              ${icon("refresh")}${state.auditLogLoading ? "刷新中..." : "刷新"}
            </button>
            <button class="button ghost" type="button" data-close-audit-log aria-label="关闭">
              ${icon("close")}
            </button>
          </div>
        </div>
        <div class="audit-body">
          ${state.auditLogLoading && !log ? `<p class="audit-empty">正在读取操作记录...</p>` : ""}
          ${!state.auditLogLoading && !events.length ? `<p class="audit-empty">暂无操作记录。</p>` : ""}
          ${events.length ? `
            <div class="audit-list">
              ${events.map(renderAuditEvent).join("")}
            </div>
            <p class="audit-note">共 ${Number(log?.total ?? events.length)} 条记录，当前显示最近 ${events.length} 条。</p>
          ` : ""}
        </div>
      </section>
    </div>
  `;
}

function renderAuditEvent(event) {
  return `
    <article class="audit-event">
      <span>${icon(auditEventIcon(event))}</span>
      <div class="audit-event-main">
        <strong>${escapeHtml(auditActionLabel(event.action))}</strong>
        <small>${escapeHtml(auditEventMeta(event))}</small>
        ${renderAuditEventDetail(event)}
      </div>
      <time>${escapeHtml(formatDate(event.occurred_at))}</time>
    </article>
  `;
}

function auditEventIcon(event) {
  const action = event.action || "";
  if (action.includes("deleted")) return "trash";
  if (action.includes("restored") || action.includes("loaded") || action.includes("imported")) return "upload";
  if (action.includes("exported") || action.includes("saved")) return "download";
  if (action.includes("updated")) return "edit";
  if (action.includes("created") || action.includes("seeded")) return "plus";
  return "file-text";
}

function auditActionLabel(action) {
  return {
    bill_created: "创建账单",
    bill_updated: "更新账单",
    bill_deleted: "删除账单",
    bill_restored: "恢复账单",
    task_created: "创建待办",
    task_updated: "更新待办",
    task_completed: "完成待办",
    task_snoozed: "延后待办",
    task_deleted: "删除待办",
    task_restored: "恢复待办",
    diary_created: "创建日记",
    diary_upserted: "保存日记",
    diary_updated: "更新日记",
    diary_deleted: "删除日记",
    diary_restored: "恢复日记",
    attachment_uploaded: "上传附件",
    attachment_deleted: "删除附件",
    attachment_ocr_recognized: "识别附件文字",
    attachment_bill_parsed: "解析附件账单",
    bill_candidate_confirmed: "确认账单候选",
    bill_candidate_deleted: "删除账单候选",
    task_candidate_confirmed: "确认待办候选",
    task_candidate_deleted: "删除待办候选",
    chat_message_processed: "处理助手消息",
    privacy_settings_updated: "更新隐私设置",
    data_exported: "导出数据",
    data_imported: "导入数据",
    data_import_dry_run: "预览导入数据",
    data_snapshot_saved: "保存本地快照",
    data_snapshot_loaded: "加载本地快照",
    data_snapshot_load_dry_run: "预览加载快照",
    data_snapshot_deleted: "删除本地快照",
    data_cleared: "清除本地数据",
    demo_data_seeded: "生成演示数据",
  }[action] ?? action ?? "未知操作";
}

function auditEventMeta(event) {
  const parts = [];
  if (event.entity_type) {
    parts.push(auditEntityLabel(event.entity_type));
  }
  if (event.method && event.path) {
    parts.push(`${event.method} ${event.path}`);
  }
  if (event.request_id) {
    parts.push(`请求 ${String(event.request_id).slice(0, 8)}`);
  }
  return parts.join(" · ") || "本地操作记录";
}

function renderAuditEventDetail(event) {
  if (event.action !== "chat_message_processed") {
    return "";
  }
  const metadata = event.metadata ?? {};
  const details = [
    chatIntentDisplay(metadata.intent),
    chatActionDisplay(metadata.action_type),
    metadata.need_user_confirmation ? "等待确认" : "无需确认",
    metadata.agent_step_count ? `步骤 ${metadata.agent_step_count}` : "",
  ].filter(Boolean);

  if (!details.length) {
    return "";
  }

  return `
    <div class="audit-detail-chips">
      ${details.map((detail) => `<span>${escapeHtml(detail)}</span>`).join("")}
    </div>
  `;
}

function chatIntentDisplay(intent) {
  return {
    create_bill: "记账",
    analyze_bills: "账单分析",
    create_task: "提醒",
    create_diary: "日记",
    diary_reflection: "日记追问",
    knowledge_answer: "知识问答",
    unsupported: "未支持",
  }[intent] ?? "";
}

function chatActionDisplay(actionType) {
  return {
    bill_candidate: "账单候选",
    task_candidate: "待办候选",
    diary_candidate: "日记候选",
    none: "无候选",
  }[actionType] ?? "";
}

function auditEntityLabel(entityType) {
  return {
    bill: "账单",
    task: "待办",
    diary: "日记",
    attachment: "附件",
    bill_candidate: "账单候选",
    task_candidate: "待办候选",
    diary_candidate: "日记候选",
    settings: "设置",
    data: "数据",
    chat: "助手",
  }[entityType] ?? entityType;
}

function privacySettingRow(key, title, note, enabled) {
  return `
    <div class="privacy-setting-row">
      <div>
        <strong>${escapeHtml(title)}</strong>
        <small>${escapeHtml(note)}</small>
      </div>
      <button class="privacy-switch ${enabled ? "is-on" : ""}" type="button"
        role="switch"
        aria-checked="${enabled ? "true" : "false"}"
        data-privacy-toggle="${escapeHtml(key)}"
        ${state.saving ? "disabled" : ""}>
        <span></span>
        <b>${enabled ? "开" : "关"}</b>
      </button>
    </div>
  `;
}

function importPreviewMetric(label, value, note) {
  return `
    <div class="import-preview-card">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(String(value ?? 0))}</strong>
      <small>${escapeHtml(note)}</small>
    </div>
  `;
}

function renderRecycleBinModal() {
  const recycle = state.recycleBin ?? emptyRecycleBin();
  const total = recycle.bills.length + recycle.tasks.length + recycle.diaries.length;
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal recycle-modal" role="dialog" aria-modal="true" aria-labelledby="recycle-title">
        <div class="modal-header">
          <div>
            <h2 class="modal-title" id="recycle-title">回收站</h2>
            <p class="section-note">这里展示最近 50 条软删除数据，可以按条恢复到原页面。</p>
          </div>
          <div class="recycle-modal-actions">
            <button class="button ghost" type="button" data-refresh-recycle-bin
              ${state.recycleBinLoading || state.saving ? "disabled" : ""}>
              ${icon("refresh")}${state.recycleBinLoading ? "刷新中..." : "刷新"}
            </button>
            <button class="button ghost" type="button" data-close-recycle-bin aria-label="关闭">
              ${icon("close")}
            </button>
          </div>
        </div>
        <div class="recycle-body">
          ${state.recycleBinLoading ? `<p class="recycle-empty">正在加载已删除数据...</p>` : ""}
          ${!state.recycleBinLoading && !total ? `<p class="recycle-empty">暂无已删除数据。</p>` : ""}
          ${!state.recycleBinLoading ? `
            ${renderRecycleGroup("账单", "bill", recycle.bills)}
            ${renderRecycleGroup("待办", "task", recycle.tasks)}
            ${renderRecycleGroup("日记", "diary", recycle.diaries)}
          ` : ""}
        </div>
      </section>
    </div>
  `;
}

function renderRecycleGroup(title, type, items) {
  if (!items.length) {
    return "";
  }
  return `
    <section class="recycle-section">
      <h3>${escapeHtml(title)} <span>${items.length}</span></h3>
      <div class="recycle-list">
        ${items.map((item) => renderRecycleItem(type, item)).join("")}
      </div>
    </section>
  `;
}

function renderRecycleItem(type, item) {
  const config = recycleItemDisplay(type, item);
  return `
    <article class="recycle-item">
      <span class="recycle-item-icon">${icon(config.iconName)}</span>
      <div class="recycle-item-main">
        <strong>${escapeHtml(config.title)}</strong>
        <small>${escapeHtml(config.meta)}</small>
      </div>
      <button class="button ghost" type="button"
        data-restore-recycle="${escapeHtml(type)}"
        data-recycle-id="${escapeHtml(item.id)}"
        ${state.saving ? "disabled" : ""}>
        ${icon("upload")}${state.saving ? "恢复中..." : "恢复"}
      </button>
    </article>
  `;
}

function recycleItemDisplay(type, item) {
  if (type === "bill") {
    return {
      iconName: iconForBill(item),
      title: `${billDisplayName(item)} · ${money(item.amount)}`,
      meta: `${labelTransaction(item.transaction_type)} · ${item.category || "未分类"} · 删除于 ${formatDate(item.deleted_at)}`,
    };
  }
  if (type === "task") {
    return {
      iconName: item.task_type === "reminder" ? "bell" : "check",
      title: item.title || "未命名待办",
      meta: `${labelTaskStatus(item.status)} · ${item.category || "未分类"} · 删除于 ${formatDate(item.deleted_at)}`,
    };
  }
  return {
    iconName: "notebook",
    title: item.title || "今天的日记",
    meta: `${item.entry_date || "未设置日期"} · ${diaryMoodLabel(item.mood)} · 删除于 ${formatDate(item.deleted_at)}`,
  };
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
    return "还没有本机备份。";
  }
  const summary = snapshot.snapshot_data_summary;
  const parts = [];
  if (summary) {
    parts.push(`${summary.bill_count} 条账单`);
    parts.push(`${summary.task_count} 条待办`);
    if (deletedDataCount(summary)) {
      parts.push("含回收站中的记录");
    }
  }
  const updatedAt = snapshot.updated_at ? `更新于 ${formatDate(snapshot.updated_at)}` : "已保存";
  return `${updatedAt}${parts.length ? `，${parts.join("，")}` : ""}`;
}

function recycleBinText(summary = {}) {
  const parts = [];
  const deletedBills = Number(summary.deleted_bill_count ?? 0);
  const deletedTasks = Number(summary.deleted_task_count ?? 0);
  const deletedDiaries = Number(summary.deleted_diary_count ?? 0);
  if (deletedBills) parts.push(`${deletedBills} 条账单`);
  if (deletedTasks) parts.push(`${deletedTasks} 条待办`);
  if (deletedDiaries) parts.push(`${deletedDiaries} 篇日记`);
  return parts.length ? `可恢复：${parts.join("，")}` : "暂无已删除数据。";
}

function deletedDataCount(summary = {}) {
  return Number(summary.deleted_bill_count ?? 0)
    + Number(summary.deleted_task_count ?? 0)
    + Number(summary.deleted_diary_count ?? 0);
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
  const prefix = bill.transaction_type === "expense" ? "−" : ["income", "refund"].includes(bill.transaction_type) ? "+" : "";
  return `${prefix}${money(bill.amount)}`;
}

function billDisplayName(bill) {
  return String(bill?.merchant || bill?.category || labelTransaction(bill?.transaction_type) || "未填写");
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

function getCategorySettings() {
  return {
    bill_categories: normalizeCategories(
      state.categorySettings?.bill_categories,
      defaultCategorySettings.bill_categories,
    ),
    task_categories: normalizeCategories(
      state.categorySettings?.task_categories,
      defaultCategorySettings.task_categories,
    ),
  };
}

function getBudgetSettings() {
  const source = state.budgetSettings ?? state.bootstrap?.budget_settings ?? defaultBudgetSettings;
  const monthlyBudget = Number(source.monthly_budget ?? defaultBudgetSettings.monthly_budget);
  const threshold = Number(
    source.warning_threshold_percent ?? defaultBudgetSettings.warning_threshold_percent,
  );
  return {
    monthly_budget: Number.isFinite(monthlyBudget) && monthlyBudget >= 0
      ? monthlyBudget
      : defaultBudgetSettings.monthly_budget,
    currency: source.currency || defaultBudgetSettings.currency,
    warning_threshold_percent: Number.isFinite(threshold)
      ? Math.min(100, Math.max(1, Math.round(threshold)))
      : defaultBudgetSettings.warning_threshold_percent,
  };
}

function normalizeCategories(values, fallback) {
  return normalizeLabels(values, fallback, 30);
}

function getTagSettings() {
  const source = state.tagSettings ?? state.bootstrap?.tag_settings ?? defaultTagSettings;
  return {
    tags: normalizeLabels(source.tags, defaultTagSettings.tags, 30),
  };
}

function normalizeLabels(values, fallback, limit = 30) {
  const normalized = [];
  (Array.isArray(values) ? values : fallback).forEach((value) => {
    const text = String(value || "").trim();
    if (!text || text.length > 40 || normalized.includes(text)) {
      return;
    }
    normalized.push(text);
  });
  return normalized.length ? normalized.slice(0, limit) : fallback.slice();
}

function parseCategoryInput(value) {
  return parseLabelInput(value, 30);
}

function parseLabelInput(value, limit = 30) {
  return normalizeLabels(
    String(value || "")
      .split(/[\n,，;；]+/)
      .map((item) => item.trim()),
    [],
    limit,
  );
}

function renderCategoryPreview(categories) {
  const items = normalizeCategories(categories, []);
  if (!items.length) {
    return `<p class="form-hint">暂无分类。</p>`;
  }
  return `
    <div class="category-preview-list" aria-label="分类预览">
      ${items
        .slice(0, 12)
        .map((item) => `<span class="category-preview-chip">${escapeHtml(item)}</span>`)
        .join("")}
      ${items.length > 12 ? `<span class="category-preview-chip muted">+${items.length - 12}</span>` : ""}
    </div>
  `;
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
    "alert-circle": '<circle cx="12" cy="12" r="9"></circle><path d="M12 7v6"></path><path d="M12 17h.01"></path>',
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
    copy: '<rect x="9" y="9" width="11" height="11" rx="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>',
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
