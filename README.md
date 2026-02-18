# Immigration Monitor

Monitors Reddit and Telegram for immigration-related questions, classifies them using AI, and sends notifications to a Telegram channel.

## Architecture

```
Reddit API ──→ RedditMonitor ──→ Classifier ──→ TelegramNotifier ──→ Your TG Channel
                                     ↑
Telegram API → TelegramMonitor ──────┘
                                     │
                              Keywords + Claude AI
                              (hybrid classification)
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get API credentials

**Reddit:**
1. Go to https://www.reddit.com/prefs/apps/
2. Create a "script" app
3. Copy `client_id` (under app name) and `client_secret`

**Telegram (for reading groups):**
1. Go to https://my.telegram.org
2. Create an app → get `api_id` and `api_hash`
3. Your account must be a member of the groups you want to monitor

**Telegram Bot (for sending notifications):**
1. Message @BotFather on Telegram
2. Create a new bot → get `bot_token`
3. Create a channel/group for notifications
4. Add the bot as admin to that channel
5. Get the channel ID (forward a message from channel to @getidsbot)

**Anthropic (for AI classification):**
1. Get API key from https://console.anthropic.com/

### 3. Configure

Edit `config.yaml`:
- Fill in all API credentials
- Add/remove Telegram groups
- Add/remove Reddit subreddits
- Adjust keywords and settings

### 4. First run

```bash
# Test notification delivery
python main.py --test-notify

# Run once to check everything works
python main.py --once

# Run continuously
python main.py
```

### 5. Run as a service (production)

```bash
# Using systemd
sudo cp immigration-monitor.service /etc/systemd/system/
sudo systemctl enable immigration-monitor
sudo systemctl start immigration-monitor

# Or using screen/tmux
screen -S monitor
python main.py
# Ctrl+A, D to detach
```

## Configuration Guide

### Adding a new Telegram group

```yaml
telegram:
  groups:
    - username: "new_group_username"
      name: "Display Name"
      language: "ru"  # ru, uk, en, es
```

### Adding a new subreddit

```yaml
reddit:
  subreddits:
    - name: "newsubreddit"
      check_comments: true  # also scan comments
```

### Classification modes

- `keywords` - Free, fast, ~70% accuracy
- `ai` - Claude Haiku, ~$0.001/post, ~95% accuracy
- `hybrid` - Keywords filter first, then AI (recommended)

### Notification format

Each notification includes:
- Source (Reddit/Telegram) and group name
- Category (visa, asylum, deportation, etc.)
- Urgency level
- Post text preview
- AI summary
- Draft response (optional)
- Direct link to source

## Commands

```bash
python main.py              # Run continuously
python main.py --once       # Run one cycle
python main.py --stats      # Show statistics
python main.py --test-notify # Test notification
python main.py --config /path/to/config.yaml  # Custom config
```

## Costs

| Component | Cost |
|-----------|------|
| Reddit API | Free |
| Telegram API | Free |
| Claude Haiku (classification) | ~$2-3/month |
| VPS | ~$5-10/month |
| **Total** | **~$7-13/month** |
