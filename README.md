# VFS Appointment Bot

[![GitHub License](https://img.shields.io/github/license/ranjan-mohanty/vfs-appointment-bot)](https://github.com/ranjan-mohanty/vfs-appointment-bot/blob/main/LICENSE)
[![GitHub Release](https://img.shields.io/github/v/release/ranjan-mohanty/vfs-appointment-bot?logo=GitHub)](https://github.com/ranjan-mohanty/vfs-appointment-bot/releases)
[![PyPI - Version](https://img.shields.io/pypi/v/vfs-appointment-bot?logo=pypi)](https://pypi.org/project/vfs-appointment-bot)
[![Downloads](https://static.pepy.tech/badge/vfs-appointment-bot)](https://pepy.tech/project/vfs-appointment-bot)
[![Endpoint Badge](https://img.shields.io/endpoint?url=https%3A%2F%2Fhits.dwyl.com%2Franjan-mohanty%2Fvfs-appointment-bot.json&style=flat&logo=GitHub&label=views)](https://github.com/ranjan-mohanty/vfs-appointment-bot)
[![GitHub forks](https://img.shields.io/github/forks/ranjan-mohanty/vfs-appointment-bot)](https://github.com/ranjan-mohanty/vfs-appointment-bot/forks)
[![GitHub Repo stars](https://img.shields.io/github/stars/ranjan-mohanty/vfs-appointment-bot)](https://github.com/ranjan-mohanty/vfs-appointment-bot/stargazers)

[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/ranjan-mohanty/vfs-appointment-bot/build.yml)](https://github.com/ranjan-mohanty/vfs-appointment-bot/actions/workflows/build.yml)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/21f1ecd428ec4342980020a6ef383439)](https://app.codacy.com/gh/ranjan-mohanty/vfs-appointment-bot/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/ranjan-mohanty/vfs-appointment-bot/badge)](https://securityscorecards.dev/viewer/?uri=github.com/ranjan-mohanty/vfs-appointment-bot)
[![GitHub Issues or Pull Requests](https://img.shields.io/github/issues/ranjan-mohanty/vfs-appointment-bot)](https://github.com/ranjan-mohanty/vfs-appointment-bot/issues)
![Libraries.io dependency status for GitHub repo](https://img.shields.io/librariesio/github/ranjan-mohanty/vfs-appointment-bot)
[![Twitter](https://img.shields.io/twitter/url?style=social&url=https%3A%2F%2Fgithub.com%2Franjan-mohanty%2Fvfs-appointment-bot)](https://twitter.com/intent/tweet?text=Check%20this%20out%20&url=https%3A%2F%2Fgithub.com%2Franjan-mohanty%2Fvfs-appointment-bot)

**vfs-appointment-bot** is a Python automation script that monitors the VFS Global visa appointment portal for available slots and notifies you via email, Telegram, or Twilio SMS/call as soon as one opens up.

## Installation

### 1. Using pip (recommended)

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows

# Install the package
pip install vfs-appointment-bot

# Install the browser binary (patchright wraps Playwright with bot-detection evasion)
patchright install
```

### 2. Manual installation (from source)

```bash
git clone https://github.com/ranjan-mohanty/vfs-appointment-bot
cd vfs-appointment-bot

python3 -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows

pip install poetry
poetry install

# Install browser binaries
patchright install
```

> **Note:** This project uses [patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) instead of the plain `playwright` + `playwright-stealth` combination. Patchright is a patched Playwright binary that evades CDP/WebDriver fingerprinting at the binary level — no extra stealth plugin call is required and it is significantly more effective against modern bot-detection systems (Cloudflare Turnstile, etc.).

## Configuration

1. Download the [`config/config.ini`](https://raw.githubusercontent.com/ranjan-mohanty/vfs-appointment-bot/main/config/config.ini) template:

   ```bash
   curl -L https://raw.githubusercontent.com/ranjan-mohanty/vfs-appointment-bot/main/config/config.ini -o config.ini
   ```

2. Edit the file with your VFS credentials and notification preferences (see [Notification Channels](#notification-channels) below).

3. Export the config file path:

   ```bash
   export VFS_BOT_CONFIG_PATH=<your-config-path>/config.ini   # Linux/macOS
   set VFS_BOT_CONFIG_PATH=<your-config-path>\config.ini      # Windows
   ```

**Manual installations** can edit `config/config.ini` directly without the environment variable.

## Usage

### Required arguments

| Flag | Long form | Description |
|------|-----------|-------------|
| `-sc` | `--source-country-code` | ISO 3166-1 alpha-2 code of the country you are applying *from* |
| `-dc` | `--destination-country-code` | ISO 3166-1 alpha-2 code of the embassy/VFS country |

### Running the bot

**Option 1 — Interactive prompts (recommended for first-time use):**

```bash
vfs-appointment-bot -sc IN -dc DE
```

The bot will prompt you to enter the required appointment parameters.

**Option 2 — Non-interactive with `-ap` / `--appointment-params`:**

```bash
vfs-appointment-bot -sc IN -dc DE -ap "visa_center=Berlin,visa_category=National Visa,visa_sub_category=Employment"
```

Appointment parameters are comma-separated `key=value` pairs. Values containing spaces do not need quoting within the pair, but the whole argument string should be quoted in your shell.

**Check the installed version:**

```bash
vfs-appointment-bot --version
```

## Notification Channels

Three notification channels are supported. Configure them in `config.ini` under `[notification]`:

```ini
[notification]
channels = email          # comma-separated: email, telegram, twilio
```

### Email (Gmail)

Requires a Gmail **App Password** — not your regular password. Generate one at:
https://support.google.com/accounts/answer/185833

```ini
[email]
email    = your.address@gmail.com
password = your-app-password
```

### Twilio (SMS & Voice Call)

```ini
[twilio]
account_sid  = ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
auth_token   = your-auth-token
to_num       = +1234567890     ; recipient number (E.164 format)
from_num     = +0987654321     ; your Twilio number (E.164 format)
sms_enabled  = True            ; default: True
call_enabled = False           ; default: False
url          = https://...     ; TwiML URL (only needed if call_enabled = True)
```

> **Important:** Set `channels = twilio` (not `slack`) in `[notification]`.

### Telegram

Create a bot via [@BotFather](https://telegram.me/BotFather) and get your token. Find your `chat_id` with the `/my_id` command.

```ini
[telegram]
bot_token  = 123456789:AAF...
chat_id    = 987654321
parse_mode = Markdown
```

## Supported Countries and Appointment Parameters

| Route | Required appointment parameters |
|-------|---------------------------------|
| India (IN) → Germany (DE) | `visa_center`, `visa_category`, `visa_sub_category` |
| Iraq (IQ) → Germany (DE) | `visa_center`, `visa_category`, `visa_sub_category` |
| Morocco (MA) → Italy (IT) | `visa_center`, `visa_category`, `visa_sub_category`, `payment_mode` |
| Azerbaijan (AZ) → Italy (IT) | `visa_center`, `visa_category`, `visa_sub_category` |
| Angola (AO) → Portugal (PT) | `visa_center`, `visa_category`, `visa_sub_category` |

> **Note:** The appointment parameter names and available values vary by country and visa type. Always check the VFS Global website for the latest options.

## Browser Configuration

```ini
[browser]
type      = firefox    ; firefox (default), chromium, or webkit
headless  = true       ; set to false to watch the browser in action
```

Firefox with `patchright` offers the best bot-detection resistance. Switch to `chromium` if you encounter rendering issues.

## Known Issues

### 1. Login failures after frequent requests

VFS Global may temporarily block access if the bot runs too frequently.

- **Workaround:** Increase the `interval` setting in `[default]` (default: 180 seconds). Wait at least 2 hours after a block before retrying.

### 2. CAPTCHA / Cloudflare Turnstile

The VFS website uses Cloudflare Turnstile on some portals. The bot waits 5 seconds for the challenge to auto-resolve. If VFS enables an interactive CAPTCHA challenge, the bot cannot solve it automatically.

- **Workaround:** Try running with `headless = false` to use Firefox in headed mode. Chromium (`type = chromium`) sometimes has better auto-resolution rates.

### 3. Portugal (AO→PT) booking form — unverified

The AO→PT site runs a newer VFS platform version ("AR-8.0.28") with a redesigned UI. The login step is confirmed; the booking form selectors are a best-effort estimate. If the bot fails after login, the `check_for_appointment` selectors in `vfs_bot_pt.py` will need updating.

## Extending Country Support

To add support for a new country:

1. Create `vfs_appointment_bot/vfs_bot/vfs_bot_XX.py` (where `XX` is the destination country code) as a subclass of `VfsBot`.
2. Implement `pre_login_steps()`, `login()`, and `check_for_appointment()`.
3. Register the new class in `vfs_bot_factory.py`.
4. Add the VFS login URL to `config/vfs_urls.ini` under `[vfs-url]` as `SC-DC = <url>`.

## Contributing

We welcome contributions! To get involved:

- **Report bugs:** Open an issue on the [GitHub repository](https://github.com/ranjan-mohanty/vfs-appointment-bot/issues).
- **Suggest features:** Create an issue or pull request.
- **Submit code:** Follow the [contributing guide](CONTRIBUTING.md).

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=ranjan-mohanty/vfs-appointment-bot&type=Date)](https://star-history.com/#ranjan-mohanty/vfs-appointment-bot&Date)

## Disclaimer

This script is provided as-is and is not affiliated with VFS Global. You are responsible for complying with VFS Global's terms and conditions. Website structures and appointment availability mechanisms may change without notice.
