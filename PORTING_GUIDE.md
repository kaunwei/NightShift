# NightShift 專案對接與外部架構指南 (Porting & Architecture Guide)

本指南說明如何以**外部專案架構（External Project Architecture）**將 NightShift 對接到任意現有專案。

採用此架構後，**你的目標專案不需要安裝任何 NightShift 檔案**，亦不需 `install.sh` 或 `remove.sh`，所有 Worker / Planner 的執行狀態、日誌、佇列與程式碼索引完全隔離在專案之外，達成對專案代碼庫的**零污染（Zero Footprint）**。

---

## 1. 三層分離架構 (Three-Tier Architecture)

```
[ Tier 1: NightShift Core ] (純工具核心庫，例如 /opt/NightShift)
    ├── scripts/worker.sh
    ├── scripts/worker_runtime.py
    └── .agents/skills/

[ Tier 2: 外部控制工作區 ] (Runner Workspace，例如 ~/nightshift-workspace)
    ├── config.json (或 config.yaml)
    └── projects/
        ├── my-app/              <-- 專屬 my-app 的所有暫存與執行檔
        │   ├── run_worker.sh    <-- 專案專屬一鍵啟動腳本
        │   ├── tasks.txt        <-- 任務佇列
        │   ├── tasks.done       <-- 已完成任務紀錄
        │   ├── progress.log     <-- 歷史執行日誌
        │   ├── worker.status    <-- Daemon 即時狀態
        │   ├── code-index/      <-- AST 導覽 (INDEX.md, index.json)
        │   └── reports/         <-- 失敗診斷報告
        └── backend-api/         <-- 另一個專案的暫存區
            └── ...

[ Tier 3: 目標專案庫 ] (Target Project，例如 /Users/you/repos/my-app)
    ├── .git/
    ├── src/
    ├── tests/
    └── scripts/run_hot.sh       <-- 專案專屬快速單元測試腳本 (由專案 Git 自行管理)
```

### 各層職責：
1. **NightShift Core**：核心執行引擎與 Agent 技能庫，隨時可 `git pull` 更新，不存放專案設定。
2. **外部控制工作區（Workspace）**：集中管理所有專案的設定檔與個別專案的暫存目錄（`projects/<project_name>/`）。各專案相互獨立，重設單一專案只需清空該專案目錄。
3. **目標專案庫（Target Project）**：使用者的業務代碼。完全不包含 NightShift 檔案或暫存日誌，維持純淨的 Git 歷程。

---

## 2. 外部專案的設定與資料夾模式

NightShift 支援兩種專案配置模式：**獨立專案資料夾模式（推薦）** 與 **全域多專案設定模式**。

### 模式 A：獨立專案資料夾模式 (One Folder Per Project，推薦)
將每個專案的 `config.json` 直接放進該專案專屬的資料夾中（例如 `projects/my-app/config.json`）。

```text
nightshift-workspace/
└── projects/
    ├── my-app/
    │   ├── config.json          <-- 專案專屬設定檔
    │   ├── run_worker.sh        <-- 專案專屬啟動腳本
    │   ├── env.sh               <-- 專案環境啟用腳本 (類似 Python venv activate)
    │   ├── tasks.txt            <-- 任務佇列
    │   ├── tasks.done           <-- 已完成任務清單
    │   ├── progress.log         <-- 執行日誌
    │   ├── worker.status        <-- 即時狀態
    │   ├── code-index/          <-- 專案 AST 導覽 (INDEX.md, index.json)
    │   └── reports/             <-- 診斷報告
    └── backend-api/
        ├── config.json
        └── ...
```

在 `projects/my-app/config.json` 中配置：
```json
{
  "version": 1,
  "projects": {
    "my-app": {
      "path": "/Users/you/repos/my-app",
      "acceptance": {
        "hot_script": "scripts/run_hot.sh",
        "cold": "npm test",
        "cold_every": 5,
        "timeout": 120
      }
    }
  },
  "agents": {
    "primary": {
      "default": true,
      "worker": {
        "task_timeout_seconds": 600,
        "step_base": { "L1": 60, "L2": 40, "L3": 20 }
      },
      "agent": {
        "adapter": "generic",
        "command": "python3",
        "args": ["-m", "codex"]
      }
    }
  }
}
```

> [!TIP]
> **自動識別優勢**：
> - 由於 `config.json` 位於 `projects/my-app/`，且只定義了單一專案，NightShift 會**自動識別**專案名稱為 `my-app`，並自動將該目錄作為暫存目錄（State Dir）。
> - 啟動時只需指定 `--config ./projects/my-app/config.json`，**不需傳入 `--project` 參數**！

