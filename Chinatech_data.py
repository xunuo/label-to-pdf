import psycopg2
from psycopg2.extras import Json
import asyncio
from playwright.async_api import async_playwright
DB_CONFIG = {
    "dbname": "postgres",
    "user": "postgres",
    "password": "9740377549",
    "host": "localhost",
    "port": 5432
}

def insert_article(metadata,content,TableName = "ChinaTech"):
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
    print(f"✅ Article inserted into the database!")   

def Chinamain(url = "https://www.chinadaily.com.cn/business/tech"):
    conn = psycopg2.connect(host='localhost',dbname='postgres',user='postgres',password = "9740377549",port = 5432)
    cur = conn.cursor()
    cur.execute("""
                CREATE TABLE IF NOT EXISTS ChinaTech(
                    id SERIAL PRIMARY KEY,
                    metadata JSONB,
                    content TEXT NOT NULL);
                """)
    conn.commit()
    cur.close()
    conn.close()
    asyncio.run(script(url))
    
    
async def script(url = "https://www.chinadaily.com.cn/business/tech"):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
             headless=True,
             args=["--disable-blink-features=AutomationControlled"]
             )
        page = await browser.new_page()
        await page.goto(url,timeout=60000,wait_until='domcontentloaded')
        articles = await page.locator('div.tw3_01_2 span.tw3_01_2_t h4').evaluate_all("""
            elements => elements.map(element => ({
                title: element.innerText.trim(),
                href: element.querySelector('a')?.getAttribute('href')
            }))
        """)
        print(len(articles))
        urls = [f"https:{article['href']}" if article["href"].startswith('/')
                else article["href"] 
                for article in articles if article["href"]]
        await asyncio.gather(*(subscript(url) for url in urls))
        await page.close()
        await browser.close()

async def subscript(url ="https://www.chinadaily.com.cn/a/202502/18/WS67b44ba5a310c240449d5ea3.html"):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True,
                                          args=["--disable-blink-features=AutomationControlled"]
             )
        page = await browser.new_page()
        try:
            await page.goto(url,timeout=60000,wait_until="domcontentloaded")
            metadata = {}
            metadata['title'] = await page.locator('meta[property = "og:title"]').get_attribute("content")
            metadata['description'] = await page.locator('meta[name = "description"]').get_attribute("content")
            metadata['author'] = await page.locator('meta[name = "author"]').get_attribute("content")
            metadata['url'] = url
            # Select the 0th div inside the article container and then find the <p> tag
            content = await page.locator('#Content p').all_text_contents()
            content = " ".join(content)
            # print(content) 
            insert_article(metadata,content) 
        except Exception as e:
             print(f"❌{e}")
        await page.close()
        await browser.close()

if __name__ == "__main__":
    Chinamain()
    # asyncio.run(subscript())