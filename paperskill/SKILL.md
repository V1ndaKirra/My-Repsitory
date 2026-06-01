---
name: thesis-writing
description: "面向本科软件类毕设论文与答辩的协作式写作 skill。适用于基于真实代码仓库、数据库、业务流程和实现细节来撰写论文、补证据、做预检和生成 docx 的场景。遇到本科毕设论文、系统设计与实现、答辩导向论文、项目型论文、代码仓库转论文、需要用户分阶段确认与补截图/补图表时触发。"
---

# Thesis Writing Skill

这个 skill 不是黑箱流水线，而是“和用户一起推进”的论文协作流程。目标不是一口气自动生成整篇论文，而是按阶段整理真实证据、停下来汇报、等用户确认、再继续往下推进。

本科毕设默认优先级：

- 工作量是否具体可见
- 技术选型理由是否说得清楚
- 系统是怎么一步步做出来的
- 开发过程中遇到的问题与解决过程是否真实
- 图表、截图、代码证据是否能支撑答辩

## Hard Rules

- 不得编造文献、DOI、页码、API、数据库结构、流程、截图、图表、测试结果或仓库事实。
- 未经用户明确提供或确认，不得扫描电脑里其他项目目录。
- 代码仓库路径必须由用户指定；如果路径未确认，只能停下来向用户要路径，不能自己猜。
- 中文文献默认由用户自行下载后提供目录或文件位置；不要假设可以自动抓到高质量中文文献。
- 截图、流程图、架构图、ER 图、部署图、组件图都必须基于真实项目证据生成；没有证据时只能列待确认项，不能补脑。
- 任何“如图所示”“根据截图可见”“系统实现了某流程”这类表述，都必须以工作区里真实存在的图或截图为前提。
- 对大而复杂的图，宁可拆成多张图，也不要把所有信息塞进一张图里。
- 系统实现过程必须体现开发推进顺序、关键模块落地、问题排查与修复，不得只写静态结果。

## Collaboration Contract

每推进到一个关键节点，都必须停下来，向用户汇报并等待确认。默认至少在下面这些节点暂停：

1. 项目路径确认后
2. 项目画像/证据索引生成后
3. 中文文献与英文文献入库后
4. 论文大纲与章节预算完成后
5. 系统实现章节初稿完成前
6. 截图需求清单整理后
7. Mermaid 流程图代码交付后
8. `.drawio` 图文件交付后
9. preflight 报告完成后
10. 最终 docx 生成前

每次暂停时，必须告诉用户：

- 做了什么
- 新写了什么
- 文件放在哪
- 还缺什么用户输入
- 下一步准备做什么

如果用户检查后提出问题，先修正当前阶段，不要直接跳到下一阶段。

## Required User Inputs

开始正式推进前，优先收集并确认这些输入：

- 项目仓库路径
- 中文文献 PDF 目录或文件路径
- 学校模板/格式要求
- 用户愿意提供的截图目录
- 用户希望补画流程图或 draw.io 图的存放目录

如果这些输入缺失，优先创建待办和占位，不要假装已有材料。

## Load References On Demand

- 需要分阶段停顿与用户确认的话术、门槛和交付格式时，读 `references/interactive-checkpoints.md`
- 需要确认 Mermaid 流程图和 `.drawio` 图的产物路线时，读 `references/diagram-route.md`
- 需要脚本能力、参数和当前已实现链路时，读 `references/workflow-detail.md`
- 需要现有图表 JSON 规格、手工截图登记格式时，读 `references/diagram-spec.md`
- 需要把 `superpowers brainstorm` 接入系统实现过程复盘、截图清单梳理、问题排查分析时，读 `references/brainstorm-route.md`
- 需要本科答辩导向写法时，读 `references/undergrad-defense-focus.md`
- 需要按章节组织本科论文时，读 `references/undergrad-chapter-blueprint.md`
- 需要把截图解释写得更自然时，读 `references/undergrad-writing-style.md`

## Workspace Contract

环境说明：`setup_env.py` 的 Graphviz / Tesseract 自动安装目前只按 Windows `.exe` 安装器实现；macOS / Linux 用户需要手动安装这些依赖后再运行相关脚本。

所有脚本默认通过 `THESIS_ROOT` 定位论文工作区：

