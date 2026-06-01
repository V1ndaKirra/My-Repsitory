# Diagram Spec

图表阶段的目标是把“图要表达什么”从“图怎么画出来”里拆开。Agent 负责语义结构，脚本负责布局和渲染。

## Default Rule

- 默认只生成 JSON 规格，不手写绘图代码
- 流程图、业务流程图、需求流程图默认优先生成 Mermaid 代码
- 架构图、ER 图、模块图、部署图、组件图默认优先生成 `.drawio`
- Graphviz 渲染链路保留为兼容/快速预览方案，不再是新的默认交付路线
- 只有明确需要复杂统计图或特殊视觉时，才使用 `custom` 图并由人工维护 `project/custom_figures.py`

## Files

- 图片规格：`project/figures-spec.json`
- 表格规格：`project/tables-config.json`
- 自定义图片函数：`project/custom_figures.py`
- Mermaid 代码输出目录：`assets/figures/*.mmd`
- draw.io 文件输出目录：`assets/figures/*.drawio`
- 手工截图目录：`assets/screenshots/`
- 生成后资产登记：`assets/manifest.json`

## figures-spec.json

顶层结构：

```json
{
  "figures": [
    {
      "id": "fig-arch-overview",
      "type": "architecture",
      "caption": "系统总体架构图",
      "section_ref": "4.1 系统总体架构设计",
      "spec": {}
    }
  ]
}
```

## Supported Figure Types

### flowchart

```json
{
  "id": "fig-order-flow",
  "type": "flowchart",
  "caption": "订单处理流程图",
  "section_ref": "4.3 订单管理模块",
  "spec": {
    "direction": "TB",
    "nodes": [
      {"id": "start", "label": "开始", "shape": "start"},
      {"id": "submit", "label": "提交订单", "shape": "process"},
      {"id": "decision", "label": "是否支付", "shape": "decision"},
      {"id": "end", "label": "结束", "shape": "end"}
    ],
    "edges": [
      {"from": "start", "to": "submit"},
      {"from": "submit", "to": "decision"},
      {"from": "decision", "to": "end", "label": "是"}
    ]
  }
}
```

节点形状：

- `start`
- `end`
- `process`
- `decision`
- `data`
- `manual`

### architecture

```json
{
  "id": "fig-arch-overview",
  "type": "architecture",
  "caption": "系统总体架构图",
  "section_ref": "4.1 系统总体架构设计",
  "spec": {
    "direction": "TB",
    "layers": [
      {
        "id": "frontend",
        "label": "前端层",
        "color": "accent",
        "nodes": [
          {"id": "admin", "label": "管理端前端\\n(Vue 3 + Vite)"},
          {"id": "client", "label": "用户端前端\\n(Vue 3 + Vite)"}
        ]
      },
      {
        "id": "backend",
        "label": "应用层",
        "color": "primary",
        "nodes": [
          {"id": "server", "label": "后端服务\\n(Spring Boot 3.3.4)"}
        ]
      }
    ],
    "connections": [
      {"from": "admin", "to": "server"},
      {"from": "client", "to": "server"}
    ]
  }
}
```

颜色值建议：

- `primary`
- `accent`
- `success`
- `danger`
- `neutral`

### er_diagram

```json
{
  "id": "fig-er-diagram",
  "type": "er_diagram",
  "caption": "数据库 E-R 图",
  "section_ref": "4.2 数据库设计",
  "spec": {
    "direction": "LR",
    "entities": [
      {
        "id": "sys_user",
        "name": "sys_user",
        "fields": [
          {"name": "user_id", "pk": true},
          {"name": "username"},
          {"name": "role"}
        ]
      }
    ],
    "relationships": [
      {"from": "sys_user", "to": "order_info", "card_a": "1", "card_b": "N", "label": "下单"}
    ]
  }
}
```

### module_tree

```json
{
  "id": "fig-module-tree",
  "type": "module_tree",
  "caption": "系统功能模块树",
  "section_ref": "3.2 功能结构",
  "spec": {
    "direction": "TB",
    "root": {
      "id": "root",
      "label": "医院门诊系统",
      "color": "primary",
      "children": [
        {"id": "user", "label": "用户管理"},
        {"id": "visit", "label": "挂号就诊"}
      ]
    }
  }
}
```

