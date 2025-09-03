import asyncio

from spiders.asx_spider import AsxSpider
from business.services.parser_service import ParseService
from database.connection import DatabaseManager
from database.repositories.asx_repository import AsxInfoRepository
from core.utils import USERNAME


class SpiderService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.spider = AsxSpider()
        self.parser = ParseService()

    async def crawl_asx_info(self, asx_codes: list[str], year: str):
        tasks = []
        for asx_code in asx_codes:
            tasks.append(self.spider.fetch_announcements_by_code(asx_code, year))
        raw_datas = await asyncio.gather(*tasks)

        with self.db_manager.session() as session:
            repo = AsxInfoRepository(session)
            for raw_data in raw_datas:
                for item in raw_data:
                    if not repo.find_duplicate(item["asx_code"], item["title"], item["pub_date"]):
                        repo.create(
                            asx_code=item["asx_code"],
                            title=item["title"],
                            pub_date=item["pub_date"],
                            pdf_mask_url=item["pdf_mask_url"],
                            page_num=item["page_num"],
                            file_size=item["file_size"],
                            update_user=USERNAME
                        )

    async def sync_asx_act_url(self, asx_codes: list):
        tasks = []
        with self.db_manager.session() as session:
            repo = AsxInfoRepository(session)

            records = session.query(repo.model).filter(
                repo.model.asx_code.in_(asx_codes),
                repo.model.pdf_mask_url.isnot(None),
                repo.model.pdf_url.is_(None),
            ).all()

            for record in records:
                tasks.append(self._process_record(repo, record))
            await asyncio.gather(*tasks)
            session.commit()

    async def _process_record(self, repo, record):
        result = await self.spider.get_pdf_actual_url(record.pdf_mask_url)
        repo.update(record.id, pdf_url=result, pdf_mask_url=None, update_user=USERNAME)
