# todo 要求合理性研究（2026-11-10）

八項提案大致有道理，但不宜照原優先序整包實作。最值得先做的是統一任務契約、補實際執行環境的 readiness，以及在任何清理前保全作品；研究任務的完成文案則可立即修正。verification resume、持久 hook 和 capability manifest 都應收斂範圍。07 的「混合 adapter 尚在規劃」已落後目前 SlugBox 原始碼；05 也沒有證據顯示分數計算錯誤。

## 範圍與判準

本次檢視 NightShift `todo/00` 至 `todo/08`，以目前原始碼、既有測試和相鄰 runner 的事故紀錄區分「歷史上發生過」與「目前仍有缺口」。NightShift 研究基準為 `eccbab372860600b81c9bfe3487c681283711b3e`。這是需求研究，不是實作派工；沒有修改 runtime、重排佇列或操作現有 Worker。專案將通用 runtime、專案 adapter 和 Planner 分工，需求也應保留此界線。[專案定位](../../README.md#components)、[待辦範圍](../../todo/README.md#scope-boundaries)。

SlugBox 的研究基準為 HEAD `33f0f08`。讀取期間曾看到 `scripts/automation/regression.py` 和 `test_regression.py` 有未提交修改，後續重讀時工作樹已乾淨；本次沒有操作或還原它們，也不推定變動原因。最後判斷以 `33f0f08` 已提交版本為準，排除短暫出現的 `as_completed` 修改。Python 混合支援已於 `120cd80` 提交。相鄰 runner notes 是當時的事故紀錄，不能取代現行程式證據；它們也可能在之後被歸檔。

| 項目 | 現況與合理性 | 建議順序／範圍 |
| --- | --- | --- |
| 00 已修復缺陷 | 有對應 commit 與 regression coverage | 保持 resolved，維持既有邊界 |
| 01 契約 preflight | prompt／Planner／gate 政策不一致，缺派工前組合檢查 | P0；先統一規則再驗證 |
| 02 保全與續驗 | 有 baseline／diff archive，沒有完整失敗作品復原 | 保全 P0；verify-only resume P1 |
| 03 環境 preflight | 已有 config／parser 檢查，缺實際 adapter sandbox 與路徑 probe | P0；沿用既有檢查 |
| 04 子程序診斷 | 已有 timeout／process group 清理與 heartbeat，細粒度 progress 不足 | P1；補觀測與產品 adapter 契約 |
| 05 capacity review | 計分符合既有公式，缺 attributable outcomes | P1；先分類與觀測，後調政策 |
| 06 durable hooks | 故意採用 session-only，目前行為符合文件 | P1；opt-in 持久化 |
| 07 framework capabilities | 核心嚴格驗收已存在，SlugBox 現已混合支援 | 與 01 合併小型 manifest／diagnostics |
| 08 bounded research | 研究 gate 已存在，任務成功條件過度綁定重現 | 文案／回報分類可先做 |

## 00：已修復項目

保留 resolved 合理，沒有理由僅因當時事故重新開案。`61f4ba1`、`08b5a70`、`eccbab3` 分別處理 watcher config precedence、explicit restart cleanup 與外部 research artifact lookup，待辦也明列曾有 unrelated Sentinel fixture failure，沒有宣稱當時 broader selection 全綠。[watcher regression coverage](../../test/test_watcher_config_precedence.py#L14)。02 若新增續驗，仍應保留現有 restart 的明確清理授權與 HEAD guard，並另外定義操作；不能順帶把 restart 改成隱式續作。[現行 cleanup 授權](../../scripts/worker_runtime.py#L2793)、[daemon 消費授權](../../scripts/lifecycle.py#L278)。

目前 watcher 先取 explicit config，未提供時才讀 activated config，再落回 installation config；對應測試涵蓋這三層。report lookup 的 regression test 則限制只能使用 selected runner reports 或 local reports，拒絕無關外部路徑及 symlink escape。[watcher 實作](../../scripts/watch_worker.sh#L16)、[config precedence 測試](../../test/test_watcher_config_precedence.py#L14)、[report 邊界測試](../../test/test_runner_report_lookup.py#L11)。

## 01：派工前檢查任務契約

**判斷：合理，P0；已有驗收檢查，但檢查時間與契約一致性有缺口。**

目前 Worker prompt 同時要求 `[CODE: FIX]` 不改測試，以及開發交付必須提供新增或有意義修改的測試；Planner 的標準 FIX 範例卻把 `src,test` 放進 TARGET。Hot gate 也確實拒絕只有原樣 baseline 案例的交付。這不是僅由事故推測的問題，文字契約本身已能對照出矛盾。[Worker 規則與交付](../../scripts/worker_runtime.py#L1854)、[Planner 範例](../../.agents/skills/nightshift/planner/SKILL.md#L40)、[實際 TDD 驗收](../../scripts/acceptance.py#L307)。runner 也留下 Worker 因 FIX 卻要求新測試而停止的紀錄。[事故紀錄](../../../NightShift_runner/slugbox/notes/chapter01-capture-ticket-type.md#L3)。

但不能據此宣稱「所有 FIX 在 runtime 都不可能過」：mechanical audit 的 test immutability 檢查只在沒有 hot config 的路徑執行，有 config 時會略過；這表示 prompt、Planner 與不同 gate 路徑沒有單一一致政策。[條件分支](../../scripts/worker_runtime.py#L1977)。目前 task claim 後才解析 TARGET、VERIFY 並進入執行，也未見這一階段組合檢查上述矛盾。[claim 與執行順序](../../scripts/lifecycle.py#L427)、[任務欄位解析](../../scripts/lifecycle.py#L474)。

建議收斂驗收為：

- 先決定 FIX 是否允許「新增／強化回歸測試但禁止削弱既有測試」，或另定既有測試修復與新測試階段；同步修正 Planner 範例、prompt、hot/mechanical gate。只加一個拒絕器會讓合法 bugfix 仍然無路可走。
- 在同一 queue lock 下先驗證、後 claim；invalid ticket 留在原位置，輸出欄位級錯誤與建議修改，不計模型失敗或扣分。
- 靜態檢查限於明確欄位，例如 task kind、write scope、test permission、證據來源、adapter 能力與 report root。自然語言「evidence-only 卻要求實作」應轉成明確欄位與 Planner review，不承諾通用語意矛盾檢測。
- 派工前只能驗證已知的能力與既有案例；尚未實作的新案例不能要求先被 discovery 找到。最終精確 ID／fingerprint 仍須在交付時驗收。探測 report 寫入能力與 discovery 時，也須避免污染產品樹。

## 02：保留失敗嘗試並可明確恢復驗證

**判斷：資料保全是 P0；精確 verification resume 合理，但宜分階段交付。現有 archive 並非完整可還原快照。**

runtime 已在執行前記錄 baseline HEAD、stash、untracked 名稱與 audit tree；失敗恢復會寫 binary diff、porcelain status 和 commits 清單後 reset/clean。因此「完全沒有保留」不正確。[baseline 擷取](../../scripts/worker_runtime.py#L2434)、[失敗 archive](../../scripts/worker_runtime.py#L2458)。但 `changes.diff` 不包含新增未追蹤檔案內容；接著 recovery 會刪除新增 untracked，未先複製其內容。archive 也沒有獨立重建失敗時 staged／unstaged 分界的資料，因此不足以承諾恢復「那一次精確嘗試」。[diff 與 status 擷取](../../scripts/worker_runtime.py#L2476)、[untracked 清理](../../scripts/worker_runtime.py#L2505)。現有 baseline-recovery 測試只斷言 untracked 的名稱在 status、專案變乾淨，並沒有斷言其內容可還原；另一個 legacy rollback 測試更明確斷言 archive 沒有 `untracked` 目錄。[baseline-recovery 測試](../../test/test_external_failure_archives.py#L29)、[legacy rollback 測試](../../test/test_worker_runtime.py#L2036)。

更關鍵的是，不能只在 explicit restart 前新增 snapshot：特定 hot failure 已會立即呼叫 recovery，先把作品還原掉。事故紀錄也明說 timeout 後已 rollback，後續任務必須重建。[自動 recovery 呼叫](../../scripts/lifecycle.py#L514)、[tuning 事故](../../../NightShift_runner/slugbox/notes/tuning01-timeout-recovery.md#L3)。現行 restart 本身是「清除失敗 pause，下一輪乾淨開始」，不是續驗；中斷的模型執行也會交回 Planner，不自動重跑。[restart](../../scripts/worker_runtime.py#L2793)、[中斷恢復路徑](../../scripts/lifecycle.py#L323)、[Planner 說明](../../.agents/skills/nightshift/planner/SKILL.md#L81)。

建議拆成兩個可獨立驗收的交付：

1. **先保全再清理**：所有 destructive recovery 入口，包含自動 failover／hot failure／explicit restart，先建立完整、有 checksum 的 attempt package；分別保存 HEAD、index、worktree、untracked（含 binary、刪檔、symlink、mode），以及 handoff、命令、選取案例、phase、logs 與相關 config。用 disposable worktree 還原並比較檔案與 index，成功後才允許清理；排除 secrets 的檔案要明列，不能仍宣稱完整恢復。
2. **獨立 verify-resume 操作**：只對明確 attempt ID 與相同 code/config fingerprint 開放，重跑原本必要 gates，由 runtime 重新判定 commit／accept／score。HEAD、檔案、case selection、adapter 或 acceptance config 改變就要求 Planner replan；不可偷改 handoff 或將前次 failure 變成 pass。對已 committed／accepted 的重播必須保持 idempotent。

「保留 live paused tree 直到人工選擇」可以是 policy，但必須明列哪些 auto-recovery 改成暫停，以及 failover 是否改在 disposable workspace 執行；它與現行自動 baseline recovery 有實質行為差異。snapshot 保留政策也應沿用既有 scratch review 的 active／pending／referenced evidence 保護條件，而不是另外做無限歷史備份。[既有 retention 邊界](../../scripts/scratch_review.py#L198)。

## 03：環境 readiness

**判斷：合理，P0；不是從零新增一套健康檢查。**

已有 config 版本、Git root、project/state mapping 驗證，安裝程序也真的啟動 parser smoke test；code-index 缺少環境時會提供 repair command。[project config](../../scripts/project_config.py#L19)、[parser setup](../../scripts/tools/setup.sh#L16)、[parser probe](../../scripts/tools/check_env.py#L6)、[repair diagnostic](../../scripts/worker_runtime.py#L1341)。缺口在模型執行前，對「實際註冊的 executable、有效 sandbox 設定、產品及 runner 路徑」做最低成本探測；只檢查 `command -v` 或另一個 CLI 能執行，不能證明 daemon 可用。本會話曾出現 shell 命令因 UID-map 權限拒絕而無法啟動，後來環境修復，這只證明 host readiness 需要探測，不證明產品失敗。

建議將這項定位為不消耗模型 turn 的 deterministic probe：實際 executable 執行 harmless command、讀取產品必要檔案、在 runner scratch 建立並移除自己建立的檔案、檢查 handoff/result destination。probe 必須重現實際 permission/profile 參數；CLI 語法依 installed `--help`，不要將此次 `codex sandbox -- ...` 寫成跨版本保證。快取鍵應包含 executable/config/permissions/path/tool 版本，前提變更時重查；失敗保留 exit/stderr 並按原因去重通知。這不是自動安裝特權套件或調低 AppArmor 的入口。[待辦要求與當時語法](../../todo/03-environment-preflight.md#L13)。

## 04：子程序監督與診斷

**判斷：合理的 P1，但主要缺口是可觀測性，並非沒有 timeout／cleanup。**

`run_verify` 已建立 process group，期限到後送 TERM、等待兩秒再 KILL，回收 direct child，並回報 timeout／elapsed／budget。adapter 也有 log streaming、heartbeat，daemon heartbeat 則表示執行器還活著，不代表某個 case 有進展。[timeout 實作](../../scripts/worker_runtime.py#L2031)、[adapter 觀測](../../scripts/worker_runtime.py#L839)、[daemon heartbeat](../../scripts/lifecycle.py#L172)。但 `run_verify` 以 `communicate` 等待終止才交回 output，因此 phase 中的 active case、child PID 與 live log 仍需 runner 契約補齊；timeout 後才看到輸出不利於定位。[output 擷取](../../scripts/worker_runtime.py#L2041)、[失敗輸出證據](../../scripts/acceptance.py#L235)。

SlugBox 已提交版本會輸出 START／log path，因此不能描述成完全沒有 live 診斷入口；但 parallel result 仍用 `list(pool.map(...))`，全部完成後才回傳，逐項完成時的 progress 仍有缺口。[START](../../../SlugBox/scripts/automation/regression.py#L295)、[ordered result 收集](../../../SlugBox/scripts/automation/regression.py#L321)。NightShift 應接收 generic phase/case/PID/log/deadline 事件，Godot 分片、fixture 和 `max_core` 留在產品 adapter。[待辦的 ownership 邊界](../../todo/04-subprocess-supervision.md#L17)。

驗收需覆蓋受控 stalled fixture 與真實 engine evidence，分別標示；允許時才做 debugger／thread sampling，ptrace 拒絕須記為限制。CPU 與 heartbeat 只能支持「觀察到忙碌或停止進展」及信心程度，不能自動推論 engine root cause。只終止 owned process；process-group cleanup 也不能承諾處理自行 `setsid` 脫離的任意 descendants。保留 outer deadline，不以 retry、跳過 case 或拉高 timeout 代替診斷。

## 05：以歸因與任務大小評估 capacity

**判斷：合理的 P1 觀測改進；沒有證據應重寫 score 算式。**

目前一般 reject 清除 success window，並不直接扣分；五次 accept 提升一分且上限五分，同 task 的第二、第三次 hard failure 才各扣一分，`no_fault` 排除在外，event ID 會去重。因此「7 accepts、9 rejects 仍顯示 5」與公式相容，不足以證明 defect。[實際算式](../../scripts/worker_runtime.py#L397)。部分研究失敗已有 neutral 分類，baseline regression 也有免 score 路徑，不能描述成完全沒有歸因。[failure scoring](../../scripts/lifecycle.py#L228)、[baseline 例外](../../scripts/lifecycle.py#L605)。

先建立 failure taxonomy，分開 product regression、Planner contract、host fault、unsupported evidence、operator interruption、superseded requirement 與 unknown，再展示 rolling outcomes、streak、task size、實際 actions、phase／wall time 和 confidence。對無法確認原因的失敗保留 unknown，不能為了 score 好看直接洗成 no-fault。score 是粗粒度、有上限的歷史指標，不是校準後成功率；後續八個較窄任務連過支持「值得繼續觀察粒度」，不能證明縮小任務是唯一原因。[原觀測與驗收方向](../../todo/05-outcome-aware-scoring.md#L9)。維持 runtime 擁有 score、event idempotency；先不自動增加 budget 或改公式。

## 06：跨 daemon 重啟保留 pending hooks

**判斷：合理的 P1 功能；不是現行實作偏離文件的 bug，應維持明確 opt-in。**

文件清楚定義 scheduler 為 in-memory，重啟會清除 one-shots、counters、pending runs 與 retry state；測試刻意驗證此行為。事故紀錄所說「重啟後要重新註冊」符合現行契約。[現行文件](../../scripts/acceptance.md#L95)、[重啟測試](../../test/test_acceptance_hooks.py#L75)、[runner 紀錄](../../../NightShift_runner/slugbox/notes/tuning01-timeout-recovery.md#L9)。若這些 hook 代表交付義務，持久化確有價值，但須修改契約與測試，不能稱為單純修復遺失狀態。

目前已有可沿用的穩定 run ID（trigger＋hook ID＋event hash）、session 內 event 去重，以及執行前的 accepted revision／clean tree 檢查；不必重造排程器。[run ID 與排程](../../scripts/acceptance_hooks.py#L58)、[event 去重](../../scripts/acceptance_hooks.py#L98)、[revision 檢查](../../scripts/acceptance_hooks.py#L151)。缺口是這些狀態都只存在記憶體，成功的 run 甚至直接刪除；持久化時需保留足夠的完成標記，才能防止 accepted-event replay 再次排程。[記憶體狀態](../../scripts/acceptance_hooks.py#L67)、[完成與 retry](../../scripts/acceptance_hooks.py#L131)。

建議最小驗收：保存選定 runner/project identity、hook 定義版本與 hash、trigger event、revision、pending/running/failed/passed 狀態及去重記錄；用 atomic persistence 定義每個 transition。crash 發生在外部命令成功但完成紀錄尚未落盤時，不能保證 exactly-once，因此 `running` 應恢復成需要判斷的 unknown/interrupted，由 idempotent command 或明確 retry policy 處理。跨 revision hook 繼續遵守現有 revision guard，不能為了「恢復」直接對新 HEAD 執行；list/status/cancel/retry 足以作第一版，不需擴成一般工作流程引擎。LAN server 生命週期仍由產品腳本負責。

## 07：framework evidence capabilities

**判斷：小型能力宣告合理；「mixed adapter 尚在規劃」須更新。**

核心已驗證 invocation nonce、唯一案例 ID、source mapping、semantic current/base fingerprint、safe path 與 reconciliation；不需要另建一個 framework 驗收平台。[invocation 驗證](../../scripts/acceptance.py#L245)、[TDD 驗證](../../scripts/acceptance.py#L307)。SlugBox 現在 `discover_python` 已取得真實 unittest ID/source/fingerprint，並將 Python 與 GUT cases 合併，與 todo 的歷史敘述不同。[Python discovery](../../../SlugBox/scripts/automation/regression.py#L92)、[合併 discovery](../../../SlugBox/scripts/automation/regression.py#L157)、[過時提案敘述](../../todo/07-framework-evidence-capabilities.md#L11)。

但支援 Python 不等於支援所有 Python 特性：目前拒絕 inherited／nested／generated test forms；adapter 也明示 `supports_case_selection: False`。manifest 必須能誠實宣告這些限制，不可以「Python supported」推導任意選取／baseline rerun 都可用。[Python 限制](../../../SlugBox/scripts/automation/regression.py#L98)、[selection capability](../../../SlugBox/scripts/automation/regression.py#L407)。

建議與 01 一起做最小 declarative capability：framework／ID namespace、source evidence、selection support 與 outcome forms，避免 preflight 透過完整 test execution 才知道能力。錯誤明確區分 unsupported framework、unknown ID、missing source、unchanged evidence、stale nonce。加 reusable contract fixtures 驗證 duplicate、skip/failure、source mismatch、invocation identity 即可；具體 discovery／execution 仍由專案 adapter 負責，不做假 GUT wrapper、不放寬 permanent evidence。

## 08：接受有界、未定論的研究

**判斷：合理，而且可先以派工／回報契約完成，不必先新增 terminal lifecycle state。**

現有研究 gate 已檢查 zero product edits、非空 report、Markdown heading、task metadata 與 optional VERIFY，所以不是欠缺研究任務驗收入口。[研究 audit](../../scripts/worker_runtime.py#L2170)。事故紀錄明確記載三次 bounded debugger-child trial 均通過、沒有重現 stall，卻因 scope 要求一定捕捉真實失敗而卡住；後續已將推測性 repair defer 到 backlog。[bounded conclusion](../../../NightShift_runner/slugbox/notes/stall-research-bounded-conclusion.md#L3)。這是驗收問題設定錯誤，未重現不等於研究沒做，也不等於缺陷已排除。

最小做法是既有 `outcome=complete` 加研究結論欄位（例如 positive／negative／inconclusive），派工前定義 attempt cap、total wall budget、per-trial deadline、命令／環境／artifacts、方法有效性、limitations 與下一個 decision。方法執行失敗、缺 log 或缺產物仍不可接受；有效方法下未重現可以研究完成，但 unresolved defect 繼續留 backlog。不能把 `complete` 轉述成「bug fixed」，也不再自動開無證據 repair 或無限 reproduction loop。

另有既有限制：source pointer audit 只抽前五個 pointer，且 source 不存在時略過；它不能證明研究論證正確。Planner 仍須審視 methods／limits／evidence relevance，而不是只看 gate PASS。[pointer audit 範圍](../../scripts/worker_runtime.py#L2210)。此限制應在研究報告驗收中說清楚，無須為 08 一次重寫全部引用驗證。

## 建議交付順序

1. 先修 08 的 bounded research ticket template，以及 01 的 FIX／TDD 規則矛盾；兩者都先讓合法任務有一致的完成路徑。
2. 做 01＋07 的最小契約 preflight，以及 03 actual executable／effective sandbox readiness；invalid contract／environment fault 不消耗模型、不改 queue/product/score。
3. 做 02 完整 attempt package 與 restoration check，涵蓋所有自動與明確清理入口。這是資料保全優先，不必等待完整 resume UI。
4. 再做 04 可觀測事件與 bounded diagnostics、02 explicit verify-resume、06 opt-in durable hooks。
5. 等 failure taxonomy 與 task metrics 穩定後做 05 capacity review，再決定是否調整 scoring／granularity 政策。

以上是設計建議，不是已驗證實作。02 會改變既有 recovery 行為，屆時須同步更新 acceptance 文件、Planner skill 與 glossary 的 clean-restart／recovery 定義；06 則須更新 session-only hook 文件與測試。本次只提出建議，沒有修改這些契約。[現行術語](../../GLOSSARY.md#L21)、[現行 recovery policy](../../.agents/skills/nightshift/planner/SKILL.md#L85)、[現行 hook 契約](../../scripts/acceptance.md#L95)。

## 驗證記錄

已在 disposable fixtures 執行：`python3 -m unittest discover -s test -p 'test_external_failure_archives.py' -v`（2 tests）、`test_worker_prompt_tdd_contract.py`（1 test）、`test_acceptance_hooks.py`（5 tests），共 8 tests 通過。這些測試證實現行契約，沒有測試尚未實作的 resume／durability 功能。初次以 `python3 -m unittest test.<module>` 呼叫遇到 import resolution 錯誤，改用專案建議的 discovery 形式後通過。沒有執行完整 regression 或 live model。

另以 unittest loader 載入 `test_parser_setup`、`test_phase_timeouts`、`test_hot_baseline_triage`、`test_hot_protocol`、`test_tdd_reconciliation`、`test_research_budget_parity`、`test_runner_report_lookup`、`test_watcher_config_precedence`、`test_worker_runtime.WorkerScoreTests`、`test_worker_runtime.MechanicalAuditContractTests`：45 tests run，44 pass、1 skip，26.933 秒，`OK (skipped=1)`。skip 是 source checkout 缺 root `install.sh` 的安裝測試，不能宣稱已驗證完整部署 readiness。

另在臨時 Git repo 執行 `capture_attempt_baseline → 新增 new_test.py 並修改 tracked file → recover_attempt_baseline`，確認 recovery 後新檔消失，archive 只有 `changes.diff`、`commits.txt`、`recovery.json`、`status.txt`；新檔名稱留在 status，但 payload 不在 archive。這證實 archive 缺內容，不代表所有 Git object 都必然無法救回；本研究沒有宣稱資料在 Git object database 中完全不存在。臨時 repo 自動清除，沒有操作現有產品／runner runtime。

## 後續實作與待辦清理

2026-11-10 已完成六張較窄的 script-only tickets：還原驗證封存、明確配置的環境 probe、POSIX live log、可選能力宣告、opt-in durable hooks、read-only capacity 摘要。原始 01/02/03/04/05/07 仍有超出這六張 ticket 的剩餘範圍；08 涉及研究派工規則尚未更動。已完成的 00 和 06 本機 todo 檔案已刪除，其餘只保留待辦；上文是實作前基準研究，程式行號以該基準為準。

需討論的 skills 政策為 FIX/TDD 一致性、有界研究成功與停止條件、明確 verification-resume；另外新 runtime 狀態與 capacity 資訊的 Planner 使用指引可以一併同步。詳見[實作操作說明](../../scripts/docs/RUNTIME_HARDENING.md)。
