---
title: 開始使用 KIRA | 安裝指南
description: 逐步指南來安裝和設定 KIRA，您的 AI 虛擬同事。了解如何連接 Slack、設定權杖，並在 15 分鐘內開始與您的 AI 助手對話。
head:
  - - meta
    - name: keywords
      content: KIRA 安裝, Slack bot 設定, AI 助手指南, KIRA 教程, AI 虛擬同事設定
  - - meta
    - property: og:title
      content: 開始使用 KIRA | 安裝指南
  - - meta
    - property: og:description
      content: 在 15 分鐘內安裝 KIRA。完整的 Slack 應用程式設定、權杖配置和開始第一次對話的指南。
  - - meta
    - property: og:url
      content: https://kira.krafton-ai.com/zh-tw/getting-started
---

# 開始使用

開始使用 KIRA 非常簡單。按照本指南，您將在 15 分鐘內開始與您自己的 AI 虛擬同事對話。

## 🎯 選擇您的模式

KIRA 可以以兩種不同的模式使用。**首先選擇您偏好的模式。**

::: info 模式比較
| 功能 | Bot 模式 | 虛擬同事模式 |
|---------|----------|----------------------|
| **安裝** | 您的電腦 | 專用電腦/VM/伺服器 |
| **Slack 帳戶** | 您的帳戶或 bot 應用程式 | AI 的專用帳戶 |
| **權杖** | Bot Token (`xoxb-...`) | User Token (`xoxp-...`) |
| **顯示** | 顯示為 bot | 顯示為真實使用者 |
| **運作時間** | 當您的電腦開啟時 | 24/7（始終開啟）|
| **操作者** | 您 | 獨立操作 |
| **設定** | 簡單 | 稍微複雜 |
:::

> 💡 **KRAFTON 使用案例**：KRAFTON 提供專用的公司帳戶和電腦來運行 KIRA 作為虛擬同事，就像入職新員工一樣。

### 🤖 Bot 模式

**在您的電腦上將 KIRA 用作個人 AI 助手。**

- 在**您的電腦**上安裝 KIRA
- 使用**您的 Slack 帳戶**或 bot 應用程式
- 您直接管理和操作它
- 當您的電腦關閉時停止

**最適合：**
- 個人工作協助
- 單獨使用 AI 助手
- 快速簡單的設定

### 👤 虛擬同事模式

**在專用電腦上將 KIRA 作為團隊共享的 AI 同事運行。**

- 在**專用電腦**（或 VM/伺服器）上安裝 KIRA
- 為 AI 創建**專用 Slack 帳戶**（例如 "KIRA Kim"）
- 24/7 獨立運行
- 像真實團隊成員一樣參與頻道

**最適合：**
- 團隊範圍的共享 AI 同事
- 24/7 始終運作
- 像真實團隊成員一樣運作

::: warning 在繼續之前選擇您的模式
根據您選擇的模式，本指南有不同的設定步驟。在每個步驟中遵循 **Bot 模式** 或 **虛擬同事模式** 的說明。
:::

## 📋 先決條件

在開始之前，您需要：

### 1. Slack 工作區
- 個人工作區或您有管理員權限的工作區
- 免費計劃即可

### 2. Node.js
- 已安裝 Node.js 18 或更高版本
- Claude Code CLI 所需
- [下載 Node.js](https://nodejs.org/)

### 3. 電腦需求
- **macOS**：10.15 (Catalina) 或更高版本
- 可用磁碟空間：500MB 或更多

### 4. Claude Pro 方案
- KIRA 在內部使用 Claude Code，這需要 **Claude Pro 方案或更高版本**
- [了解更多關於 Claude 方案](https://www.anthropic.com/pricing)

---

**注意**：完整的中文版說明文件正在準備中。目前請參閱 [英文版](/getting-started) 以獲取完整的安裝步驟。
