import psycopg2
from psycopg2.extras import Json
import asyncio
from playwright.async_api import async_playwright
i = 1
DB_CONFIG = {
    "dbname": "postgres",
    "user": "postgres",
    "password": "9740377549",
    "host": "localhost",
    "port": 5432
}
def insert_article(metadata,content,TableName = "Globaltech"):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    insert_sql =f"""
    INSERT INTO {TableName}(metadata,content)
    VALUES (%s,%s);
                """
    cur.execute(insert_sql,(Json(metadata),content))
    conn.commit()
    cur.close()
    conn.close()


def Globalmain(url = "https://techcrunch.com/latest/"):
    conn = psycopg2.connect(host='localhost',dbname='postgres',user='postgres',password = "9740377549",port = 5432)
    cur = conn.cursor()
    cur.execute("""
                CREATE TABLE IF NOT EXISTS GlobalTech(
                    id SERIAL PRIMARY KEY,
                    metadata JSONB,
                    content TEXT NOT NULL);
                """)
    conn.commit()
    cur.close()
    conn.close()
    articles = asyncio.run(script(url))
    # asyncio.run(subscript())

async def script(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
             args=["--disable-blink-features=AutomationControlled"]
             )
        page = await browser.new_page()
        await page.goto(url,timeout=60000,wait_until='domcontentloaded')
        articles = await page.locator('h3.loop-card__title').evaluate_all(
            """
            elements =>elements.map(element=>({
                title : element.innerText.trim(),
                href : element.querySelector('a')?.getAttribute('data-destinationlink')
            }))"""
        )
        print(len(articles))
        urls = [article["href"] for article in articles if article["href"]]
        await asyncio.gather(*(subscript(url) for url in urls))
        await page.close()
        await browser.close()
        
async def subscript(url ="https://techcrunch.com/2025/02/21/nvidia-ceo-jensen-huang-says-market-got-it-wrong-about-deepseeks-impact/"):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(url,timeout=60000,wait_until="domcontentloaded")
            metadata = {}
            metadata['title'] = await page.locator('meta[property = "og:title"]').get_attribute("content")
            metadata['description'] = await page.locator('meta[property = "og:description"]').get_attribute("content")
            metadata['author'] = await page.locator('meta[name = "author"]').get_attribute("content")
            metadata['url'] = url
            content = await page.locator('div.wp-block-post-content p.wp-block-paragraph').all_text_contents()
            content =" ".join(content)
            insert_article(metadata,content)            
        except Exception as e:
             print(f"❌{e}")
        await page.close()
        await browser.close()



if __name__ == "__main__":
    Globalmain()