```text
{THESIS_ROOT}/
├── thesis.json
├── project/
│   ├── profile.json
│   ├── figures-spec.json
│   ├── tables-config.json
│   └── custom_figures.py
├── library/
│   ├── metadata.json
│   ├── references.bib
│   ├── lit-index.json
│   ├── pdfs/
│   ├── fulltext/
│   └── chapter-briefs/
├── drafts/
├── assets/
│   ├── figures/
│   ├── screenshots/
│   ├── tables/
│   └── manifest.json
├── template/
│   ├── format-contract.json
│   └── original.docx
└── output/
```

## State Contract

`thesis.json` 是中心状态文件。除已有字段外，协作式流程默认还要维护：

```json
{
  "user_inputs": {
    "repo_root": "",
    "repo_root_confirmed": false,
    "zh_pdf_dir": "",
    "zh_pdf_dir_confirmed": false,
    "screenshot_dir": "assets/screenshots",
    "screenshot_dir_confirmed": false,
    "diagram_dir": "assets/figures",
    "diagram_dir_confirmed": false
  },
  "collaboration": {
    "mode": "interactive-checkpoints",
    "current_gate": "phase-0-init",
    "waiting_for_user": false,
    "required_user_actions": [],
    "last_agent_summary": ""
  }
}
```

兼容要求：

- 旧工作区缺这些字段时，只补齐缺失键，不覆盖用户已有值
- `progress.phase` 继续保留
- `context_bridge` 继续作为跨 session 桥接状态

## Operating Modes

- `full-pipeline`: 从初始化推进到 preflight / docx，但中途必须多次停下来等用户确认
- `partial-phase`: 只做用户当前指定的一个阶段
- `read-only-analysis`: 只盘点现状和缺口，不新增内容

## Core Workflow

### Phase 0: Init

目标：创建工作区、确认协作方式、确认用户输入缺口。

- 运行 `python scripts/init_workspace.py --root <THESIS_ROOT>`
- 运行 `python scripts/setup_env.py --status`
- 明确告诉用户当前工作区路径、已创建目录、还缺哪些输入

停顿条件：

- 如果项目路径还没确认，必须停下
- 如果模板要求不清楚，必须停下

### Phase 1: Project Comprehension

目标：基于用户给出的仓库路径生成第一轮项目画像，但不替用户脑补业务结论。

- 只在用户确认 `repo_root` 后运行 `python scripts/build_project_profile.py --repo <REPO_ROOT>`
- 再运行：
  - `python scripts/build_undergrad_evidence_pack.py`
  - `python scripts/build_undergrad_chapter_kits.py`
  - `python scripts/build_undergrad_draft_sidecars.py`

本阶段完成后必须停下，向用户汇报：

- 扫到了哪些模块、接口、实体、页面、SQL、配置
- `project/profile.json`、`project/chapter-kits/`、`drafts/*.guide.md` 放在哪
- 哪些推断只是候选，需要用户确认

### Phase 2: Literature Acquisition

目标：整理真实文献来源，不把中文文献抓取幻想成已解决能力。

- 英文检索可用：`python scripts/literature_search.py "query1, query2"`
- 中文文献默认走用户自备 PDF：`python scripts/literature_import_pdfs.py --dir <用户下载后的中文 PDF 目录>`
- 全文提取：`python scripts/literature_extract_fulltext.py`
- 文献验证：`python scripts/literature_verify.py --unverified-only`
- 索引生成：`python scripts/generate_lit_index.py --with-relevance`

规则：

- 中文 PDF 目录未确认前，只能让用户提供目录或把 PDF 放进 `library/pdfs/`
- 如果文献质量不足，先停下来列缺口，不直接继续写正文

### Phase 3: Outline Planning

目标：确定章节结构、每章证据来源和图表需求。

- 写回 `thesis.json.outline`
- 明确每章需要哪些代码证据、截图、流程图、表格
- 对 `ch4/ch5/ch6` 单独列出：
  - 需要用户补哪些截图
  - 需要哪些 Mermaid 流程图
  - 需要哪些 `.drawio` 图

本阶段完成后必须停下，让用户检查大纲和图表计划。

### Phase 4: Drafting

目标：逐章写正文，但实现章节和问题复盘章节要强依赖用户确认过的证据。

- 每章 Markdown 继续使用 frontmatter
- 可用引用语法：
  - 文献：`[@cite-key]`
  - 图片：`{{fig:asset-id}}`
  - 表格：`{{tab:asset-id}}`
  - 章节：`[[sec:chapter-id]]`
  - 占位：`[TODO: 描述]`

