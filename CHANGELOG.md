# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.13] - 2026-10-03

### Added
- 审计确认硬闸（人主观）与封板增量（ADR-0004 🅰4）
- 审计外层监督改活性口径（平铺墙钟 → 认 k3dit 的 K3DIT_STALL_SEC）
- k3dit 交付包 v2 双读——内容哈希 SHA-1→SHA-256 随版本派生
- 断言真值写在表达式里时阻断提交
- 未关项**hunk 级**部分落地 + `landing` 策略归调用方（closed-only/partial/all）
- ① 超时/失败**抢救出报告**（`hall export --latest`）＋③ 运行摘要随产物留
- ④收尾——升级**计入封板判据**（`closure.audit.pending += 升级行数`，单源标记）
- ④乙——未关项**不再整包拒**：部分落地 + 升级写**验证**列 + 腿的闸报升级
- 工具墙钟预算做成**声明面旋钮**（`k3dit_timeout`）＋手动入口 `--timeout`；full 缺省放宽到 2h
- 落地时**机械对账**报告行 ↔ 实际落了什么（`--exclude` 的行改标 `待修`）
- 报告落地时写明落地方式与排除项（三路合并/未落的文件）
- 落补丁补上**三路合并**（主干前进也能并修复）＋落库后校验＋显式漂移接受
- 消费侧**独立验收**（闸从"产出方自证"移到 k3dge 自己验）——报告完备性 + 本地闭环 + 哈希链
- 审计腿加 `k3dit_scope` 旋钮（送审面可控）——手动面与声明面同参数
- 工具旋钮走声明面（audit-only / pins）＋纯审计＝证据不闭环＋入口唯一
- 历史仓名提示（advisory）—— 提交信息里写 `k3ge` 非引述上下文时提示
- k3dit 的 MCP 服务端面退役 —— 审计腿翻 bundle，对等接入只剩 cli 信封
- k3dit 交付包消费侧接线（第三种审计腿 mode="bundle" + cli 传输占位）
- amend 形态进 schema 引擎（平时就红）+ 三规则确定性自动修复
- ADR amend/footnote 形态闸 adr_amend_format（新节点，进 seal 预审）
- 三个横展小闸 —— 状态表 priority 数字 / 抽取器插件新鲜度 / docs.toml 键落点
- seal 相位 3 自动刷纯投影 + k3dge where 索引自愈
- 架构文档 seal 覆盖两件 + 域表对账闸 ARCH_TABLE_DRIFT
- 生成物新鲜度闸 + README layout 并入 sync + 删 changelog 死簇 + 架构 seal 收口

