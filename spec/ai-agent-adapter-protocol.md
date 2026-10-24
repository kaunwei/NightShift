# NightShift AI Agent Adapter Protocol

Status: ready-for-agent
Date: 2026-10-24

本規格整理已確認的設計，作為後續實作與驗收依據；目前不代表功能已實作。交付範圍為本地規格，不發布 issue。

## Problem Statement

NightShift 的 Worker runtime 同時承擔任務生命週期與 AI 工具細節，包括 agy、Codex 的參數、輸出解析、步數計算、額度判斷及收尾差異。新增執行方式時，必須修改核心分支、provider 白名單及設定驗證，無法只靠符合介面的實作接入。

現有 generic wrapper 已提供外部程式的基礎，但原生工具仍使用不同路徑。工具特有的 prompt、Git 分工與結果辨識，也使同一任務在不同 agent 上的契約不一致。跨 agent 共用能力分數，則無法表達不同模型需要不同任務顆粒。

專案維護者需要讓 AI 執行方式成為黑盒子：script 透過固定 callback 啟動、查詢、停止及收尾，無須知道工具名稱；新增實作只需提供 adapter 與註冊設定。

## Solution

將 AI 呼叫移出 Worker runtime，統一為外部程式的版本化 JSON 協定。script 掌握生命週期，adapter 負責工具細節；雙方透過 `get_config`、`start`、`status`、`closeout`、`cancel` 五個 callback 互動。

同一任務版本只有一份共用 worker prompt，agent 差異透過設定傳遞。每個註冊 agent 提供自己的能力初始值與執行限制。主任務遇到額度耗盡或不回應時，可依註冊順序切換；影響任務顆粒的中途變化由 watcher 通知 Planner 處理。

AI 提供 commit message，script 執行 commit。每個原始任務最多有一次 script 內部的 ghost 收尾補救；缺少 message 也是可補救情況。ghost 不切換 agent，不形成 Planner 可見的任務或獨立評分。

## User Stories

1. As a NightShift maintainer, I want AI invocation outside the Worker runtime, so that core task execution does not depend on tool-specific branches.
2. As an adapter author, I want a documented executable protocol, so that I can implement an agent using any suitable language or transport.
3. As an operator, I want to add an adapter and registration without editing core code, so that new execution methods are independently extensible.
4. As a script author, I want to discover configuration through callbacks, so that I do not encode provider names or model-specific defaults.
5. As an operator, I want multiple registrations of the same adapter with different models and limits, so that each execution profile can be tuned independently.
6. As a Worker, I want the same task prompt across agents, so that changing execution tools does not change the assignment.
7. As a script author, I want structured execution outcomes, so that I do not interpret human-readable tool logs.
8. As an operator, I want asynchronous execution handles, so that a long-running model call does not block lifecycle control.
9. As an operator, I want status queries that do not call a model, so that monitoring consumes no additional model tokens.
10. As an adapter author, I want to recommend a status-query interval, so that polling respects the execution method.
11. As an operator, I want callback responsiveness and execution deadlines enforced separately, so that a responsive status endpoint cannot hide an indefinitely running task.
12. As an adapter author, I want to define action-budget semantics and defaults, so that the protocol supports different tool capabilities.
13. As an operator, I want registration settings to override adapter defaults, so that I can tune a particular model without editing its adapter.
14. As an operator, I want quota exhaustion and nonresponse to advance to another registered agent, so that a single unavailable execution method does not stop all main work.
15. As an operator, I want quota exhaustion persisted while nonresponse only skips the agent for the current task, so that temporary failures do not permanently disable agents.
16. As an operator, I want each agent attempted at most once per main task, so that failover cannot loop indefinitely.
17. As a project owner, I want the previous execution stopped before failover, so that two agents cannot modify the same task workspace concurrently.
18. As a project owner, I want attempt changes archived and the attempt baseline restored, so that failed work does not contaminate the next attempt or remove preexisting work.
19. As a Planner, I want independent capability scores per registered agent, so that task granularity reflects the selected execution profile.
20. As an operator, I want agy and Codex adapters to provide the highest initial score, so that their defaults preserve the agreed initial autonomy.
21. As a Planner, I want normal scoring and planning handled at batch boundaries, so that completed work is reviewed coherently.
22. As a Planner, I want watcher notification when execution conditions change mid-batch, so that I can reconsider task granularity before further dispatch.
23. As an operator, I want pending dispatch paused during that reconsideration, so that stale task sizes are not assigned to a different-capability agent.
24. As a script author, I want commit messages in structured results, so that commits do not depend on scraping model output.
25. As a project owner, I want script-owned commits after verification, so that all adapters follow the same submission rules.
26. As a Worker, I want one ghost closeout opportunity when message or closeout work is incomplete, so that an otherwise salvageable task can finish.
27. As a project owner, I want ghost barred from implementation changes, so that closeout cannot become hidden product development.
28. As a Planner, I want ghost and script-generated internal work hidden from my task and scoring workflow, so that I review original task outcomes rather than internal execution steps.
29. As an operator, I want ghost bound to its original execution agent, so that closeout cannot silently cross capability boundaries.
30. As an operator, I want legal no-change outcomes to finish without ghost, so that completed work does not consume unnecessary model calls.
31. As an operator, I want a failed or unresponsive ghost to terminate without another rescue, so that closeout has a strict one-shot bound.
32. As an adapter author, I want contract tests with fake executables, so that I can prove compliance without spending model tokens.
33. As a user deploying NightShift, I want the installer to ship all adapter dependencies and protocol documentation, so that the deployed system behaves like the source checkout.