---

### 模式 B：全域多專案設定模式 (Shared Multi-Project Config)
若你習慣將所有專案定義在同一個全域 `config.json` 中，NightShift 完全保留此支援（不需拔除）：

在工作區根目錄 `config.json`：
```json
{
  "version": 1,
  "projects": {
    "my-app": {
      "path": "/Users/you/repos/my-app",
      "state": "projects/my-app",
      "acceptance": { "hot_script": "scripts/run_hot.sh", "cold": "npm test" }
    },
    "backend-api": {
      "path": "/Users/you/repos/backend-api",
      "state": "projects/backend-api",
      "acceptance": { "hot_script": "scripts/test_unit.py", "cold": "pytest" }
    }
  },
  "agents": { ... }
}
```
透過 `--project <name>` 切換欲執行的專案：
```bash
worker.sh --config ./config.json --project my-app
```

---

## 3. Planner 與 Worker 如何知道路徑？

在多專案外部工作區中，路徑感知機制如下：

### 1. Worker 的路徑自動解析
當你啟動 Worker 時：
```bash
# 模式 A (獨立專案資料夾)：直接傳入該專案 config，自動識別名稱與目錄
/path/to/NightShift/scripts/worker.sh --config ./projects/my-app/config.json

# 模式 B (全域多專案設定)：指定全域 config 與專案名稱
/path/to/NightShift/scripts/worker.sh --config ./config.json --project my-app
```
Worker 會透過 `project_config.resolve_project` 自動綁定執行環境：
- **`NIGHTSHIFT_PROJECT_ROOT`**：指向專案實體目錄（例如 `/Users/you/repos/my-app`）。Worker 的 Agent 執行工作目錄在此，且只有專案修改會被 Git commit。
- **`NIGHTSHIFT_STATE_DIR`**：指向專案專屬暫存區（例如 `./projects/my-app`）。
- **`TASKS_FILE`**：自動指向 `projects/my-app/tasks.txt`。
- **`PROGRESS_FILE`**：自動指向 `projects/my-app/progress.log`。
- **`STATUS_FILE`**：自動指向 `projects/my-app/worker.status`。
- **`code-index`**：AST 圖譜自動生成於 `projects/my-app/code-index/`。

### 2. Planner 的路徑查詢機制
Planner 不需要猜測路徑，只要執行單一指令即可取得完整的結構化資訊：
```bash
# 模式 A：
python3 /path/to/NightShift/scripts/worker_runtime.py project-info \
  --config ./projects/my-app/config.json

# 模式 B：
python3 /path/to/NightShift/scripts/worker_runtime.py project-info \
  --config ./config.json \
  --project my-app
```
輸出 JSON：
```json
{
  "name": "my-app",
  "root": "/Users/you/repos/my-app",
  "state": "/Users/you/nightshift-workspace/projects/my-app",
  "skills": "/path/to/NightShift/.agents/skills",
  "index": "/Users/you/nightshift-workspace/projects/my-app/code-index/INDEX.md"
}
```
Planner 據此獲知：
- **閱讀程式碼與 Git 歷程**：查閱 `root`。
- **閱讀架構導覽地圖**：查閱 `index`（`INDEX.md`）。
- **佇列新增任務**：呼叫 `queue-insert --tasks <state>/tasks.txt`。
- **檢視失敗報告**：讀取 `<state>/reports/`。
- **調用 Agent 技能**：載入 `skills`。

---

## 4. Hot / Cold 驗收對接方式 (Acceptance Porting)

NightShift 採用雙層測試驗收機制，平衡開發速度與整體穩定度：

### 1. Hot Acceptance（快速單元驗收）
- **觸發時機**：每個任務實作完成後立即執行。
- **職責**：驗證當前任務修改的檔案與新加入的 TDD 測試案例。
- **耗時要求**：必須極速（建議 < 5~10 秒）。
- **對接方式**：
  在專案中建立 `scripts/run_hot.sh`：
  ```bash
  #!/usr/bin/env bash
  set -euo pipefail
  
  # 若有傳入指定測試案例，優先執行該案例
  if [ -n "${NIGHTSHIFT_TDD_CASES:-}" ]; then
    pytest $NIGHTSHIFT_TDD_CASES
  else
    # 預設執行快速單元測試
    pytest tests/unit/
  fi
  ```
  並在 `config.json` 設定：
  ```json
  "acceptance": {
    "hot_script": "scripts/run_hot.sh"
  }
  ```

