import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright
import time

print("✅ Script started successfully.")

# Google Sheets API setup
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file",
         "https://www.googleapis.com/auth/drive"]

credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
gc = gspread.authorize(credentials)
sheet = gc.open("Tweet Scraping").sheet1

urls = sheet.col_values(1)[1:]
completed_rows = sheet.col_values(2)[1:]

# Determine starting point
start_index = len([row for row in completed_rows if row.strip() != ""])
print(f"✅ Resuming from URL index: {start_index}")

# Function to scrape tweet text clearly
def scrape_tweet(page, url):
    print(f"➡️ Scraping URL: {url}")
    tweet_text = "Not found"

    try:
        page.goto(url)
        page.wait_for_selector('article div[data-testid="tweetText"]', timeout=15000)
        time.sleep(3)

        tweet_element = page.query_selector('article div[data-testid="tweetText"]')
        if tweet_element:
            tweet_text = tweet_element.inner_text()
            print(f"✅ Scraped tweet: {tweet_text[:30]}...")
        else:
            print("⚠️ Tweet text not found.")

    except Exception as e:
        print(f"❌ Error: {str(e)}")

    return tweet_text

batch_size = 50
current_batch = urls[start_index:start_index + batch_size]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    for i, url in enumerate(current_batch, start=start_index + 2):
        tweet_text = scrape_tweet(page, url)
        sheet.update_cell(i, 2, tweet_text)
        time.sleep(5)

    browser.close()

print("🎉 Batch completed and Google Sheet updated successfully!")