实现章节默认必须覆盖：

- 我做了什么
- 为什么这么做
- 关键模块怎么实现
- 开发中遇到什么问题
- 我怎么排查和修复
- 哪些截图、代码和图表能证明这些内容

如果环境里存在 `superpowers brainstorm`，默认把它作为系统实现过程分析器来用，而不是代写器。优先在这些节点调用：

- `ch5` 核心模块不知道怎么写成“开发过程”时
- `ch6` 已知问题存在，但 symptom / diagnosis / fix / result 还不清楚时
- 需要和用户一起梳理“还缺哪些截图、哪些代码证据”时

使用规则：

- 先给真实输入，再让 brainstorm 产出结构化提纲
- brainstorm 输出只能作为分析脚手架，不能直接当论文事实
- 输出后必须回到代码、截图、配置和用户确认
- 如果当前环境没有 `superpowers brainstorm`，就按 `references/brainstorm-route.md` 里的同结构普通对话引导替代

### Phase 5: Assets

目标：图表和截图都走“先确认素材，再生成产物”的路线。

进入本阶段前，必须先读 `references/diagram-route.md` 和 `references/workflow-detail.md`，确认当前脚本入口、产物类型和登记边界。

截图路线：

- 用户把页面截图、代码截图、运行结果截图放到 `assets/screenshots/`
- 可选补一份 `assets/screenshots/metadata.json`
- 运行 `python scripts/register_manual_figures.py`
- 未实际落盘的截图，不得在正文里写成已经存在

图表路线：

- 业务流程图、需求流程图：默认交付 Mermaid 代码
- 生成 Mermaid 代码：`python scripts/generate_mermaid_flowcharts.py`
- 用户把 Mermaid 代码复制到 draw.io 后，再把产物文件路径告诉 agent
- 用例图、ER 图、架构图、部署图、组件图：默认交付 `.drawio` 文件
- 生成 `.drawio` 源文件：`python scripts/generate_drawio_diagrams.py`
- 需要直接生成 Graphviz / matplotlib 图片时，运行 `python scripts/generate_all_figures.py`
- 大型 ER 图可拆成多张，例如按用户、订单、房间、支付等子域拆开
- 用户确认 Mermaid / `.drawio` 源文件后，运行 `python scripts/register_diagram_assets.py` 登记到 `assets/manifest.json`
- 如果还没有导出 PNG/JPG，允许先登记为“待导出”的图表资产，preflight 会继续提醒补导出图片

本阶段不是一次做完，而是反复停下来：

1. agent 先给图表清单
2. 用户确认清单
3. agent 生成 Mermaid 或 `.drawio`
4. 用户检查并把产物放入工作区
5. agent 再继续正文引用

### Phase 6: Preflight

目标：在排版前暴露缺口，尤其是证据缺口。

- 运行 `python scripts/run_preflight.py`
- 输出 `output/preflight-report.md`

重点检查：

- 是否还缺真实截图
- 是否还缺图表占位的实际文件
- 是否出现了无证据支撑的实现描述
- 是否有 AI 腔、空话或过度学术化表述

preflight 后必须停下，先让用户看报告，再决定是否进 docx。

### Phase 7: Layout

目标：只在证据和图表都确认后再生成 docx。

- 运行 `python scripts/layout_generate_docx.py`
- 输出 `output/thesis.docx`

如果还有 `TODO`、缺图、缺截图、缺文献确认，不要强行收尾。

## Minimal Acceptance Path

每次改 skill 后，至少验证这条链路：

1. 初始化一个工作区
2. 检查 `thesis.json` 是否带有人机协作字段
3. 读取 skill 时，能明确看出哪些节点必须停下来等用户
4. 项目路径、中文文献目录、截图目录未确认时，skill 不会鼓励 agent 自行猜测
5. Mermaid / `.drawio` 路线清晰，且图区分真实已存在资产与待用户补充资产

## Packaging Notes

推荐随 skill 发布：

- `SKILL.md`
- `agents/openai.yaml`
- `scripts/`
- `references/`
- `template/`

不要把这些内容作为 skill 发布物的一部分：

- `__pycache__/`
- `test_workspace/`
- 临时草稿、测试输出、打包压缩包
- 人工对照用的临时截图和历史备份
