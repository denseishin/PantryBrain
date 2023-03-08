from recall_processors.recall_german import GermanRecall
from datetime import datetime, timezone
from db.database import SessLocal
from db import db_utils
import json

fileaddr = "recall_processors/last_request.json"
processors = [GermanRecall()]

time_now = datetime.now(timezone.utc)
with open(fileaddr,"r") as timesave:
    try:
        saveinfo = json.load(timesave)
        if saveinfo:
            last_request = datetime.fromtimestamp(saveinfo["last_ts"], timezone.utc)
    except json.decoder.JSONDecodeError as err:
        pass
print("last request was at",last_request.isoformat())
time_now = datetime.now(timezone.utc)
for recall_processor in processors:
    results = recall_processor.fetch_recalls(last_request)
    print(recall_processor.recalls_worked, recall_processor.recalls_w_barcode, recall_processor.recalls_w_barcode/recall_processor.recalls_worked if recall_processor.recalls_worked else 0.0)
    dbs = SessLocal()
    db_utils.insert_recalls(dbs, results)
    dbs.close()
with open(fileaddr,"w") as timesave:
    json.dump({"last_ts": time_now.timestamp()},timesave)