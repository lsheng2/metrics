# 上游同步与版本核对

本项目的代码上游为`clutcher/metrics`，本方远端为`lsheng2/metrics`。
编辑器、AI Base SDK及Python依赖各自的版本升级是独立任务，不能与代码上游同步混为一谈。

## 本方主线与推送边界

用户于2026-11-07确认：本项目以本方`main`为主线，跟踪
`origin/main`（`lsheng2/metrics`）。`upstream`（`clutcher/metrics`）仅用于读取、
fetch和差异评估，不向其推送，也不修改开源上游主线。

限定提交先用明确文件清单暂存，核对暂存内容、敏感信息、文档链接及适用验证。
授权发布时显式指定本方远端和分支：

```powershell
git remote get-url --push --all origin
git push origin HEAD:refs/heads/main
git ls-remote --exit-code origin refs/heads/main
```

推送前确认`origin`只指向本方仓库，推送后核对本地/远端SHA和未提交文件。
不使用无目标的推送、`--all`、`--mirror`或强推；真实工单截图、报告和数据Git不属于
代码发布清单。遇到远端前进先检查差异，不覆盖并发提交。

## 当前结论

2026-11-07实际读取GitHub并fetch后：

- 最新正式Release：`1.22`，2026-07-14发布。
- 最新上游main：`dce92c9801628184fa04f0caf4b4f7471a2eb4fd`，2026-07-17 UTC。
- 本次检查的本地主线：`11583075f4db277f5b264064fd58cb2dc82019ef`。
- 上游独有提交为0，本地独有提交152；最新上游已经是本地祖先，**无需rebase**。
- 74项无外网的定向回归通过；没有改变依赖或启动产品服务。

逐提交收益、源码对照和证据hash见
[OpenSpec评估记录](../../openspec/changes/add-provider-neutral-project-reporting/upstream-sync-review.md)。
这是2026-11-07的观测，之后需要重新检查，不能永久视为最新。

## 下次如何检查

先读`AI_CONTRACT.md`，检查remotes、分支和脏文件，不自动stash：

```powershell
git remote -v
git status --short --branch
git ls-remote --symref upstream HEAD
git fetch --no-tags upstream main
git rev-list --left-right --count HEAD...upstream/main
git merge-base HEAD upstream/main
git log --oneline HEAD..upstream/main
```

同时查询GitHub的默认分支、最新正式Release及该tag的准确commit。
Release日期与main最新commit可能不同，不能只看README版本或缓存的remote ref。
`HEAD...upstream/main`的两个数字依次是**本地独有、上游独有**。

若上游独有为0，并且`upstream/main`是`HEAD`的祖先，应记录no-op并停止源码升级。
不要为了执行rebase而强制重放已经发布的历史。

## 有新提交时

1. 固定本地SHA、上游目标SHA、分叉点、GitHub发布日期和完整dirty-path hash清单。
2. 用`git show`评估实际diff，而不只看commit标题。逐项分类：
   新增且有收益、已包含、被本地能力替代、与目标无关、需要单独适配。
3. 先核对消费者：Jira Server PAT/CA与provider绑定、模型SDK精确版本、
   报告template/fragment、来源/分析/编辑三基线、版本CAS、数据Git和双语UI。
4. 获得隔离工作树授权后，在独立候选分支进行rebase演练。保留原主线和回退ref，
   只重放分叉点之后的本地提交；不在脏的主工作区试冲突解决。
5. 冲突按功能/模块的所有权处理，不能一律选ours/theirs。
   已发布artifact、凭据、模型请求、数据Git内容与历史证据不参与改写。
6. 验证随改动范围收敛：先直接单元/协议检查，再受影响消费者，再必要的浏览器切片。
   只有真正改变连续性或发布合同才扩大到工作周级验证。
7. 使用`git range-diff`核对重放前后本地改动、依赖组合、脚本入口及规格同步。
   rebase成功只证明Git完成重放，不代表功能、安装或运行资格通过。
8. 发布方式单独确认。已推送且多人共享的main优先保持可追溯历史；
   如果确需改写远端，必须明确授权、锁定原远端SHA并使用精确lease。
   普通同步授权不是随意force-push或丢弃并发提交的许可。

如果两次等价失败没有新信息，应停下检查冲突策略/边界或验证环境，
不要反复重跑全部测试，也不要延长原任务deadline来掩盖问题。

## 文档与交付

当前操作指南维护同步规则，OpenSpec保存每轮决策和证据，不复制另一份任务系统。
交付必须写清楚：实际同步了哪些commit、跳过哪些commit、为什么、
验证覆盖与未验证范围、当前HEAD、是否push、原有脏文件是否保持。
no-op也是有效结论，但不能写成“已经升级到新版本”。
