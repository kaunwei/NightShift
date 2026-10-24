# 01: 移除 worktree 隔離，讓既有部署直接在專案目錄執行

**What to build:** 維護者啟動或升級 NightShift 後，Worker 直接在專案目錄完成任務，不再維護隔離分支或自動發布 preview；既有工作與失敗復原能力得到保留。

**Blocked by:** None (can start immediately).

**Status:** proposed — awaiting breakdown review

- [ ] 新部署與升級後的部署，任務執行、驗證、提交與復原均以目前專案目錄為準；啟動不再建立、重用或同步 Worker worktree。
- [ ] 移除 worktree 執行模式、自動 preview 發布及其專用控制入口；成功 task 不再觸發 preview 匯出。
- [ ] 既有隔離設定有清楚且一致的退場行為；保留舊設定的部署不會意外啟用隔離或落入不明確的執行模式。
- [ ] 移除 worker env 檔的設定來源設計；runtime defaults／啟動覆寫與 name-keyed agent registry 分別管理設定。舊 env 資料僅供人工遷移，不能被 launcher、runtime、helper 或 Planner 讀取為現行設定。
- [ ] 升級不自動刪除既有 worktree、分支、preview 或其中尚未整合的修改／提交；提供檢查與人工遷移說明，說明未整合成果不會自動出現在專案目錄。
- [ ] Installer／updater、設定範例、狀態呈現、Planner／Worker 操作指引與行為文件一致反映專案目錄執行，不再引導使用已移除的隔離與自動發布流程。
- [ ] 保留失敗嘗試保存、baseline 快照與精確復原；復原不遺失任務開始前已有的工作。
- [ ] 以 fake adapter 在乾淨部署及含舊隔離設定與遺留工作資料的升級部署中，驗證成功、失敗與復原流程；不呼叫真實模型。
