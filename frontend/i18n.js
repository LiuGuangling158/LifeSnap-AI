(function () {
  const supportedLanguages = ["zh-CN", "en-US"];

  const languageMeta = {
    "zh-CN": {
      code: "zh-CN",
      locale: "zh-CN",
      title: "LifeSnap · 轻松记账",
      speechLocale: "zh-CN",
    },
    "en-US": {
      code: "en-US",
      locale: "en-US",
      title: "LifeSnap · Easy Expense Tracking",
      speechLocale: "en-US",
    },
  };

  const en = {
    "首页": "Home",
    "账单": "Bills",
    "待办": "Tasks",
    "日记": "Diary",
    "助手": "Assistant",
    "设置": "Settings",
    "更多": "More",
    "AI 记账": "AI Ledger",
    "AI 帮记": "AI Ledger",
    "本地体验": "Local Experience",
    "手动记录": "Manual Entry",
    "提醒辅助": "Reminder Helper",
    "生活记录": "Life Log",
    "帮你整理": "Organize for You",
    "隐私与数据": "Privacy & Data",
    "今天先把账记顺": "Get today recorded clearly",
    "记下收支，随时知道钱花在哪里。": "Track income and expenses, and know where your money goes.",
    "账单列表": "Bill List",
    "查找、核对和修改每一笔收支。": "Find, review, and edit every transaction.",
    "待办提醒": "Task Reminders",
    "把要做的事记下来。": "Keep track of what needs to be done.",
    "留下一点今天的心情。": "Save a little bit of today's mood.",
    "智能助手": "Smart Assistant",
    "把一句话、图片或语音整理成可确认的生活操作。": "Turn text, images, or voice into actions you can confirm.",
    "管理个人偏好和数据备份。": "Manage preferences and data backups.",
    "按你的习惯来": "Make it yours",
    "更多与设置": "More & Settings",
    "日常工具、个人偏好和数据管理。": "Daily tools, preferences, and data management.",
    "语言": "Language",
    "界面语言": "Interface language",
    "切换后只影响界面展示，不会修改已有账单、分类和智能体参数。": "Switching only changes the interface. Existing bills, categories, and agent parameters stay unchanged.",
    "中文": "Chinese",
    "英文": "English",
    "生活记录": "Life Log",
    "待办事项": "Tasks",
    "查看、新增和完成待办": "View, add, and complete tasks",
    "我的日记": "My Diary",
    "记录文字、照片和心情": "Record text, photos, and moods",
    "记账偏好": "Ledger Preferences",
    "月预算": "Monthly Budget",
    "收支分类": "Income & Expense Categories",
    "调整餐饮、交通等常用分类": "Adjust common categories like dining and transport",
    "隐私设置": "Privacy Settings",
    "选择图片和文字是否允许交给外部 AI 处理": "Choose whether images and text can be processed by external AI",
    "我的数据": "My Data",
    "导出备份文件": "Export Backup",
    "下载账单、待办和日记，方便保留或迁移": "Download bills, tasks, and diaries for backup or migration",
    "从备份文件恢复": "Restore from Backup",
    "选择之前导出的文件，预览后再导入": "Choose an exported file, preview it, then import",
    "回收站": "Recycle Bin",
    "更多设置": "More Settings",
    "个人资料、备份与问题排查": "Profile, backup, and troubleshooting",
    "个人资料": "Profile",
    "修改昵称和签名": "Edit nickname and signature",
    "日记标签": "Diary Tags",
    "管理记录生活的常用标签": "Manage tags used for life logs",
    "保存本机备份": "Save Local Backup",
    "在当前设备上保留一份可恢复的记录": "Keep a restorable copy on this device",
    "恢复本机备份": "Restore Local Backup",
    "最近操作": "Recent Activity",
    "查看记录的新增、修改和删除操作": "View create, update, and delete activity",
    "连接与问题排查": "Connections & Troubleshooting",
    "识别不可用时，在这里查看原因": "Check here when recognition is unavailable",
    "清空所有记录": "Clear All Records",
    "清空前会再次确认，建议先导出备份": "You will confirm first. Export a backup before clearing.",
    "今天": "Today",
    "本月": "This Month",
    "全部": "All",
    "收入": "Income",
    "支出": "Expense",
    "金额": "Amount",
    "类型": "Type",
    "分类": "Category",
    "商家": "Merchant",
    "备注": "Notes",
    "日期": "Date",
    "时间": "Time",
    "搜索": "Search",
    "筛选": "Filter",
    "重置": "Reset",
    "保存": "Save",
    "保存中...": "Saving...",
    "取消": "Cancel",
    "确认": "Confirm",
    "删除": "Delete",
    "编辑": "Edit",
    "关闭": "Close",
    "撤销": "Undo",
    "恢复": "Restore",
    "恢复中...": "Restoring...",
    "导出": "Export",
    "导入": "Import",
    "上传": "Upload",
    "上传图片": "Upload Image",
    "语音输入": "Voice Input",
    "停止": "Stop",
    "开始": "Start",
    "发送": "Send",
    "帮我整理": "Organize",
    "需要确认": "Needs Review",
    "已执行": "Done",
    "执行中": "Running",
    "读取图片": "Read Image",
    "已接收上传图片并尝试识别内容。": "Received the uploaded image and tried to recognize its content.",
    "暂时没有足够信息生成可确认账单。": "There is not enough information yet to create a bill for review.",
    "图片记账": "Image Ledger",
    "文字记账": "Text Ledger",
    "预算分析": "Budget Analysis",
    "消费分析": "Spending Analysis",
    "可视化分析": "Visual Analysis",
    "AI 评估": "AI Assessment",
    "折线图": "Line Chart",
    "趋势": "Trend",
    "类别": "Category",
    "占比": "Share",
    "餐饮": "Dining",
    "交通": "Transport",
    "购物": "Shopping",
    "日用": "Daily Goods",
    "医疗": "Healthcare",
    "娱乐": "Entertainment",
    "学习": "Education",
    "住房": "Housing",
    "工资": "Salary",
    "其他": "Other",
    "生活": "Life",
    "工作": "Work",
    "个人": "Personal",
    "财务": "Finance",
    "健康": "Health",
    "开心": "Happy",
    "轻松": "Relaxed",
    "成长": "Growth",
    "朋友": "Friends",
    "家庭": "Family",
    "旅行": "Travel",
    "新增账单": "Add Bill",
    "编辑账单": "Edit Bill",
    "保存账单": "Save Bill",
    "账单详情": "Bill Details",
    "新增待办": "Add Task",
    "编辑待办": "Edit Task",
    "保存待办": "Save Task",
    "写日记": "Write Diary",
    "保存日记": "Save Diary",
    "通知中心": "Notification Center",
    "提醒摘要": "Reminder Summary",
    "逾期": "Overdue",
    "今日": "Today",
    "即将到来": "Upcoming",
    "逾期待处理": "Overdue",
    "今天要处理": "Due Today",
    "未来提醒": "Future Reminders",
    "暂无通知": "No Notifications",
    "问候昵称": "Greeting Name",
    "生活签名": "Life Signature",
    "头像色调": "Avatar Tone",
    "暖阳": "Warm Sun",
    "薄荷": "Mint",
    "天空": "Sky",
    "粉桃": "Rose",
    "保存资料": "Save Profile",
    "用于个人页问候展示，暂存在当前浏览器。": "Used for greetings on your profile page and stored in this browser.",
    "记录生活，遇见更好的自己": "Record life and meet a better self",
    "今天也要加油呀": "Let's make today count",
    "当前设备": "Current Device",
    "本地": "Local",
    "外部 AI": "External AI",
    "已开启": "On",
    "已关闭": "Off",
    "启用": "Enable",
    "停用": "Disable",
    "已删除": "Deleted",
    "账单已删除": "Bill deleted",
    "日记已删除": "Diary deleted",
    "待办已删除": "Task deleted",
    "这笔账已保存，可以在账单里查看。": "This bill has been saved. You can view it in Bills.",
    "事项已保存，可以在待办里查看。": "This task has been saved. You can view it in Tasks.",
    "日记已保存，可以在日记里查看。": "This diary entry has been saved. You can view it in Diary.",
    "这笔账没有保存。": "This bill was not saved.",
    "这件事没有保存。": "This task was not saved.",
    "这篇日记没有保存。": "This diary entry was not saved.",
    "待核对账单": "Bill to Review",
    "待核对事项": "Task to Review",
    "待核对记录": "Record to Review",
    "待核对日记": "Diary to Review",
    "待核对内容": "Content to Review",
    "信息": "Info",
    "本月预算": "Monthly Budget",
    "预算": "Budget",
    "消费": "Spending",
    "结余": "Balance",
    "平均": "Average",
    "最高": "Highest",
    "最低": "Lowest",
    "同比": "YoY",
    "环比": "MoM",
    "完成": "Done",
    "未完成": "Pending",
    "进行中": "In Progress",
    "暂无数据": "No data yet",
    "暂无记录": "No records yet",
    "加载中...": "Loading...",
    "请求失败": "Request failed",
    "企业级就绪度": "Enterprise Readiness",
    "就绪": "Ready",
    "降级": "Degraded",
    "可用但降级": "Available but degraded",
    "已就绪": "Ready",
    "已检查": "Checked",
    "知识": "Knowledge",
    "审计": "Audit",
    "问题": "Issues",
    "管理": "Admin",
    "管理员": "Admin",
    "管理员页面": "Admin Page",
    "RAG 管理": "RAG Admin",
    "Agent RAG 管理": "Agent RAG Admin",
    "更新 Agent 的 RAG 业务知识库。": "Update the Agent's RAG business knowledge base.",
    "更新本地业务知识库，下一次对话和 function calling 检索会直接使用新内容。": "Update the local business knowledge base. The next chat and function calling retrieval will use the new content directly.",
    "刷新知识库": "Refresh Knowledge Base",
    "刷新中...": "Refreshing...",
    "去测试 Agent": "Test Agent",
    "活跃知识": "Active Docs",
    "内置知识": "Built-in Docs",
    "管理员知识": "Admin Docs",
    "最近刷新": "Last Refreshed",
    "现有知识库内容": "Current Knowledge Base Content",
    "这里是当前实际参与 RAG 检索的完整内容（内置 + 管理员覆盖），只读查看。": "This is the complete read-only content currently used by RAG retrieval: built-in docs plus admin overrides.",
    "复制 JSON": "Copy JSON",
    "下载 JSON": "Download JSON",
    "如果这里有内容而下方编辑框是 []，说明当前只有内置知识，还没有管理员自定义条目。": "If this area has content but the editor below is [], the app only has built-in knowledge and no admin custom documents yet.",
    "已复制现有知识库内容": "Current knowledge base content copied",
    "已下载现有知识库 JSON": "Current knowledge base JSON downloaded",
    "RAG 检索测试": "RAG Search Test",
    "先用真实问题测试命中情况，再决定是否补充关键词或正文。": "Test real queries first, then decide whether to add keywords or content.",
    "测试检索词": "Search Test Query",
    "例如：奶茶应该归到什么分类？": "Example: Which category should milk tea use?",
    "测试检索": "Test Search",
    "检索中...": "Searching...",
    "还没有检索结果。保存知识后，可以在这里验证 RAG 是否命中。": "No search results yet. After saving knowledge, verify RAG hits here.",
    "RAG 版本历史": "RAG Version History",
    "每次保存、重置或回滚都会生成快照，便于审计和恢复。": "Each save, reset, or rollback creates a snapshot for audit and recovery.",
    "还没有版本记录。保存或重置管理员知识后会自动生成快照。": "No versions yet. Saving or resetting admin knowledge will create a snapshot automatically.",
    "空管理员知识库": "Empty admin knowledge base",
    "管理员知识": "Admin Docs",
    "启用": "Enabled",
    "保存": "Save",
    "重置": "Reset",
    "回滚": "Rollback",
    "回滚中...": "Rolling back...",
    "RAG 知识库已回滚，并生成新的版本记录。": "RAG knowledge base rolled back and a new version was created.",
    "编辑管理员知识": "Edit Admin Knowledge",
    "这里不是现有知识库全文，只编辑管理员自定义条目；内置知识保留在代码里，必要时可用相同 source_id 覆盖。": "This is not the full current knowledge base. It only edits admin custom documents. Built-in documents remain in code and can be overridden with the same source_id.",
    "恢复内置知识": "Restore Built-in Knowledge",
    "管理员密钥": "Admin Key",
    "对应后端 LIFESNAP_ADMIN_KEY": "Matches backend LIFESNAP_ADMIN_KEY",
    "输入管理员密钥后才能保存": "Enter the admin key before saving",
    "读取中...": "Loading...",
    "填入本机密钥": "Fill Local Key",
    "仅当后端启用 LIFESNAP_ALLOW_ADMIN_KEY_REVEAL=true 且从本机访问时可用。": "Available only when the backend enables LIFESNAP_ALLOW_ADMIN_KEY_REVEAL=true and the app is opened locally.",
    "已从本机环境填入管理员密钥。": "Admin key filled from the local environment.",
    "知识库 JSON": "Knowledge Base JSON",
    "数组格式，最多 50 条": "Array format, up to 50 items",
    "JSON 示例": "JSON Example",
    "source_id、title、content 必填": "source_id, title, and content are required",
    "重新读取": "Reload",
    "保存知识库": "Save Knowledge Base",
    "当前知识条目": "Current Knowledge Documents",
    "这里展示实际参与管理视图的知识，管理员覆盖项会标记为自定义。": "This shows the knowledge visible to admin management. Admin overrides are marked as custom.",
    "知识库暂时为空。": "The knowledge base is empty.",
    "内置": "Built-in",
    "已禁用": "Disabled",
    "关键词": "Keywords",
    "搜索商家或备注": "Search merchant or notes",
    "搜索商家、用途或备注": "Search merchant, purpose, or notes",
    "清除": "Clear",
    "金额（元）": "Amount (CNY)",
    "收支类型": "Transaction Type",
    "商家或用途": "Merchant or Purpose",
    "支付方式": "Payment Method",
    "选填": "Optional",
    "如 餐饮": "e.g. Dining",
    "商家/用途、分类、支付方式或备注": "Merchant/purpose, category, payment method, or notes",
    "商家/用途、分类、备注": "Merchant/purpose, category, or notes",
    "例如：午餐、超市购物、工资": "Example: lunch, grocery shopping, salary",
    "例如：微信、支付宝、现金": "Example: WeChat Pay, Alipay, cash",
    "想补充的信息，留空也可以": "Extra details. You can leave this blank.",
    "要做什么": "What to do",
    "例如：交房租、买牛奶": "Example: pay rent, buy milk",
    "需要带什么，或其他想补充的信息": "What to bring, or anything else to add",
    "每周复盘": "Weekly review",
    "可选，比如提前准备材料。": "Optional, such as prepare materials in advance.",
    "今天的日记": "Today's diary",
    "晴天": "Sunny",
    "轻松，成长，朋友": "Relaxed, growth, friends",
    "记录今天发生的小事、心情和想法。": "Record today's moments, moods, and thoughts.",
    "想记录的内容": "What you want to record",
    "例如：今天在沙县吃午餐，花了 28 元，用微信付的": "Example: Lunch at Shaxian today, spent 28 CNY, paid with WeChat.",
  };

  const phraseRules = [
    [/^当前预算\s*(.+)$/u, (_match, budget) => `Current budget ${budget}`],
    [/^(.+) 条记录$/u, (_match, count) => `${count} records`],
    [/^共\s*(.+)\s*条$/u, (_match, count) => `${count} total`],
    [/^第\s*(.+)\s*页$/u, (_match, page) => `Page ${page}`],
    [/^(.+)分钟前$/u, (_match, count) => `${count} min ago`],
    [/^(.+)小时前$/u, (_match, count) => `${count} hr ago`],
    [/^(.+)天前$/u, (_match, count) => `${count} days ago`],
    [/^图片「(.+)」已上传，但暂时没能读出内容。可以输入商家、金额或要记录的事项。$/u, (_match, file) => `Image "${file}" was uploaded, but I could not read enough content yet. You can enter the merchant, amount, or what to record.`],
    [/^图片「(.+)」已上传，已生成待核对账单。$/u, (_match, file) => `Image "${file}" was uploaded and a bill is ready for review.`],
    [/^例如：(.+)$/u, (_match, example) => `Example: ${translateInline(example)}`],
  ];

  const inlineWords = Object.fromEntries(
    Object.entries(en).filter(([key]) => key.length <= 12).sort((left, right) => right[0].length - left[0].length),
  );

  function normalizeLanguage(value) {
    const raw = String(value || "").toLowerCase();
    if (raw.startsWith("en")) return "en-US";
    return "zh-CN";
  }

  function getLanguageMeta(language) {
    return languageMeta[normalizeLanguage(language)];
  }

  function translateText(value, language) {
    const normalized = normalizeLanguage(language);
    const text = String(value ?? "");
    if (normalized === "zh-CN" || !text.trim()) return text;
    const trimmed = text.trim();
    const leading = text.match(/^\s*/u)?.[0] ?? "";
    const trailing = text.match(/\s*$/u)?.[0] ?? "";
    if (en[trimmed]) return `${leading}${en[trimmed]}${trailing}`;
    for (const [pattern, formatter] of phraseRules) {
      const match = trimmed.match(pattern);
      if (match) return `${leading}${formatter(...match)}${trailing}`;
    }
    return `${leading}${translateInline(trimmed)}${trailing}`;
  }

  function translateInline(value) {
    let output = String(value ?? "");
    for (const [source, target] of Object.entries(inlineWords)) {
      output = output.replaceAll(source, target);
    }
    return output;
  }

  function shouldSkipElement(element) {
    if (!element || element.nodeType !== Node.ELEMENT_NODE) return false;
    if (element.closest("[data-no-i18n], .no-i18n")) return true;
    return Boolean(element.closest("script, style, code, pre"));
  }

  function translateAttributes(root, language) {
    const attributes = ["placeholder", "aria-label", "title"];
    const elements = root.querySelectorAll(attributes.map((name) => `[${name}]`).join(","));
    elements.forEach((element) => {
      if (shouldSkipElement(element)) return;
      attributes.forEach((name) => {
        const value = element.getAttribute(name);
        if (value) element.setAttribute(name, translateText(value, language));
      });
    });
  }

  function applyI18nToDom(root, language) {
    if (!root || normalizeLanguage(language) === "zh-CN") return;
    translateAttributes(root, language);
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const parent = node.parentElement;
        if (!parent || shouldSkipElement(parent)) return NodeFilter.FILTER_REJECT;
        if (parent.tagName === "TEXTAREA") return NodeFilter.FILTER_REJECT;
        if (parent.tagName === "OPTION" && !parent.hasAttribute("value")) return NodeFilter.FILTER_REJECT;
        if (!node.nodeValue || !/[\u4e00-\u9fff]/u.test(node.nodeValue)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((node) => {
      node.nodeValue = translateText(node.nodeValue, language);
    });
  }

  window.LifeSnapI18n = {
    supportedLanguages,
    normalizeLanguage,
    getLanguageMeta,
    translateText,
    applyI18nToDom,
  };
})();