## Implementation Decisions

### 1. Roles and ownership

- **Registered agent**：一個具有穩定 ID 的執行設定，可指定 adapter、模型及其他覆寫。同一 adapter 可以註冊多個 agent。
- **Adapter**：實作外部程式協定，對接 CLI、HTTP API 或其他 AI 執行方式。agy、Codex 與既有 generic 行為均遷移至這個邊界。
- **Script / runtime**：管理 queue、任務與嘗試識別、callback 呼叫、計時、取消、切換、工作目錄、快照與回復、驗證／audit、commit、狀態與事件。
- **Planner**：管理任務範圍、依賴、顆粒、批次評分與驗收。runtime 不自行把粗任務改寫成細任務。
- **Watcher**：以機械式狀態觀察通知 Planner，不為查詢進度而呼叫模型，也不自動啟動 Planner。
- **Ghost**：script 管理的內部收尾補救，不是 Planner 派發的工作，也不是 agent 自行建立的任務。

### 2. Extension boundary

- 核心 script 不得依 agy、Codex、執行檔名稱或固定 provider 清單決定行為；註冊 ID 僅用於識別、歸屬與追蹤。
- 不得從執行檔名稱推測 provider，或從工具原始日誌推測額度、步數及結果。
- 工具特有的命令、模型／effort 轉換、原始輸出解析及步數計算，全部留在 adapter。
- 新增實作只新增符合協定的程式及註冊設定，不修改 runtime、CLI 允許值或核心 provider registry。
- callback 是 script 呼叫 adapter 的生命週期操作，不要求 adapter 反向呼叫 script。

### 3. Callback input and output contracts

採版本化 JSON request／response。外部程式的 callback 操作可使用子命令表達；控制回應與診斷日誌必須分離。所有 callback 呼叫均有期限，不得無限阻塞。

| Callback | 輸入契約 | 輸出契約 |
|---|---|---|
| `get_config` | 協定版本、註冊 ID、該 agent 的設定覆寫 | 受支援版本、能力初始分數、限制、查詢間隔與解析後設定 |
| `start` | 任務 ID／版本、嘗試 ID、工作目錄、共用 prompt 路徑、輸出目錄、解析後設定與限制、執行環境 | 立即返回執行識別碼與後續查詢所需的本機狀態位置 |
| `status` | 執行識別碼、本機狀態位置 | 統一狀態；終態包含結果或明確的結果檔位置、診斷指標與可用的預算資訊 |
| `closeout` | 原執行識別碼、共用收尾 prompt 路徑、剩餘預算、收尾期限、輸出目錄及必要的原執行脈絡 | 立即返回 ghost 執行識別碼與狀態位置，後續沿用 `status`／`cancel` |
| `cancel` | 執行識別碼、取消原因、停止期限 | 可供 script 確認已停止的結果；僅收到取消要求不代表已停止 |

