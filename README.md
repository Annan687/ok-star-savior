# OKSS · 星之守護者日課

Star Savior 繁體中文 PC 版日課助手。

OKSS 使用 [ok-script](https://github.com/ok-oldking/ok-script) 框架與
[PyAppify](https://github.com/ok-oldking/pyappify) 安裝器，
透過遊戲畫面辨識與前台滑鼠操作，自動完成 Star Savior 的日常流程。

> ⚠️ **目前仍在測試階段**
>
> 已完成主要日課流程與單一帳號實機測試。
> 不同帳號進度、新活動、遊戲 UI 更新及不同解析度仍可能需要額外校正。

**快速連結**

[Releases](https://github.com/Annan687/ok-star-savior/releases) ·
[Issues](https://github.com/Annan687/ok-star-savior/issues) ·
[原始碼](https://github.com/Annan687/ok-star-savior)

---

## ⚠️ 使用前須知

OKSS 是第三方遊戲自動化工具：

- 並非 Star Savior 官方產品。
- 並非 ok-script 官方維護的遊戲專案。
- 主要透過畫面辨識與前台滑鼠輸入操作。
- 執行期間 Star Savior 必須保持在前台。
- 執行期間請不要移動滑鼠、操作其他視窗或改變遊戲視窗大小。
- 不支援遊戲最小化後完整背景執行。

自動化流程可能因以下情況失效：

- 遊戲版本更新
- UI 或活動介面變更
- 帳號功能解鎖進度不同
- 網路延遲
- 畫面解析度或比例不同
- Windows 環境差異
- 防毒軟體或其他程式干擾

使用第三方自動化工具可能存在帳號或使用風險，
請自行評估後使用。

---

## 🚀 安裝與開始

### 下載

正式安裝版本將透過：

**[GitHub Releases](https://github.com/Annan687/ok-star-savior/releases)**

提供。

目前專案仍在測試與安裝器驗證階段。

如果 Releases 頁面尚未出現可下載版本，
代表目前尚未正式發布安裝檔。

預計提供兩種安裝方式：

#### Global

```text
ok-star-savior-win32-Global-setup.exe
```

已包含主要執行環境。

一般使用者**不需要另外安裝 Python**。

#### Online Installer

```text
online-setup.exe
```

首次啟動需要連網下載：

- OKSS
- Python
- Python 套件
- 相關執行環境

因此第一次啟動時間可能較長。

一般使用者建議優先使用 **Global** 版本。

---

### 開始使用

1. 開啟 Star Savior PC 版。
2. 將遊戲語言設定為 **繁體中文**。
3. 使用 **16:9** 畫面。
4. 回到遊戲大廳。
5. 啟動 OKSS。
6. 在「遊戲連線」選擇：

```text
StarSavior.exe
```

7. 按下：

```text
檢查遊戲畫面
```

確認 OKSS 能正常取得遊戲畫面。

8. 勾選需要執行的日課及刷關設定。
9. 按下「開始日課」。

首次設定本身不會消耗體力。

限時據點目前預設略過，需要時請自行啟用。

---

## 💻 執行環境

| 項目 | 狀態 |
| --- | --- |
| Windows 10 64-bit | ✅ |
| Windows 11 64-bit | ✅ |
| Star Savior PC 繁體中文版 | ✅ |
| 16:9 | ✅ 必要 |
| 1920 × 1080 | ✅ 已實測 |
| 1600 × 900 | ⚠️ 符合尺寸條件，但仍需更多實測 |
| 前台執行 | ✅ 必要 |
| 最小化 / 完整背景操作 | ❌ |
| 執行時操作滑鼠 | ❌ |

目前主要開發與測試解析度：

```text
1920 × 1080
```

其他 16:9 解析度可能可以使用，
但不保證所有辨識流程都已完成實測。

---

## ✨ 日課功能

目前包含約 **17 項日常流程**：

- 登入彈窗
- 支援金
- 郵件
- 好友點數
- 免費禮包
- 指定商店商品
- 探索免費券
- 體力刷關
- 立方
- 限時據點
- 屬性迴廊
- 策略戰
- 活動
- 任務
- 派遣
- 公會
- 通行證

部分任務會依照遊戲目前狀態，
判斷是否需要執行。

遇到無法辨識或不確定的畫面時，
OKSS 會優先停止流程並保留除錯資訊，
而不是持續盲目點擊。

---

## 🛒 遊戲資源消耗

部分選項會消耗遊戲內資源。

請確認設定符合自己的需求後再啟用。

### 啟示錄商店

指定兩種五折商品：

```text
購買 MAX
```

### 公會

可執行：

```text
購買星光石
捐獻黃金
捐獻活動證明
```

### 策略戰

允許：

```text
免費刷新
黃金刷新
```

### 體力刷關

只使用帳號目前已有的體力。

目前不會自動：

```text
購買體力
使用體力回復道具
```

---

## 🔄 更新與本機資料

OKSS 使用 PyAppify 與 GitHub 版本標籤檢查更新。

正常更新後會保留使用者本機設定。

主要資料目錄：

| 目錄 | 用途 |
| --- | --- |
| `configs` | 使用者設定、日課與刷關選項 |
| `runs` | 執行相關資料 |
| `logs` | 程式紀錄及錯誤資訊 |
| `screenshots` | 異常或未知畫面截圖 |

這些資料預設保存在使用者本機，
**不會由 OKSS 自動上傳**。

> 回報問題前，請確認 log、截圖或其他附件中
> 沒有 UID、帳號資訊、角色名稱或其他不希望公開的內容。

---

## 🔧 疑難排解

<details>
<summary><b>無法取得遊戲畫面</b></summary>

請確認：

1. Star Savior 已正常啟動。
2. 遊戲語言為繁體中文。
3. 畫面比例為 16:9。
4. 遊戲已進入大廳。
5. 「遊戲連線」已選擇正確的 `StarSavior.exe`。
6. 再次按下「檢查遊戲畫面」。

如果仍然失敗，
可以重新啟動 Star Savior 與 OKSS 後再試。

</details>

<details>
<summary><b>沒有點擊、點錯位置或任務突然失效</b></summary>

請確認：

- Star Savior 位於前台。
- 執行期間沒有移動滑鼠。
- 沒有切換其他視窗。
- 遊戲視窗大小沒有改變。
- 遊戲沒有被其他視窗遮住。

如果問題是在 Star Savior 更新之後才出現，
可能是 UI、圖示或辨識素材已經改變。

請保留：

```text
logs
screenshots
```

並透過 GitHub Issues 回報。

</details>

<details>
<summary><b>卡在未知畫面</b></summary>

不同帳號可能因以下差異，
出現目前尚未收錄的畫面：

- 新手進度
- 功能解鎖狀態
- 活動頁面
- 新增彈窗
- 遊戲版本差異

請查看 `logs` 最後的錯誤紀錄，
以及 `screenshots` 是否保存了當時畫面。

</details>

<details>
<summary><b>遊戲更新後突然不能使用</b></summary>

遊戲更新可能修改：

- UI
- 圖示
- 按鈕位置
- 活動頁面
- 字體
- 彈窗
- 操作流程

如果遊戲更新後 OKSS 突然失效：

1. 停止 OKSS。
2. 確認遊戲本身運作正常。
3. 保留錯誤畫面。
4. 保留相關 log。
5. 至 GitHub Issues 回報。

</details>

<details>
<summary><b>防毒軟體出現警告</b></summary>

完整版本可能包含：

- Python 執行環境
- 自動化相關套件
- 打包後的執行檔
- 安裝與更新元件

部分防毒軟體可能因 Python、
自動化輸入、打包程式或更新機制產生警告。

請先確認檔案確實來自：

```text
https://github.com/Annan687/ok-star-savior/releases
```

不要對來源不明的安裝檔加入防毒排除。

</details>

<details>
<summary><b>Online Installer 無法下載</b></summary>

Online Installer 首次執行需要下載 Python
及相關套件。

可以檢查：

- 網路連線
- VPN
- 防火牆
- 防毒軟體
- GitHub 存取
- Python 套件下載服務

如果持續失敗，
建議使用 Global 完整版本。

</details>

---

## 🐛 問題回報

請使用：

**[GitHub Issues](https://github.com/Annan687/ok-star-savior/issues)**

建議附上：

```text
OKSS 版本：
Windows 版本：
Star Savior 版本：
遊戲解析度：
發生問題的任務：
問題發生時間：
是否能穩定重現：
```

並盡量提供：

- `logs` 中相關紀錄
- `screenshots` 中異常畫面
- 錯誤訊息截圖
- 問題發生前後的操作步驟

範例：

```text
OKSS：v0.1.0
Windows：Windows 11 64-bit
Star Savior：目前遊戲版本
解析度：1920 × 1080
任務：策略戰
問題：進入策略戰後停在隊伍選擇畫面
重現：每次都會
```

只留下：

```text
不能用
卡住了
沒反應
```

通常不足以判斷問題。

越完整的資訊越容易重現與修正。

---

## 🧪 目前測試狀態

目前已使用一個實際帳號測試：

- 完整日課流程
- 任務單獨執行
- 分段續跑
- 中途停止後重新開始
- 部分異常畫面處理

仍需要更多測試：

- 不同帳號解鎖進度
- 新手帳號
- 不同活動週期
- 新活動介面
- 不同 Windows 環境
- 其他 16:9 解析度
- 完整安裝器乾淨安裝
- 第二台電腦安裝及執行

> **原始碼可用不代表安裝檔已正式發布。**
>
> 正式版本請以 GitHub Releases
> 實際提供的內容為準。

---

## 👨‍💻 從原始碼執行

一般使用者建議使用正式安裝版本。

目前開發與除錯環境：

```text
Python 3.12
Windows 10 / 11 64-bit
```

### 1. Clone

```bash
git clone https://github.com/Annan687/ok-star-savior.git
cd ok-star-savior
```

### 2. 建立虛擬環境

```bash
py -3.12 -m venv .venv
```

啟用虛擬環境：

```bash
.venv\Scripts\activate
```

### 3. 安裝套件

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. 檢查環境

```bash
python main.py --check
```

正常情況下會檢查：

- Python
- 專案內的 ok-script
- 任務模組
- OpenCV
- OpenCC

### 5. 啟動

```bash
python main.py
```

OKSS 會優先載入專案內：

```text
vendor/ok-script
```

而不是系統中其他位置安裝的同名框架。

實際使用的上游 ok-script 版本
記錄於：

```text
vendor/ok-script-source.json
```

---

## 📜 授權與第三方元件

OKSS 是獨立的 Star Savior 日課自動化專案。

使用的主要第三方專案與套件包括：

### ok-script

https://github.com/ok-oldking/ok-script

作為 OKSS 的主要自動化框架。

實際使用的上游 commit 與來源校驗資訊保存在：

```text
vendor/ok-script-source.json
```

上游原始授權條款亦保留於專案中。

### PyAppify

https://github.com/ok-oldking/pyappify

用於安裝、更新及 Python 執行環境管理。

### PySide6-Fluent-Widgets

OKSS 的 Python 相依套件中包含
PySide6-Fluent-Widgets。

其授權條款請以上游專案目前公布的
授權資訊為準。

### 其他第三方套件

完整套件與第三方授權資訊請參考：

```text
requirements.txt
THIRD-PARTY-NOTICES.md
licenses/
```

所有第三方元件仍遵循各自原作者的授權條款。

---

### OKSS 自有程式碼

OKSS 自有程式碼的授權條款
以專案根目錄中的：

```text
LICENSE
```

為準。

第三方元件不受 OKSS 自有程式碼授權取代，
仍各自遵循其原始授權條款。

---

## 📌 專案狀態

| 功能 | 狀態 |
| --- | --- |
| 核心日課 | ✅ 可用 |
| 繁體中文 | ✅ |
| 1920 × 1080 | ✅ 已實測 |
| 1600 × 900 | ⚠️ 待更多實測 |
| 前台滑鼠操作 | ✅ |
| 背景操作 | ❌ |
| 多帳號環境 | ⚠️ 待測 |
| 安裝器 | 🧪 驗證中 |
| 新活動 | 🔄 持續適配 |

歡迎透過 Issues
提供不同環境的測試結果與問題紀錄。
