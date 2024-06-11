from db.crud.crud_base import CRUDBase
from db.models import ResetPoints


class CRUDResetPoints(CRUDBase):
    pass


crud_resetpoints = CRUDResetPoints(ResetPoints)
