# 配置了不等于能用——集成状态为什么要有"静态检查"和"真实探测"两层

> **系列**：LifeSnap AI Agent 踩坑日志
> **关键词**：外部集成、连通性探测、diagnostics、configured、ready、probe

---

## 一、如果只看"配没配"会怎样？

用户把外部 OCR/AI 的 endpoint 和 api_key 填进配置后，最容易写的判断是：

```python
if settings.external_ocr_endpoint:
    status = "ready"
```

前端看到"已接入"，于是放心使用。

**但真实世界里可能发生**：

1. **地址写错**：多了一个 `/`、端口不对、协议写成了 `http`；
2. **服务挂了**：外部服务宕机或临时不可用；
3. **key 过期**：api_key 已失效或被吊销；
4. **协议不匹配**：endpoint 通，但返回结构对不上。

这些情况，配置项全都"非空"，但一次真实调用就会暴露。

**结论**：配置齐全 ≠ 服务可用，必须把"检查配置"和"验证连通性"拆成两层。

---

## 二、两层诊断

```sql
GET /diagnostics/integrations      静态检查：只读配置与隐私阻断
   │
   └─ ready / fallback / blocked     （不出网、无副作用）

POST /diagnostics/integrations/probe  真实探测：真的发一次外部请求
   │
   └─ success / failed / skipped       （出网、有隐私与费用成本）
```

静态检查回答"**能不能去试**"，真实探测回答"**现在能不能连上**"。

---

## 三、当前项目做法

静态检查的判定：

```python
def _integration_check_status(self, configured, blockers):
    if not configured:
        return "fallback"
    if blockers:
        return "blocked"
    return "ready"
```

真实探测的判定：

```python
def _probe_status(self, success_count, failed_count):
    if failed_count:
        return "failed"
    if success_count:
        return "success"
    return "skipped"
```

两种状态词故意不同，避免混用。

---

## 四、为什么不能合成一层

1. **静态检查快、免费、无副作用**，适合启动时/首页直接展示；
2. **真实探测慢、会出网**，有隐私和费用成本，必须按需、确认后执行；
3. 混在一起，要么把"没配置"误报成"连不上"，要么每次启动都出网打一次外部服务。

---

## 核心要点

1. **配置齐全不等于服务可用**；
2. **诊断要拆成静态检查 + 真实探测两层**；
3. **只有真实探测能给出"现在能连上"的结论**。
