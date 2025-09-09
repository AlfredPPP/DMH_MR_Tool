import aiohttp
import asyncio
import re
from asyncio import Semaphore
from datetime import datetime
from lxml import etree
from urllib.parse import urljoin
from config.settings import CONFIG

ASX_COOKIE_URL = "https://www.asx.com.au/markets/trade-our-cash-market/historical-announcements"
ASX_BASE_URL = "https://www.asx.com.au/asx/v2/statistics"
ASX_SEARCH_URL = f"{ASX_BASE_URL}/announcements.do"
ASX_TODAY_URL = f"{ASX_BASE_URL}/todayAnns.do"
ASX_PRE_DAY_URL = f"{ASX_BASE_URL}/prevBusDayAnns.do"
PROXY = "http://127.0.0.1:7890"
MAX_RETRIES = 3


class AsxSpider:
    def __init__(self):
        self.semaphore = Semaphore(CONFIG.spider.concurrent_downloads)

    async def fetch_announcements_by_code(self, asx_code: str, year: str) -> list[dict]:
        params = {
            "by": "asxCode",
            "asxCode": asx_code[:3],
            "timeframe": "Y",
            "year": year
        }
        result = []
        async with self.semaphore:
            async with aiohttp.ClientSession() as session:
                async with session.get(ASX_SEARCH_URL, params=params, proxy=PROXY) as resp:
                    html = await resp.text()
                    tree = etree.HTML(html)
                    for report in tree.xpath("//announcement_data//tbody/tr"):
                        title = re.sub("[\\t\\r\\n]", "", ''.join(report.xpath("./td[3]//a/text()")))
                        title = title.replace("/", " - ").strip()
                        page_num = re.search("\\d*", ''.join(report.xpath("./td[3]//a/span[1]/text()"))).group(0)
                        file_size = re.sub("[\\t\\r\\n]", '', ''.join(report.xpath("./td[3]//a/span[2]/text()")))
                        file_size = file_size.strip()
                        pub_date = re.sub("[\\t\\r\\n/]", '', ''.join(report.xpath("./td[1]/text()")))
                        pub_date = pub_date.strip()
                        pub_date = datetime.strptime(pub_date, "%d%m%Y")
                        pdf_mask_url = report.xpath("./td[3]//a/@href")[0]
                        pdf_mask_url = urljoin(ASX_BASE_URL, pdf_mask_url)
                        result.append({
                            "asx_code": asx_code,
                            "title": title,
                            "page_num": page_num,
                            "file_size": file_size,
                            "pub_date": pub_date,
                            "pdf_mask_url": pdf_mask_url,
                        })
        return result

    @staticmethod
    async def fetch_announcements_by_day(is_today: bool = False) -> list[dict]:
        result = []
        url = ASX_TODAY_URL if is_today else ASX_PRE_DAY_URL
        async with aiohttp.ClientSession() as session:
            async with session.get(url, proxy=PROXY) as resp:
                html = await resp.text()
                tree = etree.HTML(html)
                for report in tree.xpath("//announcement_data//table/tr"):
                    if not report.xpath("./td[1]//text()"):
                        continue
                    asx_code = re.sub("[\\t\\r\\n]", "", ''.join(report.xpath("./td[1]//text()"))).strip()
                    title = re.sub("[\\t\\r\\n]", "", ''.join(report.xpath("./td[4]//a/text()")))
                    title = title.replace("/", " - ").strip()
                    page_num = re.search("\\d*", ''.join(report.xpath("./td[4]//a/span[1]/text()"))).group(0)
                    file_size = re.sub("[\\t\\r\\n]", '', ''.join(report.xpath("./td[4]//a/span[2]/text()")))
                    file_size = file_size.strip()
                    pub_date = re.sub("[\\t\\r\\n/]", '', ''.join(report.xpath("./td[2]/text()")))
                    pub_date = pub_date.strip()
                    pub_date = datetime.strptime(pub_date, "%d%m%Y")
                    pdf_mask_url = report.xpath("./td[4]//a/@href")[0]
                    pdf_mask_url = urljoin(ASX_BASE_URL, pdf_mask_url)
                    result.append({
                        "asx_code": asx_code,
                        "title": title,
                        "page_num": page_num,
                        "file_size": file_size,
                        "pub_date": pub_date,
                        "pdf_mask_url": pdf_mask_url,
                    })
        return result

    async def download_pdf(self, pdf_url: str, save_path: str) -> None:
        retries = 0
        last_exception = None

        while retries < MAX_RETRIES:
            try:
                async with self.semaphore:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(pdf_url, proxy=PROXY) as resp:
                            if resp.status == 200:
                                with open(save_path, 'wb') as f:
                                    while True:
                                        chunk = await resp.content.read(1024)
                                        if not chunk:
                                            break
                                        f.write(chunk)
                                return
                            else:
                                retries += 1
                                await asyncio.sleep(2 ** retries)
            except Exception as e:
                last_exception = e
                retries += 1
                await asyncio.sleep(2 ** retries)

        raise Exception(
            f"Failed to download {pdf_url} after {MAX_RETRIES} attempts. Last exception: {last_exception}"
        )

    async def get_pdf_actual_url(self, mask_url: str) -> str:
        async with self.semaphore:
            async with aiohttp.ClientSession() as session:
                async with session.get(mask_url, proxy=PROXY) as resp:
                    html = await resp.text()
                    tree = etree.HTML(html)
                    pdf_url = tree.xpath("//input[@name='pdfURL']/@value")[0]
        return pdf_url


def my_test():
    a = AsxSpider()
    try:
        asyncio.create_task(a.fetch_announcements_by_code('PLUS', '2025'))
    except RuntimeError:
        b = asyncio.run(a.fetch_announcements_by_day(is_today=True))
        print(b)


if __name__ == "__main__":
    my_test()
