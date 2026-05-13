#!/bin/bash
: "${GROQ_API_KEY:?GROQ_API_KEY not set}"

echo "[$(date)] === 開始執行攻略文產生器 ==="
cd ~/Downloads/lewislunora/xiangchuan
python3 -u guide_content_generator.py >> guide_gen_v2.log 2>&1

echo "[$(date)] === 攻略文完成，休息 120 秒 ==="
sleep 120

echo "[$(date)] === 開始執行 AI 短劇劇本產生器 ==="
python3 -u ai_drama_script_generator.py >> drama_gen_v2.log 2>&1

echo "[$(date)] === 全部完成 ==="
