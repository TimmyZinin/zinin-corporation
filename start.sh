#!/bin/bash
# Start Telegram bots (Streamlit disabled to save RAM)

# Start Маттиас (CFO) Telegram bot in background
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
    echo "Starting Маттиас (CFO) Telegram bot..."
    python run_telegram.py &
    TELEGRAM_PID=$!
    echo "Маттиас bot started (PID: $TELEGRAM_PID)"
else
    echo "TELEGRAM_BOT_TOKEN not set — Маттиас bot skipped"
fi

# Start Алексей (CEO) Telegram bot in background
if [ -n "$TELEGRAM_CEO_BOT_TOKEN" ]; then
    echo "Starting Алексей (CEO) Telegram bot..."
    python run_alexey_bot.py &
    CEO_BOT_PID=$!
    echo "Алексей bot started (PID: $CEO_BOT_PID)"
else
    echo "TELEGRAM_CEO_BOT_TOKEN not set — Алексей bot skipped"
fi

# Start Юки (SMM) Telegram bot in background
if [ -n "$TELEGRAM_YUKI_BOT_TOKEN" ]; then
    echo "Starting Юки (SMM) Telegram bot..."
    python run_yuki_bot.py &
    YUKI_BOT_PID=$!
    echo "Юки bot started (PID: $YUKI_BOT_PID)"
else
    echo "TELEGRAM_YUKI_BOT_TOKEN not set — Юки bot skipped"
fi

echo "All bots started. Waiting..."

# Keep container alive — wait for any background process to exit
wait -n

echo "A process exited. Shutting down..."
# Clean up remaining processes
if [ -n "$TELEGRAM_PID" ]; then
    kill $TELEGRAM_PID 2>/dev/null
fi
if [ -n "$CEO_BOT_PID" ]; then
    kill $CEO_BOT_PID 2>/dev/null
fi
if [ -n "$YUKI_BOT_PID" ]; then
    kill $YUKI_BOT_PID 2>/dev/null
fi
