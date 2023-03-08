import base64
import decimal
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from pydantic import condecimal
from db import db_model, py_schema
from datetime import timezone, date, datetime, timedelta


def insert_or_update_product(dbs: Session, prod: py_schema.CreateProduct, max_weight: condecimal(max_digits = 8, decimal_places=2)):
    db_item = db_model.Product(**prod.dict())
    hist_item = dbs.query(db_model.Product).filter(db_model.Product.EAN == prod.EAN).first()
    if hist_item:
        hist_item.product_name = prod.product_name
        hist_item.producer = prod.producer
        hist_item.net_weight = prod.net_weight
        hist_item.last_update = prod.last_update
        hist_item.source = prod.source
        if hist_item.max_weight <= max_weight:
            hist_item.max_weight = max_weight
        dbs.flush()
        dbs.commit()
        return hist_item
    else:
        db_item.max_weight = max_weight
        dbs.add(db_item)
        dbs.commit()
        dbs.refresh(db_item)
        return db_item


def get_product(dbs: Session, iEAN:int):
    return dbs.query(db_model.Product).filter(db_model.Product.EAN == iEAN).first()


def get_inventory(dbs: Session):
    resultlist = []
    q = dbs.query(db_model.Product, db_model.Item).join(db_model.Item).filter(
        or_(db_model.Item.out_time <= db_model.Item.in_time, db_model.Item.out_time == None))
    qres = q.all()
    for prod_info, item_info in qres:
        new = py_schema.ApiInventoryItem(item_id=item_info.item_id, EAN=prod_info.EAN, product_name=prod_info.product_name,
                                         net_weight=prod_info.net_weight, max_weight=prod_info.max_weight, current_weight=item_info.current_weight,
                                         expiry_date=item_info.expiry_date, add_time=item_info.add_time.replace(tzinfo=timezone.utc))
        resultlist.append(new)
    return resultlist


def get_photos(dbs: Session, itemId: int):
    return dbs.query(db_model.item_photo).filter(db_model.item_photo.item_id == itemId).all()


def insert_item(dbs: Session, item: py_schema.AddItem):
    db_item = db_model.Item(**item.dict())
    dbs.add(db_item)
    update_prod = get_product(dbs, item.EAN)
    if update_prod.max_weight is None:
        update_prod.max_weight = item.current_weight
    elif update_prod.max_weight < item.current_weight:
        update_prod.max_weight = item.current_weight
    dbs.flush()
    dbs.commit()
    dbs.refresh(db_item)
    return db_item


def save_photo(dbs: Session, photo: py_schema.CreatePhoto):
    db_photo = db_model.item_photo(**photo.dict())
    dbs.add(db_photo)
    dbs.commit()
    dbs.refresh(db_photo)
    return db_photo


def item_set_bbbc(dbs: Session, id: int, best_by: date = None, batch: str = None, comment: str = None):
    item_bb = dbs.query(db_model.Item).filter(db_model.Item.item_id == id).first()
    if item_bb:
        if best_by: item_bb.expiry_date = best_by
        if batch: item_bb.batch = batch
        if comment: item_bb.comment = comment
        dbs.flush()
        dbs.commit()
    return item_bb


def product_set_weights(dbs: Session, item_id: int, net_w: condecimal(max_digits = 8, decimal_places=2) = None,
                        max_w: condecimal(max_digits = 8, decimal_places=2) = None):
    prod_w = dbs.query(db_model.Product).join(db_model.Item).filter(db_model.Item.item_id == item_id).first()
    if prod_w:
        if net_w: prod_w.net_weight = net_w
        if max_w: prod_w.max_weight = max_w
        dbs.flush()
        dbs.commit()
    return prod_w