### Changed
- ADR-0004 🅰4 审计确认硬闸（人主观）与封板增量
- M11 审计报告落盘（消费被拒 VERIFY_FAILED）
- 入账外部 OCR 全量再扫描报告（ocr2- 817 条；悬空示例号按先例改非匹配写法并加口径注）
- M11 align 机械产物（refused 轮 phase-1 落盘，重跑封板前入账清树）
- M11 审计报告落盘（消费被拒 BUNDLE_VERSION_UNSUPPORTED）
- 两份扫描报告最终闭合——tests-scan 部分修清零（已修349），ocr-scan 修一行行首双竖线错列
- 测试扫描报告收口——状态列待修清零（已修343/部分修6/有意留1）+ 6 个 incident
- 测试扫描报告加「续作口径」（读表索引／已吃掉的机械簇／下一刀形状）
- 回填 t-215（测试扫描待修 263→262）
- 25 行 mkdtemp 站点逐行改判（15 已修／6 部分修／4 复原待修）
- 回填 18 行「死导入/重复局部导入」闭合（测试扫描待修 301→283）
- 死导入/局部重复导入的 AST 不变量（并入 test_test_file_hygiene）
- 补清三处残留（函数内死导入 json、_P 别名局部导入、_same_commit 带 noqa 的死导入）
- 清掉死导入与函数内重复导入（116 行）
- 报告表形不变量 + 四份报告并格修好（竖线破表）
- 再修 t-013 错列（回填时把竖线写进处置列又偏了一格）
- 修一处回填错列（描述含裸竖线的行，左数索引带偏）；统计改右锚定
- 隐式编码读写全部收口（75/75），反向机检转零容忍
- 刷新投影（新票入 docs-index）
- 编码票计数收紧（本轮收掉 4 处，非 6）
- 更正编码收口票的事实：生产侧同形 23 处（非 0），且优先级更高
- 开票登记测试面显式编码收口（实测 271 处 / 生产侧 0）
- 回填 t-071/285/303/324
- 回填中批缺陷/安全面 5 条（11/11 全闭）
- 回填 t-103/139/242/243/326/331
- 自查——新测落在 __main__ 守卫之后，按 hygiene 不变量移到末尾
- t-339 归并到 t-118（补扫副本早于修复的重复），前言记两批时序
- 报告前言计数按实际表体重算（349 条）
- 并入补扫两文件的 8 条（t-339..），前言记分批出件原因
- 测试扫描高批第四组 5 行回填（含 t-254 投喂形状判定），验证列改指 3a938fe
- 回填测试扫描高批第三组 8 条
- 回填测试扫描高批第二组 11 条
- 回填测试扫描高批第一组 8 条；更正 ocr-420（判错过，现真修）
- 报告前言记透镜质量信号（4 条引用了不存在的 ADR 号）
- OCR 单元测试扫描落表（338 条：高32/中168/低138）
- 09-29 设计族 7 条闭合（4 张 M12 票 + 1 条归席判断），三份报告待修归零
- 回填 09-29 低批 13 已修（含复核即闭）+ 15 有意留
- code-7 已修回填；ocr-443 记 seal 链已强制、通用执行器强制仍留
- code-12 归档 memo 指针判有意留（活面已标注研究用）
- 回填 09-29 治理文档族 5 已修 + 1 有意留
- 回填 TS 生成件 5 已修 + 3 有意留（两份 k3dit 报告）
- 回填 09-28 报告 17 已修（含复核即闭）+ 6 有意留
- 回填 OCR 低批末段 22 已修 + 1 有意留
- 回填 OCR 低批 prompt/pure/seal 等 12 已修
- 回填 OCR 低批 nextstep/nodes/pipeline 11 已修 + 1 有意留
- 回填 OCR 低批 manifest/markers/mcp/milestone/models/nextstep 12 已修
- 回填 OCR 低批 doc_gate/gates/extractor 11 已修 + 1 有意留
- 回填 OCR 低批 audit/changelog/diff/doc_catalog 13 已修 + 1 有意留
- 回填 OCR 低批 status/adr/attest/audit 13 已修 + 1 有意留
- 回填 OCR 低批首段 14 已修
- 回填 OCR 中批末段 14 已修 + 1 有意留
- 回填 OCR 中批 gate/generate-docs 三轨 13 已修
- 回填 OCR 中批 task/version/worktree/sync/schema/hooks 14 已修
- 回填 OCR 中批 search/spec/state/dag/index 14 已修 + LEFTOVERS 记 re 回溯残留
- LEFTOVERS 记 ocr-316 有意留（增量化需实测消费者）
- 回填 OCR 中批 report_table/archive/seal/seal_flow/search 13 已修 + 1 有意留
- 回填 OCR 中批 prompt/protocol/pure_* 14 已修
- 回填 OCR 中批 nextstep/nodes/pipeline/process_audit 13 已修 + 1 有意留
- 回填 OCR 中批 mcp_json/milestone/nextstep 13 已修 + 1 有意留
- 回填 OCR 中批 gates/generated_docs/manifest/markers 14 条已修
- 回填 OCR 中批 doc_fix/doc_gate/evaluator/events 等 14 条已修
- 回填 OCR 中批 3 已修 + ocr-230 有意留
- 回填 OCR 中批 audit_verify/changelog/contract/diff 10 条已修
- 回填 OCR 中批 audit_* 14 条已修
- 回填 OCR 中批 adr_gate/align/attest/audit_bundle 12 条已修
- 回填 OCR 中批 mcp/cli/adr_gate 11 已修 + 1 有意留
- 回填 OCR 中批 init/pre-commit/version 8 已修 + 4 有意留
- 回填 OCR 中批 gate/generate-docs 9 已修 + 3 有意留
- 回填 OCR 中批 gate 三轨 11 已修 + 1 有意留
- 回填 OCR 中批 adr_gate 2 条已修
- 回填 OCR 中批 build-pyz/commit-msg 6 条已修
- 回填 OCR 高批 assets/scaffold 8 条已修
- 回填 OCR 高批 worktree/generator/commit-msg 5 已修 + 5 有意留
- 回填 OCR 高批 search/state_machine/task_* 4 已修 + 6 有意留
- 回填 OCR 高批 pure_refs/... 6 已修 + 4 有意留
- 回填 OCR 高批 nodes/.../prompt 10 条已修
- 回填 OCR 高批 manifest/markers/models/milestone_pointer 6 已修 + 4 有意留
- 回填 OCR 高批 events/evaluator/doc_gate/extractor_gen 7 已修 + 2 有意留
- 回填 OCR 高批 contract/diff/doc_* 8 已修 + 2 有意留
- 回填 OCR 高批 audit_*/changelog/contract 10 条已修
- 回填 OCR 高批 audit_* 9 已修 + ocr-039 有意留
- 回填 OCR 高批 src/k3dge 10 条已修
- 回填 OCR 高批 scripts 16 条已修 + 09-28 code-1 前提有误
- 回填 k3dit 报告 P1 处置（3 已修 / 7 有意留）
- 回填两份 review 的 13 条 P0 已修 + 修 OCR 报告悬空 ADR 号
- M11 续跑审计报告落盘 + 抬 k3dit_timeout 6h + 判读腿并发 memo
- M11 审计报告落盘（消费被拒 DIRTY_TREE）
- M11 审计报告落盘（消费被拒 VERIFY_FAILED）
- 补 TC-ENG-33/TC-TPL-09 引用 pre-commit 接线与 ADR 便携性测试（消 ORPHAN_TEST）
- M11 审计报告落盘（消费被拒 INPUT_MISMATCH）
- M11 审计报告落盘（消费被拒 VERIFY_FAILED）
- M11 首轮包不可落的教训（审计后改同文件 ⇒ 包过期；重跑非默认动作）+ 释放被停轮留下的在办单
- M11 审计报告落盘（手动入口 包 72e0b6b139a8）
- 更正误登记——评审登记规则（索引/归档）是 k3dit 的仓规，不是 k3dge 的流程问题
- A 路达成——审计修复经三路合并进主干（11 文件、一次提交 5c2c8cc）与为此补的四件事
- 记 FLOW-REVIEWS-01（落报告后消费仓评审格式必红；口径归消费方，k3ge 不另抄）
- 流程体检——"落报告→投影→提交"合并为唯一入口（三入口共用），并修过时模板注释
- 消费侧验收**复用既有单源**（列名/解析/未关态），不另立口径
- C 验收结账——治理链路已通（含提交相位），途中修 3 个真缺陷（入口悬空/投影-提交/钉行子串）
- 0025 §2.7 amend 🅰5 —— 判读窗旧债可见性实测更正（在途不共享＝防御口径，收益未测；窗树含在途钉）
- LINE-M10-01 —— 残留 worktree 已清（分支/救援 tag 保留）；线内 5 提交未进主干，待人工判
- 清掉棘轮残余（RATCHET-01）——audit_flow 裁到判据面，ratchet_open 状态退役
- 棘轮形状退休（形状只剩 bundle / oneshot）——声明 ratchet 显式拒绝
- k3dit 按**本地命令行工具**编排（与 git 同层）——报告落地、包出仓、撤对等声明
- 清掉旧名 k3ge 与跨仓 ADR 引用（今日新写处）
- 修掉一处旧称 k3ge → k3dge（pure_schema.py 注释）
- 对齐 audit —— downstream 手册跟上 hooks 下发；六条持久设计并入 ADR-0004/0018
- 悬空设计盘点 —— 删 3 个零调用 API + facts_of 接入生产自检
- 补全流程与状态变迁 + 状态集覆盖闸 ARCH_STATE_DOC_DRIFT
- gap-trap 吸收评估收口归档（①⑤ 已落，③④ 判不做）
- agent-dev-tools 吸收评估收口归档（8/8 行已落或已判）
- 钩子化盘点 memo 收口归档（A/D 已落地，B/C/E 判为不做）
- 更正 PRE-02 —— 14 处 DANGLING 分布已查明，非缺口（archive 13 + 报告引用历史编号 1）

