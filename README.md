<div align="right"><sub>**简体中文**&nbsp;&nbsp;⇄&nbsp;&nbsp;<a href="./README.en.md">English</a></sub></div>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/hero-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="./assets/hero-light.svg">
  <img src="./assets/hero-light.svg" width="880" alt="MargLedger hero">
</picture>

<p align="center"><sub>为每一次 agent-loop 迭代归因边际价值，并在收益递减处给出停止建议——让循环停在价值拐点，而不是硬预算截断。</sub></p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/github/license/SuperMarioYL/margledger?color=0071E3" alt="MIT"></a>
  <a href="https://github.com/SuperMarioYL/margledger/releases"><img src="https://img.shields.io/github/v/release/SuperMarioYL/margledger?color=5E5CE6" alt="release"></a>
  <a href="https://github.com/SuperMarioYL/margledger/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/SuperMarioYL/margledger/ci.yml?branch=main&label=ci&color=10A37F" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-5E5CE6" alt="python">
  <img src="https://img.shields.io/badge/Agent-stop_at_value-5E5CE6" alt="Agent">
  <img src="https://img.shields.io/badge/Loop--Engineering-value_ledger-10A37F" alt="Loop-Engineering">
</p>

**一句话：跑 agentic coding loop，唯一可用的终止条件是硬 token 预算截断——跑到预算耗尽才停，事后审计才发现后半程测试通过率几乎没净增。MargLedger 把"这一轮到底值不值"做成有据可查的算法输出，让循环停在收益递减处。**

<h2><img src="https://api.iconify.design/tabler:topology-star-3.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 架构</h2>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/atlas-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="./assets/atlas-light.svg">
  <img src="./assets/atlas-light.svg" width="880" alt="MargLedger 架构：transcript -> ledger -> stop/report，测试 oracle 喂入边际价值">
</picture>

数据流：转录本（transcript）经 `sources/` 归一化为逐轮迭代 → `ledger.py` 用测试套件 delta 归因每轮边际价值 → `stop.py` 检测收益递减拐点并给出停止建议 + `report.py` 导出 Markdown。价值来自机器可校验的 oracle（测试套件），不是黑盒打分——这是 ground truth 真实存在的 coding loop 才成立的前提。

## 目录

