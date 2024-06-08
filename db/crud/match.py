from db.crud.crud_base import CRUDBase
from db.models import Match


class CRUDMatch(CRUDBase):
    pass


crud_group_history = CRUDMatch(Match)