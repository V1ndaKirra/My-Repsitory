# Interactive Checkpoints

这份文档专门约束 thesis-writing skill 的“停下来等用户确认”流程。

## Default Rule

每个关键阶段都要形成一个可检查的小交付，然后暂停。

暂停时必须输出五类信息：

1. 本阶段做了什么
2. 新增或更新了哪些文件
3. 用户现在应该检查什么
4. 还缺哪些用户输入
5. 用户确认后下一步做什么

## Mandatory Gates

### Gate 1: Repo Confirmed

继续条件：

- 用户明确给出项目路径
- 路径已经写入 `thesis.json.user_inputs.repo_root`

暂停说明模板：

- 已记录项目路径
- 下一步将扫描哪些内容
- 输出会写到 `project/profile.json`

### Gate 2: Project Profile Reviewed

继续条件：

- 用户确认 `project/profile.json` 的模块、接口、实体没有明显误判

暂停说明模板：

- 已生成项目画像和证据索引
- 请检查模块命名、核心接口、实体关系是否准确
- 如果有误，先修正这里再往下写论文

### Gate 3: Literature Inputs Reviewed

继续条件：

- 用户确认中文文献目录或 PDF 位置
- 英文检索结果没有明显无关条目

暂停说明模板：

- 已入库哪些文献
- 哪些条目仍需用户删除或补充
- 哪些文献将支撑哪一章

### Gate 4: Outline Reviewed

继续条件：

- 用户确认章节结构
- 用户确认截图需求和图表需求清单

暂停说明模板：

- 已生成章节计划
- 每章证据来源是什么
- 哪些截图和图表必须补

### Gate 5: Implementation Evidence Requested

继续条件：

- 用户已知晓当前缺哪些截图
- 用户准备补充页面图、代码图、报错图、运行结果图

暂停说明模板：

- 当前实现章节还缺哪些证据
- 每张截图建议证明什么
- 建议用户放到哪里

### Gate 6: Mermaid Delivered

继续条件：

- 用户拿到 Mermaid 代码
- 用户自行复制到 draw.io 并保存产物
- 用户把产物路径告诉 agent

暂停说明模板：

- 已生成哪几张流程图的 Mermaid
- 对应建议文件名是什么
- 请用户保存后回传路径

### Gate 7: Drawio Delivered

继续条件：

- `.drawio` 文件已经放进工作区
- 用户确认主要结构可编辑、可接受

暂停说明模板：

- 已生成哪些 `.drawio`
- 每个文件对应论文哪一节
- 如果图太挤，优先拆图

### Gate 8: Preflight Reviewed

继续条件：

- 用户看过 `output/preflight-report.md`
- 用户决定是继续修文还是生成 docx

## User Action Lists

当阶段需要用户补材料时，优先输出清单，不要只输出泛泛建议。

推荐清单格式：

```text
请补这 3 类截图到 assets/screenshots/：
1. 登录成功后的后台首页
2. 核心模块的代码截图
3. 真实报错或修复后的运行结果截图
```

## Do Not

- 不要在等待用户确认时继续推进下一阶段
- 不要把“建议用户补截图”写成“截图已经存在”
- 不要把 Mermaid 代码和 draw.io 产物混成一个交付
- 不要让用户同时做过多任务；每次优先给最小可执行动作

## Brainstorm Hand-off

当用户说“这个模块我做过，但我不知道怎么写”或“这个 bug 我修过，但我记不清怎么排查的”时：

1. 不要直接替用户编故事
2. 先暂停正文推进
3. 优先调用 `superpowers brainstorm`
4. 如果当前环境没有该 skill，就按同样结构做普通对话引导

推荐先围绕这 4 个问题引导：

1. 最开始做的是页面、接口、服务还是数据库
2. 中间卡住的具体点是什么
3. 最后改了哪几处代码或配置
4. 哪张截图最能证明这段过程