def insert_or_update_item(dbs: Session, iEAN: int, iweight: condecimal(max_digits = 8, decimal_places=2), shelfno: int, intime: datetime):
    qbuild = dbs.query(db_model.Item).filter(db_model.Item.EAN == iEAN,
                                             db_model.Item.current_weight >= iweight - decimal.Decimal("5.0"),
                                             db_model.Item.out_time >= db_model.Item.in_time,
                                             (intime - timedelta(hours=1)) < db_model.Item.out_time
                                             #func.timediff(intime - db_model.Item.out_time) < timedelta(hours=1.0)
                                             ).order_by(func.abs(db_model.Item.current_weight - iweight)).limit(1)
    hist_item = qbuild.first()
    #Problematik: Welches alte Item wählen? Das, zu dem der Gewichtsunterschied am geringsten ist -
    # > Kann bei manchen Fällen zur Falschauswahl führen!
    #z.B.: 2x selbes altes Gewicht oder neues Gewicht hat geringeren Unterschied zur falschen entnommenen Packung
    #Unique Identifier wäre gut, aber unter Entwurfbedingungen nicht erreichbar
    # -> Kameratracking in Küche oder Smart Labels
    # -> oder stateless arbeiten
    if hist_item:
        hist_item.current_weight = iweight
        hist_item.in_time = intime
        dbs.flush()
        dbs.commit()
    else:
        item_model = py_schema.AddItem(EAN=iEAN, current_weight = iweight, shelf = shelfno, pos_x = 0, pos_y = 0,
                                       add_time = intime, in_time = intime)
        hist_item = insert_item(dbs, item_model)
    return hist_item


def take_out_item(dbs: Session, iEAN: int, iweight: condecimal(max_digits = 8, decimal_places=2), shelfno: int,
                  out_time: datetime):
    querybuild = dbs.query(db_model.Item).filter(db_model.Item.EAN == iEAN,
                                                 db_model.Item.current_weight >= iweight - decimal.Decimal("4.0"),
                                                 db_model.Item.current_weight <= iweight + decimal.Decimal("4.0"),
                                                 or_(db_model.Item.out_time <= db_model.Item.in_time, db_model.Item.out_time == None)
                                                 ).order_by(func.abs(db_model.Item.current_weight - iweight)).limit(1)
    takeout = querybuild.first()
    #Problematik: Welches gelagerte Item wählen? Auswahl kann falsch sein wenn zwei circa gleich schwere Items der selben EAN
    #im Lager sind! Lösung: Koordinaten für Lebensmittel (aber keine Zeit rip)
    if takeout:
        takeout.out_time = out_time
    dbs.flush()
    dbs.commit()
    return takeout


def take_out_item_id(dbs: Session, id: int, out_time: datetime):
    querybuild = dbs.query(db_model.Item).filter(db_model.Item.item_id == id,
                                                 or_(db_model.Item.out_time <= db_model.Item.in_time,
                                                     db_model.Item.out_time == None))
    takeout = querybuild.first()
    if takeout:
        takeout.out_time = out_time
    dbs.flush()
    dbs.commit()
    return takeout


def get_item(dbs: Session, iEAN: int, shelfno: int, iweight: condecimal(max_digits = 8, decimal_places=2)):
    return dbs.query(db_model.Item).filter(db_model.Item.EAN == iEAN, db_model.Item.shelf == shelfno,
                                           or_(db_model.Item.out_time <= db_model.Item.in_time,
                                               db_model.Item.out_time == None)).order_by(func.abs(
        db_model.Item.current_weight - iweight)).limit(1).first()


def get_item_info(dbs: Session, item_id: int):
    result = None
    res = dbs.query(db_model.Item, db_model.Product).join(db_model.Product).filter(
        db_model.Item.item_id == item_id).first()
    item, prod = res if res else (None,None)
    if item and prod:
        result = py_schema.ApiItem(item_id=item_id, EAN=item.EAN, product_name = prod.product_name, net_weight = prod.net_weight,
                                   max_weight = prod.max_weight, current_weight = item.current_weight, expiry_date = item.expiry_date,
                                   batch = item.batch, comment = item.comment, shelf = item.shelf)
        item_photos_db = item.photos
        photo_list = []
        for p in item_photos_db:
            photo_list.append({"photo":base64.b64encode(p.photo).decode('ascii'),"taken_at":p.taken_at})
        result.photos = photo_list
    return result


def get_expiring_items(dbs: Session, ex_date: date, add_days: int = 3):
    date_thresh = ex_date + timedelta(days=add_days)
    items = dbs.query(db_model.Item, db_model.Product).join(db_model.Product).filter(
        or_(db_model.Item.out_time <= db_model.Item.in_time, db_model.Item.out_time == None),
        db_model.Item.expiry_date <= date_thresh).all()
    ex_item_list = []
    for item, product in items:
        ex_item_list.append(
            py_schema.ExpiryAlertItem(item_id = item.item_id, EAN = item.EAN, name = product.product_name,
                                      expiry_date=item.expiry_date, net_weight = product.net_weight,
                                      max_weight = product.max_weight, current_weight = item.current_weight))
    return ex_item_list


