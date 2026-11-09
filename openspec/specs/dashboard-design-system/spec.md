# dashboard-design-system Specification

## Purpose
Dashboard design system 统一定义 Django dashboard 的以下内容：

- 视觉 token
- light/dark/system 主题
- 应用框架导航
- 共享界面 primitives
- 对比度要求
- 运行时资源来源
- 前端质量门禁

目标是让所有页面在任何主题下都呈现一致、清新、高密度且可访问的界面。

## Requirements

### Requirement: Visual tokens are the single styling source
Dashboard 的颜色、字体、字号、间距、圆角、阴影和层级 SHALL 来自同一套 design tokens。主题 token 中的每个颜色 token SHALL 同时定义 light 和 dark 取值；provider 身份色和报告 paper 色在两种主题下保持不变，SHALL 只在 base tokens 中定义一次。页面级样式 SHALL 只引用 semantic tokens，SHALL NOT 写入原始颜色值或自定义 font-family。

#### Scenario: Maintainer changes a token
- **WHEN** 维护者修改 token 源并重新生成主题样式
- **THEN** 所有引用该 token 的页面元素 SHALL 一致地反映新值
- **AND** 已提交的主题样式与 token 源不一致时，frontend check SHALL 失败

#### Scenario: A theme color token lacks one theme
- **WHEN** 主题 token 中的某个颜色 token 只定义了 light 或 dark 其中一个取值
- **THEN** token 构建 SHALL 失败，并指出缺少取值的 token

#### Scenario: Page styles hard-code a color
- **WHEN** 页面级样式出现 hex、命名颜色、颜色函数或非 token 的 font-family
- **THEN** frontend lint gate SHALL 报错，该变更 SHALL NOT 被视为完成

### Requirement: Users can choose light, dark or system theme
Dashboard SHALL 让用户在 light、dark 和 system 三种主题之间切换。用户的选择 SHALL 在页面跳转和重新加载后保留；system 模式 SHALL 跟随操作系统的 color scheme。

#### Scenario: User selects the dark theme
- **WHEN** 用户在侧栏底部的主题切换（或命令面板的主题动作）中选择 dark
- **THEN** 当前页面 SHALL 立即切换为 dark，不需要重新加载
- **AND** 之后打开的每个 dashboard 页面都 SHALL 使用 dark，直到用户再次修改

#### Scenario: System mode follows the operating system
- **WHEN** 主题为 system，且操作系统的 color scheme 在 light 与 dark 之间变化
- **THEN** Dashboard SHALL 在不重新加载的情况下切换到对应主题

#### Scenario: Page loads with a stored theme
- **WHEN** 用户已保存主题选择并打开任意 dashboard 页面
- **THEN** 保存的主题 SHALL 在首次绘制之前生效，页面 SHALL NOT 先闪现另一种主题

### Requirement: Charts follow the active theme
Dashboard 图表的轴线、网格、文字、tooltip 和数据系列颜色 SHALL 取自当前主题的 tokens。主题切换后，已显示的图表 SHALL 重新着色，且不需要重新获取数据。同一数据系列在两种主题下 SHALL 保持相同的身份色相。

#### Scenario: User switches theme while charts are visible
- **WHEN** 页面上已渲染一个或多个图表，用户切换主题
- **THEN** 每个图表 SHALL 使用新主题的颜色重新绘制
- **AND** 图表数据、当前选择和下钻状态 SHALL 保持不变

### Requirement: Application shell provides grouped navigation
每个 dashboard 页面 SHALL 渲染同一个应用框架；只有 404/500 错误页和 iframe 桥接页（如 Grafana selection）例外，它们 SHALL 继承不依赖页面 context 的 `standalone_base.html`。框架中的分组导航 SHALL 来自同一份服务端导航定义，并标记当前页面。导航 SHALL 可折叠，折叠状态 SHALL 在页面之间保留；在手机宽度下，导航 SHALL 以抽屉形式呈现。

#### Scenario: User opens a dashboard page
- **WHEN** 用户打开任意 dashboard 页面
- **THEN** 侧边导航 SHALL 按任务分组列出所有一级页面
- **AND** 当前页面对应的导航项 SHALL 带有 `aria-current="page"`，并在视觉上突出显示

#### Scenario: User collapses the navigation
- **WHEN** 用户折叠侧边导航后打开另一个页面
- **THEN** 新页面 SHALL 保持折叠状态

#### Scenario: User opens the navigation on a phone
- **WHEN** 视口为手机宽度，用户点击 topbar 中的导航按钮
- **THEN** 导航 SHALL 以覆盖内容的抽屉形式打开
- **AND** 用户按下 Esc 时抽屉 SHALL 关闭

### Requirement: Command palette provides keyboard navigation
Dashboard SHALL 提供命令面板。用户可通过 Ctrl/⌘+K 打开它；当焦点不在文本输入控件中时，也可以按 `/` 打开。命令面板 SHALL 支持按名称过滤导航目标和主题动作，并且整个跳转过程 SHALL 可以只用键盘完成。

#### Scenario: User navigates with the command palette
- **WHEN** 用户按下 Ctrl/⌘+K，输入页面名称的一部分后按 Enter
- **THEN** Dashboard SHALL 跳转到当前高亮的匹配页面（默认高亮第一个匹配项）

#### Scenario: User dismisses the command palette
- **WHEN** 命令面板处于打开状态时用户按下 Esc
- **THEN** 命令面板 SHALL 关闭，并且 SHALL NOT 改变当前页面