### 2. Cold Acceptance（全量回歸驗收）
- **觸發時機**：每完成 `cold_every` 個任務（預設每 5 個任務）在背景執行一次。
- **職責**：跑整個專案完整的測試套件（含慢速整合測試、E2E 測試、linting 等）。
- **前置條件**：執行前會檢查 `git status`，必須在乾淨的代碼樹下運行。若失敗會暫停 Worker 並留下診斷報告，防止潛在回歸蔓延。
- **對接方式**：
  直接在 `config.json` 設定專案標準的測試指令：
  ```json
  "acceptance": {
    "cold": "pytest tests/ --cov",
    "timeout": 300
  }
  ```

---

## 5. 快速上手：建立專案專屬一鍵啟動腳本

在你的控制工作區（`~/nightshift-workspace`）中，各專案建立 `projects/<project_name>/run_worker.sh`：

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. 取得目錄絕對路徑
PROJECT_STATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "$PROJECT_STATE_DIR/../.." && pwd)"
PROJECT_NAME="$(basename "$PROJECT_STATE_DIR")"

# 2. 指定 NightShift 核心位置 (依實際安裝路徑調整)
NIGHTSHIFT_CORE="/Volumes/Vault500G/workspace/NightShift"

CONFIG_FILE="$PROJECT_STATE_DIR/config.json"

echo "=== Starting NightShift Worker ==="
echo "Project : $PROJECT_NAME"
echo "Config  : $CONFIG_FILE"
echo "State   : $PROJECT_STATE_DIR"
echo "=================================="

# 3. 執行 Worker (自動識別專案並將目前目錄作為暫存目錄)
exec "$NIGHTSHIFT_CORE/scripts/worker.sh" \
  --config "$CONFIG_FILE" \
  "$@"
```
賦予執行權限：
```bash
chmod +x projects/my-app/run_worker.sh
```

### 日常操作：
- **啟動專案 Worker**：
  ```bash
  ./projects/my-app/run_worker.sh
  ```
- **查看即時進度**：
  ```bash
  tail -f projects/my-app/progress.log
  ```
- **重設專案執行狀態**：
  只需清理該專案目錄下的暫存檔即可，專案代碼庫毫髮無損：
  ```bash
  rm -rf projects/my-app/worker.status projects/my-app/.scratch
  ```

---

## 6. Planner 終端環境定錨：`env.sh` (類似 Python venv 啟動腳本)

在外部三層架構中，目標專案庫與外部狀態目錄完全分離。為了**避免 Planner 在不同路徑間切換迷路或浪費大量 Token 處理長絕對路徑**，且**完全不需在目標專案建立軟連結或修改專案的 `.gitignore`**，各專案目錄下提供 `env.sh`。

### 運作原理：
如同 Python virtualenv 的 `source venv/bin/activate`，在開啟終端機時執行：
```bash
source projects/my-app/env.sh
```

### `env.sh` 完整腳本範本：
在 `projects/<project_name>/env.sh` 中：
```bash
# NightShift Project Environment Activator (Bash & Zsh compatible)
# Usage: source /path/to/env.sh

# Detect script path across bash and zsh
if [ -n "${ZSH_VERSION:-}" ]; then
  _SOURCE="${(%):-%N}"
  if [[ "${ZSH_EVAL_CONTEXT:-}" != *file* ]]; then
    echo "Error: env.sh must be sourced, not executed directly." >&2
    echo "Run: source $_SOURCE" >&2
    return 1 2>/dev/null || exit 1
  fi
elif [ -n "${BASH_SOURCE[0]:-}" ]; then
  _SOURCE="${BASH_SOURCE[0]}"
  if [ "${BASH_SOURCE[0]}" = "${0:-}" ]; then
    echo "Error: env.sh must be sourced, not executed directly." >&2
    echo "Run: source ${BASH_SOURCE[0]}" >&2
    exit 1
  fi
else
  _SOURCE="${0:-}"
fi

_ENV_DIR="$(cd "$(dirname "$_SOURCE")" && pwd)"
_CONFIG_FILE="$_ENV_DIR/config.json"
NIGHTSHIFT_CORE="${NIGHTSHIFT_CORE:-/Volumes/Vault500G/workspace/NightShift}"

if [ ! -f "$_CONFIG_FILE" ]; then
  echo "Error: Missing config.json in $_ENV_DIR" >&2
  return 1 2>/dev/null || exit 1
fi

