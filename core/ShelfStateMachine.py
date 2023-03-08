import base64
import datetime, decimal, json, threading, queue
import time
from core.baseclient import BaseClient
from db.database import SessLocal
from db import db_utils, py_schema
from core.OFF_fetcher import OpenFoodFactFetcher


class StateMachine(BaseClient):
    _inputqueue = queue.Queue()
    _work = True
    _trans_ts = datetime.datetime.now(datetime.timezone.utc)
    _trans_weight = decimal.Decimal("0.0")
    _trans_barcode = 0
    _trans_dev = 0
    _metadataSources = [OpenFoodFactFetcher()]
    last_item = 0
    _trans_photos = []

    class WeightWatcher(object):
        _current_weights = {}
        _weightqueue = queue.Queue()
        _work = True
        _tolerance = decimal.Decimal("0.0")

        def __init__(self, outputqueue, tolerance = decimal.Decimal("5.0")):
            self._output_queue = outputqueue
            self._tolerance = tolerance

        def watch(self):
            while self._work:
                tmp = self._weightqueue.get()
                curr_wei = self._current_weights.setdefault(tmp[0], tmp[1])
                if curr_wei - self._tolerance <= tmp[1] <= curr_wei + self._tolerance:
                    self._current_weights[tmp[0]] = tmp[1]
                elif tmp is not None:
                    new_item_weight = tmp[1] - self._current_weights[tmp[0]]
                    msg = {"action": "new_weight",
                           "param": new_item_weight.quantize(decimal.Decimal("1.00")),
                           "ts": datetime.datetime.now(datetime.timezone.utc),
                           "dev": tmp[0]}
                    self._output_queue.put(msg)
                    self._current_weights[tmp[0]] = tmp[1]

    def __init__(self, mqttconf = "statemachine_mqtt.json"):
        super().__init__(mqttconf)
        self._wwatch = StateMachine.WeightWatcher(self._inputqueue)
        self._weight_q = self._wwatch._weightqueue
        self.closedWait = readyClosedState(self)
        self.openWait = readyOpenState(self)
        self.barcodeWait = waitBarcodeState(self)
        self.weightWait = waitWeightState(self)
        self.invUpdate = updateInventoryState(self)
        self.errDisplay = errorState(self)
        #self.photoSave = savePhotoState(self)
        self.currentstate = self.closedWait

    def _sub_on_connect(self, client, userdata, flags, rc, prop):
        self._client.subscribe("regal/weight/+/filtered")
        self._client.subscribe("regal/camera/+/barcode")
        self._client.subscribe("regal/camera/+/photo")
        self._client.subscribe("regal/reed/#")

    def _on_msg(self, client, userdata, message):
        src_topics = message.topic.split("/")
        sensor = src_topics[1]
        sensorno = int(src_topics[2])
        #infotype = src_topics[3]
        if sensor == "weight":
            jsonmsg = json.loads(message.payload)
            weight_msg = (str(sensorno), decimal.Decimal(jsonmsg["g"]))
            suc = self._weight_q.put(weight_msg)
        elif sensor == "camera":
            infotype = src_topics[3]
            jsonmsg = json.loads(message.payload)
            cam_msg = {"ts": datetime.datetime.fromtimestamp(jsonmsg["timestamp"], datetime.timezone.utc)}
            if infotype == "barcode":
                cam_msg["action"] = "barcode"
                cam_msg["param"] = jsonmsg["code"]
            elif infotype == "photo":
                cam_msg["action"] = "photo"
                cam_msg["param"] = (jsonmsg["code"],jsonmsg["photo"])
            self._inputqueue.put(cam_msg)
        elif sensor == "reed":
            reed_state = not bool(int(message.payload))
            reed_msg = {"action": "reed",
                        "param": int(reed_state),
                        "ts": datetime.datetime.now(datetime.timezone.utc)}
            suc = self._inputqueue.put(reed_msg)
        return

    def _connect(self):
        self._client.on_connect = self._sub_on_connect
        self._client.on_message = self._on_msg
        rtn = self._client.connect(self._host, self._port, 60)
        self._client.loop_start()
        return rtn

    def send(self, topic, data, retain = False):
        return self._client.publish(topic, data, retain=retain)

    def start(self):
        self._wwatch_t = threading.Thread(None,self._wwatch.watch,"WeightWatching thread")
        self._wwatch_t.start()
        self._connect()

    def runMachine(self):
        self.currentstate.run({"action": "start"})
        while self._work:
            try:
                mqtt_input = self._inputqueue.get(timeout=10)
            except queue.Empty as emfaul:
                mqtt_input = {"action": "timeout"}
            self.currentstate = self.currentstate.next(mqtt_input)
            self.currentstate.run(mqtt_input)

    def give_input(self, item):
        return self._inputqueue.put(item)

    def clear_input(self):
        q_empty = False
        #Empty queues!
        while not q_empty:
            try:
                self._inputqueue.get(False)
            except queue.Empty as em:
                q_empty = True

    def fetchProduct(self, barcode: int):
        prod = py_schema.CreateProduct(last_update=datetime.datetime.now(datetime.timezone.utc), EAN=barcode,
                                                product_name="", producer = "",
                                                net_weight = decimal.Decimal(0), source=0)
        for fetcher in self._metadataSources:
            tmp = fetcher.fetch(barcode)
            if not prod.product_name: prod.product_name = tmp.product_name
            if not prod.producer: prod.producer = tmp.producer
            if not prod.net_weight: prod.net_weight = tmp.net_weight
            prod.last_update = tmp.last_update
            prod.source += tmp.source
            if prod.product_name and prod.net_weight:
                break
        return prod

    @property
    def trans_barcode(self):
        return self._trans_barcode

    @trans_barcode.setter
    def trans_barcode(self, barcode):
        if isinstance(barcode, str):
            barcode = int(barcode)
        if isinstance(barcode, int):
            self._trans_barcode = barcode

    @property
    def trans_weight(self):
        return self._trans_weight

    @trans_weight.setter
    def trans_weight(self, weight):
        if isinstance(weight, decimal.Decimal):
            self._trans_weight = weight

    @property
    def trans_dev(self):
        return self._trans_dev

    @trans_dev.setter
    def trans_dev(self, dev):
        if isinstance(dev, str):
            dev = int(dev)
        if isinstance(dev, int):
            self._trans_dev = dev

    @property
    def trans_ts(self):
        return self._trans_ts

    @trans_ts.setter
    def trans_ts(self, ts):
        if isinstance(ts, datetime.datetime):
            self._trans_ts = ts

    @property
    def trans_photos(self):
        return self._trans_photos

    def add_photo(self,photodata):
        self._trans_photos.append(photodata)

    def clear_photos(self):
        self._trans_photos.clear()

