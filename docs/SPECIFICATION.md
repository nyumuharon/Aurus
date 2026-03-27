# Aurus — Project Specification Document

**Version:** 1.0
**Date:** March 2026
**Lead Engineer:** Haron
**Status:** Pre-Development

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [System Objectives](#3-system-objectives)
4. [System Architecture](#4-system-architecture)
5. [Component Specifications](#5-component-specifications)
6. [Project Structure](#6-project-structure)
7. [Development Sprints](#7-development-sprints)
8. [Technology Stack](#8-technology-stack)
9. [Risks and Constraints](#9-risks-and-constraints)
10. [Success Criteria](#10-success-criteria)
11. [Glossary](#11-glossary)

---

## 1. Executive Summary

Aurus is an autonomous AI-powered trading system designed to detect and execute high-probability trade setups on the **XAU/USD (Gold vs US Dollar)** currency pair. The system integrates multiple machine learning models, a local large language model for trade validation, and a rule-based risk management engine — working in concert to identify patterns that human traders cannot reliably detect at speed or scale.

The ultimate goal of Aurus is to pass a prop firm evaluation challenge and trade a funded account consistently, targeting **8% monthly returns** while maintaining a maximum drawdown below **5%**.

| | |
|---|---|
| **Mission** | Build a fully autonomous, AI-driven gold trading system that operates 24/5 with institutional-grade discipline and no emotional interference. |
| **Target Market** | XAU/USD (Gold) — 5-minute to 1-hour timeframes on MetaTrader 5. |
| **Target Output** | 8% monthly return, max 5% daily drawdown, max 10% total drawdown, prop firm ready. |

---

## 2. Problem Statement

Manual trading of XAU/USD presents several compounding challenges that systematically erode performance:

- Human traders cannot monitor markets 24 hours a day across multiple timeframes simultaneously.
- Emotional decision-making — fear and greed — causes deviation from established trading rules.
- Complex pattern recognition across volume, price action, and correlated markets exceeds human cognitive bandwidth.
- Reaction time to news events and sudden price movements is too slow for optimal entry and exit.
- Consistent application of risk management rules is undermined by psychological pressure in live trading.

Aurus addresses each of these problems through automation, multi-model AI ensemble detection, local LLM validation, and a non-negotiable rule-based risk engine.

---

## 3. System Objectives

### 3.1 Primary Objectives

| ID | Objective | Metric | Target |
|---|---|---|---|
| OBJ-01 | Generate consistent profit | Monthly return | 8%+ |
| OBJ-02 | Capital preservation | Max daily drawdown | < 5% |
| OBJ-03 | Prop firm compliance | Max total drawdown | < 10% |
| OBJ-04 | Operate autonomously | Human intervention | Zero during live session |
| OBJ-05 | Pattern detection speed | Signal latency | < 2 seconds |

### 3.2 Secondary Objectives

- Maintain a detailed trade journal for post-session analysis and model improvement.
- Send real-time alerts via Telegram when trades are opened or closed.
- Provide a performance dashboard showing live equity curve, win rate, and drawdown.
- Allow easy model swapping without disrupting the broader system architecture.

---

## 4. System Architecture

Aurus follows an **Event-Driven Architecture (EDA)** developed using an **Agile methodology** in six sequential sprints. Each layer is independent — it can be tested, modified, or replaced without affecting adjacent layers.

### 4.1 Architectural Layers

| Layer | Name | Responsibility | Technology |
|---|---|---|---|
| 1 | Data Engine | Collect and clean all market data in real time | Python, MT5 API, REST APIs |
| 2 | Pattern Detection | Run ML models to identify trade signals | TensorFlow, Scikit-learn |
| 3 | AI Validator | Validate signals against news and context | Ollama + Qwen3:8b (local) |
| 4 | Risk Manager | Enforce all capital protection rules | Python rules engine |
| 5 | Execution Engine | Send orders and manage open positions | MetaTrader5 Python API |
| 6 | Monitoring | Log trades, alert, and display dashboard | SQLite, Telegram Bot, Flask |

### 4.2 Event Flow

```
MARKET TICK (every second)
      |
      v
[ Layer 1 ] Data Engine
  - Fetch OHLCV from MT5
  - Fetch news headlines from API
  - Fetch DXY correlation data
  - Fetch economic calendar events
      |
      v
[ Layer 2 ] Pattern Detection (parallel)
  - LSTM          -> price sequence signal
  - Transformer   -> market structure signal
  - Random Forest -> indicator confluence signal
  - SMC Detector  -> BOS / FVG / S&D signal
  - ENSEMBLE VOTE -> BUY | SELL | NO_TRADE
      |
      v  (only if signal = BUY or SELL)
[ Layer 3 ] AI Validator (Qwen3:8b)
  - Input:  signal + current news + DXY bias
  - Output: YES (proceed) | NO (skip)
      |
      v  (only if YES)
[ Layer 4 ] Risk Manager
  - Check: daily drawdown < 5%?
  - Check: total drawdown < 10%?
  - Check: trades today < 3?
  - Calculate: ATR position size
  - Output: APPROVED (lot size) | BLOCKED
      |
      v  (only if APPROVED)
[ Layer 5 ] Execution Engine
  - Send order to MT5 broker
  - Set SL and TP automatically
  - Monitor position in real time
      |
      v
[ Layer 6 ] Monitoring
  - Log trade to SQLite database
  - Send Telegram alert
  - Update dashboard
```

---

## 5. Component Specifications

### 5.1 Layer 1 — Data Engine

The Data Engine is the foundation of Aurus. All other layers depend on clean, timely data. Any failure in this layer stops the entire system gracefully.

| Component | Source | Frequency | Data Points |
|---|---|---|---|
| XAU/USD Price | MetaTrader 5 | Every tick | OHLCV, Bid/Ask, Spread |
| News Headlines | NewsAPI / Alpha Vantage | Every 5 minutes | Title, source, timestamp, sentiment |
| DXY Index | MT5 / Yahoo Finance | Every minute | Price, 4H trend direction |
| Economic Calendar | Forex Factory API | Daily refresh | Event name, impact level, time |

---

### 5.2 Layer 2 — Pattern Detection Models

#### 5.2.1 LSTM Neural Network

- **Purpose:** Detect repeating price sequence patterns across time.
- **Input:** 60 candles of OHLCV data (1-minute timeframe).
- **Output:** Probability score for BUY, SELL, or HOLD.
- **Training data:** Minimum 2 years of XAU/USD 1-minute historical data.
- **Framework:** TensorFlow / Keras.

#### 5.2.2 Transformer Model

- **Purpose:** Understand long-range market structure context.
- **Input:** 200 candles of 15-minute OHLCV data.
- **Output:** Directional bias (Bullish / Bearish / Neutral).
- **Framework:** PyTorch or TensorFlow.

#### 5.2.3 Random Forest

- **Purpose:** Multi-indicator confluence detection.
- **Input:** RSI, MACD, ATR, EMA 50/200, volume delta.
- **Output:** Signal confidence score (0.0 to 1.0).
- **Framework:** Scikit-learn.

#### 5.2.4 SMC Detector

- **Purpose:** Detect Smart Money Concept structures.
- **Detects:** Break of Structure (BOS), Change of Character (CHoCH), Fair Value Gaps (FVG), Supply and Demand zones.
- **Logic:** Pure rule-based Python — no ML required.
- **Output:** Structure type + price level + direction.

#### 5.2.5 Ensemble Voting

All four models vote on direction. A trade signal is only passed to Layer 3 when at least 3 of 4 models agree.

| Votes in Agreement | Action |
|---|---|
| 4 of 4 | Strong signal — pass to Layer 3 |
| 3 of 4 | Moderate signal — pass to Layer 3 |
| 2 of 4 or fewer | No trade — discard signal |

---

### 5.3 Layer 3 — AI Validator (Qwen3:8b)

The AI Validator uses a locally-running Qwen3:8b language model via Ollama to perform contextual validation of each trade signal. It acts as a second opinion that human traders would normally provide by reading the news before entering a trade.

**Prompt template sent to Qwen3:8b for each signal:**

```
Signal: {BUY | SELL}
Asset: XAU/USD
Entry price: {price}
Current DXY bias: {BULLISH | BEARISH | NEUTRAL}
Recent news headlines:
  - {headline_1}
  - {headline_2}
  - {headline_3}
Economic events next 4 hours: {events}

Should I take this trade? Reply YES or NO followed
by one sentence of reasoning. Nothing else.
```

The validator is intentionally kept simple. It only needs to catch obvious contextual conflicts — such as a BUY signal on gold during a strong USD rally driven by Fed hawkishness. It does not predict price.

---

### 5.4 Layer 4 — Risk Manager

Risk management rules are **absolute**. No other layer can override them. They are defined as constants at system startup.

| Rule | Value | Enforcement |
|---|---|---|
| Max daily loss | 5% of account balance | Hard block — no trades after breach |
| Max total drawdown | 10% of account balance | Hard block — system shuts down |
| Max trades per day | 3 trades | Hard block on 4th signal |
| Position sizing | ATR-based (1% risk per trade) | Calculated per trade dynamically |
| Stop loss | Mandatory on every order | Order rejected if SL not set |
| Take profit ratio | Minimum 1:2 Risk/Reward | Signal discarded if target not met |

**Position sizing formula:**

```
lot_size = (account_balance * risk_per_trade) / (stop_loss_pips * pip_value)

Where:
  risk_per_trade = 1% (0.01)
  stop_loss_pips = ATR(14) * 1.5
  pip_value      = $1 per 0.01 lot on XAU/USD
```

---

### 5.5 Layer 5 — Execution Engine

- Connect to MetaTrader 5 via the official Python MT5 library.
- Send market orders with pre-calculated SL and TP on every approved trade.
- Monitor open positions every 5 seconds for trailing stop updates.
- Close positions automatically when TP or SL is hit.
- Handle partial closes at 1:1 R/R to lock in profit on strong moves.

---

### 5.6 Layer 6 — Monitoring

| Feature | Implementation | Output |
|---|---|---|
| Trade journal | SQLite database | Every trade logged with full metadata |
| Telegram alerts | Telegram Bot API | Open, close, and daily summary messages |
| Performance dashboard | Flask + HTML | Live equity curve, win rate, drawdown gauge |
| Error logging | Python logging module | All errors written to rotating log files |

---

## 6. Project Structure

```
aurus/
  docs/
    SPECIFICATION.md
    data_flow.md
    model_design.md
    risk_management.md
    api_reference.md
  src/
    data/
      price_feed.py
      news_feed.py
      dxy_feed.py
      calendar_feed.py
      data_manager.py
    models/
      lstm_model.py
      transformer_model.py
      random_forest.py
      smc_detector.py
      ensemble.py
    validator/
      ai_validator.py
      prompt_builder.py
    risk/
      risk_manager.py
      position_sizer.py
    execution/
      mt5_connector.py
      trade_manager.py
    monitoring/
      trade_logger.py
      telegram_bot.py
      dashboard.py
    main.py
  tests/
    test_data.py
    test_models.py
    test_risk.py
    test_execution.py
  config/
    settings.py
  logs/
  requirements.txt
  README.md
```

---

## 7. Development Sprints

Development follows six sequential sprints. No sprint begins until the previous sprint is tested and approved.

| Sprint | Name | Deliverable | Duration |
|---|---|---|---|
| 1 | Data Pipeline | Live XAU/USD data flowing reliably from MT5 and APIs | 1 week |
| 2 | Pattern Detection | All four models built, trained, and tested on historical data | 3 weeks |
| 3 | AI Validator | Qwen3:8b integrated and validating signals correctly | 1 week |
| 4 | Risk Manager | All risk rules enforced with full test coverage | 1 week |
| 5 | Execution Engine | Live demo trades executing correctly on MT5 demo account | 1 week |
| 6 | Monitoring & Polish | Dashboard live, Telegram alerts working, full system test | 1 week |

**Total estimated development time: 8–10 weeks.**

Each sprint ends with a sprint review where all components are tested against defined acceptance criteria before proceeding.

---

## 8. Technology Stack

| Category | Technology | Version | Purpose |
|---|---|---|---|
| Language | Python | 3.11+ | All system components |
| ML Framework | TensorFlow / Keras | 2.x | LSTM and Transformer models |
| ML Framework | Scikit-learn | 1.x | Random Forest model |
| Local LLM | Ollama + Qwen3:8b | Latest | Trade signal validation |
| Broker API | MetaTrader5 (Python) | 5.x | Price data + order execution |
| Database | SQLite | 3.x | Trade journal and logging |
| Alerts | Telegram Bot API | Latest | Real-time notifications |
| Dashboard | Flask + HTML/CSS | 3.x | Performance monitoring UI |
| News API | Alpha Vantage / NewsAPI | Latest | Market news sentiment |
| Environment | Windows 10/11 | Current | Local development and runtime |

---

## 9. Risks and Constraints

### 9.1 Hardware Constraints

| Resource | Available | Implication |
|---|---|---|
| RAM | 16 GB | Models must be quantized or lightweight. Qwen3:8b fits comfortably. |
| CPU | AMD Ryzen 5 PRO 2600 (6-core, 3.4GHz) | Inference slower than GPU. Parallel model runs must be managed carefully. |
| GPU | None (CPU only) | No CUDA acceleration. Training will take hours rather than minutes. |
| Storage | Local SSD | Historical data and model weights stored locally. |

### 9.2 Project Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Model overfitting on training data | High | High | Walk-forward validation on out-of-sample data |
| API rate limiting on news/data feeds | Medium | Medium | Implement caching and fallback sources |
| MT5 connection drops during live session | Medium | High | Auto-reconnect logic with position state recovery |
| Qwen3 inference too slow for real-time use | Low | Medium | Pre-cache responses for common market conditions |
| Prop firm rule violation | Low | Critical | Risk manager is always the final decision authority |

---

## 10. Success Criteria

Aurus is considered successfully built when all of the following are met:

1. All 6 sprints completed with passing tests on each component.
2. System runs for 5 consecutive days on a demo account without crashing or manual intervention.
3. Backtesting on 12 months of historical XAU/USD data shows positive expectancy (profit factor > 1.5).
4. Maximum drawdown does not exceed 10% in any backtest period.
5. Win rate is above 45% with average R/R of 1:2 or better.
6. Telegram alerts fire correctly for every trade event.
7. All prop firm challenge rules are encoded and enforced by the risk manager.
8. System passes a live prop firm demo evaluation challenge.

---

## 11. Glossary

| Term | Definition |
|---|---|
| XAU/USD | The trading symbol for Gold (XAU) priced in US Dollars (USD). |
| BOS | Break of Structure — price breaking a previous swing high or low, indicating trend continuation. |
| CHoCH | Change of Character — price breaking structure in the opposite direction, signaling a potential trend reversal. |
| FVG | Fair Value Gap — an imbalance in price where a candle skips over a price range, leaving a gap that price often revisits. |
| S&D Zone | Supply and Demand Zone — price areas where institutional orders are likely resting. |
| ATR | Average True Range — a measure of market volatility used to set stop losses and calculate position sizes. |
| LSTM | Long Short-Term Memory — a type of neural network well-suited for learning patterns in sequential time-series data. |
| Ensemble | A method of combining multiple models to produce a more reliable prediction than any single model alone. |
| Prop Firm | Proprietary trading firm — provides funded accounts to traders who pass a performance evaluation challenge. |
| Drawdown | The peak-to-trough decline in account equity, measured as a percentage of the peak balance. |
| R/R | Risk-to-Reward ratio — the ratio of potential loss to potential gain on a trade. |
| Ollama | A tool for running large language models locally on a personal computer without internet. |
| EDA | Event-Driven Architecture — a system design pattern where components communicate by producing and consuming events. |

---

*Aurus v1.0 — Built with engineering discipline.*
