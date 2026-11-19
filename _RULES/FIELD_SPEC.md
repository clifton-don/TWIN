---
type: rule
updated: 2026-11-10
privacy: public
---
# 字段规范（Frontmatter）

## 一、所有文件都必须有的字段

| 字段 | 说明 | 示例 |
|---|---|---|
| `type` | 文件类型，见下表 | `skill` |
| `updated` | 最后修改日期 | `2026-10-20` |
| `privacy` | 密级：`public` / `internal` / `private` / `secret` | `internal` |
| `tags` | 可选，自由标签 | `[esp32, rtos]` |

缺 `privacy` 的文件一律按 `secret` 处理（见 AI_ACCESS_RULES.md）。

## 二、type 取值

| type | 放在哪 | 模板 |
|---|---|---|
| `summary` | 每个分支目录下的 `_SUMMARY.md` | 自动生成 |
| `skill` | 01_Skills/分支/ 或 02_Life/分支/（能力类） | `_TEMPLATES/skill.md` |
| `life` | 02_Life/分支/（偏好、清单、足迹、状态类） | `_TEMPLATES/life.md` |
| `person` | 05_Network/分支/ | `_TEMPLATES/person.md` |
| `milestone` | 04_Milestones/分支/ | `_TEMPLATES/milestone.md` |
| `project` | 03_Projects/ | `_TEMPLATES/project.md` |
| `decision` | 07_Decisions/ | `_TEMPLATES/decision.md` |
| `asset` | 06_Assets/分支/ | `_TEMPLATES/asset.md` |
| `crown` | 00_Crown/ | — |
| `rule` | _RULES/ | — |

> `project` 类型另有两个可选字段，只有拆了版本文件夹的多版本项目才写：`current_version`（当前在做或最新交付的版本，如 `V2`）、`versions`（版本文件夹列表，如 `["V1_2024原版", "V2_2026重做"]`）。board.md 里的 `status`、`due`、`goal` 等字段只描述 `current_version` 这一版。什么时候拆版本见 `03_Projects/diy_mk/整理新项目的操作流程.md` 的「已有项目做新版本」。

## 三、默认密级建议

| 类型 | 默认 privacy |
|---|---|
| summary、crown | `public`（这是上云的那一层，写的时候就要按可公开的标准写） |
| skill、life、milestone、project、decision | `internal` |
| person、asset | `private` |
| 保险箱里的东西 | 不建 md，放在知识库外的 `G:\VAULT\` |

## 四、子分支

分支下面不再建子文件夹。叶子文件直接放在分支文件夹里，用 `sub_branch` 字段标明属于哪个子分支（见各分支 `_SUMMARY.md` 的「子分支」表）。

## 五、命名规则

- **全部用英文**，单词之间用下划线，不用空格和中文。
- **文件夹**：`两位编号_英文名`。每一层都从 01 开始编号，编号只决定排列顺序，没有别的含义。例如 `02_Life/04_Music/`。
- **新增分支**：接着最后一个编号往后排，不要插队，也不要改已有编号。
- **叶子文件**：英文名，不加编号。例如 `Arduino.md`、`Guitar.md`、`Zhang_San.md`。文件里的标题和正文可以写中文。
- **决策文件**：加日期前缀，例如 `2026-10-20_Freelance_XX.md`。
- **系统文件**：以下划线开头（`_RULES`、`_TEMPLATES`、`_SUMMARY.md`）以及 `tools`、`README.md`、`CLAUDE.md`，保持原名。
- **项目库**：`03_Projects/diy_mk` 沿用它自己的命名规范。
  - **版本文件夹**：同一个项目做了新版本（已交付过一版，且这轮是硬件改版、换主控、交互大改或重新报价交付）时，在项目文件夹下按 `V<序号>_<年份><说明>` 建版本文件夹，例如 `V1_2024原版`、`V2_2026重做`。序号从 1 开始，不跳号、不改号；项目文件夹本身不改名，根目录只留 index.md（版本总览）和 board.md。
- **双链**：统一写文件名，例如 `[[Arduino]]`。

## 六、等级定义

**技能 level**

| 值 | 含义 |
|---|---|
| 1 | 了解：知道是什么 |
| 2 | 能用：照着资料能做出来 |
| 3 | 熟练：独立完成项目 |
| 4 | 精通：能教别人、能解决疑难 |
| 5 | 专家：业内认可 |

**优先级 priority**（决策端和待办统一使用）

| 值 | 含义 |
|---|---|
| P0 | 今天/本周必须做，不做有明确损失 |
| P1 | 本月内，重要且和当前焦点直接相关 |
| P2 | 本季度，重要但不紧急 |
| P3 | 有空再做 / 想法池 |
