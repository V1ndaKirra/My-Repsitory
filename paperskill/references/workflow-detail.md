# Workflow Detail

本文件记录与当前脚本实现对齐的工作流细节。它优先回答“脚本今天真的支持什么”，而不是“未来理想上想支持什么”。

## Current Verified Scope

基于当前 `scripts/` 目录核对后，以下能力已经有对应实现：

- 工作区初始化：`init_workspace.py`
- 项目画像初扫：`build_project_profile.py`
- 答辩素材包生成：`build_undergrad_evidence_pack.py`
- 章节写作包生成：`build_undergrad_chapter_kits.py`
- 草稿侧边提示生成：`build_undergrad_draft_sidecars.py`
- 环境检测与 Windows 优先自动安装：`setup_env.py`
- 英文文献检索、中文 PDF 入库、全文提取、文献验证、索引生成
- 章节摘要桥接：`generate_chapter_brief.py`
- 手工截图登记：`register_manual_figures.py`
- Mermaid 流程图代码生成：`generate_mermaid_flowcharts.py`
- draw.io 图文件生成：`generate_drawio_diagrams.py`
- 用户确认后的 Mermaid / draw.io 资产登记：`register_diagram_assets.py`
- 图片调度、Graphviz 渲染、表格登记
- 本地文献索引阅读与检索辅助：`literature_read.py`
- 论文预检：`run_preflight.py`
- Markdown 到 `.docx` 的排版输出：`layout_generate_docx.py`

以下部分仍主要依赖 Agent 自己完成，而不是独立脚本：

- `project/profile.json` 的二次补全与确认
- `figures-spec.json` / `tables-config.json` 的内容设计

## Undergrad Thesis Orientation

这个 skill 的目标场景以本科毕设为主，因此默认要优先服务“答辩可解释性”而不是研究型论文腔调。

默认重心：

- 工作量证据是否具体
- 技术选型理由是否说得明白
- 实现过程是否能落到模块、接口、表结构、页面或配置
- 开发难点与解决过程是否真实存在

当前已经落实到实现层的地方：

- `run_preflight.py` 会继续检查 fake citation、套话、测试数字等高风险内容
- `generate_chapter_brief.py` 现在额外抽取 `evidence_refs`、`framework_mentions`、`technical_decisions`、`development_challenges`
- `run_preflight.py` 现在额外提示实现证据不足、缺少选型理由、缺少难点与解决
- `run_preflight.py` 现在还会提示实现章节缺少截图型证据，以及明显的 AI 腔/模板化口吻
- `run_preflight.py` 现在还会提示截图引用不自然，例如只有截图占位、没有上下文解释

## Phase 0: Workspace Initialization

### 实际脚本行为

`python scripts/init_workspace.py --root <THESIS_ROOT>`

会创建：

- 目录结构
- 本科答辩导向 `thesis.json`
- 默认 `project/profile.json`
- 与当前预检脚本兼容的章节骨架
- 初始 `drafts/*.md`
- `assets/screenshots/` 目录

`python scripts/setup_env.py`

支持参数：

- `--install`: 自动安装缺失的 Python 依赖
- `--status`: 仅输出 JSON 状态
- `--skip-graphviz`
- `--skip-tesseract`

### 已核对事实

- Python 依赖安装链路存在，优先尝试清华、阿里云、USTC、PyPI
- Graphviz / Tesseract 自动安装逻辑是 Windows `.exe` 安装器
- `setup_env.py` 会把环境结果写回 `thesis.json.environment`
- 如果 `context_bridge` 缺失，脚本会初始化它

### 文档约束

- 不要把 Graphviz / Tesseract 自动安装写成“跨平台能力”
- 没有 `thesis.json` 时，环境结果不会成功写回
- 自动安装失败时，要允许回退到 `offline-manual-setup`

## Phase 1: Project Comprehension

### 当前约束

当前已经有 `build_project_profile.py` 可做第一轮仓库扫描，但它仍然是“证据优先”的基础画像，不会替你编出业务职责、选型理由和开发难点。

建议输出结构：

```json
{
  "status": "confirmed",
  "repo_root": "E:/repo",
  "tech_stack": {
    "backend": [],
    "frontend": [],
    "database": []
  },
  "architecture": {},
  "modules": [],
  "data_model": {},
  "apis": {},
  "core_services": [],
  "scale": {}
}
```