class State(object):
    def __init__(self, machine: StateMachine):
        self._machine = machine

    def run(self, inputData: dict):
        raise NotImplementedError("Please implement this method")

    def next(self, inputData: dict):
        raise NotImplementedError("Please implement this method")


class readyClosedState(State):
    def __init__(self, machine: StateMachine):
        super().__init__(machine)

    def run(self, inputData: dict):
        print("Closed")
        retval = self._machine.send("regal/ctrlsig", "SIGCLS")
        return retval

    def next(self, inputData: dict):
        if inputData["action"] == "reed":
            if inputData["param"] == 1:
                return self._machine.openWait
            else:
                return self._machine.closedWait
        else:
            return self._machine.closedWait


class readyOpenState(State):
    def __init__(self,machine: StateMachine):
        super().__init__(machine)

    def run(self, inputData: dict):
        print("Open")
        self._machine.send("regal/ctrlsig", "SIGRDY")
        if inputData["action"] != "timeout":
            self._machine.send("regal/ctrlsig", "SIGFIN")
        self._machine.trans_weight = decimal.Decimal("0.0")
        self._machine.trans_dev = 0
        self._machine.trans_barcode = 0
        self._machine.trans_ts = datetime.datetime.now(datetime.timezone.utc)
        return

    def next(self, inputData: dict):
        if inputData["action"] == "reed":
            if inputData["param"] == 0:
                return self._machine.closedWait
            else:
                return self._machine.openWait
        elif inputData["action"] == "new_weight":
            self._machine.trans_weight = inputData["param"]
            self._machine.trans_ts = inputData["ts"]
            self._machine.trans_dev = inputData["dev"]
            return self._machine.barcodeWait
        elif inputData["action"] == "barcode":
            self._machine.trans_barcode = inputData["param"]
            self._machine.trans_ts = inputData["ts"]
            self._machine.send("regal/ctrlsig", "SIGRCV")
            print(self._machine.trans_barcode)
            return self._machine.weightWait
        else:
            return self._machine.openWait


