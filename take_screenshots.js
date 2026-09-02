const puppeteer = require('puppeteer');

(async () => {
  let browser;
  try {
    browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    const page = await browser.newPage();

    // 1. Capture Widget page
    await page.setViewport({ width: 1280, height: 800 });
    console.log('Opening http://localhost:5173...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle2' });
    await page.screenshot({ path: 'screenshots/student_chat_screenshot_real.jpg', type: 'jpeg' });
    console.log('Saved student_chat_screenshot_real.jpg');

    // 2. Capture Mobile view of Widget
    await page.setViewport({ width: 375, height: 812 });
    await page.screenshot({ path: 'screenshots/mobile_telugu_widget_real.jpg', type: 'jpeg' });
    console.log('Saved mobile_telugu_widget_real.jpg');

    // 3. Capture Admin page
    await page.setViewport({ width: 1280, height: 800 });
    console.log('Opening http://localhost:5174...');
    await page.goto('http://localhost:5174', { waitUntil: 'networkidle2' });
    await page.screenshot({ path: 'screenshots/admin_dashboard_screenshot_real.jpg', type: 'jpeg' });
    console.log('Saved admin_dashboard_screenshot_real.jpg');
    
  } catch (error) {
    console.error('Error during screenshots:', error);
  } finally {
    if (browser) {
      await browser.close();
    }
  }
})();