### 实际调用方式

```bash
python scripts/build_project_profile.py --repo E:\path\to\repo
python scripts/build_project_profile.py --repo E:\path\to\repo --confirm
python scripts/build_undergrad_evidence_pack.py
python scripts/build_undergrad_chapter_kits.py
python scripts/build_undergrad_draft_sidecars.py
```

### 与脚本的接缝

- `run_preflight.py` 会检查 `thesis.json.project.status == "confirmed"`
- `run_preflight.py` 还会检查草稿中的 `path:` 证据路径是否能在 `project/profile.json` 中解析
- `build_project_profile.py` 目前能自动抽取：技术栈、基础架构层次、模块分组、API 路径、实体字段、前端页面、SQL 文件、配置文件、evidence_index
- `build_project_profile.py` 现在还会额外抽取可观察到的 `Service` 类与公开方法，用来补强“自己写了哪些核心代码”的证据
- `build_project_profile.py` 现在还会生成“难点候选”而不是直接编造“已发生难点”：它会结合认证/跨域配置、SQL 文件、环境配置、模块拆分线索以及代码中的 `TODO/FIXME` 标记，给出适合回忆和补写的 `challenge_log`
- 这些 `challenge_log` 候选现在默认还带四段式写作骨架：`symptom_prompt`、`diagnosis_prompt`、`fix_prompt`、`result_prompt`
- `build_project_profile.py` 目前不会自动可靠抽取：业务职责中文说明、真实技术选型理由、开发难点与解决过程
- `build_undergrad_evidence_pack.py` 会把 profile 进一步整理成：章节聚焦点、建议截图目标、可直接放进正文的 `path:` 候选、技术选型解释提示词
- `build_undergrad_chapter_kits.py` 会继续把上述信息按 `ch4/ch5/ch6` 分章整理，并尝试为已登记截图生成更自然的正文引用句
- `build_undergrad_draft_sidecars.py` 会把章节包再压缩成贴着 `drafts/*.md` 的 `.guide.md` 文件，方便一边看提示一边写正文
- `ch6` 的章节包和 sidecar 现在会优先展示这些四段式难点骨架，帮助把“真实问题复盘”写得更像本科答辩材料
- `register_manual_figures.py` 现在还支持可选的 `assets/screenshots/metadata.json`，可为截图补充证明点、模块提示和章节归属

对本科毕设，建议 `project/profile.json` 额外维护这些信息，哪怕先由 Agent 写入：

- `tech_decisions`: 记录框架/数据库/认证方案为何选用
- `implementation_highlights`: 记录自己完成的关键模块
- `challenge_log`: 记录典型报错、瓶颈和解决方案
- `evidence_index`: 把草稿里可能引用的 `path:` 路径集中维护

如果要让这个阶段更稳定，后续应该补一个独立的 `profile` 生成脚本；当前文档不能假装它已经存在。

## Phase 2: Literature Acquisition

### 2.1 英文文献检索

实际调用方式：

```bash
python scripts/literature_search.py "web management system, spring boot"
```

注意：

- 当前不是 `--keywords` 参数风格，而是位置参数里放逗号分隔查询
- 默认调用 Semantic Scholar 和 CrossRef
- 输出 `library/metadata.json` 与 `library/references.bib`
- 脚本会更新 `thesis.json.library` 统计与 `progress.phase`

### 2.2 中文 PDF 入库

实际调用方式：

```bash
python scripts/literature_import_pdfs.py --dir <用户下载后的中文 PDF 目录>
```

注意：

- 当前没有 `--pdf-dir` 参数
- 支持 `--dir <用户目录>`：把用户下载好的中文 PDF 复制进 `library/pdfs/` 后再统一入库
- 未传 `--dir` 时，仍会扫描 `library/pdfs/`
- 条目语言写为 `zh`

### 2.3 全文提取

实际调用方式：

```bash
python scripts/literature_extract_fulltext.py
python scripts/literature_extract_fulltext.py --pdf sample.pdf --force
```

注意：

