# CR Rank 自動收成器

定時點擊 [CR Rank 知識領土](https://crrank.xpgs25.com/game) 上方的「收成 +金幣/建材」按鈕。單一 exe，電腦和手機都能用。

## 下載

到 [Releases](../../releases) 下載 `CRRank自動收成器.exe`，直接執行即可（不用安裝 Python）。

## 電腦連點

- **選位置**：按「🎯 在螢幕上選位置」再點按鈕，或把滑鼠移到按鈕上按 **F8**；也可直接輸入 X / Y。
- **間隔**：秒 / 分 / 時，可加隨機誤差與次數上限。
- **開始 / 停止**：按鈕或 **F9**（全域熱鍵）。
- 點完預設把滑鼠移回原位。瀏覽器視窗要保持在原位、不被擋住。

## 手機

手機與電腦連同一個 Wi-Fi，用手機掃程式「手機」分頁的 QR Code：

1. **書籤 / 使用者腳本（在手機瀏覽器裡自動點）**：照頁面說明新增書籤，在遊戲頁開啟會出現可拖動的面板，可設間隔、選「自動找收成按鈕」或「點自訂位置」。有 Tampermonkey / Violentmonkey 的瀏覽器可直接安裝 `.user.js`。
2. **遙控電腦**：用手機開始 / 停止電腦端連點、改間隔。連結帶隨機密碼。

「📁 匯出手機用檔案」會產生使用者腳本、書籤碼和說明網頁。

> 手機請保持螢幕亮著、遊戲分頁在前景，否則瀏覽器會暫停計時。
> 第一次執行時 Windows 防火牆若詢問，請按「允許」，手機才連得到。

## 自行建置

```bash
pip install pyinstaller qrcode
python -m PyInstaller --onefile --noconsole --name "CRRank自動收成器" --hidden-import qrcode crrank_clicker.py
```

## 注意

自動點擊可能違反網站規則，使用風險自負。