### Fixed
- 收尾批7——报告回填已修/误报标注
- 收尾批6——本轮包33条之代码/配置/规则/ADR + 落报告
- 收尾批5——doc-11 覆盖重叠记载 + value-3 rule04 分节
- 收尾批4——文档类发现（doc-6/7/8/9/10/13/14/15, value-2/5）
- 收尾批3——TS extractor 语义切体（code-1/2/4/6/10）
- 收尾批2——TS extractor 未识别 node/parse-error 可见降级
- 收尾批1——配置/README/ADR/encyclopedia/spec-AUTHORING/rules
- adr_gate aux 判定大小写不敏感（挡封板回归）
- OCR 低危全收（子代理 4 批，251 行）
- OCR 中危 G2 收官批（子代理，88 行）
- OCR 中危 F/G1 两批（子代理，129 行）
- OCR 中危 B2/E 两批（子代理，105 行）
- OCR 中危 ACD/B1 两批（子代理，114 行）
- OCR 高危收官（测试空转批 + 剩余引擎/scripts）
- OCR 高危第十三批（scripts/ps1 完整性）
- OCR 高危第十二批（引擎单点B/C）
- OCR 高危第十一批（引擎单点A）
- OCR 高危第十批（CLI/引擎单点）
- OCR 高危第九批（attest/commit-msg）
- OCR 高危第八批（scaffold 命名与路径）
- OCR 高危第七批（scripts 安全项）
- OCR 高危第六批（gate.ps1 完整性）
- OCR 高危第五批（version 三件）
- OCR 高危第四批（adr_gate 去重/来源 + task_write 三件）
- OCR 高危生产批（bundle/merge/verify/mcp fail-open）
- OCR 高危第二批（收据空洞全家桶 + Landed-by 同族）
- OCR 严重 7 条收口（6 修 1 有意留）
- 哈希链接受原始字节摘要——无尾换行文件不再被去钉语义层多出的 \n 误判
- 部分修尾巴清零（t-034/069/154/213/272/348）+ 修一个测试顺序依赖的真 bug
- OCR 测试扫描收口（报告待修清零）——生产收紧 15 处 + 守卫下沉机制
- t-215 自指断言换成可失败的内容断言
- 45 个裸 mkdtemp 站点全部注册清理句柄 + 防退化守卫
- 收口 36/75 处隐式编码读写 + 棘轮式防退化闸
- docstring 归位/残句注释/非 ASCII 夹具编码/显式 import（t-071/285/303/324）
- 清 OCR 测试扫描中批的缺陷/安全面（t-013/014/015/031/319）
- 编码/拷贝/纯度守卫（t-103/139/242/243/326/331）
- 外部扫描报告不得冒充里程碑审计报告（新增 kind=scan）
- 清 OCR 测试扫描高批第四组（t-274/281/305/311）+ 下发件自限定中心化
- 清 OCR 测试扫描高批第三组（t-010/011/012/095/214/218/219/255）
- 清 OCR 测试扫描高批第二组（t-002/029/127/140/206/247/265/289/292/300/318）
- 清 OCR 测试扫描高批第一组（t-024/042/048/112/118/143/154/170、t-420 半边）
- 审计条件清单改回 gitignored 投影，解封 DIRTY_TREE 死路
- 桩判定只认真桩；行内代码支持任意长度反引号串
- 路径坐标统一与 guides 入口层（k3dit 09-29 doc-1..doc-13、value-11）
- extractors README 与 memo AUTHORING 的路径/口径（k3dit 09-29 doc-1/doc-2/doc-13）
- 幂等重入不再二次提版（k3dit 09-28 code-7；补 ocr-443 的执行半边）
- 关恒真证据 + 配置副本（k3dit 09-29 code-21/15/18/19/20、value-1）
- 生成件的路径面与解码形状（code-7/code-3/code-8/value-3/09-29、code-9/09-28）
- 清 k3dit 09-28 复核类与文档面（code-3/4/6/11、doc-1/2/4/5/6/7/8/9/10/11/14）
- 清 OCR 低批 state/dag/task_*/version/sync/scaffold/三轨（ocr-463..485）
- 清 OCR 低批 prompt/pure_*/report_table/review_archive/seal*（ocr-451..462）
- 清 OCR 低批 nextstep/nodes/pipeline_*（ocr-439..450）
- 清 OCR 低批 manifest/markers/mcp_json/milestone_*/models/nextstep（ocr-427..438）
- schema 文件损坏走 _add 档位面并按 type 报一次（ocr-419）
- 清 OCR 低批 doc_gate/doc_fix/extractor_gen/gates/generated_docs（ocr-415..426）
- 清 OCR 低批 audit_*/changelog/diff/doc_catalog（ocr-401..414）
- 清 OCR 低批 status/adr_gate/attest/audit_*（ocr-387..400）
- 清 OCR 低批首段 三轨脚本与 CLI 出口（ocr-373..386）
- 清 OCR 中批 init/wrapper/pre-commit/scaffold（ocr-358..372）
- 清 OCR 中批 gate/generate-docs 三轨（ocr-345..357）
- 清 OCR 中批 task_index/task_write/version/worktree/sync/schema/hooks（ocr-331..344）
- 清 OCR 中批 search/spec_schema/state_machine/task_dag/task_index（ocr-317..330）
- 清 OCR 中批 report_table/review_archive/seal/seal_flow/search（ocr-303..316）
- 清 OCR 中批 prompt/protocol/pure_refs/pure_schema（ocr-289..302）
- 清 OCR 中批 nextstep/nodes/pipeline_*（ocr-275..287）
- 清 OCR 中批 mcp_json/milestone_*/models/nextstep（ocr-261..274）
- 清 OCR 中批 gates/generated_docs/manifest/markers（ocr-247..260）
- 清 OCR 中批 doc_fix/doc_gate/evaluator/events/extractor_gen/gate_facts（ocr-233..246）
- 清 OCR 中批 contract/doc_catalog/doc_fix（ocr-226/231/232）
- 清 OCR 中批 audit_verify/changelog/contract/diff（ocr-219..229）
- 清 OCR 中批 audit_bundle/checklist/flow/merge/trigger/verify（ocr-205..218）
- 清 OCR 中批 adr_gate/align/attest/audit_bundle（ocr-192..204）
- 清 OCR 中批 mcp/cli/adr_gate 边界（ocr-180..190）
- 清 OCR 中批 init/pre-commit/version/CLI（ocr-167..178）
- 清 OCR 中批 gate.sh + generate-docs 双轨（ocr-155..165）
- 统一 gate.{sh,py,ps1} 源政策闸（ocr-144..147/148..154）
- 清 OCR 中批 adr_gate 两处 fail-open（ocr-191/194）
- 清 OCR 中批 build-pyz/commit-msg（ocr-137..142）
- 清 OCR 高批 assets 镜像/scaffold（ocr-129/132/134/135/136）
- 清 OCR 高批 worktree/generator/commit-msg（ocr-119/123/125）
- 清 OCR 高批 search/state_machine/task_index/task_write（ocr-110..114）
- 清 OCR 高批 pure_refs/pure_schema/report_table（ocr-100..105）
- 清 OCR 高批 nodes/pairs/pipeline_runner/schema/process_audit/prompt（ocr-089..098）
- 清 OCR 高批 manifest/markers/models/milestone_pointer（ocr-080..088）
- 清 OCR 高批 events/evaluator/doc_gate/extractor_gen/gate_facts（ocr-069..077）
- 清 OCR 高批 contract/diff/doc_gate/doc_fix/doc_catalog（ocr-059..068）
- ocr-052 audit_trigger 变更文件解析（-z + untracked-files=all + rename 取新路径）
- 清 OCR 高批 audit_* / changelog / contract（ocr-049..058）
- 清 OCR 高批 audit_bundle/audit_flow/checklist（ocr-040..048）
- 清 OCR 高批 src/k3dge（ocr-029..038）
- 补 ocr-017/024（ps1 README 归 sync；init.sh pip 选项注入）
- 清 OCR 高批 scripts（ocr-013..028）+ 镜像同步
- 清 k3dit 报告生成器 P1（code-1/2/6）并重生成 TS 插件
- 清 OCR 报告 P0 续批（report_table / MCP 出口 + 测试）
- 清 OCR 报告 P0 批次（7 处 + 测试）
- 清 12 条 OCR 审计遗留（缺 import/恒真判断/契约漂移/测试假阳）
- M11 审计轮逐条处置 + INPUT_MISMATCH 集成修复
- 按 M11 报告**人工重做** 15 条（落不了包就以报告为规格修）
- `git merge-file` 的返回码是**冲突个数**（rc=2＝两处冲突），不是错误码
- 落地守卫收紧（**验包+落补丁都成功**才落报告）＋超时提示可操作
- 工具状态不得落到外部被审仓（否则脏被审树 ⇒ 消费被自家 DIRTY_TREE 拒）
- 落地提交的收集面扩到整个 docs/（契约哈希在 docs/specs/，漏在提交外 ⇒ 钩子拦）
- 回滚要连投影一起退（声明的校验可能刷了投影）；消费仓声明里加 sync/index
- 清理上一编辑留下的旧校验块（它把新块变成死代码 ⇒ 校验又跑在临时 worktree 里）
- 落库后校验在工作区跑（venv/钩子在那）+ 不过就回滚；无内容可提交视为 no-op
- 合并兜底要接在**试跑失败**之后（此前 dry-run 一失败就返回，合并永远走不到）；结构性失败不退合并
- 落报告的提交信息别再前置 M（真跑把 M0 写成 MM0）
- 落报告时重生**全部**相关投影（且只用 engine 自有写入器，不越域 import sync）
- 手动入口的里程碑 id 不许拿包路径顶（真跑踩到）；落地失败退非零
- 拒绝路径**也要留下审计报告**（跑完没留证据＝这一轮白跑）
- 落树后**先重生投影再提交**，且提交失败**带 git 报错**（C 验收真跑抓到）
- `milestone audit` 入口**悬空**（棘轮退休删了调用、只剩 print(msg)）——真跑当场崩
- `k3ge` 按**错写**处理（不是历史名）——裸写即提示，只留反引号豁免
- 检讨补丁——新增可机检规则必须配齐三件（码/消费者/引导），并反向机检兜住
- hooks 与治理件随 init 下发（D1/D2）+ 到达环机检
- k3dge commit 回显 hook 输出（git 把 hook stdout 接到 stderr）
- k3dge commit 不再跳过 live hook（PRE-01 收口）
- 引用闸漏检的两个实例收口；记 PRE-02（存量悬空 16 处）
- SYNC-01 文案改陈述事实；task 状态词表单源化；落点闸 docstring 错名
- 边界 tag 与封版提交同一进程身份
- 三道闸并行且进程提交必须 attestation
- 堵住 M10 真跑的封板死锁与收摊时序

