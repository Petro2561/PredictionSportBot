from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.crud.crud_base import CRUDBase
from db.models import Tour

class CRUDGroupHistory(CRUDBase):
    async def get_tour_by_id(self, tour_id: int, session: AsyncSession):
        db_obj = await session.execute(
            select(self.model).where(self.model.id == tour_id)
        )
        return db_obj.scalars().first()
    
crud_tour = CRUDGroupHistory(Tour)