#\!/bin/bash

echo "Installing Playwright for Arch Linux"

# Install Python Playwright from official repos
sudo pacman -S --noconfirm python-playwright python-pytest-playwright

# Install browser dependencies
python -m playwright install-deps

# Install specific browsers
python -m playwright install chromium

# Update package.json to use Python-based Playwright
cat > playwright-arch-install.js << 'EOF'
const fs = require('fs');

try {
  const packageJson = JSON.parse(fs.readFileSync('package.json', 'utf8'));
  
  // Update the scripts to use Python Playwright
  if (packageJson.scripts) {
    packageJson.scripts['test:e2e'] = 'python -m pytest tests/e2e --browser chromium';
    packageJson.scripts['test:e2e:ui'] = 'python -m pytest tests/e2e --browser chromium --headed';
    packageJson.scripts['test:e2e:simple'] = 'python -m pytest tests/e2e/custom-test.py --browser chromium';
    packageJson.scripts['test:e2e:comprehensive'] = 'python -m pytest tests/e2e/comprehensive_test.py --browser chromium';
    packageJson.scripts['test:api'] = 'python -m pytest tests/e2e/api_tests.py --browser chromium';
    packageJson.scripts['install:playwright'] = 'python -m playwright install chromium';
  }
  
  // Remove @playwright/test from devDependencies
  if (packageJson.devDependencies && packageJson.devDependencies['@playwright/test']) {
    delete packageJson.devDependencies['@playwright/test'];
  }
  
  // Write the updated package.json
  fs.writeFileSync('package.json', JSON.stringify(packageJson, null, 2));
  console.log('Updated package.json to use Python-based Playwright');
} catch (error) {
  console.error('Error updating package.json:', error);
}
EOF

# Run the update script
node playwright-arch-install.js

# Create Python versions of the test files
mkdir -p tests/e2e/test-data

cat > tests/e2e/custom-test.py << 'EOF'
import pytest
from playwright.sync_api import expect

def test_basic_functionality(page):
    # Create a simple HTML page
    page.set_content("""
    <html>
      <head>
        <title>Test Page</title>
      </head>
      <body>
        <h1>RedBarSushiAI Test</h1>
        <p id="desc">This is a simple test page for RedBarSushiAI.</p>
        <button id="btn">Click Me</button>
        <div id="result"></div>
        
        <script>
          document.getElementById('btn').addEventListener('click', () => {
            document.getElementById('result').textContent = 'Button clicked\!';
          });
        </script>
      </body>
    </html>
    """)
    
    # Verify the page content
    expect(page.locator('h1')).to_have_text('RedBarSushiAI Test')
    
    # Click the button
    page.click('#btn')
    
    # Verify the result
    expect(page.locator('#result')).to_have_text('Button clicked\!')
EOF

cat > tests/e2e/conftest.py << 'EOF'
import os
import pytest
from playwright.sync_api import sync_playwright

@pytest.fixture(scope="session")
def browser_type(playwright):
    browser_name = os.environ.get("BROWSER", "chromium")
    if browser_name == "chromium":
        return playwright.chromium
    elif browser_name == "firefox":
        return playwright.firefox
    elif browser_name == "webkit":
        return playwright.webkit
    else:
        raise ValueError(f"Unsupported browser: {browser_name}")

@pytest.fixture(scope="session")
def browser(browser_type):
    browser = browser_type.launch(headless=not bool(os.environ.get("HEADED", False)))
    yield browser
    browser.close()

@pytest.fixture
def page(browser):
    page = browser.new_page()
    yield page
    page.close()

@pytest.fixture(scope="session")
def playwright():
    with sync_playwright() as playwright:
        yield playwright
EOF

echo "Arch Linux Playwright installation complete"

