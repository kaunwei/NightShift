# 02: 由 Planner 插入普通 task，交付當下可跑的 bin

**What to build:** 使用者向 Planner 要求試用後，下一個 task 邊界會執行一張普通試用工單，交付當下版本的可跑 bin、版本與啟動方式，Worker 隨後繼續開發。

**Blocked by:** 01: 移除 worktree 隔離，讓既有部署直接在專案目錄執行。

**Status:** proposed — awaiting breakdown review

- [ ] Planner 操作規範包含試用請求的工單內容：目標程式、專案適用的建置／最低限度可執行檢查、交付位置、必要資源檢查及交付證據。
- [ ] Planner 使用既有 queue 鎖定與替換機制，將試用 task 排在目前 task 之後、其他待辦之前；閒置時排在待辦首位，保留其餘待辦順序，且不遺失或重複已 claim 的 task。
- [ ] 試用採普通 task 與既有 audit／驗收流程，不新增 runtime 特殊 task 類型或成功後自動發布機制。
- [ ] 建置與最低限度可執行檢查使用試用 task 執行時的版本；成功結果包含獨立放置的 bin、來源 task／程式版本、建置／檢查證據及實際啟動方式。
- [ ] 交付 bin 不因後續一般開發或建置而被直接覆寫；連續兩次交付可以分辨，且新交付保留上一份 bin。
- [ ] 僅產出可忽略的建置產物、沒有原始碼變更的合法 task 仍可完成，不要求製造無意義的提交。
- [ ] 建置或可執行檢查失敗時，回報具體原因交由 Planner 安排修復，不將舊版或未驗證產物宣稱為本次可跑版本。
- [ ] Planner／Worker 指引與部署文件一併交付；以小型 bin fixture 與 fake adapter，驗證 queue 插入、產物交付、失敗回報及後續 task 繼續執行，不呼叫真實模型。