- [为什么存在](#为什么存在)
- [安装](#安装)
- [快速开始](#快速开始)
- [用法](#用法)
- [Demo](#demo)
- [配置](#配置)
- [付费](#付费)
- [路线图](#路线图)
- [License](#license)

<h2><img src="https://api.iconify.design/tabler/target.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 为什么存在</h2>

当前的 agentic coding loop 缺一个 flow primitive：在每次迭代上计算"边际价值账本"。loop-engineering 这门 2026 年才被命名的工程纪律，已经把成本计量（`loop-cost`）出货，但它是 cost-only 的——看不到"价值"什么时候停止增长。结果就是具体的失败动作：开发者用硬 token/时间预算截断终止循环，事后审计才发现后半程几乎零净增测试，token 白烧。MargLedger 把每轮的 test-suite delta 归因到该轮，对照其边际 token/时间成本，浮现一条价值/成本曲线，并给出停止建议——停止决策从经验拍脑袋变成有据可查的算法结论。

<h2><img src="https://api.iconify.design/tabler:rocket.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 安装</h2>

```bash
uv tool install margledger      # 或 pipx install margledger
```

开发安装：

```bash
git clone https://github.com/SuperMarioYL/margledger
cd margledger && pip install -e ".[dev]"
```

<h2><img src="https://api.iconify.design/tabler:terminal-2.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 快速开始</h2>

```bash
# 1. 解析 Claude Code 转录本 + JUnit oracle -> ledger.json
margledger trace ~/.claude/projects/my-proj --tests junit.xml -o ledger.json

# 2. 看价值/成本曲线 + 停止建议
margledger stop ledger.json --hard-budget 10
```

<details><summary>样例输出</summary>

```
STOP at iter 4 — marginal_value <= 0.0 for 7 consecutive iters from iter 4;
~50,000 tokens saved vs a 10-iter hard budget.
observed: 10 iters, 104,000 tokens spent, final cumulative value 55 passing tests.
```

</details>

没有真实转录本？用仓库自带的合成 fixture 试一把：

```bash
margledger trace tests/fixtures/sample_transcript.jsonl \
  --tests tests/fixtures/sample_junit.xml -o /tmp/ledger.json
margledger stop /tmp/ledger.json --hard-budget 10
```

<h2><img src="https://api.iconify.design/tabler:terminal-2.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 用法</h2>

最常用的五个工作流：

```bash
# 逐轮账本（边际价值 / 边际 token / value-per-ktoken）
margledger trace transcript.jsonl --tests junit.xml -o ledger.json

# 价值/成本曲线 + 拐点 + 停止建议（hero 时刻）
margledger stop ledger.json --hard-budget 10

# 只出曲线
margledger plot ledger.json

# 只出停止建议（可 --json 接入流水线）
margledger recommend ledger.json --hard-budget 10 --json

# 团队可分享的 Markdown 快照
margledger replay ledger.json --markdown -o report.md
```

数据源自动识别：`.jsonl` → Claude Code / 通用 JSONL；`.vscdb` → Cursor（best-effort，`schema_unverified`）。Claude Code JSONL 没有原生迭代标记，迭代由 assistant↔user 轮次序列合成；`usage.input_tokens/output_tokens` 与 `timestamp` 是真实字段。Cursor `state.vscdb` 的 token 字段是 per-file 附加上下文代理（非模型 token），且稀疏——诚实标注为 `sparse`，不冒充 m1/m2 的 token 数学。

完整命令参考见 `margledger --help`，更多示例见 [`examples/`](./examples/README.md)。

<h2><img src="https://api.iconify.design/tabler:photo.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> Demo</h2>

![demo](assets/demo.gif)

Hero 时刻：一条本会烧掉 ~50k token 换 0 测试净增的循环，在 iter 4 被自动判为收益递减拐点并建议停止。渲染脚本见 [`docs/demo.tape`](./docs/demo.tape)，`.github/workflows/demo.yml` 手动触发可刷新。

<h2><img src="https://api.iconify.design/tabler:adjustments.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 配置</h2>

停止规则为纯函数：`marginal_value ≤ ε` 连续 `K` 轮即建议停止（默认 `ε=0`、`K=2`）。

| 参数 | 类型 | 默认 | 含义 |
|---|---|---|---|
| `--epsilon` | float | `0.0` | 边际价值低于此值视为"无新增价值"的阈值 |
| `--k` | int | `2` | 连续多少轮无新增价值才触发停止建议 |
| `--hard-budget` | int | `None` | 硬预算迭代数（仅用于"省了多少 token"的叙事框架） |
| `--tests` | path | `None` | JUnit XML oracle（最终测试状态，可对账最终累计价值） |
| `--source` | str | `auto` | `auto \| claude_code \| generic \| cursor` |
| `--output` | path | `ledger.json` | 账本输出路径 |

<h2><img src="https://api.iconify.design/tabler:building-store.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 付费</h2>

v0.1 是自由 OSS CLI（MIT），是楔子。商业读法在 v0.2：**可自部署的团队仪表盘 + 实时停止 webhook**——仪表盘聚合全团队的 `ledger.json`，停止 webhook 在价值拐点自动叫停循环。

**先付费的人群**：信创 / 私有化部署的企业 agent 团队，在自有 GPU 上跑 DeepSeek-V3 / Qwen2.5-Coder / GLM-4.6 的 loop——每次叫停的循环 = 省下的真实 GPU 小时，停止决策直接等于省钱。按团队售卖（≤10 席 + 1 GPU 集群），不是按 token。

**定价**：¥4,800 / 团队月（约 $660，≤10 席 + 1 GPU 集群），或 ¥48k / 年 / GPU 集群节点。依据：一条叫停的 loop 省下 ~50k token ≈ 一小部分 GPU 小时；一个团队每天跑成百上千条 loop。

**交付形态**：优先自部署（信创 air-gap、数据不出境）——Docker 镜像 + license key，对公转账 / 开票（国内企业标准）；全球团队可选 Stripe。不是 SaaS——买方的硬约束是数据主权。

**首个付费目标**：day 45 内 1 个企业团队试用，day 90 内 1 张签约 license。

v0.1 的 CLI / 仪表盘在 v0.1 明确 out of scope——这是契约，不是含糊。CLI 是现在的可落地楔子，团队仪表盘 + 实时 webhook 是它的商业读法。

<h2><img src="https://api.iconify.design/tabler:map-2.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 路线图</h2>

- [x] **m1 解析 + oracle**：Claude Code JSONL 转录本 + JUnit 测试套件解析为逐轮账本 → `ledger.json`
- [x] **m2 停止曲线**：价值/成本曲线 + 收益递减拐点 + 停止建议 + tokens-saved；终端图表
- [x] **m3 Cursor + Demo**：Cursor `state.vscdb` best-effort 适配（`schema_unverified`）+ hero 停止时刻 demo
- [ ] v0.2 可自部署团队仪表盘 + 实时停止 webhook（`ledger.json` 的商业读法）
- [ ] 二级 oracle：type-check / lint-delta / build-status（覆盖没有测试套件的库）
- [ ] 跨框架停止协议（Cline / Aider / Claude Code 的 stop-hook）

<h2><img src="https://api.iconify.design/tabler:license.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> License</h2>

MIT —— 见 [`LICENSE`](./LICENSE)。提 issue / PR 欢迎，去 [`Issues`](https://github.com/SuperMarioYL/margledger/issues) 开。

<p align="center"><sub><a href="./LICENSE">MIT</a> © 2026 SuperMarioYL</sub></p>
