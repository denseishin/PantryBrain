import datetime, json, fastapi
from db import py_schema, db_utils
from db.database import SessLocal
from sqlalchemy.orm import Session
import uvicorn

app = fastapi.FastAPI()


def depend_inject():
    data_dep = SessLocal()
    try:
        yield data_dep
    finally:
        data_dep.close()


@app.get("/item/{item_id}", response_model = py_schema.ApiItem)
async def get_item(item_id: int, db: Session = fastapi.Depends(depend_inject)):
    db_item = db_utils.get_item_info(db, item_id)
    if db_item is None:
        raise fastapi.HTTPException(status_code=404, detail="Item not found")
    return db_item


@app.put("/item/{item_id}")
async def update_item(item_id: int, item_data: py_schema.ApiUpdateItem, db: Session = fastapi.Depends(depend_inject)):
    db_item = db_utils.item_set_bbbc(db, item_id, item_data.expiry_date, item_data.batch, item_data.comment)
    if db_item: db_product = db_utils.product_set_weights(db, db_item.EAN, item_data.net_weight, item_data.max_weight)
    return

@app.patch("/item/{item_id}")
async def deactivate_item(item_id: int, db: Session = fastapi.Depends(depend_inject)):
    db_item = db_utils.take_out_item_id(db, item_id, datetime.datetime.now(datetime.timezone.utc))
    return

@app.get("/inventory", response_model=list[py_schema.ApiInventoryItem])
async def get_inventory(db: Session = fastapi.Depends(depend_inject)):
    inv_list = db_utils.get_inventory(db)
    return inv_list


@app.post("/foodalerts/expiry", response_model=list[py_schema.ExpiryAlertItem])
async def get_expiry_alerts(params: py_schema.ExpiryAlertParams, db: Session = fastapi.Depends(depend_inject)):
    alerts = db_utils.get_expiring_items(db, params.before, 5)
    return alerts


@app.post("/foodalerts/recall", response_model=list[py_schema.RecallWarning])
async def get_expiry_alerts(params: py_schema.RecallAlertParams, db: Session = fastapi.Depends(depend_inject)):
    alerts = db_utils.get_recall_warnings(db, params.after)
    return alerts

def run(cfg_file = "web_cfg.json"):
    cfg_details = {}
    with open(cfg_file,"r") as f:
        cfg_details = json.load(f)
    uvicorn.run(app, host=cfg_details.setdefault("host","0.0.0.0"), port=cfg_details.setdefault("port",8000))

if __name__ == "__main__":
    run()