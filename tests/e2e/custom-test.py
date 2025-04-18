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
