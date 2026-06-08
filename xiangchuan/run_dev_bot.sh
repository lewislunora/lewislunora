#!/bin/bash
# 開發助理啟動腳本
cd "$(dirname "$0")"
echo "🤖 啟動開發助理 Telegram Bot..."
echo "按 Ctrl+C 停止"
python3 dev_assistant.py
