[English](./README.en.md) · [Website](https://margledger.lei6393.com) · [GitHub](https://github.com/SuperMarioYL/margledger)

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/hero-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/hero-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/hero-dark.svg">
  <img src="./assets/presentation/hero-light.svg" width="960" alt="Hero diagram">
</picture>

# margledger

**看清记录的测试进展何时停滞。**

MargLedger 将记录的迭代成本与通过测试数变化配对，按明确停滞规则生成事后停止建议。

## 为什么需要它

固定预算只说明循环最多可花多少，不能展示测试进展是否继续。账本让每轮已记录增益与成本可检查。

- **进展与成本配对** — 每行同时保留测试变化与 token 成本。
- **明确停止规则** — 阈值与连续轮数可检查。
- **保留来源限定** — 稀疏或未验证字段保留标记。

## 架构

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/architecture-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/architecture-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/architecture-dark.svg">
  <img src="./assets/presentation/architecture-light.svg" width="960" alt="Architecture diagram">
</picture>

来源适配器生成 RawIteration；build_ledger 计算通过测试数差值和累计 token，可用最终 JUnit 快照对齐最后一轮价值。recommend 查找连续 K 轮不高于 epsilon 的边际值，报告该事后停滞段起点。

| 组件 | 职责 |
| --- | --- |
| `Transcript adapter` | margledger/sources |
| `Test oracle` | margledger/oracle.py |
| `Iteration ledger` | margledger/ledger.py |
| `Stop recommendation` | margledger/stop.py |

## 安装与快速上手

使用仓库清单指定的运行时版本构建，并在仓库根目录运行示例。

```bash
git clone https://github.com/SuperMarioYL/margledger.git
cd margledger
uv venv .venv
uv pip install --python .venv/bin/python -e .
source .venv/bin/activate
```

四轮合成输入声明通过数 1、3、3、3，每轮 1100 token。示例生成账本并应用 K=2。

```bash
.venv/bin/python examples/presentation-demo.py
```

## 实际运行示例

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/process-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/process-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/process-dark.svg">
  <img src="./assets/presentation/process-light.svg" width="960" alt="Process diagram">
</picture>

The retrospective rule identifies the flat run beginning at iteration 3; no running agent is interrupted.

```text
{
  "marginal_values": [
    1.0,
    2.0,
    0.0,
    0.0
  ],
  "cumulative_tokens": 4400,
  "recommendation": {
    "stop": true,
    "knee_iter": 3,
    "stop_iter": 3,
    "reason": "marginal_value <= 0 for 2 consecutive iters from iter 3",
    "tokens_saved": 1100,
    "hard_budget_iters": null,
    "consecutive_flat": 2,
    "epsilon": 0,
    "k": 2
  }
}
```

完整命令与输出保存在 [docs/demo-results.json](./docs/demo-results.json). 输入和复现代码均随仓提供。

![已有终端录制](./assets/demo.gif)

保留已有录制供参考；上方文字示例给出当前可复现的操作。

## 用法

CLI 提供以下操作。示例之外的命令需要替换成你的文件路径或标识。

```bash
margledger trace tests/fixtures/sample_transcript.jsonl --tests tests/fixtures/sample_junit.xml -o ledger.json
margledger recommend ledger.json --epsilon 0 --k 2 --json
margledger replay ledger.json --markdown -o report.md
```

## 配置

--epsilon 与 --k 控制停滞规则；--hard-budget 是迭代数比较背景。--source 可选 auto、claude_code、generic 或 cursor；Cursor 字段可能标记 sparse 或 schema_unverified，需要保留这些限定。

## 集成与职责分工

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="./assets/presentation/integrations-mobile-dark.svg">
  <source media="(max-width: 600px)" srcset="./assets/presentation/integrations-mobile-light.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/presentation/integrations-dark.svg">
  <img src="./assets/presentation/integrations-light.svg" width="960" alt="Integrations diagram">
</picture>

以下路径已有源码实现。按任务选择输入，并把生成的结果与项目一起保存。

| 路径 | 已实现职责 |
| --- | --- |
| JSONL transcripts | Recorded iteration inputs |
| JUnit / pytest summaries | Test-count snapshots |
| Ledger JSON | Costs and deltas |
| Markdown / terminal | Post-hoc report |

## 限制与后续方向

- 工具分析已完成数据，不会自动停止 Agent。
- 通过测试数量是有限信号；修改或不稳定测试可能改变数量而未改进软件。缺少轮内测试快照时当前实现记为零已记录增益。
- 拐点是依赖后续观察的事后结果；tokens_saved 是对已记录消费的反事实标签，不是已实现节省。

实时停止钩子与团队面板属于后续工作；更好的逐轮归因依赖可靠的逐轮测试快照。

## 许可与贡献

许可见 [LICENSE](./LICENSE). 反馈问题时请提供最小输入、执行命令和实际输出。