## [0.1.12] - 2026-09-20

### Added
- Event Log：`.k3dge/events.jsonl` 操作事实日志

- 统一 [NEXT] 通道：stdout + sidecar 双投递
- 提取器生成器：`.agent/extractors.toml` + `k3dge extractor sync`
- 多处理点交付：sidecar 单槽 → 列表 + STATE_OPTIONS priority（[NEXT] 复数处理点）
- doc 策略五点落地：格式硬闸 / 新建重复覆盖确认（并入优先）/ seal 轮规约化（外部优先，降级 k3dge）/ 用现成 checks 编排
- 封板边界与标识：`tag <M> = B`、封版提交 trailer（四键）、版号在审计正常返回后前进
- 里程碑重挂：`milestone reassign <from> <to>` + 归属闸 + 修子串一致性检查
### Changed
- 归档 Rust memo（ADR-0001 §2.9 已否决重写）；gap-trap proven-red 进审计协议 Pass 4；可检规则配闸进 `AGENTS.md` §12
- 删除 `engine.milestone` 兼容门面；CLI/测试直连叶子模块
- engine 内部不再经 `milestone` 门面 import；闸核禁依赖生命周期；`.mcp.json` 读取归 `engine/mcp_json`
- 清活协议面：去掉 k3lity 点名与 4-peers 枚举，改按 pipeline.toml 角色路由