### timeline

```json
{
  "id": "fig-dev-timeline",
  "type": "timeline",
  "caption": "系统开发阶段安排",
  "section_ref": "1.4 研究计划",
  "spec": {
    "direction": "TB",
    "steps": [
      {"id": "p1", "label": "需求分析"},
      {"id": "p2", "label": "系统设计"},
      {"id": "p3", "label": "实现与测试"}
    ]
  }
}
```

### custom

只在确有必要时使用：

```json
{
  "id": "fig-custom-metrics",
  "type": "custom",
  "caption": "实验结果对比图",
  "section_ref": "6.3 性能分析",
  "function": "fig_custom_metrics"
}
```

然后由人工在 `project/custom_figures.py` 中维护同名函数。

## tables-config.json

`assets_generate_tables.py` 读取的是表格配置，不是自动从 `profile.json` 反推表格。

```json
[
  {
    "id": "tab-use-cases",
    "caption": "系统主要功能用例",
    "section_ref": "3.2 功能需求分析",
    "headers": ["编号", "角色", "用例"],
    "rows": [
      ["UC-01", "管理员", "维护科室信息"],
      ["UC-02", "患者", "预约挂号"]
    ]
  }
]
```

## Generation Commands

```bash
python scripts/generate_mermaid_flowcharts.py
python scripts/generate_drawio_diagrams.py
python scripts/generate_all_figures.py
python scripts/generate_all_figures.py --type flowchart
python scripts/assets_generate_tables.py
python scripts/register_manual_figures.py
```

推荐顺序：

1. 先生成 Mermaid 流程图代码，交给用户复制到 draw.io
2. 再生成 `.drawio` 结构图，交给用户检查可编辑性
3. 用户确认并补齐工作区产物后，再决定是否走 Graphviz 预览图或最终导出图片

## Manual Screenshot Flow

本科毕设建议把这些截图作为“真实性证据”纳入论文：

- 核心页面截图
- 后台管理界面截图
- 关键运行结果截图
- 核心代码截图
- 报错与修复前后对比截图

流程：

1. 把截图放到 `assets/screenshots/`
2. 可选：补一份 `assets/screenshots/metadata.json`，写明每张截图证明了什么、对应哪个模块、适合放哪一章
3. 运行 `python scripts/register_manual_figures.py`
4. 到 `assets/manifest.json` 中确认生成了 `shot-01`、`shot-02` 之类的 figure 资产
5. 在草稿中使用 `{{fig:shot-01}}`

更推荐的写法不是单独放一行截图，而是让截图跟着叙述自然出现：

```text
如 {{fig:shot-01}} 所示，登录成功后系统会跳转到后台首页，并在右上角显示当前管理员账号。
```

示例 manifest 条目：

```json
{
  "id": "shot-01",
  "type": "figure",
  "caption": "用户登录功能截图",
  "file": "assets/screenshots/login-page.png",
  "source_format": "manual-screenshot",
  "section_ref": "5.1 系统实现",
  "module_hint": "auth",
  "proof_note": "管理员登录成功后可以进入后台首页，并显示当前账号信息",
  "tags": ["登录", "认证", "后台首页"]
}
```

可选的 `assets/screenshots/metadata.json` 可以写成：

```json
[
  {
    "file": "login-page.png",
    "caption": "用户登录功能截图",
    "section_ref": "5.1 系统实现",
    "module": "auth",
    "proof": "管理员登录成功后可以进入后台首页，并显示当前账号信息",
    "tags": ["登录", "认证", "后台首页"]
  }
]
```

## Practical Guidance

- 架构图重点表达层次、边界、依赖方向，不要把所有类都塞进去
- 流程图重点表达状态转移和判断条件
- ER 图重点表达主键、外键、基数关系
- 图表 caption 要能直接放进论文，不要写成调试标签
- `section_ref` 要和草稿中的章节结构对上，便于排版和人工复查
- 截图 caption 要说明它证明了什么，例如“订单管理页面截图”“JWT 登录拦截配置代码截图”，不要只写“截图 1”
- 截图引用要和正文句子连在一起，先讲这个截图说明了什么，再引用它
