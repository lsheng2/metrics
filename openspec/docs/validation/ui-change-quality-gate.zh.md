# UI Change Quality Gate

## Purpose

任何改到 Dashboard UI 的 OpenSpec change，除了功能行为，还必须定义视觉层级、组件密度、状态覆盖和浏览器验证。目标是让 UI 在第一次实现时就达到产品化可用状态，而不是靠多轮主观返工。

## Proposal 阶段必须说明

- 目标用户和主任务：例如低上下文 operator、daily dashboard user、reviewer 或 admin。
- 第一屏主路径：用户进入页面后先看什么、先点什么、哪些内容只属于高级区。
- 页面类型：dashboard、admin table、wizard/editor、diagnostic/readiness、workbench 或 chart/evidence。
- 复用基线：必须说明复用哪个现有页面的布局、按钮、表格、状态、help tip 和 responsive pattern。
- 禁止项：不能新增卡片套卡片、无意义 hero、只靠长说明文字解释流程、无法量化的“更现代”要求。

## Design 阶段必须说明

- 布局分区：header、summary、primary inventory、editor/detail、advanced config、danger zone。
- 组件规格：按钮尺寸、主/次/危险动作、表格列宽、行高、输入框高度、textarea 默认高度。
- 状态矩阵：empty、draft、enabled、archived、invalid、loading、error、success、import/export、destructive confirmation。
- 低上下文提示：必填字段、enable blocker、profile/scope/binding authority、provider-specific capability。
- Provider 视觉语言：Jira 绿色、HSD-ES 蓝色、future provider neutral，并说明使用位置。
- Responsive contract：至少定义 desktop、narrow desktop、mobile 的布局期望和不允许出现的 overlap/overflow。

## Tasks 阶段必须包含

- Browser smoke：用 Playwright 或等价浏览器检查 desktop 与 mobile viewport。
- Layout assertions：页面不得横向溢出；按钮高度差不得明显不一致；关键 editor/list/table 可见。
- Monkey-user path：至少一条真实用户路径，从创建/编辑到保存/错误/恢复或 handoff。
- Screenshot review：实现者必须生成或检查关键页面截图，记录发现的 UI 问题和修复。
- Regression tests：按钮/菜单/高级区/错误状态/导入导出/危险操作必须有 view 或 browser 测试。

## Implementation Checklist

- 页面只保留一个主要工作焦点；高级 JSON、危险操作和批量操作默认收拢。
- 表格操作列最多展示 2-3 个主动作，其余进入 `More` 或明确分组。
- 同一区域按钮高度、字号和 padding 必须一致。
- 表格行高应该稳定，动态内容不能把每行撑成不规则卡片。
- Editor 顶部必须先给 provider/profile identity，再进入 source、mapping、readiness。
- Help tip 用于解释字段语义，不代替页面布局。
- 新增 CSS 必须使用页面级 namespace，避免污染 Scope Library、Workbench 或 Data Health。

## Validation Evidence

完成 UI change 前，最终报告至少列出：

- 运行的 Django/view tests。
- 运行的 browser smoke viewport。
- 生成或检查的页面路径。
- `python manage.py check`。
- `git diff --check`。
- OpenSpec strict validation。