- `start` 與 `closeout` 不等待模型完成才返回。callback 程序結束，不代表其管理的執行已結束。
- `get_config` 提供 adapter 預設，註冊設定可以覆寫；工具特有的覆寫語義由 adapter 解讀，script 不硬編碼它們。
- 執行環境包含適用的連接埠、測試環境及允許存取的工作範圍。不得在遷移時遺失原有必要脈絡。
- 各識別碼須能區分原任務、任務版本、主工作嘗試與內部 ghost；執行及狀態檔位置不得互相覆蓋。
- 每次操作的 prompt 與結果位置必須一致；ghost 不得誤讀主工作的 prompt 或覆寫尚待使用的結果。
- 不支援版本、無效設定、格式錯誤或缺少必要欄位，必須回傳明確的設定／協定失敗，不以日誌文字補猜。
- Porting guide 必須定義完整欄位、必填性、單位、狀態、錯誤及 callback 期限；具體序列化細節需維持上述契約。

### 4. Unified status and result

- 狀態至少區分執行中、完成、需要收尾、額度耗盡、超出步數、執行逾時、取消及一般失敗；保留 scope／guidance 等既有任務結果的語義。
- callback 不回應、回應格式錯誤與模型執行失敗必須可區分。script 可觀察並產生 callback 不回應／執行逾時結果，不依賴失去回應的 adapter 自行宣告。
- 完成結果提供任務結果、驗證證據、變更／無變更說明及 `commit_message` 等明確欄位。結果檔是結構化結果的傳遞方式，不是任意工具日誌。
- 缺少 `commit_message` 不直接代表任務不可補救；它是可以觸發一次 ghost 的收尾缺口。
- 非空 message 不等於成功或允許 commit。一般任務的驗證、scope、audit 與 Planner 驗收要求仍有效。
- 合法無變更結果必須有可驗證的理由與結果；不能將遺失輸出或未完成工作當成無變更成功。

### 5. Prompt invariance

- 同一任務版本的共用 worker prompt 由 script 建立一次；不同 agent 收到相同內容，可用內容 hash 驗證。
- prompt 保留任務意圖、TARGET、LEVEL、VERIFY、限制及共用行為規範，但不得混入 provider 分支、agent 特有政策或不同模型的執行限制。
- 模型、effort、權限、timeout、步數及工具啟動差異透過設定與執行環境傳遞，不藉由 adapter 拼接額外任務指示。
- budget 不得繼續以每個 agent 不同的數字寫入同一任務 prompt；適用限制從 callback 的執行設定取得。
- 工具可以將相同 prompt 轉成原生 API／CLI 的必要傳輸格式，但不得藉此改變任務要求。
- ghost 使用另外一份共用收尾 prompt，與 worker prompt 不同；收尾 prompt 同樣與工具名稱無關。
- Planner 改變任務範圍或顆粒時才形成新的任務內容；單純切換 agent 不暗中改寫原 prompt。

### 6. Limits and token-free status

- adapter 提供能力與執行方式適用的 timeout、callback 回應期限、步數及查詢間隔預設；註冊設定可覆寫。
- script 控制實際計時與停止，不允許失去回應的 adapter 阻止切換流程。
- **回應期限**限制單次 callback，尤其 `status`；**執行期限**限制實際工作。即使 callback 一直回報執行中，整體期限仍然有效。
- `status` 僅讀取 adapter 的本機狀態、程序狀態或已存在輸出，禁止發 prompt 問模型進度，也不主動查詢模型額度。
- script 遵守 adapter 建議的查詢間隔，不以高頻率忙迴圈查詢。沒有新日誌本身不是不回應。
- 步數的單位、計算、強制執行及超限語義由各 adapter 實作並在 porting guide 說明；不同工具的一步不必等價。
- ghost 接收原執行的剩餘預算與明確的收尾期限，不透過遞迴收尾取得無限資源。

