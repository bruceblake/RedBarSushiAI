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
