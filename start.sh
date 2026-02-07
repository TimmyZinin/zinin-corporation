#!/bin/bash
# Start both Telegram bot and Streamlit web interface

# Start Telegram bot in background (only if token is set)
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
    echo "Starting Telegram bot..."
    python run_telegram.py &
    TELEGRAM_PID=$!
    echo "Telegram bot started (PID: $TELEGRAM_PID)"
else
    echo "TELEGRAM_BOT_TOKEN not set — Telegram bot skipped"
fi

# Start Streamlit in foreground
echo "Starting Streamlit..."
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true

# If Streamlit exits, clean up
if [ -n "$TELEGRAM_PID" ]; then
    kill $TELEGRAM_PID 2>/dev/null
fi