- engine 解耦：门面不再当总线 + 闸核禁依赖生命周期 + mcp.json 单读取器
- 删除 engine.milestone 兼容门面，调用方直连叶子
- 归档 Rust memo；gap-trap ① 进审计协议、⑤ 进 §12 触发
- 复杂度债续（非 milestone 文件）：CC≥11 函数逐个拆
- P2: 7 处时间戳加时区偏移
- 重构：提取 MCP peer 管理出 cli/main.py
- 流程精简：审计腿模式显式化 + 修 doc-audit 空壳票
- 术语撞名：审计腿 mode "scaffold" → "oneshot"
- 路线残留清理：frontmatter 三头 + doc_catalog 死代码 + parse_doc_schema 去重
- 抽取零依赖 schema 校验层：`scripts/lib/schema_check.py`
- 术语清理：deferred 值级碰撞 + 两处重复常量
- ADR 归档移出封板（seal → sync）+ 删冗余 gates.toml
- 落 ADR：投影三维契约（目标 × 语法 × 范围）
- 判定到动作的结构化派发：gate_id 到 action（替掉散文子串匹配）
- 判定点单源化：prompt 文案源出 STATE_OPTIONS
- 编排骨架收敛·第一刀：闸红文案单源 + 阻断档位统一（Violation 只产 code+事实，文案/severity/options 归声明）
- ADR 编号截断：废物理删除、退役单一面 obsolete/、13 个永久退役号入表、分配=max+1、复用可机检
- ADR-0026 追加：D 线不变量（k3dge 不编排自主↔自主）+ 骨架声明的下游可配边界
- ADR 修正案：doc 规约化策略重划（C1-C5：0022 §2.2 时机/产物、0005 §2.7 同形同路、耐久改闸、先并入后新建配闸）
- ADR 合并退役：reconcile 不覆盖合并路径 + obsolete/ 去向字段无闸（merged-into 无人写无人验）
- 编排骨架收敛·节点表：pipeline.toml [checks.*] 单一声明面 + 五属性 + ctx + 单执行器（下游可配）
- incidents frontmatter id 双写收成单一源（文件名）
- 闸红声明面收尾：pure_* 检查器产结构化事实（3-tuple），Violation.message 降为兜底
- 封版三相位重排：预审（align+形式闸）→ 审计 → 审核后自动；`full_matrix` 移出封板动作、删 `satisfies`
- 报告降级为可选产物：`audit_closed`/`evidence_chain` 不再卡门、`audit-submit` 只补证据、运行态明标投影
### Fixed
- seal/align 任务扫描不含 archive/<M>/：提前归档的 done 里程碑任务致封板被拒（No tasks found）