### 7. Main-task failover and recovery

- 主任務的額度耗盡與不回應／執行逾時，都可切換下一個已註冊 agent；依註冊順序選擇可用者。
- 同一原任務中，每個 agent 最多嘗試一次，不無限輪轉。一般執行錯誤或步數超限不因此自動切換。
- 額度耗盡持續標記不可用，直到狀態重設；不回應／timeout 只跳過本次原任務，下個任務仍可嘗試。
- 全部不可用時，保留／重新入列原任務並等待恢復；不忙迴圈重試。保留 run-once 可退出的測試模式。
- 每次嘗試前保存可回復的起點，涵蓋 HEAD、index、tracked／untracked 變更與原本既有工作。
- 切換前先停止舊執行，確認不再寫入，再保存診斷與失敗變更、回復該次嘗試的起點。不得只還原 worktree 而留下該次 commit 或 staged 變更。
- 不得刪除或搬走任務開始前原有的工作；不得把失敗 agent 的半成品交給下一個 agent。
- 若無法確認停止或安全回復，暫停任務，不啟動下一個 agent。
- 保留各次嘗試的診斷，不因下一次嘗試而刪掉前次紀錄。
- 下一個 agent 的啟動受顆粒重新確認的派發閘門約束；切換本身不授權 runtime 自行拆任務。

### 8. Per-agent scores and batch planning

- 每個註冊 ID 獨立保存能力分數與既有升降所需的歷史；同 adapter 的不同模型設定不共用分數。
- 初始分數透過 `get_config` 取得。agy 與 Codex adapter 預設回傳 5；能力較弱的實作可回傳較低值。script 不得寫死這兩種工具的名稱與數值對應。
- 分數範圍沿用 1–5：5 對應 L1，3–4 對應 L2，1–2 對應 L3。最高分代表能處理較大的任務、自主性較高，不是 LEVEL 數字較大。
- 保留既有升降規則，但歸屬到實際執行的註冊 agent；Planner 給出驗收結果，runtime 管理算術與持久化。ghost 不獨立計分。
- 正常情況由 Planner 在批次邊界統一檢視結果與評分，依各 agent 當時分數規劃下一批工作。
- 執行中 agent 切換、能力分數／對應顆粒變化等會影響既有派發假設時，由 watcher 通知 Planner。
- 通知期間暫停新的派發；其他已在執行的主工作可完成。由 Planner 重新確認待執行任務是否適合新的 agent，必要時拆分／調整後恢復派發。
- watcher 使用持久化事件識別與已處理位置，避免同一事件重複通知或重啟後遺失；事件包含原因、前後 agent ID／分數及受影響任務。
- score 與額度可用性是不同狀態，不能以「模型能力較低」代替「暫時沒有額度」。

### 9. Commit ownership and one-shot ghost

- 主工作與 ghost 的共用 prompt 均不得要求 AI 自行 commit。AI 提供 message，script 在驗證與適用檢查通過後自動 commit。
- 已完成、message 齊全且驗證成功的工作直接由 script 提交，不額外呼叫 ghost。
- 每個原始 task ID 最多有一次 ghost 補救機會；中途更換主工作 agent 不重設額度。只有實際發出 ghost 才使用這次機會。
- 可補救情況包括缺少 commit message、需要驗證或尚未完成收尾。不得以「沒有 message」為理由拒絕 ghost。
- ghost 可以驗證、補齊 message、整理收尾結果；不能修改實作或成為新一輪開發。script 保留執行前後的檔案變更檢查。
- ghost 綁定發出時原執行的 agent 與任務脈絡；不能切換到另一個 agent，也不能接力交付半成品。
- ghost 失敗、不回應、逾時或額度耗盡時，回報原任務的最終失敗；不得因額度或 timeout 觸發外層主工作切換，也不得再發 ghost。
- 合法無變更結果直接結束，不 commit、不發 ghost。ghost 本身沒有另一份 ghost 補救機會。
- 其他由 script 自動發出的內部 AI 工作，同樣不走 Planner 任務派發／獨立評分，也不允許切換 agent。

