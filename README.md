<p align="center">



  <img src="assets/icon.png" width="240" alt="OKSS 角色圖示" />



</p>



<h1 align="center">ok-star-savior</h1>



Star Savior 繁體中文 PC 版日課助手。



OKSS 使用 [ok-script](https://github.com/ok-oldking/ok-script) 框架與



[PyAppify](https://github.com/ok-oldking/pyappify) 安裝器，



透過遊戲畫面辨識與前台滑鼠操作，自動完成 Star Savior 的日常流程。



> ⚠️ **目前仍在測試階段**



>



> 已完成主要日課流程與單一帳號實機測試。



> 不同帳號進度、新活動、遊戲 UI 更新及不同解析度仍可能需要額外校正。



**快速連結**



**v0.2.4 測試版已發布**，新增獨立自訂排程、探索一鍵掃蕩與環形鏈路自動換盤，詳見 [更新紀錄](CHANGELOG.md)。安裝包已通過 SHA-256 校驗、內含來源比對與包內 Python 的離線載入及自訂排程介面檢查；各功能的實機驗證範圍見下方說明。



[下載 Global 測試版](https://github.com/Annan687/ok-star-savior/releases/download/v0.2.4/ok-star-savior-win32-Global-setup.exe) ·



[版本說明](https://github.com/Annan687/ok-star-savior/releases/tag/v0.2.4) ·



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



**[v0.2.4 測試版已公開發布](https://github.com/Annan687/ok-star-savior/releases/tag/v0.2.4)。一般使用者請下載 Global 安裝版。**



| 檔案 | 用途 |



| --- | --- |



| [ok-star-savior-win32-Global-setup.exe](https://github.com/Annan687/ok-star-savior/releases/download/v0.2.4/ok-star-savior-win32-Global-setup.exe) | 包含 OKSS、Python、執行套件及 OCR 模型。不需要另外安裝 Codex、OKPY 或 Python。 |



| [ok-star-savior-win32-online-setup.exe](https://github.com/Annan687/ok-star-savior/releases/download/v0.2.4/ok-star-savior-win32-online-setup.exe) | 線上安裝版，首次使用需要連網下載程式與環境，準備時間較長。 |



| `ok-star-savior-win32.zip` | 精簡啟動器壓縮包，不包含完整執行環境。 |



| `SHA256SUMS.txt` | 以上三個檔案的 SHA-256 校驗碼。 |



全部檔案與版本說明均位於 [GitHub Releases](https://github.com/Annan687/ok-star-savior/releases)。



本版尚待安裝精靈及第二台電腦實測；已完成與待完成的驗證列於下方「目前測試狀態」。



### 開始使用



1. 執行下載的 Global 安裝檔，依安裝精靈完成安裝。



2. 開啟 Star Savior PC 版，設定為**繁體中文**，使用接近 **16:9** 的畫面並回到大廳。



3. 啟動 OKSS，在「遊戲連線」選擇 `StarSavior.exe`。



4. 按「檢查遊戲畫面」，確認能正常取得遊戲畫面。



5. 勾選需要的日課與刷關目標，再按「開始日課」。需要手動操作時，先按「暫停」或「停止」。

中斷後再按「開始日課」，會跳過上一輪已處理的項目，從需檢查及尚未執行的項目接續；重開 OKSS 後也保留進度。續跑限電腦本機同一日期、相同勾選與刷關設定。要重跑全部勾選項目，請按「重新開始」。整輪完成後、日期或設定改變後會開始新一輪；計劃任務仍照該排程完整執行，不套用首頁續跑紀錄。



首次使用時，體力刷關預設為「不消耗體力」，限時據點預設略過。



勾選項目的資源使用方式，請參閱下方「遊戲資源消耗」。



v0.2.3 介面改為分類展開／折疊：勾選體力刷關、限時據點或激戰委託後，關卡設定會出現在該項下方。取消勾選會隱藏設定並保留原選擇；折疊分類不會取消勾選。活動襲擊與活動任務下方顯示包內支援的活動名稱，完成後關閉則放在「執行設定」。



---



## 計劃任務與自動啟動（實驗功能）



v0.2.2 已加入以下功能，目前已完成離線驗證，仍待實際定時啟動至任務結束的整段測試。首次使用請在有人操作時測試。



1. 首次先手動開啟遊戲，在 OKSS 完成遊戲連線，讓框架記住執行檔位置。Steam 版會透過 Steam 啟動；Steam 必須已能正常登入遊戲。



2. 在「星守日課」勾選日課與刷關目標。v0.2.3 已將啟動等待獨立，僅勾單項日課也會等待 Logo／資料載入畫面結束，看到 Touch to Start 才登入，最長等待 180 秒。「登入彈窗」控制活動簽到獎勵的領取。舊 v0.2.2 自動登入須保留「登入彈窗」，且啟動載入等待存在已知問題。

3. 到左側「計劃任務」建立任務，選擇「跟隨日課設定」或「自訂任務」，再設定每天及執行時間。跟隨版執行時讀首頁最新設定；自訂版按「設定執行項目…」勾選並儲存這筆排程自己的項目與刷關目標，不影響首頁或其他排程。例如跨日跑完整日課，晚間另建只勾好友點數的自訂排程。

4. 若要跑完關閉，勾選排程中的「完成後退出（-e）」。跟隨版也沿用首頁的關閉設定；自訂版只由該筆排程的退出選項控制。自訂設定若缺少或損毀會停止，不會改跑首頁日課。2026-09-20 已核對本機原始碼版 22:00 自訂排程：自動啟動 Steam 遊戲、完成勾選的五項流程，再自動關閉遊戲與 OKSS。這是單一帳號的實測，不代表所有項目與環境均已通過。



成功結束後沿用框架的關閉流程，結束匹配的遊戲程序並退出 OKSS；日課報錯時不執行這個成功後關閉流程。這不是遊戲內登出。排程使用建立時的程式路徑，移動或重新安裝 OKSS 後請重新建立。



電腦需開機、Windows 已登入且未鎖定，並保持遊戲可前台操作；不會自動開機或喚醒休眠。遊戲未開時，框架的自動啟動流程需要管理員權限，請先在有人操作時確認提升權限與 Steam 啟動流程可用。



排程頁會一起顯示 Windows 工作排程器中以 `ok-` 開頭的其他專案群組；其他專案的項目在本版框架中只能檢視。每個排程仍啟動自己的程式，不共用遊戲設定。多款遊戲請安排不同時間並預留足夠間隔，列表共通不代表會自動排隊。



## 💻 執行環境



| 項目 | 條件或驗證狀態 |



| --- | --- |



| Windows 10 / 11 64-bit | 支援目標；不同電腦與 Windows 環境仍待更多實測。 |



| Star Savior PC 繁體中文版 | 目前適用版本。 |



| 畫面比例 | 接近 16:9；執行中不要改變視窗大小。 |



| 約 1920 × 1057 | 已有實測紀錄的**遊戲擷取尺寸**。 |



| 1600 × 900 | 已完成單一帳號跨日日課測試，途中校正後分段續跑；仍待其他帳號驗證。 |



| 前台執行 | 必要；執行時避免移動滑鼠或操作其他視窗。 |



| 最小化 / 完整背景操作 | 不支援。 |



遊戲設定中的解析度、整個視窗大小與實際擷取尺寸可能不同。



例如視窗設定為 1920 × 1080 時，工具取得的遊戲畫面不一定剛好是 1920 × 1080。



請以「檢查遊戲畫面」的結果確認實際尺寸；其他尺寸仍可能需要校正。



---



## ✨ 日課功能



目前包含 **20 項日常流程**：



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

- 激戰委託

- 活動襲擊

- 活動任務

- 環形鏈路

- 任務



- 派遣



- 公會



- 通行證



部分任務會依照遊戲目前狀態，

判斷是否需要執行。



激戰委託提供「封閉的心象、異形的攻勢、虛假的契約」三選一，預設略過。

清單有獨立「活動」區，四項可各自勾選。灰色研究的襲擊與每日／點數／特殊任務分開選擇；活動名稱由新版程式提供，不需自行輸入；舊設定中的「魔女的帷幕」會自動忽略。此修正尚未包含在 v0.2.4 安裝器。只領獎時只勾「活動任務」，不會掃蕩。

激戰委託與活動襲擊各自使用自己的免費票，固定 MAX 用完剩餘票券，不提供掃蕩次數選項。

環形鏈路獨立勾選，領取自己的任務票券後全部抽取。舊版合併的「活動襲擊與任務」勾選會轉成兩項。



遇到無法辨識或不確定的畫面時，



OKSS 會優先停止流程並保留除錯資訊，



而不是持續盲目點擊。



---



## 案件檔案（v0.2.3 新增）



左側「任務」新增獨立的「案件檔案」，整合v1.4.1助手，不列入20項日課。先停在案件檔案活動首頁，使用1600×900視窗模式，按開始即可解盤至結算。



保留「自動重開」與「使用舊搜尋器」兩項，預設皆關閉。自動重開在正常結算2秒後繼續，也可從RESULT開始；舊搜尋器使用v1.2策略，保留新版觀測驗證。



改用OK共用啟停快捷鍵（預設F9）或任務卡停止；因有即時倒數，暫停也會結束本次操作，不恢復舊盤面。切換視窗、視窗大小／位置改變或辨識異常都會停止。保留前台擷取與輸入，每局紀錄在 `runs/case-files/`，不自動領獎。整合版仍待真實遊戲驗證。



## 🛒 遊戲資源消耗



部分選項會消耗遊戲內資源。



請確認設定符合自己的需求後再啟用。



### 啟示錄商店



指定兩種五折商品皆購買 **MAX**。



### 公會



- 購買星光石



- 捐獻黃金



- 捐獻活動證明



### 策略戰



允許免費刷新與黃金刷新。



### 體力刷關



只使用帳號目前已有的體力。



不自動購買體力或使用體力回復道具。



---



## 🔄 更新與本機資料



OKSS 使用 PyAppify 與 GitHub 版本標籤檢查更新。



更新機制設計為保留使用者本機設定；目前已驗證版本查詢，實際跨版本升級與設定保留仍待測試。



安裝版的 OKSS 資料位於安裝目錄下的 `data/apps/ok-star-savior/working/`，以下目錄均相對於此位置；從原始碼啟動時則位於專案資料夾內：



| 目錄 | 用途 |



| --- | --- |



| `configs` | 使用者設定、日課與刷關選項 |



| `runs` | 執行相關資料 |



| `logs` | 程式紀錄及錯誤資訊 |



| `screenshots` | 異常或未知畫面截圖 |



啟動器本身的紀錄則位於安裝目錄下的 `logs/`。回報安裝或更新問題時，請區分啟動器紀錄與 OKSS 日課紀錄。



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



請保留 OKSS 的 `logs` 與 `screenshots`。



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



請先確認檔案確實來自[本專案的 GitHub Releases](https://github.com/Annan687/ok-star-savior/releases)，並可使用隨附的 `SHA256SUMS.txt` 核對檔案。



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



OKSS：v0.2.2



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



以下分別列出本機原始碼、日課流程及安裝包的驗證結果；各版安裝器以 Release 說明為準。



| 範圍 | 已完成的驗證 |



| --- | --- |



| 日課流程 | v0.2.4 通過 280 項離線測試與 21 個子測試；單一帳號 1600×900 已實測探索三關一鍵掃蕩共 9 張免費票。完整日課包含分段修正續跑，非一次無人介入完成。[修正內容](CHANGELOG.md) |

| 自訂排程 | 本機原始碼版已實測 22:00 定時啟動 Steam 遊戲，只跑保存的五項設定，完成後關閉遊戲及 OKSS；首頁仍保留完整日課設定。 |

| GitHub Windows 建置 | v0.2.0 的兩種安裝器建置、套件相依檢查及 17 項日課介面測試通過；各新版以對應 Actions 結果為準。 |



| 安裝包內容 | v0.2.0 Global 安裝包已解包驗證；各新版校驗碼隨 Release 提供。 |



| 包內執行環境 | v0.2.0 使用包內 Python 載入 OKSS 與介面成功，套件檢查及實際 OCR 辨識測試通過。 |



| 啟動器版本查詢 | 在一般 Windows 使用者工作階段成功取得 GitHub 的 `v0.2.0` 版本資訊。 |



**尚待測試或擴大驗證：**



- 安裝版排程、不同任務組合及長期跨日穩定性；目前完整啟動至關閉的排程實测限本機原始碼版的五項自訂流程。



- 環形鏈路新增自動換盤分支、限時商店整個分類消失及案件檔案整合的實機驗證。



- 完整安裝精靈、乾淨 Windows 環境及第二台電腦的安裝與執行。



- 實際跨版本升級，以及升級後設定是否完整保留。



- 不同帳號解鎖進度、新手帳號、活動週期與新活動介面。



- 不同 Windows 環境與其他遊戲擷取尺寸。



---



## 👨‍💻 從原始碼執行



一般使用者可直接使用上方的 Global 安裝版。



開發與除錯請先安裝 **Git 與 Python 3.12（64 位元，包含 `py` 啟動器）**，再於 **PowerShell** 依序執行：



```powershell



git clone https://github.com/Annan687/ok-star-savior.git



cd ok-star-savior



py -3.12 -m venv .venv



.\.venv\Scripts\python.exe -m pip install --upgrade pip



.\.venv\Scripts\python.exe -m pip install -r requirements.txt



.\.venv\Scripts\python.exe main.py --check



.\.venv\Scripts\python.exe main.py



```



以上指令直接使用虛擬環境內的 Python，**不需要先執行 activate**。



`main.py --check` 會確認專案內的框架路徑，以及任務模組、OpenCV、OpenCC 等能否載入；



**不會測試遊戲畫面擷取、滑鼠點擊、OCR 辨識或完整日課流程**。



啟動後仍需按「檢查遊戲畫面」確認擷取，並另外實測所選日課。



OKSS 優先載入專案內的 `vendor/ok-script`。



使用的上游版本記錄於 [`vendor/ok-script-source.json`](vendor/ok-script-source.json)。



---



## 📜 授權與第三方元件



OKSS 是獨立的 Star Savior 日課自動化專案。



使用的主要第三方專案與套件包括：



### ok-script



https://github.com/ok-oldking/ok-script



作為 OKSS 的主要自動化框架。



實際使用的上游 commit 與來源資訊見 [`vendor/ok-script-source.json`](vendor/ok-script-source.json)。



上游原始條款保留於 [`vendor/ok-script/LICENSE.txt`](vendor/ok-script/LICENSE.txt)，包含 Commons Clause 與額外條款。



### PyAppify



https://github.com/ok-oldking/pyappify



用於安裝、更新及 Python 執行環境管理。



- 安裝器建置使用 **PyAppify v1.2.3**，見 [`BUILDING.md`](BUILDING.md)。



- Python 執行期套件為 **`pyappify==1.0.13`**，見 [`requirements.txt`](requirements.txt)。



安裝器上游授權見 [`licenses/pyappify/LICENSE.txt`](licenses/pyappify/LICENSE.txt)。



### PySide6-Fluent-Widgets



OKSS 的 Python 相依套件中包含



PySide6-Fluent-Widgets。



本版隨附的授權文件見 [`licenses/PySide6-Fluent-Widgets/LICENSE`](licenses/PySide6-Fluent-Widgets/LICENSE)。



### 其他第三方套件



完整套件與第三方授權資訊見 [`requirements.txt`](requirements.txt)、



[`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md) 與 [`licenses/`](licenses/)。



所有第三方元件仍遵循各自原作者的授權條款。



---



### OKSS 自有程式碼



OKSS 自有程式碼的授權尚待確認，目前未提供根目錄 `LICENSE`。



第三方元件不受 OKSS 自有程式碼授權取代，



仍各自遵循其原始授權條款。



---



## 📌 專案狀態



目前提供 `v0.2.4` 測試版；各項驗證進度與限制見上方「目前測試狀態」。



歡迎透過 [Issues](https://github.com/Annan687/ok-star-savior/issues) 提供不同環境的測試結果與問題紀錄。



