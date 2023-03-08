import decimal
from datetime import date, datetime
from typing import Union
from pydantic import BaseModel
from pydantic import condecimal

class ProductBase(BaseModel):
    EAN: int
    source: int

class SimpleProduct(BaseModel):
    EAN: int
    product_name: str
    class Config:
        orm_mode = True

class ItemBase(BaseModel):
    EAN: int
    current_weight: int

class CreateProduct(ProductBase):
    product_name: str
    producer: str
    net_weight: condecimal(max_digits = 8, decimal_places=2)
    last_update: datetime

class WeightProduct(BaseModel):
    EAN: int
    max_weight: condecimal(max_digits = 8, decimal_places=2)

class UpdateProduct(CreateProduct):
    pass

class AddItem(ItemBase):
    shelf: int
    pos_x: int
    pos_y: int
    add_time: datetime
    in_time: datetime

class ViewProduct(ProductBase):
    product_name: str
    producer: str
    net_weight: condecimal(max_digits = 8, decimal_places=2)
    max_weight: condecimal(max_digits = 8, decimal_places=2)
    last_update: datetime
    class Config:
        orm_mode = True

class ViewItems(ItemBase):
    expiry_date: date
    batch: str
    shelf: int
    pos_x: int
    pos_y: int
    comment: str
    class Config:
        orm_mode = True

class PhotoBase(BaseModel):
    item_id: int
    photo: bytes
    taken_at: datetime

class ViewPhoto(PhotoBase):
    class Config:
        orm_mode = True

class CreatePhoto(PhotoBase):
    pass

class ApiPhoto(BaseModel):
    photo: bytes
    taken_at: datetime
    class Config:
        orm_mode = True

class ApiItemBase(ItemBase):
    item_id: int
    net_weight: Union[condecimal(max_digits = 8, decimal_places=2), None] = None
    max_weight: Union[condecimal(max_digits = 8, decimal_places=2), None] = None
    expiry_date: Union[date, None] = None

class ApiItem(ApiItemBase):
    product_name: str
    current_weight: condecimal(max_digits = 8, decimal_places=2)
    batch: Union[str, None] = None
    comment: Union[str, None] = None
    photos: Union[list[ApiPhoto], None] = None
    shelf: int
    class Config:
        orm_mode = True

class ApiUpdateItem(BaseModel):
    net_weight: Union[condecimal(max_digits = 8, decimal_places=2), None] = None
    max_weight: Union[condecimal(max_digits = 8, decimal_places=2), None] = None
    expiry_date: Union[date, None] = None
    batch: Union[str, None] = None
    comment: Union[str, None] = None

class ApiInventoryItem(ApiItemBase):
    product_name: str
    current_weight: condecimal(max_digits = 8, decimal_places=2)
    add_time: datetime
    class Config:
        orm_mode = True

class ApiInventoryList(BaseModel):
    inv_list: list[ApiInventoryItem]

class ExpiryAlertItem(ApiItemBase):
    name: str

class ExpiryAlertList(BaseModel):
    ex_list: list[ExpiryAlertItem]

class ExpiryAlertParams(BaseModel):
    before: date

class RecalledBatch(BaseModel):
    recall_id: int
    batch: str

class RecalledBBDate(BaseModel):
    recall_id: int
    expiry_date: date

class RecalledUPC(BaseModel):
    recall_id: int
    UPC: int

class AddRecall(BaseModel):
    UPCs: Union[set[int], None] = None
    reason: str
    batches: Union[set[str], None] = None
    expiry_dates: Union[set[date], None] = None
    issued_at: date
    info_url: str
    source: int

class RecallWarning(BaseModel):
    UPC: int
    name: str
    reason: str
    batches: Union[list[str], None] = None
    expiry_dates: Union[list[date], None] = None
    issued_at: date
    info_url: str

class RecallAlertParams(BaseModel):
    after: date