- closure 收摊模板陈旧：写死「审计双腿闭环」+ 版本记 bump 前值（应与合并审计模块单份报告/终版一致）
- audit job 19d4564724ca: src,docs
- doc-audit: 文档作者合规审计（adr, guides, memo 等 4 处）
- 业务逻辑闸：task 元数据 frontmatter ↔ body 分歧检测
- 补测试：4 个零覆盖/浅覆盖的关键 engine 模块
- 引用便携：k3dge 的 ADR 引用在下游仓指错靶
- doc-audit 改动集只看未提交：先提交即集体失明（并回单一源 diff.get_changed_files）
- pipelines.on_seal_enter/on_pre_seal 无执行者：AGENTS.md §12 声称的 seal hook 机制不存在（接通或废声明，只留一套声明面）
- doc-audit: 文档作者合规审计（adr, architecture, guides 等 11 处）
- 保证审计不可空转：`run_audit_flow` 必须看 `ok/skipped`，`audit-result` 闭集落进封版提交 trailer

## [0.1.11] - 2026-09-13

### Fixed
- audit job cc4125a36936: src,docs

- audit job 137ed128e134: src,docs

## [0.1.10] - 2026-09-12

### Changed
- k3dge 侧文档/配置对齐合并审计模块（单份 12 列报告、无独立 quality fallback）

