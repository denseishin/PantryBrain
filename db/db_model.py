from sqlalchemy import Column, ForeignKey, Integer, String, Date, DateTime, DECIMAL, BLOB
from sqlalchemy.orm import relationship

from db.database import Base

class Product(Base):
    __tablename__ = "product"

    EAN = Column(Integer,primary_key = True)
    product_name = Column(String)
    producer = Column(String)
    net_weight = Column(DECIMAL(6,2))
    max_weight = Column(DECIMAL(6,2))
    last_update = Column(DateTime)
    source = Column(Integer)
    instances = relationship("Item", back_populates="product")

class Item(Base):
    __tablename__ = "inventory"

    item_id = Column(Integer, primary_key = True, autoincrement = True)
    EAN = Column(Integer, ForeignKey("product.EAN"))
    current_weight = Column(DECIMAL(6,2))
    expiry_date = Column(Date)
    batch = Column(String)
    pos_x = Column(Integer)
    pos_y = Column(Integer)
    shelf = Column(Integer)
    comment = Column(String)
    add_time = Column(DateTime)
    out_time = Column(DateTime)
    in_time = Column(DateTime)
    product = relationship("Product", back_populates="instances")
    photos = relationship("item_photo", back_populates="item")

class item_photo(Base):
    __tablename__ = "inv_photos"

    photo_id = Column(Integer, primary_key = True, autoincrement = True)
    item_id = Column(Integer, ForeignKey("inventory.item_id"))
    photo = Column(BLOB)
    taken_at = Column(DateTime)
    item = relationship("Item", back_populates="photos")

class usage_log_entry(Base):
    __tablename__ = "usage_log"
    item_id = Column(Integer, ForeignKey("inventory.item_id"), primary_key = True, autoincrement = True)
    action_time = Column(DateTime, primary_key = True)
    action_type = Column(Integer)
    weight = Column(DECIMAL(6,2))

class Recall(Base):
    __tablename__ = "recalls"
    id = Column(Integer, primary_key = True, autoincrement = True)
    #EAN = Column(Integer,ForeignKey("product.EAN"))
    reason = Column(String)
    issued_at = Column(Date)
    info_url = Column(String)
    source = Column(Integer)
    batches = relationship("recalledBatches", back_populates="b_src_recall")
    expiry_dates = relationship("recalledExpiryDates", back_populates="e_src_recall")
    UPCs = relationship("recalledUPCs", back_populates="u_src_recall")

class recalledBatches(Base):
    __tablename__ = "recalled_batches"
    recall_id = Column(Integer, ForeignKey("recalls.id"), primary_key = True)
    batch = Column(String, primary_key = True)
    b_src_recall = relationship("Recall", back_populates="batches")

class recalledExpiryDates(Base):
    __tablename__ = "recalled_expiry_dates"
    recall_id = Column(Integer, ForeignKey("recalls.id"), primary_key = True)
    expiry_date = Column(Date, primary_key = True)
    e_src_recall = relationship("Recall", back_populates="expiry_dates")

class recalledUPCs(Base):
    __tablename__ = "recalled_upcs"
    recall_id = Column(Integer, ForeignKey("recalls.id"), primary_key = True)
    UPC = Column(Integer, primary_key = True)
    u_src_recall = relationship("Recall", back_populates="UPCs")
    affected_items = relationship(
        "Item",
        primaryjoin="and_(recalledUPCs.UPC==Item.EAN, or_(Item.out_time <= Item.in_time, Item.out_time == None))",
        foreign_keys = UPC,
        remote_side = "Item.EAN"
    )

#class base_item_photo(item_photo):
#    item = relationship("BaseItem", back_populates="photos")

#class BaseItem(Base):
#    __tablename__ = "inventory"#
#
#    item_id = Column(Integer, primary_key = True)
#    EAN = Column(Integer, ForeignKey("product.EAN"))
#    current_weight = Column(DECIMAL(6,2))
#    expiry_date = Column(Date)
#    batch = Column(String)
#    shelf = Column(Integer)
#    comment = Column(String)
#    add_time = Column(DateTime)
#    product = relationship("BaseProduct", back_populates="instances")
#    photos = relationship("item_photo", back_populates="item")

#class BaseProduct(Base):
#    __tablename__ = "product"
#    EAN = Column(Integer,primary_key = True)
#    product_name = Column(String)
#    net_weight = Column(DECIMAL(6,2))
#    max_weight = Column(DECIMAL(6,2))
#    instances = relationship("BaseItem", back_populates="product")