- OCR 可用性依赖 `thesis.json.environment.ocr_available`
- 没有 OCR 时，扫描件会被跳过而不是强行处理
- 成功时会写 `full_text_path`、`extracted_sections`、`key_claims`、`extraction_quality`

### 2.4 文献验证与索引

实际调用方式：

```bash
python scripts/literature_verify.py --unverified-only
python scripts/generate_lit_index.py --with-relevance
```

注意：

- 这里补上了此前文档里缺失的 `2.4`
- `literature_verify.py` 默认只验证英文且缺 DOI 的条目
- `generate_lit_index.py --with-relevance` 是启发式相关度，不是 LLM 语义判断

### 文献质量规则

脚本层今天能直接帮助约束的风险包括：

- 不存在的 cite-key
- `verification_status = unverifiable` 的高频引用
- DOI 格式异常
- 高频引用但既无摘要也无全文的条目

不能写成脚本已实现的能力：

- 学术质量评分
- 研究方法优劣判定
- 自动判断“是否足够前沿”

本科默认提醒：

- 文献是支撑材料，不是论文主角
- 如果实现章节、问题处理章节很空，仅靠多引用几篇文献不能弥补工作量表达不足

## Phase 3: Outline Planning

### 推荐结构

`thesis.json.outline` 推荐至少包含：

```json
{
  "id": "ch1",
  "title": "绪论",
  "draft_path": "drafts/01-introduction.md",
  "word_budget": 3000,
  "word_actual": 0,
  "status": "planned",
  "subsections": []
}
```

### 已核对事实

- `run_preflight.py` 当前硬编码检查 `ch0`、`ch3`、`ch4`、`ch5`、`ch6`、`ch7`
- 如果你的学校模板不是这套章节结构，必须同步修改脚本

所以文档里应该把这件事写成“当前默认假设”，而不是“普适论文结构”。

## Phase 4: Chapter Drafting

### frontmatter

```yaml
---
chapter_id: ch1
title: 绪论
word_budget: 3000
word_actual: 1984
status: drafted
last_updated: 2026-05-26T09:00:00+00:00
---
```

### 中途校验

`python scripts/literature_check_cite.py --draft drafts/01-introduction.md --strict`

`--strict` 的实际作用：

- 继续把不存在的 cite-key 视为错误
- 额外把 `verification_status = unverifiable` 的引用作为 warning 提示

### 写作质量提示

这些规则在 `run_preflight.py` 里有对应实现或近似实现：

- 研究现状引用量不足
- 相关技术小节引用量不足
- 段落过短/过长
- 同段重复引用
- 模板化套话
- 术语写法不一致
- 实现章节证据路径不足
- 技术选型理由缺失
- 开发难点与解决过程缺失

如果前面已经生成 `project/chapter-kits/`，建议写作时先看对应章节包：

- `ch4-system-design.md`：偏设计、选型与结构解释
- `ch5-implementation.md`：偏模块实现、`path:` 证据与截图自然引用
- `ch6-test-and-debug.md`：偏问题复盘、测试结果与修复过程

如果已经存在 `drafts/*.guide.md`，它们更适合在真正落文时开着一起写：

- `.guide.md` 更短，偏提醒
- 正式 `.md` 草稿仍然是最终写作目标

## Phase 5: Asset Generation

### 当前支持的图片类型

- `flowchart`
- `architecture`
- `er_diagram`
- `module_tree`
- `timeline`
- `custom`

前五种由 Graphviz 链路处理，`custom` 走 matplotlib + `project/custom_figures.py`。

### 当前支持的输入文件

- `project/figures-spec.json`
- `project/tables-config.json`
- `assets/screenshots/*` 手工截图资源

### 当前支持的脚本

```bash
python scripts/generate_mermaid_flowcharts.py
python scripts/generate_drawio_diagrams.py
python scripts/generate_all_figures.py
python scripts/generate_all_figures.py --type flowchart
python scripts/assets_generate_tables.py
python scripts/register_manual_figures.py
```

### 重要约束