| 情況 | 行為 |
|---|---|
| 主工作完成、message 齊全、驗證通過 | script 自動 commit |
| 缺 message 或尚有可補救的收尾缺口，且未用過 ghost | 發出一次 ghost；通過後由 script commit |
| 合法無變更結果 | 直接結束，不發 ghost、不 commit |
| ghost 失敗或不回應 | 結束補救，回報原任務失敗；不重試、不切換、不再發 ghost |

### 10. Ghost visibility boundary

- ghost 不進 Planner queue，不形成獨立 task、DONE 紀錄、review cadence 或 score feedback。
- ghost 的啟動、執行狀態、缺 message 補救及內部失敗，不作為獨立 watcher 通知送給 Planner；其他 script 自動發出的內部工作遵守相同原則。
- Planner 只看原任務最終結果及通常的驗證／驗收證據。最終成功或失敗可以沿用原任務通知流程，但不暴露獨立的 ghost 工作項目。
- adapter、執行識別碼及 script 內部仍須可追蹤 ghost，以實作取消、期限、一次額度及診斷；Planner 不可見不等於刪除內部診斷。

### 11. Migration and deployment

- Worker runtime 設定由 launcher 的預設值與啟動環境管理；移除 `.worker.env` 的設定來源設計。launcher、runtime、helper 與 Planner 都不能再要求或讀取該檔。
- Agent 註冊集中在單一 JSON object，以穩定 agent name 為 key；每筆包含 `default`、`adapter`、`command`、可選 `args`／`env` 及 adapter 專屬 `config`。`default: true` 優先，同組保留 JSON 順序；`config` 經共用 callback 傳遞給 adapter 解讀，不另外建立各工具專用的設定入口。
- 更新保留既有 registry 與舊 env 資料供人工遷移，移除舊 env 範例；舊 env 資料不再生效。launcher 屬於更新會覆蓋的檔案，須說明如何檢查並重套本地 runtime 設定。helper 需要自訂路徑／Worker ID 時，傳入與實際 Worker 相同的啟動環境設定。
- 這次以 agy、Codex 與 generic 路徑的協定化為主，不順便加入其他實際供應者。
- 保留既有任務、scope、驗證、失敗保存／復原與驗收行為；依按需求試用規格移除 worktree 隔離與自動 preview，改在專案目錄執行，使用普通試用 task 交付 bin 與資源衝突提示。
- 需同步調整共用執行規範、設定範例、Planner／watcher 操作說明與 porting guide，移除相衝突的 provider prompt、共用 score、AI 自行 commit 及 ghost 切換規則。
- 安裝／更新程序必須部署 adapter、必要共用支援與測試資源；不能只複製 runtime 而漏掉新的執行依賴。
- 保留使用者設定與既有工作資料。舊設定／score 的相容及遷移方式須明確記錄，不得猜測歷史共享分數屬於哪個 agent。

## Testing Decisions

