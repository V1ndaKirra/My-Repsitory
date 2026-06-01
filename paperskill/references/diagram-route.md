# Diagram Route

这份文档定义 thesis-writing skill 的图表交付路线，重点是“真实项目驱动”和“用户可编辑”。

## Core Rule

图表不是为了堆信息，而是为了帮用户答辩时讲清楚：

- 业务是怎么流转的
- 系统是怎么设计的
- 数据是怎么组织的
- 模块之间怎么协作
- 系统是怎么一步步实现出来的

## Output Routes

### Mermaid Route

默认用于：

- 业务流程图
- 需求流程图
- 功能处理流程图
- 问题排查流程图
- 开发推进步骤图

交付形式：

- 先给 Mermaid 代码
- 用户自行复制进 draw.io
- 用户保存 draw.io 文件后，把路径告诉 agent
- 用户确认源文件后，运行 `python scripts/register_diagram_assets.py` 登记到 `assets/manifest.json`

约束：

- Mermaid 代码必须基于真实模块、真实业务步骤、真实判断条件
- 不得凭空补业务节点
- 节点要保持可编辑、可拆分

### Drawio Route

默认用于：

- 用例图
- ER 图
- 架构图
- 部署图
- 组件图

交付形式：

- 直接生成 `.drawio` 文件
- 每张图一个文件
- 文件默认放在 `assets/figures/`
- 用户确认 draw.io 源文件后，同样通过 `register_diagram_assets.py` 登记

约束：

- 大图允许拆成多张图
- ER 图尤其不要硬塞成一张
- 图中元素名称必须来自真实项目证据

## Recommended Mapping

### Chapter 2 / Chapter 3

- 需求分析、业务流程分析：优先 Mermaid
- 适合拆成多张小流程图，不追求全量总图

### Chapter 4

- 系统总体架构图：`.drawio`
- 部署图：`.drawio`
- 组件图：`.drawio`
- ER 图：`.drawio`，必要时拆图

### Chapter 5 / Chapter 6

- 开发步骤、调用流程、问题排查流程：优先 Mermaid
- 页面、代码、报错、运行结果：优先手工截图

## Placeholders In Drafts

当图还没落盘时，只允许这样写：

```text
[TODO: 插入订单处理流程图，待用户确认 Mermaid 并保存 draw.io 产物]
```

不要提前写成：

```text
如图所示，订单处理流程已经……
```

## ER Split Guidance

如果实体很多，按子域拆图，例如：

- 用户与权限 ER 图
- 商品与类型 ER 图
- 订单与记录 ER 图
- 支付与结算 ER 图

拆图后在正文里分别解释每张图证明什么，不要让一张图承担全部解释任务。