- `assets_generate_tables.py` 不是“根据 profile 自动造表”，而是读取 `project/tables-config.json`
- `generate_mermaid_flowcharts.py` 只生成 Mermaid 代码文件，不会自动登记为论文可插入图片资产
- `generate_drawio_diagrams.py` 只生成 `.drawio` 文件，不会自动登记为论文可插入图片资产
- `generate_all_figures.py` 会把成功生成的图片登记到 `assets/manifest.json`
- `generate_dot_diagrams.py` 是 `generate_all_figures.py` 调用的 Graphviz 兼容后端，不作为主流程入口单独执行
- `generate_chen_er_from_profile.py` 是独立辅助脚本，不在主流程自动调用
- `literature_read.py` 是文献索引生成后的本地阅读/检索辅助，不替代 `literature_extract_fulltext.py`
- `register_manual_figures.py` 会把截图登记成 `type=figure`、`source_format=manual-screenshot` 的资产，供 `layout_generate_docx.py` 插入

### 协作式交付约束

- Mermaid 和 `.drawio` 产物默认是“给用户检查/编辑”的中间工件，不应直接写成论文里已经存在的最终插图
- `register_diagram_assets.py` 会把已确认的 `.mmd` / `.drawio` 登记进 `assets/manifest.json`
- 如果还没有导出 PNG/JPG，登记后会标记 `ready_for_docx=false`，preflight 继续提示补导出图片
- 如果正文需要先预留图位，请用 `[TODO: 插入...，待用户确认图文件]` 形式，而不是提前写“如图所示”
- 用户确认图文件并放入工作区后，再继续补正文引用和导出链路

详细 JSON 结构见 `references/diagram-spec.md`。

## Phase 6: Preflight

### 实际输出

```bash
python scripts/run_preflight.py
```

输出：

- 标准输出会打印 JSON 摘要
- 文件输出为 `output/preflight-report.md`

### 已核对的重要检查

`critical`：

- 缺失必需章节或草稿
- 引用键不在 `library/metadata.json`
- 图表/表格引用未登记到 `assets/manifest.json`
- `[[sec:...]]` 无法解析
- TODO 残留
- 被引用文献缺关键字段
- 测试章节中疑似编造量化指标
- 高频引用 `unverifiable` 文献
- DOI 格式异常

`high`：

- 字数偏离预算
- 套话
- stale 资产
- 章节未 finalized
- 实现过程缺少可追溯工作量证据
- 缺少技术选型理由说明
- 缺少开发难点与解决过程

`medium` / `low`：

- 未使用文献或资产
- 段落长度异常
- 同段重复引用
- 常见术语不一致
- 绪论与相关技术引用不足
- 英文比例不足
- 文献总量不足
- 实现章节缺少截图型证据
- 写作口吻偏空泛或 AI 腔
- 截图引用不够自然

### 解释边界

这些检查中有不少是启发式，不代表学术结论。文档里必须使用“检测”“提示”“风险”这类措辞，不能写成“保证学术质量”。

## Phase 7: Layout & Output

### 实际脚本行为

`python scripts/layout_generate_docx.py`

已核对行为：

- 生成 `output/thesis.docx`
- 支持封面、摘要、目录、正文、参考文献
- 支持 `[@cite-key]` 到 `[N]` 编号引用
- 支持首次图表引用后插入图片/表格与题注
- 更新 `thesis.json.progress.last_updated`

### 当前限制

- `format-contract.json` 并不是“唯一生效配置源”
- 大部分字体、标题样式、页码格式仍在脚本里硬编码
- 当前真正被消费的 contract 字段范围见 `references/format-spec.md`

## Minimal Acceptance Path

这条链路适合作为每次修改 skill 后的 smoke test：

1. 准备最小 `thesis.json`
2. 运行 `setup_env.py --status`
3. 准备最小 `project/profile.json`
4. 用 `literature_search.py` 或 `literature_import_pdfs.py` 得到 2-3 篇文献
5. 写两章最小草稿，并包含真实 `[@cite-key]`
6. 用 `figures-spec.json` 生成 1 张图，用 `tables-config.json` 生成 1 张表
7. 运行 `run_preflight.py`
8. 运行 `layout_generate_docx.py`

## Release Hygiene

推荐保留：

- `SKILL.md`
- `agents/openai.yaml`
- `scripts/`
- `references/`
- `template/`

建议忽略或移出发布包：

- `scripts/__pycache__/`
- `test_workspace/`
- 临时图片、草稿、压缩包、样张