- **主要測試 seam**：沿用現有 runtime CLI／daemon 與持久化狀態的外部行為測試，透過可控制的假 adapter executable 驗證完整流程。避免以私有函式、模組切割或命令字串形狀作為正確性判準。
- **Adapter 合規 seam**：在同一外部協定上提供可重用的 contract checks，涵蓋五個 callback。真實供應者不需要在測試中消耗 token。
- **既有先例**：現有測試已使用暫存 repository、fake CLI、run-once daemon、queue／score／failover／closeout／installer 行為；延伸這些模式，不另建一套平行框架。
- 使用獨立第三種、核心從未見過名稱的假 adapter，證明僅新增程式與註冊即可執行，且核心沒有 provider 白名單或執行檔推測。
- 對同一任務以不同註冊 agent 執行，驗證 worker prompt hash 一致，agent 特有設定與限制僅透過協定傳入。
- 驗證 `get_config` 預設與註冊覆寫、同 adapter 多模型註冊、不同 agent 的初始分數與後續升降互不污染。
- 假 adapter 記錄所有呼叫，證明 `status` 不觸發模型呼叫、不主動查額度，並遵守查詢間隔。
- 分開模擬卡住的 callback 與一直回應但執行超時的工作，驗證兩種期限都由 script 生效。
- 驗證 quota 與 timeout 可切換、一般失敗／步數超限不自動切換、每個 agent 每原任務最多嘗試一次、quota 持續排除與 timeout 下個任務可重試。
- 在切換測試中同時涵蓋原有 dirty／staged／untracked 工作與失敗嘗試產生的 commit，確認起點完整回復、既有工作保留、診斷不遺失。
- 以仍存活的舊執行及無法回復的假案例，驗證下一個 agent 不會啟動。
- 驗證中途事件持久化、watcher 通知去重、重啟不遺失、Planner 確認前新派發暫停，並維持原任務顆粒。
- 驗證批次評分按實際註冊 ID 歸屬，ghost 不產生獨立評分、任務紀錄或 cadence。
- 驗證主工作完成後 script 使用結構化 message commit；AI 不自行提交，缺 message 也不從日誌抓取。
- 特別測試「缺 message → 一次 ghost 補 message → script commit」，防止錯誤地跳過這條補救路徑。
- 驗證合法無變更不發 ghost、ghost 不能修改實作、不能再發 ghost、不能切換 agent；主工作曾切換也不增加 ghost 額度。
- 模擬 ghost quota、timeout 與無回應，證明不會落入外層主工作 failover，Planner 僅取得原任務最終結果。
- 驗證 ghost 與其他 script 內部工作不出現在 Planner queue、獨立 ledger／score／watcher 事件中，同時 script 仍保有取消與內部診斷資訊。
- 在安裝後的暫存目標專案執行相同協定流程，證明部署完整，不依賴來源 checkout 才能找到 adapter。
- 驗證不需要 worker env 檔的啟動、name-keyed registry 的 default 順序及 config 傳遞、升級保留 registry／舊工作資料，以及自訂 pause／status 路徑的 helper 指令。

## Out of Scope

- 本次文件工作不實作功能、不啟動 Worker、不修改執行中的 queue 或 agent 狀態。
- 不建立 Python 動態插件系統或固定供應者的核心擴充 API。
- 不新增額外真實 AI 供應者，不自動選模型，不以能力分數覆寫人類的模型設定。
- 不統一各工具的步數計算單位，不把不同模型的 timeout 預設強制設為相同。
- 不以 AI 查詢進度或額度，不增加週期性的模型監控呼叫。
- 不讓 runtime 自動拆分任務、不自動啟動 Planner，也不讓 ghost 進 Planner 的任務與評分流程。
- 不支援跨 agent 的 ghost 接力、反覆收尾或 ghost 修改實作。
- 不進行與 adapter 介面、score／watcher、收尾及部署無關的重構。

## Further Notes

- 這是對既有 NightShift 行為規格的後續變更；涉及共用 score、timeout 不切換、工具專屬 prompt、AI 自行 commit、ghost 切換等衝突時，以本規格的已確認決策為準。舊文件描述的是目前實作，不能據此撤回本次設計。
- agy、Codex 預設最高分是各 adapter 的設定，不是 script 可見的工具知識。
- 「每個工作一次補救」以原始 task ID 計算，包含缺 message 的情況；合法無變更免補救，ghost 不能再被補救。
- 「Planner 看不到 ghost」指任務與控制流程的隔離；Planner 仍須對原任務的最終成果進行正常驗收。
- 後續實作拆票應優先交付可由 fake adapter 跑通的協定與完整生命週期，再遷移內建工具、score／watcher 及部署，避免長期保留兩套行為來源。