### Requirement: Dense pages compose shared primitives
Dashboard 页面 SHALL 由共享界面 primitives 组合而成：page header、toolbar、KPI、card、dense table、tag、disclosure 和 empty state。页面级样式 SHALL NOT 修改 primitive 的 display 或尺寸，pages、shell 和报告页样式 SHALL NOT 使用 `!important`；控件的 dirty 和 required-missing 状态 SHALL 使用 foundation 提供的状态 class。缺失值 SHALL 统一显示为弱化的 "—"。

#### Scenario: A table cell has no value
- **WHEN** 表格单元格或 KPI 的值缺失
- **THEN** 该位置 SHALL 显示弱化的 "—"，而不是空白、"None" 或 "N/A"

#### Scenario: A data region has no rows
- **WHEN** 表格或列表的数据集为空
- **THEN** 该区域 SHALL 显示一条 empty state 消息，说明原因或下一步操作

#### Scenario: A heading carries a long value on a phone
- **WHEN** 390px 宽的手机视口中，pane 标题旁的 chip 带有很长的值（例如 Workbench 的 bucket 选择）
- **THEN** chip SHALL 以省略号截断，完整值放在 `title` 中
- **AND** 标题 SHALL 保持单行，chip SHALL NOT 延伸到同一 header 中的操作按钮下方

#### Scenario: Page styles use !important
- **WHEN** pages、shell 或报告页样式中的声明使用 `!important`
- **THEN** frontend lint gate SHALL 报错
- **AND** 只有覆盖导出 HTML 内联样式、并带有写明原因的 lint disable 注释的声明可以例外

### Requirement: Colors meet WCAG AA contrast in every theme
在 light 和 dark 两种主题下，正文文字与其背景的对比度 SHALL 不低于 4.5:1；交互控件、焦点指示和图形元素与相邻背景的对比度 SHALL 不低于 3:1。键盘焦点 SHALL 始终有可见的指示。

#### Scenario: Contrast check runs over theme tokens
- **WHEN** frontend check 计算已声明的前景/背景 token 对在 light 和 dark 下的对比度
- **THEN** 任一 token 对低于其阈值时，检查 SHALL 失败，并报告主题、token 名称和实际对比度

#### Scenario: User navigates with the keyboard
- **WHEN** 用户用 Tab 在链接、按钮、表单控件和 disclosure 之间移动焦点
- **THEN** 获得焦点的元素在两种主题下都 SHALL 显示可见的焦点环

### Requirement: Runtime frontend assets are served locally
Dashboard 运行时需要的字体、图标、样式和 JavaScript 库 SHALL 全部由应用自身的静态文件提供，并固定版本。每个 vendored 文件的来源包、版本和 sha256 SHALL 记录在 manifest 中；本地构建的报告编辑器（Milkdown）bundle SHALL 在自己的 manifest 中记录 bundle、构建 metafile、源入口 `report_milkdown.js` 以及构建所用 `package.json` 和 lockfile 的 sha256。Dashboard SHALL NOT 在运行时依赖 CDN。

#### Scenario: Dashboard runs without internet access
- **WHEN** Dashboard 部署在无法访问外部网络的内网环境中
- **THEN** 字体、图标、图表和 htmx 交互 SHALL 全部正常工作

#### Scenario: A vendored file drifts from its manifest
- **WHEN** 某个 vendored 文件、报告编辑器 bundle 或其构建输入被修改、缺失，或与 manifest 记录的 sha256 不一致
- **THEN** frontend check SHALL 失败，并指出不一致的文件

### Requirement: Frontend source files stay reviewable
Dashboard 的模板、样式表和浏览器脚本 SHALL 受仓库体积门禁约束。共享的样式表和脚本 SHALL 只在唯一一份有序资源清单中登记一次；只有报告页通过页面模板加载自己专用的样式表、脚本和 ES module，且 SHALL NOT 再次加载清单中的资源。仓库中每个被跟踪的文件 SHALL 被一条体积规则或一条带理由的豁免认领。已超过上限的存量文件 SHALL NOT 增长。

#### Scenario: A file matches no size rule
- **WHEN** 变更新增了一个没有任何体积规则或豁免能匹配的文件
- **THEN** 体积门禁 SHALL 失败，并列出这个未认领的文件

#### Scenario: A legacy oversized file grows
- **WHEN** 变更给一个已超过上限、只靠 legacy allowance 放行的文件增加了行数
- **THEN** 体积门禁 SHALL 失败，并报告 base 行数和允许的最大行数

#### Scenario: A stylesheet is split by concern
- **WHEN** 维护者把一个样式表按关注点拆成多个文件
- **THEN** 新文件 SHALL 只在资源清单中登记一次，页面和浏览器测试 SHALL 按清单顺序加载它们

#### Scenario: An asset is orphaned or loaded twice
- **WHEN** 某个顶层样式表或脚本既不在资源清单中，也没有被任何页面模板加载；或者页面模板再次加载了清单中的资源
- **THEN** 前端资源测试 SHALL 失败，并列出这些文件

### Requirement: UI changes pass the frontend quality gates
修改模板、样式、前端脚本或图表的变更，在被视为完成之前 SHALL 通过 frontend check 和 browser QA。browser QA SHALL 覆盖受影响的路由，并在 light 与 dark 主题下分别使用 desktop 和 phone 宽度运行。

#### Scenario: Browser QA runs over touched routes
- **WHEN** browser QA 在每个主题与视口组合下渲染受影响的路由
- **THEN** 出现以下任一情况时，检查 SHALL 失败：
  - HTTP 错误
  - 页面级横向溢出
  - 实际生效的主题与请求的主题不一致
  - console 错误
  - 同源请求返回 HTTP 错误，或没有得到响应（被导航或 htmx 交换中止的请求除外）
  - serious 或 critical 级别的可访问性违规
