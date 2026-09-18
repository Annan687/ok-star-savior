# 建置 OKSS 安裝器

這份來源使用 PyAppify，會輸出：

- `ok-star-savior-win32-Global-setup.exe`：包含預先準備的環境。
- `ok-star-savior-win32-online-setup.exe`：首次使用時連網準備環境。
- `SHA256SUMS.txt`：供下載後核對。

## 第一次發佈

1. 使用整理好的乾淨來源建立 GitHub 倉庫。不要上傳原開發目錄的 `.venv`、`configs`、`screenshots`、`runs`、`logs` 或 `backups`。
2. `pyappify.yml` 中的 `git_url` 必須指向朋友及建置器可讀取、具有版本標籤的來源倉庫。初版設定使用同一個公開 GitHub 倉庫；私人倉庫尚未整合登入憑證。
3. 為已審查的來源建立版本標籤（目前來源為 `v0.2.3`）並推送。這會觸發 Build OKSS installers。也可以在標籤存在後手動執行該工作流程。
4. 工作流程先驗證來源與 Python 相依套件，再編譯 PyAppify 和兩種安裝器。安裝檔會保存為 Actions artifact，**不會自動建立公開 Release**。
5. 下載 artifact，先測試在乾淨的 Windows 環境安裝、開啟、OCR 與退出，再把安裝檔及校驗碼附到對應 Release。

首次發佈前需確認專案的授權檔、第三方聲明及可公開內容。不要將個人帳號的 Token 寫進 `pyappify.yml` 或程式碼。

## 後續更新

修改日課程式後更新程式版本、測試、提交並建立新版本標籤。PyAppify 依標籤下載版本；已可被使用者讀取的標籤應視為對外更新，先完成審查再推送。

框架直接從 `vendor/ok-script/ok` 載入，不安裝開發機的 editable 套件，也不依赖開發者的 Python 路徑。`requirements.txt` 固定執行期套件版本，安裝器自行建立 Python 3.12 環境。

工作流程固定 PyAppify v1.2.3 及 pyappify-action commit `c5cc8fe5c9bd5c732969018694a2645474c48b7e`，正式發佈前仍須完成實際建置測試。若有套件版本無法取得，須先重建並驗證依賴鎖定檔，不能略過安裝失敗。
