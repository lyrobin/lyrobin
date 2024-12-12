# 立院知更 - 基於大型語言模型實作的立法院搜尋引擎

在 2024 年初，台灣立法院在立委席次減半後，首次出現了三黨不過半的局面。
對於許多重大議題，多出了許多衝突和需要討論的地方。
然而，現行立法院的官方系統難以提供有效的方法幫助大眾匯整資料進而理解不同立場的觀點。
在這樣的情況下，立院知更希望透過科技的方式，建立更加直覺且便利的立院搜尋引擎。
期待透過這樣的方式，幫助每一個人用自己的方式理解並深度參與公眾議題。

🌐 現在就前往[立院知更](https://lyrobin.com) ([https://lyrobin.com](https://lyrobin.com))，
開始探索立院大小事！

## 快速開始

立院知更包含了前端和後端的程式碼，並透過 Google Cloud 佈署。
完整的環境設置教學，可以參考[開發環境設定](docs/environment_setup.md)。

### <img src="docs/assets/angular.png" alt="angular" width="16"/> 前端開發

主要框架是 Angular，可透過以下指令執行開發用伺服器。

```bash
npm run start
```

### 後端開發

主要包含兩個部份：資料處理和提供 API。
資料處理的部份使用 Python，搭配 Firebase 框架。
API 伺服器則是使用 Go 語言，以 Docker container 的方式佈署於 Cloud Run。

#### <img src="docs/assets/firebase.png" alt="firebase" width="16"/> Firebase 開發

資料處理的邏輯使用 Firebase Cloud Function 完成。可參考
[官方文件](https://firebase.google.com/docs/functions/get-started?gen=2nd)
來初如化工作環境。

執行以下指令啟動開發用模擬環境：

```bash
firebase emulators:start --only=auth,firestore
```

#### <img src="docs/assets/docker.png" alt="docker" width="16"/> API 開發

主要程式碼位於 `cloudrun` 底下。可以透過 `docker-compose` 啟動開發用環境：

```bash
docker-compose up -d
```

## 🔰 貢獻你的力量

我們歡迎每一個對公眾議題有熱情的公民貢獻自己的力量！
但在開始之前，我們希望您先閱讀[社群守則](docs/code_of_conduct.md)，
為維護有善包容的開發環境盡一份心力。

我們會在近期更新開發規範，幫助你了解如何開始。

在此之前，你可以[預約訪談](https://calendar.app.google/YrNrYZLWvxmT4VvT9)來和主要的開發者分享你的想法！

## 📣 加入我們

[![X](https://img.shields.io/badge/@lyrobintw-%23000000.svg?style=for-the-badge&logo=X&logoColor=white)](https://x.com/lyrobintw)
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/tu8PGtPBgX)
[![YouTube](https://img.shields.io/badge/YouTube-%23FF0000.svg?style=for-the-badge&logo=YouTube&logoColor=white)](https://www.youtube.com/channel/UC-ZDaiyWzJRLLB0pklIEoOQ)
[![Gmail](https://img.shields.io/badge/Gmail-D14836?style=for-the-badge&logo=gmail&logoColor=white)](mailto:lyrobin@gmail.com)

- X (原 twitter): [@lyrobintw](https://x.com/lyrobintw)
- Discord: https://discord.gg/tu8PGtPBgX
- YoTube: [立院知更](https://www.youtube.com/channel/UC-ZDaiyWzJRLLB0pklIEoOQ)
- Gmail: lyrobintw@gmail.com

## 支持我們

立院知更的資料建置與儲存、大型語言模型的使用、網域的使用與流量都是開發上的成本，如果你願意付出小額的費用當我們初期的使用者，我們會將你對網站的期望做更優先的可行性分析，也會讓你優先使用最新最有趣的功能

<a
    href="https://www.buymeacoffee.com/blueworryb6"
    target="_blank"
    class="mx-2">
<img
    src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png"
    alt="Buy Me A Coffee"
    style="height: 40px !important; width: 180px !important" />
</a>