### Added
- G1: 审计模块合并 + 接口冻结（一本账）

- G2: Hall 内核常驻进程（人肉窗先行）
- G3: W1 席目录墙 + 签名钥验签（先 opencode/pi 两宿主）
- G3b: CLI root 白名单能力实测（W1 前置探测）
- G4: 窗版工单 + 工具事实注入 + 复核声明模型
- G5: W2 轮间清场 + W6 看门狗注入
- G6: 割接（seal hook/消费侧/k3lity 归档）
- G7: Hall 测试骨架（W1/W2/W6/账本复算）
- G8: 进程侧观测（统计席位+逃逸率+观测行）
- 修席接受改由快照 diff 推断（禁二值空翻已修）
- 空转熔断机制化（W6 活性墙的最小实现）
### Fixed
- doc-audit: 文档作者合规审计（architecture 等 3 处）

- 核 milestone 棘轮对 collect=open(待修>0) 是否误判 closed
- 审计 scope=src 时模板 pairs 不可同步致 verify TEMPLATE_DRIFT 假红
- 判读席禁止重提已 leftover

## [0.1.9] - 2026-09-05

### Added
- G3 换源：`roles.audit.mode="ratchet"` 幂等步进器（建单/探单/collect/写回重试一体；旧一次性链降为缺省形，quality 腿不变
- 首案真跑闭环（job ae911e744eff）：席 10 findings＝7 fixed＋3 有意留；主干带回 F-1/F-2/F-5/F-6/A-2/A-3/F-3 修复；vanished×角色门互锁与进程提交绕闸两处活体缺陷当场修
- P0 present 推送接线：`audit_flow.push_present`（submit 首程底＋`audit advance` 随程推），pipeline `audit.present`；k3dit 缺口回填见其 gap 单
- ratchet v3 exchange implementation ledger（施工账本体）
- ratchet v3 施工十单封账凭条
- 真跑前置：席位工单棘轮化 + ratchet_open 路由
- 席位工单棘轮化（G1）＋ `[NEXT] ratchet_open` 路由：编排认识在办工单（G2）
- ratchet v3 施工账十单全绿（ADR-0025 落地）：bundle 单文件交换原子＋身份/位置分家（②④）；分支工作现场 ensure/advance CAS/merge_back P1＋seal prune 钩子（③⑤⑦）；k3dit 句柄透传零代码落盘、角色门（fixed 仅审计席）、audit-report 机械渲染＋署名结案两步（①⑧⑨）；`k3dge audit` 四动词与 `bundle create`（⑩）；peer_contract v0.6 与 memo 化石条目（⑥）
- task create duplicate check via cache role

