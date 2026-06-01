# Paperskill

面向本科软件类毕设论文与答辩的协作式写作 skill。不是黑箱流水线，而是**和用户一起推进**的论文协作流程。

## 设计理念

区别于"输入标题、一键生成"的论文工具，Paperskill 的核心假设是：

- 本科毕设的含金量在于**工作量是否具体可见**、**技术选型理由是否说得清楚**、**系统是怎么一步步做出来的**
- 真实项目证据（代码、截图、配置、数据库结构）优先于学术话术堆砌
- 图表、文献、正文之间必须形成闭环引用，杜绝"如图所示"但图不存在的情况
- 每到一个关键节点停下来汇报，等用户确认后再推进，而不是一口气生成整篇

## 核心能力

| 阶段 | 内容 | 产物 |
|------|------|------|
| Phase 0 | 工作区初始化 | 标准化目录结构、状态文件 |
| Phase 1 | 项目理解 | 项目画像、模块/API/实体/页面索引、章节写作包 |
| Phase 2 | 文献获取 | 英文自动检索 + 中文 PDF 导入、全文提取、引用验证 |
| Phase 3 | 大纲规划 | 章节结构、每章证据来源与图表需求 |
| Phase 4 | 逐章撰写 | Markdown 草稿，含 YAML frontmatter 与证据绑定 |
| Phase 5 | 图表资产 | Mermaid 流程图、draw.io 图、Graphviz 图、截图登记 |
| Phase 6 | 预检 | 证据缺口扫描、AI 腔检测、TODO 追踪 |
| Phase 7 | 排版输出 | docx 生成（基于 python-docx） |

## 协作机制

10 个强制暂停节点，每次暂停时告知用户：

- 做了什么
- 新写了什么
- 文件放在哪
- 还缺什么用户输入
- 下一步准备做什么

## 硬规则

- 不编造文献、DOI、页码、API、数据库结构、流程、截图、图表
- 不扫描用户未指定的项目目录
- 所有图表和截图必须有真实素材支撑
- 系统实现章节必须体现开发推进顺序、关键模块落地、问题排查与修复

## 项目结构

```
Paperskill/
├── SKILL.md              # 完整 skill 定义与工作流
├── README.md
├── agents/
│   └── openai.yaml       # OpenAI agent 配置
├── scripts/              # 26 个工具脚本
│   ├── init_workspace.py          # 工作区初始化
│   ├── build_project_profile.py   # 项目画像生成
│   ├── build_undergrad_evidence_pack.py
│   ├── build_undergrad_chapter_kits.py
│   ├── build_undergrad_draft_sidecars.py
│   ├── literature_search.py       # 英文文献检索
│   ├── literature_import_pdfs.py  # 中文 PDF 导入
│   ├── literature_extract_fulltext.py
│   ├── literature_verify.py       # 文献验证
│   ├── generate_lit_index.py      # 文献索引
│   ├── literature_check_cite.py   # 引用完整性检查
│   ├── literature_read.py
│   ├── generate_mermaid_flowcharts.py  # Mermaid 流程图
│   ├── generate_drawio_diagrams.py     # draw.io 图
│   ├── generate_dot_diagrams.py        # Graphviz 图
│   ├── generate_chen_er_from_profile.py # 陈氏 ER 图
│   ├── generate_all_figures.py
│   ├── generate_chapter_brief.py
│   ├── assets_generate_figures.py
│   ├── assets_generate_tables.py
│   ├── register_diagram_assets.py
│   ├── register_manual_figures.py
│   ├── run_preflight.py           # 预检
│   ├── layout_generate_docx.py    # docx 排版
│   ├── setup_env.py               # 环境检测
│   └── thesis_schema.py           # 状态模式定义
├── references/           # 12 个参考文档
│   ├── interactive-checkpoints.md      # 交互检查点话术
│   ├── undergrad-chapter-blueprint.md  # 章节蓝图
│   ├── undergrad-defense-focus.md      # 答辩导向写法
│   ├── undergrad-writing-style.md      # 写作风格指南
│   ├── diagram-route.md                # 图表产线路线
│   ├── diagram-spec.md                 # 图表规格
│   ├── brainstorm-route.md             # 头脑风暴接入
│   ├── workflow-detail.md              # 工作流详情
│   ├── citation-format.md              # 引用格式
│   ├── citation-guide.md               # 引用指南
│   ├── format-spec.md                  # 格式规格
│   └── figure-templates.py             # 图模板
└── template/
    ├── format-contract.json     # 格式约定
    └── original.docx            # 学校模板
```

## 使用方式

将此 skill 安装到你的 AI 助手中（HanaAgent 直接放入 skills 目录），触发场景包括：

- 本科毕设论文写作
- 系统设计与实现类论文
- 需要将代码仓库转为论文
- 需要答辩导向的论文预检

## 许可

个人使用。脚本依赖 Graphviz（流程图渲染）和 Tesseract（可选，OCR），`setup_env.py` 目前仅支持 Windows 自动安装。