class waitWeightState(State):
    def __init__(self, machine: StateMachine):
        super().__init__(machine)

    def run(self, inputData: dict):
        print("waiting for weight")
        retval = self._machine.send("regal/ctrlsig", "SIGPRC")
        return retval

    def next(self, inputData: dict):
        if inputData["action"] == "new_weight":
            self._machine.trans_weight = inputData["param"]
            self._machine.trans_dev = inputData["dev"]
            if self._machine.trans_weight >= 0.0:
                return self._machine.invUpdate
            else:
                return self._machine.weightWait
        elif inputData["action"] == "barcode":
            return self._machine.weightWait
        elif inputData["action"] == "timeout":
            return self._machine.errDisplay
        elif inputData["action"] == "photo":
            self._machine.add_photo((inputData["ts"], base64.b64decode(inputData["param"][1].encode('ascii'))))
            print("photo taken")
            return self._machine.weightWait
        else:
            return self._machine.weightWait


class waitBarcodeState(State):
    def __init__(self, machine: StateMachine):
        super().__init__(machine)

    def run(self, inputData: dict):
        print(self._machine.trans_weight, "grams changed. waiting for barcode")
        retval = self._machine.send("regal/ctrlsig", "SIGPRC")
        return retval

    def next(self, inputData: dict):
        if inputData["action"] == "barcode":
            self._machine.trans_barcode = inputData["param"]
            return self._machine.invUpdate
        elif inputData["action"] == "timeout":
            return self._machine.errDisplay
        else:
            return self._machine.barcodeWait


class updateInventoryState(State):
    def __init__(self, machine: StateMachine):
        super().__init__(machine)

    def run(self, inputData: dict):
        print("updating inventory", self._machine.trans_barcode)
        db_sess = SessLocal()
        product = self._machine.fetchProduct(self._machine.trans_barcode)
        if self._machine.trans_weight >= 0.0:
            db_utils.insert_or_update_product(db_sess, product, self._machine.trans_weight)
            last_item = db_utils.insert_or_update_item(db_sess, self._machine.trans_barcode, self._machine.trans_weight,
                                                                self._machine.trans_dev, self._machine.trans_ts)
            if last_item is not None: self._machine.last_item = last_item.item_id
        #database code
        else:
            #product = self._machine.fetchProduct(self._machine.trans_barcode)
            db_utils.insert_or_update_product(db_sess, product, decimal.Decimal(0))
            last_item = db_utils.take_out_item(db_sess, self._machine.trans_barcode, abs(self._machine.trans_weight),
                                                        self._machine.trans_dev, self._machine.trans_ts)
            if last_item is not None: self._machine.last_item = last_item.item_id
        for photo in self._machine.trans_photos:
            photo_obj = py_schema.CreatePhoto(item_id = self._machine.last_item,
                                                       photo = photo[1], taken_at = photo[0])
            db_utils.save_photo(db_sess, photo_obj)
        db_sess.close()
        self._machine.clear_photos()
        self._machine.send("regal/last_item", self._machine.last_item, True)
        self._machine.clear_input()
        self._machine.give_input({"action": "inv_update"})
        return

    def next(self, inputData: dict):
        return self._machine.openWait

#class savePhotoState(State):
#    def __init__(self, machine: StateMachine):
#        super().__init__(machine)
#
#    def run(self, inputData: dict):
#        print("saving photo")
#        db_sess = SessLocal()
#        photo_obj = db.py_schema.CreatePhoto(item_id = self._machine.last_item, photo = inputData["param"][1],
#                                                  taken_at = inputData["ts"])
#        db.db_utils.save_photo(db_sess,photo_obj)
#        db_sess.close()
#        self._machine.give_input({"action": "save_photo"})
#        return
#
#    def next(self, inputData: dict):
#        return self._machine.weightWait


class errorState(State):
    def __init__(self, machine: StateMachine):
        super().__init__(machine)

    def run(self, inputData: dict):
        print("Error")
        retval = self._machine.send("regal/ctrlsig", "SIGERR")
        self._machine.clear_photos()
        time.sleep(5)
        self._machine.give_input({"action": "nothing"})
        return retval

    def next(self, inputData: dict):
        return self._machine.openWait

def run(config = "statemachine_mqtt.json"):
    machine = StateMachine(config)
    machine.start()
    machine.runMachine()

if __name__ == "__main__":
    run()