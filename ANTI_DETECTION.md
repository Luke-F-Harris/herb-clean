# Anti-Detection Features

This document details all the anti-detection mechanisms built into the bot.

## Keyboard Input Randomization

### Key Press Timing
Every single keypress has **unique timing** to avoid pattern detection:

**Press Duration** (time key is held down):
- Uses **Gamma distribution** (right-skewed, natural variance)
- Range: 30-200ms
- Mean: ~60-120ms
- Never the same twice

**Pre-Key Delay** (hand movement to keyboard):
- **First press after mouse**: 150-400ms (simulates hand moving from mouse)
- **Subsequent presses**: 50-150ms (hand already near keyboard)
- Context-aware: knows if you just used keyboard recently

**Example ESC press timing:**
```
Press 1: 180ms travel + 85ms hold
Press 2: 95ms travel + 112ms hold
Press 3: 220ms travel + 67ms hold
```
All different, all realistic!

### Bank Closing Variation

**Random method selection:**
- **70% ESC key** (default)
- **30% Click close button**
- Configurable in `config/default_config.yaml`

Real players mix both methods. Never doing the same thing 100% of the time is critical for appearing human.

**Can use ESC-only:**
```yaml
bank:
  esc_chance: 1.0  # 100% ESC if you don't have close button template
```

## Mouse Movement

### Bezier Curves
- Cubic Bezier curves with 2 randomized control points
- Variable speed: slow start, fast middle, slow end
- **30% overshoot chance** with correction movement
- Speed: 200-400 pixels/second (randomized)

### Click Randomization

**Position:**
- Gaussian distribution centered on target
- Sigma = width / 6 (tight cluster, not perfectly centered)
- Each click lands in a slightly different spot

**Duration:**
- Gamma distribution: 50-200ms
- Right-skewed (occasional longer holds)

## Action Delays

### Timing Distribution
All delays use **Gamma distribution** (not uniform):
- Right-skewed: most actions quick, occasional longer pauses
- Herb click: ~600ms mean (configurable)
- Bank actions: ~800ms mean

### Fatigue System
After **30 minutes**, performance degrades:
- **10-50% slowdown** on all actions
- **1-5% misclick rate** (increases with fatigue)
- **Attention lapses**: 1-5 second pauses

### Think Pauses
- **5% chance** per action of brief "thinking" pause
- Duration: 500-2000ms
- Simulates momentary distraction/thought

### Micro-Pauses
- **2% chance** per action
- Duration: 300-1500ms
- Simulates brief attention shifts

## Break Schedule

### Micro-Breaks
- **Interval**: 8-15 minutes (randomized)
- **Duration**: 2-10 seconds
- Simulates checking something quickly

### Long Breaks
- **Interval**: 45-90 minutes (randomized)
- **Duration**: 1-5 minutes
- Simulates getting up, checking phone, etc.

### Break Recovery
- Breaks reduce accumulated fatigue
- Longer breaks = more recovery
- 5-minute break essentially resets fatigue

## Attention Drift

### Random Mouse Movements
- **3% chance** per action (increases with fatigue)
- Targets: minimap (50%), chat (33%), random (17%)
- Duration: 0.3-2 seconds at drift location

### Idle Movements
- **10% chance** during waits
- Small movements: 1-5 pixels
- Simulates hand tremor/micro-adjustments

## Pattern Breaking

### Why Variation Matters

**Bad (detectable):**
```
Action 1: 600ms delay, 100ms click
Action 2: 600ms delay, 100ms click
Action 3: 600ms delay, 100ms click
```
Perfect pattern = instant ban

**Good (this bot):**
```
Action 1: 547ms delay, 87ms click, ESC close
Action 2: 681ms delay, 123ms click, click X close
Action 3: 592ms delay + 1200ms think pause, 94ms click, ESC close
```
Natural variance = human-like

### Multiple Layers of Randomness

Every action has **5+ sources of randomness**:
1. Base timing (Gamma distribution)
2. Fatigue multiplier
3. Think pause chance
4. Micro-pause chance
5. Movement path (Bezier control points)
6. Click position (Gaussian)
7. Method variation (ESC vs click)

## Configuration Tuning

### Speed vs Safety

**Aggressive** (faster, higher risk):
```yaml
timing:
  click_herb_mean: 400
  click_herb_std: 100
breaks:
  micro:
    interval: [900, 1200]  # Less frequent
attention:
  drift_chance: 0.01  # Rarely drift
bank:
  esc_chance: 1.0  # Always ESC (fastest)
```

**Conservative** (slower, safer):
```yaml
timing:
  click_herb_mean: 800
  click_herb_std: 250
breaks:
  micro:
    interval: [300, 600]  # More frequent
attention:
  drift_chance: 0.05  # More drift
bank:
  esc_chance: 0.50  # 50/50 ESC vs click
```

## What Makes This Bot Different

Most bots fail because they:
1. ❌ Use uniform random delays
2. ❌ Click same exact spot every time
3. ❌ Never make mistakes
4. ❌ Never take breaks
5. ❌ Move mouse in straight lines
6. ❌ Have perfect, inhuman consistency

This bot:
1. ✅ Uses statistical distributions (Gamma, Gaussian)
2. ✅ Varies click position naturally
3. ✅ Simulates fatigue and mistakes
4. ✅ Takes realistic breaks
5. ✅ Uses Bezier curves with overshoot
6. ✅ Has 5+ layers of variance per action

## Detection Risk Factors

### Low Risk
- ✅ Randomized timing with Gamma distribution
- ✅ Variable action methods (ESC vs click)
- ✅ Fatigue simulation
- ✅ Regular breaks
- ✅ Natural mouse movement

### Medium Risk
- ⚠️ Playing for 4+ hours
- ⚠️ Using aggressive timing settings
- ⚠️ Not taking long breaks

### High Risk
- ⛔ Running 24/7
- ⛔ Multiple bots on same IP
- ⛔ Botting on high-value account
- ⛔ Using same patterns daily

## Best Practices

1. **Start Conservative**: Use default/slow settings first
2. **Vary Schedule**: Don't bot same hours every day
3. **Mix Legitimate Play**: Play manually sometimes
4. **Monitor Bans**: If you get banned, settings were too aggressive
5. **Session Limits**: Respect the 4-hour maximum
6. **Take Breaks**: Let the break scheduler work

## Disclaimer

**No bot is undetectable.** Jagex has sophisticated behavioral analysis. With enough data, any pattern can be detected. This bot minimizes risk through extensive randomization, but the safest option is always to play manually.

Use at your own risk.
