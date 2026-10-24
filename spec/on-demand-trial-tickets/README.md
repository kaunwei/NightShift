# 按需求交付試用版本：實作工單

Source: [按需求交付試用版本](../on-demand-trial.md).

本地工單草案，待審閱粒度與 blocking edges；尚未發布 issue、排入 queue 或執行。使用者已指定交付在 `spec/`，因此本次不依預設 tracker 設定發布至 GitHub。

| 工單 | Blocked by | What it delivers |
|---|---|---|
| [01: 移除 worktree 隔離，讓既有部署直接在專案目錄執行](01-in-place-execution.md) | None | 新部署與升級後的部署都直接執行任務，保留復原能力及既有工作，停止自動發布 preview。 |
| [02: 由 Planner 插入普通 task，交付當下可跑的 bin](02-on-demand-bin.md) | 01 | 人提出試用要求後，在下一個 task 邊界建置、檢查並取得有版本資訊的 bin，Worker 接續開發。 |
| [03: 在試用交付中檢查資源衝突並提供人工暫停指引](03-resource-conflicts.md) | 02 | 需要 script 或共用資源的程式也能交付明確的試用條件；人根據具體指令決定何時暫停 Worker。 |

初始 frontier：**01**。02 使用 01 的單一工作目錄契約；03 延伸 02 的試用工單與交付結果。每張工單連同相關部署、文件與有意義的驗收一起完成。

審閱重點：工單是否過粗或過細、blocking edges 是否為真正前置條件，以及是否需要合併或拆分。