- k3dge 出向 MCP 客户端与 endpoint 唯一事实源
### Fixed
- 首夜案卷互踩事故：collect 落盘命名按 role；案卷防跨类覆盖闸；签署件自机构账本复原（INC-20260904-AUD-01）
- k3dge status 抛 NameError 致 [NEXT] 永不输出

- task list 把 docs/tasks/AUTHORING.md 当幽灵任务
- k3che 检索索引把 docs/*/AUTHORING.md 当语料
- audit job ae911e744eff: src
- audit job 0300799a8a4a: src
- k3dge 自身 MCP server 在 mcp 2.x 下无法启动（resource 严格校验）
- doc-audit: 文档作者合规审计（本轮 docs 改动 26 处）
### Changed
- `k3dge milestone seal` archives this-milestone reviews to `docs/reviews/archive/<id>/` and rewrites leftover hrefs in `docs/reviews/LEFTOVERS.md`.
- Move the intentional-leftovers table from `docs/reviews/README.md` to `docs/reviews/LEFTOVERS.md`.
- Align ADRs 0001–0006 / 0008 / 0010 with current AGENTS, 0018 catalog, and pipeline `[peers]` schema.
- `k3dge check` rejects legacy `pipeline.toml` `[harnesses]` / `[hooks]` keys (`PIPELINE_SCHEMA_INVALID`).
- Move per-type structure gates from README comment blocks to `docs/<type>/.schema.json`.
- Move per-type soft rules from README `## Authoring` to `docs/<type>/AUTHORING.md`.

- ADR-0006 就地修订为入向/出向双向契约 + AUTHORING 例外条款

## [0.1.8] - 2026-08-27

### Fixed
- fix AGENTS route 05 branches misroute

- fix architecture guide dangling overview links
- fix audit rule deprecated protocol path
- fix mcp-bridge deprecated protocol pointer
- fix template sync missing protocols asset

## [0.1.7] - 2026-08-27

### Added
- k3che 接 GateReport 入 BranchThrottler 闭环
- k3lity 为 INC-20260826-REG 补 B-T-D 复现用例

## [0.1.6] - 2026-08-26

### Fixed
- `mcp.json` 损坏/非 dict 时静默覆盖丢 peer（`src/k3dge/templates/scaffold.py:115`）
- `tomllib` py3.10 缺失时 `mcp sync` 假成功（`src/k3dge/cli/main.py:255`）
- `create_task` 未校验 `milestone` 致 `../` 逃逸（`src/k3dge/engine/milestone.py:194`）

### Changed
- `overview` 补 `cli→templates` 边（`docs/architecture/overview.md:38`）
- `pipeline` 的 `k3dit` 降级 `python -m` 改 `k3dit` 控制台脚本

### Security
- 隔离外部 `mcp.json` 损坏覆盖风险

## [0.1.5] - 2026-08-26

### Added
- `k3dge task` 支持 `M1` 编码与 `ls` 快筛（`AGENTS.md:56`）
- `k3dge mcp sync` 幂等合并 `harnesses`（`src/k3dge/cli/main.py:244`）

### Changed
- `HUMAN_CHECKPOINT` 四处双编码收敛为单一事实源（`engine/milestone.py:343`）

### Fixed
- `seal` 的 `CHANGELOG` 双轨漂移（`cli` 列任务清单、`mcp` 仅一句）

## [0.1.4] - 2026-08-26

### Added
- `09-absorption` 规则落地（`docs/adr/0020`）
- `pipeline.toml` 对等 `harnesses` 声明

### Changed
- `AGENTS.md` 微内核 51 行
- `mcp.json` 幂等合并

## [0.1.3] - 2026-08-26

### Added
- `Mastra Observational Memory` 上层 `harness` 落地

### Fixed
- 空 `ignore` 崩闸、`tomllib` 假成功、`NUL` 未拒、`rglob` 符号链接外泄等 7 项 `P1`

## [0.1.2] - 2026-08-25

### Fixed
- `P1-01..08` 空 `ignore`/`UTF-8`/`Windows`/`NUL`/`rglob`/`changelog`/`SemVer` 等 `7` 项 `P1` 修复

## [0.1.1] - 2026-08-24

### Added
- `M0` 19 项：本地安装、契约/`MCP`/封板闸、`.agent` 协议等

## [0.1.0] - 2026-08-23

### Added
- Spec-gate harness 基线：`engine`/`cli`/`sync`/`templates` 四域契约门禁
- `k3dge check` / `sync` / `milestone` 三闸机与 `mcp` 零漂移桥接
