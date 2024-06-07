from db.crud.crud_base import CRUDBase
from db.models import GroupHistory


class CRUDGroupHistory(CRUDBase):
    pass


crud_group_history = CRUDGroupHistory(GroupHistory)
