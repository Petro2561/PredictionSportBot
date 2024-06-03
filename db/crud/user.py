from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.crud.crud_base import CRUDBase
from db.models import User


class CRUDuser(CRUDBase):
    async def get_by_telegram_id(self, telegram_id: int, session: AsyncSession):
        db_obj = await session.execute(
            select(self.model).where(self.model.telegram_id == telegram_id)
        )
        return db_obj.scalars().first()
    
crud_user = CRUDuser(User)