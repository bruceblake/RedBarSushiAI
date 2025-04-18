# Using Playwright on Arch Linux

Playwright requires specific system dependencies to run properly. Since Arch Linux is not officially supported by Playwright, we need to take a few extra steps to make it work correctly.

## Installation

We've provided two scripts to help you set up Playwright on Arch Linux:

1. First, install Playwright and Python dependencies:
```bash
./install-playwright-pip.sh
```

2. Then, install the required system dependencies:
```bash
./install-playwright-arch-deps.sh
```

## Fixing Dependency Issues

If you see warnings about missing dependencies, you can:

1. Set the environment variable to skip validation:
```bash
export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1
```

2. Install the required dependencies manually:
```bash
sudo pacman -Syu --needed --noconfirm \
    nss \
    nspr \
    atk \
    at-spi2-atk \
    cups \
    libx11 \
    libxcomposite \
    libxdamage \
    libxext \
    libxfixes \
    libxrandr \
    mesa \
    libxcb \
    libxkbcommon \
    pango \
    cairo \
    alsa-lib \
    at-spi2-core
```

## Running Tests

Once everything is set up:

1. Activate the virtual environment:
```bash
source venv/bin/activate
```

2. Run the simple test to verify everything works:
```bash
python -m pytest tests/e2e/custom-test.py
```

3. Run comprehensive tests:
```bash
./run-comprehensive-tests.sh
```

## Using with npm scripts

You can also use the npm scripts we've configured:

```bash
# Run simple test
npm run test:e2e:simple

# Run all tests
npm run test:e2e

# Run with UI (headed mode)
npm run test:e2e:ui
```

## Common Issues

### Browser Fails to Launch

If the browser fails to launch with errors about missing libraries:

1. Try installing additional dependencies:
```bash
sudo pacman -S gtk3 libdrm libxshmfence glib2
```

2. Check the specific error message for the missing library name and install it:
```bash
sudo pacman -S package-name
```

### Missing Font Issues

If you see issues with fonts:

```bash
sudo pacman -S noto-fonts ttf-dejavu
```

### Electron-based Browser Failures

If you're having issues with the default browser, try using Firefox instead:

```bash
python -m playwright install firefox
BROWSER=firefox python -m pytest tests/e2e/custom-test.py
```