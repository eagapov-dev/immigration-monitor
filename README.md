# Immigration Monitor

Multi-source monitoring system that tracks immigration-related discussions across Reddit, Telegram, and web forums. Classifies posts by category and urgency using AI (Claude Haiku) and keyword matching, then sends actionable notifications to a Telegram channel.

## Architecture

```
Reddit (RSS)     ──→ RedditSource    ──┐
                                       │
Telegram (API)   ──→ TelegramSource  ──┼──→ Classifier ──→ TelegramOutput ──→ Your TG Channel
                                       │        ↑
Forums (RSS)     ──→ ForumSource     ──┘   Keywords + Claude AI
                                           (hybrid classification)
```

## Features

- **3 data sources**: Reddit (14 subreddits via RSS), Telegram (9+ groups/channels via Telethon), VisaJourney forums (12 RSS feeds)
- **Multilingual classification**: English (hybrid: keywords pre-filter + AI), Russian/Ukrainian (AI-first with keyword fallback)
- **8 immigration categories**: visa, asylum, deportation, green card, work permits, family, citizenship, TPS
- **3 urgency levels**: high, medium, low
- **Smart deduplication**: SQLite database prevents duplicate notifications
- **Rate limiting**: configurable max notifications per hour
- **AI draft responses**: optional AI-generated reply suggestions
- **Location detection**: 50+ locations recognized, Chicago highlighted with a star
- **Zero-cost sources**: Reddit and forums use RSS (no API keys needed)

## Supported Languages

| Language  | Classifier | Approach |
|-----------|-----------|----------|
| English   | `EnglishClassifier` | Hybrid: keywords gate → AI verification |
| Russian   | `CyrillicClassifier` | AI-first (morphology too complex for keywords) |
| Ukrainian | `CyrillicClassifier` | AI-first, shared with Russian classifier |

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` and fill in:
- **Telegram API** credentials (`api_id`, `api_hash`, `phone`) — get from https://my.telegram.org
- **Telegram Bot** token (`bot_token`) — create via @BotFather
- **Notification channel** ID (`notification_channel_id`)
- **Anthropic API** key (`anthropic_api_key`) — get from https://console.anthropic.com/ (optional, needed for `ai`/`hybrid` classification)

### 3. Run

```bash
# Test notification delivery
python main.py --test-notify

# Run one cycle to verify everything works
python main.py --once

# Run continuously
python main.py

# Show statistics
python main.py --stats
```

## Classification Modes

| Mode | Cost | Accuracy | How it works |
|------|------|----------|--------------|
| `keywords` | Free | ~70% | Keyword matching only |
| `ai` | ~$0.001/post | ~95% | Claude Haiku for every post |
| `hybrid` | ~$0.0005/post | ~95% | Keywords pre-filter, then AI (recommended) |

Set in `config.yaml`:
```yaml
classification:
  method: "hybrid"  # "keywords", "ai", or "hybrid"
```

## Notification Format

Each notification includes:
- Source icon and group/subreddit name
- Category (visa, asylum, deportation, etc.) with emoji
- Urgency level (high/medium/low)
- Post text preview (500 chars)
- Location (with Chicago highlighted)
- AI summary
- Draft response (optional)
- Direct link to source

## Project Structure

```
immigration-monitor/
├── main.py                 # Core orchestrator, CLI entry point
├── database.py             # SQLite deduplication & stats
├── config.example.yaml     # Configuration template
├── requirements.txt        # Python dependencies
├── classifiers/
│   ├── __init__.py         # Router: picks classifier by language
│   ├── base.py             # BaseClassifier, ClassificationResult, AI calls
│   ├── en.py               # English: hybrid (keywords → AI)
│   └── ru.py               # Russian/Ukrainian: AI-first
├── sources/
│   ├── base.py             # MonitorItem dataclass, BaseSource
│   ├── reddit.py           # Reddit via RSS feeds
│   ├── telegram.py         # Telegram via Telethon (user account)
│   └── forums.py           # VisaJourney.com via RSS feeds
├── outputs/
│   ├── base.py             # BaseOutput interface
│   └── telegram_bot.py     # Telegram bot notifications
├── data/                   # SQLite database (gitignored)
└── logs/                   # Application logs (gitignored)
```

## Production Deployment

### systemd service

```bash
sudo cp immigration-monitor.service /etc/systemd/system/
sudo systemctl enable immigration-monitor
sudo systemctl start immigration-monitor
```

### screen/tmux

```bash
screen -S monitor
python main.py
# Ctrl+A, D to detach
```

## Estimated Costs

| Component | Cost |
|-----------|------|
| Reddit (RSS) | Free |
| Telegram API | Free |
| Forums (RSS) | Free |
| Claude Haiku (hybrid mode) | ~$2-3/month |
| VPS (e.g. DigitalOcean) | ~$5-10/month |
| **Total** | **~$7-13/month** |

## Tests

```bash
pytest test_classifiers.py -v
```

Tests cover word boundary matching, false positive prevention (e.g. "самовивіз" should not match visa keywords), and hyphenated keyword handling (H-1B, I-485).