def get_recall_warnings(dbs: Session, filter_date: date):
    item_sql = dbs.query(db_model.Recall, db_model.Item.EAN, db_model.Product.product_name).join(db_model.recalledUPCs).join(
        db_model.recalledUPCs.affected_items)\
        .join(db_model.Product)\
        .filter(db_model.Recall.issued_at >= filter_date)
    item = item_sql.all()
    recall_list: list[py_schema.RecallWarning] = list()
    for recall_info, EAN, name in item:
        warn = py_schema.RecallWarning(UPC = EAN, name = name, reason = recall_info.reason, issued_at = recall_info.issued_at, info_url = recall_info.info_url)
        recall_dates = [i.expiry_date for i in recall_info.expiry_dates]
        recall_batches = [i.batch for i in recall_info.batches]
        warn.batches = recall_batches
        warn.expiry_dates = recall_dates
        recall_list.append(warn)
    #print(item)
    return recall_list


def insert_recalls(dbs: Session, recalls: list[py_schema.AddRecall]):
    for recall in recalls:
        db_item = db_model.Recall(reason=recall.reason, issued_at=recall.issued_at, info_url=recall.info_url,
                                  source=recall.source)
        dbs.add(db_item)
        dbs.commit()
        dbs.refresh(db_item)
        recall_id = db_item.id
        for UPC in recall.UPCs:
            s = py_schema.RecalledUPC(recall_id = recall_id, UPC = UPC)
            to_add = db_model.recalledUPCs(**s.dict())
            dbs.add(to_add)
        for recall_date in recall.expiry_dates:
            s = py_schema.RecalledBBDate(expiry_date = recall_date, recall_id = recall_id)
            to_add = db_model.recalledExpiryDates(**s.dict())
            dbs.add(to_add)
            #dbs.commit()
        for recall_batch in recall.batches:
            s = py_schema.RecalledBatch(recall_id = recall_id, batch = recall_batch)
            to_add = db_model.recalledBatches(**s.dict())
            dbs.add(to_add)
            #dbs.commit()
        dbs.commit()
    return

if __name__ == "__main__":
    from .database import SessLocal

    dbs = SessLocal()
    #test_item = py_schema.CreateProduct(EAN=1337,source=0,product_name="Test",producer="Testrun",
    #                                    net_weight=decimal.Decimal("1337.42"),last_update = datetime.now(timezone.utc))
    #lol = insert_product(db,test_item)
    #print(lol)
    #prodtest = get_product(db,1337)
    #print(prodtest.EAN,prodtest.product_name,prodtest.producer)
    adtim = datetime.now(timezone.utc) - timedelta(hours=4)
    itemtest = py_schema.AddItem(EAN=1337, current_weight = decimal.Decimal(25), shelf = 0, pos_x = 0, pos_y = 0,
                                 add_time = adtim, in_time = adtim)
    ins_item = insert_item(dbs,itemtest)
    print(ins_item.item_id)
    #test = get_item(db,1337,0,decimal.Decimal(1330.0))
    #todate = datetime.now(timezone.utc)
    #takeout2 = take_out_item(db,1337,decimal.Decimal(25),0,todate)
    #indate = datetime.now(timezone.utc)
    #putin = insert_or_update_item(db,1337,decimal.Decimal(24),0,indate)
    #item_set_bbbc(db,putin.item_id,date(2023,1,1),"L1337")
    #print(test.item_id)
    #print(takeout2.item_id)
    #print(putin.item_id)
    droptim = datetime.now(timezone.utc) - timedelta(hours=2)
    take_out_item(dbs,ins_item.EAN, decimal.Decimal(ins_item.current_weight), ins_item.shelf, droptim)
    adtim = datetime.now(timezone.utc)
    tt = insert_or_update_item(dbs,ins_item.EAN,decimal.Decimal(ins_item.current_weight),ins_item.shelf,adtim)
    print(tt.item_id)
    inv = get_inventory(dbs)
    print(inv)
    #photos = get_photos(db,30)
    #test = get_item_info(db,30)
    #for img in photos:
    #    raw = numpy.frombuffer(img.photo, numpy.uint8)
    #    #pic = cv2.imread()
    #    pic = cv2.imdecode(raw,cv2.IMREAD_COLOR)
    #    cv2.imwrite("1"+str(img.photo_id)+".png",pic)
    #test = get_recall_warnings(db, date(2022,1,1))
    #print(test)
    dbs.close()