# 1. 透過 project_config.py 導出所有標準環境變數
eval "$(python3 "$NIGHTSHIFT_CORE/scripts/project_config.py" --config "$_CONFIG_FILE" --root "$_ENV_DIR")"
export NIGHTSHIFT_CORE

# 2. 將 Runner 目錄加入 PATH，讓 `run_worker.sh` 與 `status.sh` 能直接當作全域指令執行
if [[ ":$PATH:" != *":$_ENV_DIR:"* ]]; then
  _OLD_NS_PATH="$PATH"
  export PATH="$_ENV_DIR:$PATH"
fi

# 3. 注入常用便捷指令
ns-status() { "$NIGHTSHIFT_CORE/scripts/status.sh" --config "$NIGHTSHIFT_CONFIG_FILE" "$@"; }
ns-worker() { "$_ENV_DIR/run_worker.sh" "$@"; }
ns-watch() { "$_ENV_DIR/watch_worker.sh" "$@"; }
ns-pause() { touch "$PAUSE_FILE" && echo "[PAUSED] Worker paused via $PAUSE_FILE"; }
ns-resume() { rm -f "$PAUSE_FILE" && echo "[RESUMED] Worker unpaused"; }
deactivate-ns() {
  unset PROJECT_ROOT NIGHTSHIFT_CONFIG_FILE NIGHTSHIFT_PROJECT_ROOT NIGHTSHIFT_PROJECT_NAME
  unset NIGHTSHIFT_STATE_DIR TASKS_FILE TASKS_DONE_FILE PROGRESS_FILE STATUS_FILE PAUSE_FILE
  unset WORKER_AGENT_EVENTS_FILE WORKER_AGENT_EVENTS_CURSOR_FILE WORKER_AGENT_EVENTS_ACK_FILE
  unset AGENT_DISPATCH_GATE_FILE NIGHTSHIFT_CORE
  unset -f ns-status ns-worker ns-watch ns-pause ns-resume deactivate-ns 2>/dev/null || true
  unalias ns-status ns-worker ns-watch ns-pause ns-resume 2>/dev/null || true
  if [ -n "${_OLD_NS_PATH:-}" ]; then PATH="$_OLD_NS_PATH"; unset _OLD_NS_PATH; fi
  if [ -n "${_OLD_NS_PS1:-}" ]; then PS1="$_OLD_NS_PS1"; unset _OLD_NS_PS1; fi
  if [ -n "${_OLD_NS_PROMPT:-}" ]; then PROMPT="$_OLD_NS_PROMPT"; unset _OLD_NS_PROMPT; fi
  echo "NightShift environment deactivated."
}

# 4. 更新提示字元 (像 Python venv，避免重複疊加)
if [[ "${PS1:-}" != *"(ns:$NIGHTSHIFT_PROJECT_NAME)"* ]]; then
  _OLD_NS_PS1="${PS1:-}"
  PS1="(ns:$NIGHTSHIFT_PROJECT_NAME) ${PS1:-}"
fi
if [[ "${PROMPT:-}" != *"(ns:$NIGHTSHIFT_PROJECT_NAME)"* ]]; then
  _OLD_NS_PROMPT="${PROMPT:-}"
  PROMPT="(ns:$NIGHTSHIFT_PROJECT_NAME) ${PROMPT:-}"
fi

# 4. 自動切換至專案代碼根目錄
cd "$NIGHTSHIFT_PROJECT_ROOT" || return 1 2>/dev/null || exit 1

echo "========================================================"
echo " Activated NightShift: $NIGHTSHIFT_PROJECT_NAME"
echo " Code Root   : $NIGHTSHIFT_PROJECT_ROOT"
echo " State Dir   : $NIGHTSHIFT_STATE_DIR"
echo " Tasks Queue : $TASKS_FILE"
echo " Quick cmds  : ns-status | ns-worker | ns-watch | ns-pause | ns-resume | deactivate-ns"
echo "========================================================"
```

### 帶來的核心優勢：
1. **目標專案 100% 乾淨**：不需在專案內建軟連結、不需修改專案的 `.gitignore`。
2. **Planner 零 Token 浪費**：終端直接處於專案代碼根目錄，查閱代碼永遠是相對路徑；讀寫任務直接使用 `$TASKS_FILE` 或 `$STATUS_FILE`，絕不迷路或反覆重試。
3. **體驗一致**：終端提示字元顯示 `(ns:my-app)`，多專案切換一目了然；輸入 `deactivate-ns` 即可乾淨復原。
