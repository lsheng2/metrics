# UI Change Quality Gate

## Purpose

任何改到 Dashboard UI 的 OpenSpec change，除了功能行为，还必须定义视觉层级、组件密度、状态覆盖和浏览器验证。目标是让 UI 在第一次实现时就达到产品化可用状态，而不是靠多轮主观返工。

本 gate 与具有约束力的 `openspec/docs/current-baseline/frontend-design-requirements.md`（Meridian 前端设计要求）配套使用；两者冲突时以后者的硬规则和 Definition of Done 为准。

## Proposal 阶段必须说明

- 目标用户和主任务：例如低上下文 operator、daily dashboard user、reviewer 或 admin。
- 第一屏主路径：用户进入页面后先看什么、先点什么、哪些内容只属于高级区。
- 页面类型：dashboard、admin table、wizard/editor、diagnostic/readiness、workbench 或 chart/evidence。
- 复用基线：必须说明复用哪些 Meridian primitive（见 frontend-design-requirements 的组件目录）以及哪个现有页面的布局、按钮、表格、状态、help tip 和 responsive pattern。
- 禁止项：不能新增卡片套卡片、无意义 hero、只靠长说明文字解释流程、无法量化的“更现代”要求。

## Design 阶段必须说明

- 布局分区：header、summary、primary inventory、editor/detail、advanced config、danger zone。
- 组件规格：按钮尺寸（`--control-height`、`-sm`、`-xs`）、主/次/危险动作、表格列宽、行高、输入框高度、textarea 默认高度。
- 主题：light 与 dark 都必须成立；颜色只用 semantic tokens，新增颜色对必须加入 `contrast-pairs.json`。
- 状态矩阵：empty、draft、enabled、archived、invalid、loading、error、success、import/export、destructive confirmation。
- 低上下文提示：必填字段、enable blocker、profile/scope/binding authority、provider-specific capability。
- Provider 视觉语言：Jira 绿色、HSD-ES 蓝色、future provider neutral，并说明使用位置。
- Responsive contract：至少定义 desktop、narrow desktop、mobile 的布局期望和不允许出现的 overlap/overflow。

## Tasks 阶段必须包含

- Browser smoke：`npm run qa:browser`（Playwright + axe，light/dark × desktop/phone）覆盖改动路由，并在真实浏览器中复查 light、dark 和手机宽度。
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
- 页面样式放 `ui_web/static/css/pages/<feature>.css`，脚本放 `ui_web/static/js/<feature>.js`，并只在 `ui_web/static_assets.py` 登记一次；不存在兜底的总样式表或总脚本，放不进现有文件的规则就新建一个文件并登记。
- 文件接近体积上限（模板 300、CSS 400、浏览器 JS 400 行）时先按关注点拆分（partial、组件族、feature 模块），不得靠豁免或调高上限过关。
- 图标 class 必须写成字面量 `iconoir-<name>`，不能拼接；新增图标后运行 `npm run build:vendor`。
- 颜色、间距、圆角、阴影和 z-index 只能引用 tokens；页面 CSS 不得覆盖 primitive 的 display 或尺寸。

## Validation Evidence

完成 UI change 前，最终报告至少列出：

- 运行的 Django/view tests。
- `ui_web/frontend` 下的 `npm run check`（token 漂移、vendor manifest、Stylelint、WCAG 对比度）。
- `npm run qa:browser` 的路由、主题与 viewport 结果，以及 light/dark 截图复查记录。
- 生成或检查的页面路径。
- `python manage.py check`。
- `python scripts/check_file_size_limits.py --include-untracked` 与 `python scripts/check_diff_whitespace.py --include-untracked`。
- `git diff --check`。
- OpenSpec strict validation。
