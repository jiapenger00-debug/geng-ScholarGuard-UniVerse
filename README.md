# Academic Fraud Detector — 全科目论文打假检测技能

> A universal AI Agent Skill for detecting academic fraud across **all disciplines** — STEM, social sciences, humanities, and arts.

[![Skill Type: Agent Skill](https://img.shields.io/badge/Skill_Type-AI_Agent_Skill-blueviolet)]()
[![Disciplines: All](https://img.shields.io/badge/Disciplines-All-success)]()
[![Inspired by: 耿同学讲故事](https://img.shields.io/badge/Inspired_by-耿同学讲故事-red)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)]()

## 📖 概述

**Academic Fraud Detector** 是一个系统性的论文打假检测框架，覆盖**所有学科领域**。本技能的灵感来源于 [wooly99/geng-academic-fraud-detector](https://github.com/wooly99/geng-academic-fraud-detector)（致敬 B 站 UP 主**耿同学讲故事**在 36 天内揭露 4 所高校 5 位杰青学术造假的事迹），并在此基础上做了**关键扩展**：

- **学科覆盖**：从生物医学扩展到**全科目**（理化、计算机、社科、人文、数学）
- **检测体系**：从"耿同学六式"扩展为**三层级检测框架**
- **可执行工具**：内置 3 个 Python 脚本（Benford's Law、统计验证、图片相似度）
- **报告输出**：结构化风险评估报告 + 证据链

学术造假**不是某个学科的专利**——抄袭、捏造、统计操纵、引用造假这些手段**跨学科通用**，只是具体表现形式不同。本技能让 AI 学会识别这些**通用模式**，无论论文来自哪个领域。

---

## 🎯 核心特性

### ✨ 三层级检测框架

```
┌─────────────────────────────────────────────────────┐
│  Layer 1: 通用扫描 (5-10 min)                       │
│  → 文本抄袭 / 数据异常 / 统计矛盾 / 图片初检         │
│  → 适用所有科目；任一红旗触发即进入 Layer 2           │
├─────────────────────────────────────────────────────┤
│  Layer 2: 学科专项 (10-30 min)                      │
│  → 生物医学 / 物理化学 / CS / 社科 / 人文 / 数学     │
│  → 按论文所属学科调用对应专项检测模块                  │
├─────────────────────────────────────────────────────┤
│  Layer 3: 综合报告                                  │
│  → 风险评分 + 证据链 + 结构化报告输出                │
└─────────────────────────────────────────────────────┘
```

### 🛠 三大可执行工具

| 脚本 | 用途 | 适用场景 |
|------|------|---------|
| `scripts/benford.py` | Benford's Law 数值分布检测 | 跨数量级数据可能捏造 |
| `scripts/stat_check.py` | 检验统计量与 p 值一致性验证 | 报告的统计学结果真实性 |
| `scripts/image_similarity.py` | 感知哈希图片相似度检测 | 图片复用 / 旋转 / 裁剪 |

### 📋 标准化报告输出

每次检测产出结构化报告，包含：
- **论文元信息**（标题/作者/期刊/DOI）
- **执行摘要**（2-3 句关键发现 + 风险等级）
- **风险等级评估**（🔴🔴🔴 极高 → ✅ 清洁 5 档）
- **按 Layer 1/2 分组的发现列表**
- **证据汇总表**（编号 / 发现 / 层级 / 严重度 / 证据 / 置信度）
- **优点**（保持客观公正）
- **分析局限性说明**
- **具体建议**

---

## 📦 安装

### 通过 npx 安装（推荐）

```bash
npx skills add https://github.com/jiapenger00-debug/geng-ScholarGuard-UniVerse
```

### 手动安装（Claude Code）

将 `academic-fraud-detector/` 目录复制到 Claude Code 技能目录：

**Windows:**
```bash
# 用户级（所有项目可用）
xcopy /E /I academic-fraud-detector %USERPROFILE%\.claude\skills\academic-fraud-detector

# 项目级（仅当前项目可用）
xcopy /E /I academic-fraud-detector .claude\skills\academic-fraud-detector
```

**macOS / Linux:**
```bash
# 用户级
cp -r academic-fraud-detector ~/.claude/skills/

# 项目级
mkdir -p .claude/skills
cp -r academic-fraud-detector .claude/skills/
```

### 手动安装（其他 Agent Skills 兼容平台）

参考 [Agent Skills 规范](https://agentskills.io/specification) 将本技能部署到任何支持该规范的环境。

---

## 🚀 快速开始

### 基础用法

在 Claude Code（或任何加载了该技能的环境）会话中直接说：

```
帮我打假这篇论文 /path/to/paper.pdf
```

或者：

- "看看这篇 [URL] 有没有造假"
- "分析 doi:10.1371/journal.pone.0313446 的论文"
- "验证下这个统计结果：t=2.5, df=28, p=0.001 是否合理"
- "扫描这个目录的图片看有没有重复：./figures/"
- "用 Benford's Law 检验一下这组数据：[CSV 路径]"

### 检测模式

技能支持两种模式，由用户主动选择或由技能判断：

| 模式 | 时长 | 适用场景 |
|------|------|---------|
| **快速筛查 (Quick Scan)** | 5-10 min | 期刊编辑、审稿人初步判断 |
| **深度调查 (Deep Investigation)** | 30+ min | 学术打假、调查记者、撤稿建议 |

默认行为：群聊和首次接触走**快速筛查**；发现红旗后询问是否深入。

### 输出示例

一份典型的快速筛查报告：

```markdown
# Academic Fraud Detection Report

## Paper Information
- **Title:** [论文标题]
- **DOI:** 10.xxxx/xxxxx
- **Analysis Date:** 2026-06-06
- **Analysis Mode:** Quick Scan

## Executive Summary
该论文在 Layer 1 扫描中检测到 2 处红旗：1 处 p 值与统计量不一致，
1 处参考文献疑似捏造。建议进入 Layer 2 深入调查。

## Overall Risk Assessment: 🔴🔴 HIGH RISK

## Evidence Summary
| # | Finding | Layer | Severity | Evidence | Confidence |
|---|---------|-------|----------|----------|------------|
| 1 | p=0.000 报告，不可能 | 1.2 | 🔴🔴🔴 | Table 2, line 5 | High |
| 2 | 文献 [23] 不存在 | 1.1 | 🔴🔴 | References | Medium |
```

---

## 🔬 学科专项检测详解

### 1.1 生物医学 & 生命科学

继承并扩展了**耿同学六式**的核心能力：

- **图片复用**（耿同学第一式）—— Western blot、流式细胞图、显微镜图跨图重复
- **图片拼接**（耿同学第三式）—— 泳道拼接、背景不一致
- **Western blot 深度分析**—— 加载控制复用、条带形态、上样量异常
- **临床试验验证**—— 注册号核对、终点指标漂移、"幽灵患者"
- **动物实验 n 值核查**—— 缺失的样本量是重大红旗

### 1.2 物理 / 化学 / 材料

- **谱图一致性**—— NMR、MS、IR、XRD 与结构的对应
- **合成化学**—— 100% 收率、元素分析、熔点验证
- **物理实验**—— 误差分析、量纲一致性、守恒定律

### 1.3 计算机科学 & 工程

- **ML 论文**—— 数据泄露、基准对比造假、硬编码种子
- **代码可复现性**—— 是否真的发布代码
- **工程论文**—— 性能声称 vs 硬件极限

### 1.4 社会科学 & 经济管理

- **问卷数据**—— 直线作答、速度陷阱、α 系数>0.95
- **计量经济**—— 工具变量、R²>0.99、控制变量挖掘
- **心理学**—— 可选停止、研究者自由度

### 1.5 人文学科

- **史料真伪**—— 引用档案号、时代错误
- **文学引文**—— 引文准确度、上下文完整性
- **翻译当原创**—— 外文作品的翻译是否被冒充原创

### 1.6 数学

- **证明漏洞**—— "显然"背后的非平凡跳跃
- **定理误用**—— 在不成立条件下应用定理
- **数值可复现性**—— 标准方法能否复现声称的结果

详细指南见 [`references/discipline_guides.md`](./references/discipline_guides.md)。

---

## 🛠 工具脚本使用

### 前置要求

**Python 3.7+** 是必需的。脚本**不需要**任何第三方依赖——所有统计函数都用纯 Python 实现（chi-square、t、F 分布都有内置 fallback）。可选加速：

```bash
# 可选：让统计计算更精确
pip install scipy

# 可选：让图片对比支持旋转/裁剪检测（默认 MD5 fallback 只能检测完全相同的图）
pip install Pillow

# 可选：让 benford 生成图表
pip install matplotlib
```

**Windows 用户注意**：命令里用 `python` 而不是 `python3`（Windows 上 `python3` 经常走 Microsoft Store shim）。如果都没装好，先装 Python 3：https://www.python.org/downloads/

### Benford's Law 检测

```bash
# 从 CSV 读取
python scripts/benford.py --input data.csv --column "values"

# 直接传数字
python scripts/benford.py --numbers "123,456,789,1024,2048,4096,8192,16384,32768,65536,131072,262144,524288"

# 生成图表（需 matplotlib）
python scripts/benford.py --input data.csv --column "values" --plot
```

**适用条件**（任一不满足则 Benford's Law **不适用**）：
- 数据跨越多个数量级 ✓
- 非人为分配的数字（不是 ID、电话）✓
- 无固定上下界（不是百分比）✓
- 至少 50 个数据点 ✓

**实测验证**（已亲测）：
- 11 个数据 → 报 "Insufficient data, need at least 50"（优雅退出）
- 100 个 `random.uniform(1, 100000)` → 报"显著偏离 Benford"（正确）
- 200 个 `random.expovariate(0.5) * 100`（指数分布应符合 Benford）→ 报"一致"（正确）

### 统计量验证

```bash
# t 检验
python scripts/stat_check.py --test t --df 28 --stat 2.5 --p 0.019

# F 检验（ANOVA）
python scripts/stat_check.py --test F --df1 2 --df2 45 --stat 5.3 --p 0.008

# 卡方检验
python scripts/stat_check.py --test chi2 --df 3 --stat 12.5 --p 0.006

# Pearson 相关
python scripts/stat_check.py --test r --n 100 --stat 0.35 --p 0.0004
```

**红旗识别**：
- p = 0.000（不可能）
- p < 0 或 p > 1（数学上不可能）
- 报告 p 与计算的 p 差距 > 0.05（很可能是编造的）

**实测验证**（已亲测）：
- t(28)=2.5, p=0.019 → 判 OK（实际 p=0.018551，匹配）
- t(28)=2.5, p=0.001 → 判 MODERATE 异常（差 0.018，编造）
- F(2,45)=5.3, p=0.008 → 判 OK（实际 p=0.008572，匹配）
- r(98)=0.35, p=0.0004 → 判 OK（实际 p=0.000358，匹配）

### 图片相似度扫描

```bash
# 扫描整个图片目录
python scripts/image_similarity.py --paper-dir ./figures/

# 对比两张特定图片
python scripts/image_similarity.py --compare figure1.png figure2.png

# 调整阈值（默认 15，数字越小越严格）
python scripts/image_similarity.py --paper-dir ./figures/ --threshold 10
```

**距离解读**（64-bit 感知哈希）：
- 0 = 完全相同
- ≤ 5 = 高度相似（可能仅做了亮度/对比度调整）
- ≤ 15 = 相似（红旗）
- > 15 = 不同

**实测验证**（已亲测，无 Pillow 的纯 MD5 fallback 模式）：
- 两张相同内容的 PNG → 判 IDENTICAL
- 三张图混合扫描 → 正确识别唯一一对重复

详细统计方法见 [`references/statistical_checks.md`](./references/statistical_checks.md)。

---

## ⚖️ 与原项目 `geng-academic-fraud-detector` 的对比

| 维度 | 原项目 | Academic Fraud Detector |
|------|--------|------------------------|
| **学科覆盖** | 仅生物医学 | **全科目**（6 大领域） |
| **检测框架** | 耿同学六式 | **三层级检测**（通用→专项→综合） |
| **图片检测** | 仅 Western blot | **通用感知哈希** + 学科专项图检 |
| **可执行脚本** | 无 | **3 个 Python 脚本**（Benford/统计/图片） |
| **统计验证** | 基础 | **深度**（p值一致性、自由度、样本量、效应量） |
| **报告模板** | 无固定格式 | **结构化报告**（风险评分+证据表+建议） |
| **参考深度** | 无 | **两份参考文件**（学科指南+统计方法） |

本项目完全**继承**了原项目在生物医学领域的检测能力，并将其推广为通用框架。

---

## 🎓 致敬耿同学讲故事

本技能的灵感与命名致敬 **耿洪伟（B 站：耿同学讲故事）**：

> 前北航博士生，生物学背景。2025 年退学后用 AI + Excel 在 36 天内揭露了同济、南开、中山、上海大学 4 所高校 5 位杰青的学术造假，被称为"**学术圈的海瑞**"。

他的方法论核心是**用统计规律识破伪造**：
- 末位数字分布
- 称重精度异常
- 统计不可能值
- 期刊产出模式

这些**通用模式**正是本技能的 Layer 1 检测基础。**学术打假不是生物医学的专利**，造假者换到任何学科都会留下相似的"数字指纹"。

---

## 📚 重要原则

### 1. Iron Law: 没有证据不下结论

```
NO JUDGMENT WITHOUT EVIDENCE. NO ACCUSATION WITHOUT VERIFICATION.
```

每个发现都必须能追溯到**具体的、可验证的证据**。如果不能指出来，就没有这个发现。

### 2. 公平原则

- 每条红旗都列出**可能的无辜解释**
- 区分**系统性的造假模式**与**孤立的错误**
- 客观列出**论文的优点**

### 3. 置信度声明

- 区分"**这是造假**"与"**这看起来可疑需要调查**"
- AI 分析是**筛查工具**，不是**最终判决**
- **永远不要**在没有证据的情况下下定论

---

## 🤝 贡献

欢迎贡献：
- 新增学科专项检测模块
- 改进工具脚本（更精确的算法）
- 扩充参考文档（更多案例）
- 翻译成其他语言

请通过 PR 提交。

---

## 📄 许可证

MIT License — 见 [LICENSE](./LICENSE) 文件。

---

## 🔗 相关资源

- **原项目**：[wooly99/geng-academic-fraud-detector](https://github.com/wooly99/geng-academic-fraud-detector)
- **Agent Skills 规范**：[agentskills.io/specification](https://agentskills.io/specification)
- **技能开发者文档**：[writing-skills 最佳实践](https://github.com/obra/superpowers)

---

## 📝 版本

**v1.0.1** (2026-06-06) — 脚本兼容性修复

- ✅ 修复 Windows GBK 控制台 emoji 崩溃（所有脚本加 `_safe_emoji` fallback）
- ✅ 修复 `scipy` 缺失时脚本崩溃（所有统计函数加纯 Python 实现：t/F/chi2/beta 分布）
- ✅ 修复 `Pillow` 缺失时图片脚本崩溃（MD5 fallback）
- ✅ 修复 `python3` 在 Windows 上的 shim 问题（README 命令改用 `python`，并加 `py` 备选）
- ✅ 亲测所有脚本的典型用例（结果在 README 列出）
- ✅ npx skills add 已亲测可用（Vercel Labs `skills` v1.5.10）

**v1.0.0** (2026-06-06) — 首次发布

- 全科目 6 大学科专项检测
- 3 个 Python 工具脚本
- 2 份参考文档
- 标准化报告模板

---

## ⚠️ 免责声明

本工具仅供**学术诚信监督、研究学习、调查报道**使用。AI 检测分析**不构成正式指控**，所有结论必须经过独立人工验证。作者不对工具使用产生的任何后果负责。请在符合当地法律法规和学术规范的前提下使用。
