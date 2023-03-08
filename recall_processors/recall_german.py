import decimal
import json
import cv2
import numpy as np
from .recalls import RecallFetcher
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, date, timedelta
import re
from core.product_fetcher import calc_unit
from db import py_schema,db_utils
from db.database import SessLocal


class GermanRecall(RecallFetcher):
    recalls_worked = 0
    recalls_w_barcode = 0
    _img_url_prefix = "https://www.lebensmittelwarnung.de"
    _api_url = "https://megov.bayern.de/verbraucherschutz/baystmuv-verbraucherinfo/rest/api/warnings/merged"
    _auth_head = {"Authorization":"baystmuv-vi-1.0 os=ios, key=9d9e8972-ff15-4943-8fea-117b5a973c61"}
    _gtin_regex = r"([0-9]{8,13})"
    _gtin_string_regex = r"(((EAN|GTIN|UPC|Barcode)[\-\s\w\:]?\w{0,7}:*\s*)[0-9]{8,13})|\([0-9]{8,13}\)"
    _mhd_regex = r"(MHD|Mindesthaltbarkeitsdat((um)|(en))):*\s(([0-3][0-9](\.|/))?[0-1][0-9](\.|/)\d{2,4}\s?(,|(und)|\+)?\s?)+"
    _mhd_data_regex = r"(([0-3][0-9](\.|/))?(([0][0-9])|([1][0-2]))(\.|/)\d{2,4})"
    _mhd_split_regex = r"\s?(,|(und)|\+|\s)\s?"
    _mhd_range_regex = r"(zwischen)?(?(1)\s?)(([0-3][0-9](\.|/))?[0-1][0-9](\.|/)\d{2,4})\s?(bis|\-|(?(1)und))\s?\w*\s?(([0-3][0-9](\.|/))?[0-1][0-9](\.|/)\d{2,4})"
    _batch_regex = r"(([L][\-.]?)?(?(2)\s?|)([0-9A-Z]{5,}|\d{4,}))"

    def _make_params(self,publishedDate: datetime, rows = 1000):
        schema = {"food": {
            "rows": rows,
            "sort": "publishedDate asc",
            "start": 0,
            "fq": [
                "publishedDate > {:.0f}".format(publishedDate.timestamp()*1000) #1630067654000
            ]
        }}
        return schema

    def fetch_recalls(self, start_: datetime) -> list[py_schema.AddRecall]:
        requ = requests.post(self._api_url,json=self._make_params(start_),headers=self._auth_head)
        res = requ.json()
        product_recalls = list()
        for product in res["response"]["docs"]:
            info_url = product["link"]
            if "bedarfsgegenstaende" in info_url or "kosmetische+mittel" in info_url:
                continue
            self.recalls_worked += 1
            image_urls = set()
            best_by_dates = set()
            batches = set()
            barcodes = set()
            api_mhds, title = self._detect_bestby(product["title"])
            best_by_dates = best_by_dates.union(api_mhds)
            api_ean, title = self._detect_gtin(title)
            barcodes = barcodes.union(api_ean)
            reason = product["warning"]
            date_of_issue = date.today()
            publishedDate = datetime.fromtimestamp(product["publishedDate"]/1000,timezone.utc).date()
            web_data = requests.get(info_url).text
            htmldoc = BeautifulSoup(web_data,'html.parser')
            infodivs = htmldoc.findAll("div",class_="form-group")
            filtered_info = {}
            for rawinfo in infodivs:
                infotype = rawinfo.find_next("label").text.strip(": ")
                info = rawinfo.find_next("span").text
                if infotype and info:
                    if infotype == "Datum der ersten Veröffentlichung":
                        date_of_issue = info = datetime.strptime(info+"+0000","%d.%m.%Y%z").date()
                    elif infotype == "Produktbezeichnung" or infotype == "Haltbarkeit":
                        if infotype == "Haltbarkeit":
                            mhds, info = self._get_date_range(info)
                            best_by_dates = best_by_dates.union(mhds)
                        mhds, info = self._detect_bestby(info, not infotype == "Haltbarkeit")
                        best_by_dates = best_by_dates.union(mhds)
                        if infotype == "Produktbezeichnung":
                            ean, info = self._detect_gtin(info)
                            barcodes = barcodes.union(ean)
                        info = info.replace("\n","")
                    elif infotype == "Verpackungseinheit":
                        info = info.replace(",",".")
                        unit = calc_unit(info)
                        info = info.replace(unit,"")
                        #handle cases like 5x80g
                        operands = info.split("x")
                        weight_result = decimal.Decimal("1.0")
                        for op in operands:
                            numsearch = re.search(r"\d+\.?\d*",info)
                            if numsearch:
                                weight_result = weight_result * decimal.Decimal(numsearch.group())
                        weight_tup = (weight_result, unit)
                    elif infotype == "Los-Kennzeichnung":
                        ean, info = self._detect_gtin(info)
                        barcodes = barcodes.union(ean)
                        mhds, info = self._detect_bestby(info, False)
                        best_by_dates = best_by_dates.union(mhds)
                        separate_batches = self._detect_batch(info)
                        batches = batches.union(separate_batches)
                    elif infotype == "Produktbilder":
                        imglinks = rawinfo.find_all("a", href=True)
                        for filelink in imglinks:
                            image_urls.add(self._img_url_prefix+filelink["href"])
                    filtered_info[infotype] = info
                elif "attachment-group" in rawinfo.get('class'):
                    imglinks = rawinfo.find_all("a", href=True)
                    for filelink in imglinks:
                        image_urls.add(self._img_url_prefix+filelink["href"])
                elif "Behörden" in infotype:
                    break
                else:
                    continue
            if not barcodes:
                barcget = cv2.barcode_BarcodeDetector()
                for img_url in image_urls:
                    img_raw = requests.get(img_url, stream=True).content
                    img_arr = np.frombuffer(img_raw,np.uint8)
                    dec_img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
                    images = []
                    if dec_img is not None:
                        ok, imginfo, type, corners = barcget.detectAndDecode(dec_img)
                        if ok:
                            barcodes.add(int(imginfo[0]))
                            dec_img = None
                    if dec_img is not None:
                        #cv2.imshow("debugwin", image)
                        #cv2.waitKey(0)
                        half_width = dec_img.shape[1] // 2
                        half_height = dec_img.shape[0] // 2
                        top_half = dec_img[:half_height,:]
                        bot_half = dec_img[half_height:,:]
                        images.append(top_half)
                        images.append(bot_half)
                        r_half = dec_img[:,:half_width]
                        l_half = dec_img[:,half_width:]
                        images.append(r_half)
                        images.append(l_half)
                        top_r_half = dec_img[:half_height,:half_width]
                        top_l_half = dec_img[:half_height,half_width:]
                        bot_r_half = dec_img[half_height:,:half_width]
                        bot_l_half = dec_img[half_height:,half_width:]
                        images += [top_r_half,top_l_half,bot_l_half,bot_r_half]
                        for image in images:
                            ok, imginfo, type, corners = barcget.detectAndDecode(image)
                            resultinfos = zip(imginfo,type)
                            if ok:
                                for bres in resultinfos:
                                    if bres[0]:
                                        barcodes.add(int(bres[0]))
                                break
                        images.clear()
            if not barcodes or not best_by_dates: #or not batches?
                file_infos = htmldoc.findAll("a", href=True, class_="attachment")
                pdf_list = []
                for filelink in file_infos:
                    if ".pdf" in filelink["href"].lower():
                        pdf_list.append(self._img_url_prefix+filelink["href"])
                #TODO: download and analyze PDFs
            if barcodes:
                self.recalls_w_barcode += 1
            #for code in barcodes:
            if barcodes:
                product_recalls.append(
                    py_schema.AddRecall(UPCs=barcodes, reason=reason, issued_at=date_of_issue,
                                                       info_url=info_url, batches=batches, expiry_dates=best_by_dates,
                                                       source=1))
            #time.sleep(1)
        return product_recalls



    def _detect_bestby(self, raw: str, validate: bool = True):
        result = set()
        filtered_input = raw
        if validate:
            where = re.search(self._mhd_regex, raw)
            if where:
                where = where.group()
                filtered_input = filtered_input.replace(where,"").strip(" ,")
            else:
                return result, filtered_input
        else:
            where = raw
        matches = re.findall(self._mhd_data_regex,where)
        for match in matches:
            final_date = self._str_to_date(match[0].strip())
            result.add(final_date)
        return result, filtered_input

    def _detect_gtin(self, raw: str):
        result_set = set()
        filtered_input = raw
        where = re.search(self._gtin_string_regex,raw)
        while where:
            results = re.findall(self._gtin_regex,where.group())
            filtered_input = filtered_input.replace(where.group(),"")
            for res in results:
                result_set.add(int(res))
            where = re.search(self._gtin_string_regex,filtered_input)
        return result_set, filtered_input

    def _detect_batch(self, raw: str):
        result_set = set()
        results = re.findall(self._batch_regex, raw)
        for res in results:
            result_set.add(res[0])
        return result_set

    def _get_date_range(self,raw):
        filtered_input = raw
        result_set = set()
        where = re.search(self._mhd_range_regex, raw)
        if where:
            fullmatch = where.group(0)
            filtered_input = filtered_input.replace(fullmatch,"")
            op1 = self._str_to_date(where.group(2))
            op2 = self._str_to_date(where.group(7))
            start = min(op1, op2)
            end = max(op1, op2)
            while start <= end:
                result_set.add(start)
                start = start + timedelta(days=1)
        return result_set, filtered_input

    def _str_to_date(self, raw):
        prep_date_str = raw.replace(".","/")
        date_components: list = prep_date_str.split("/")
        year = int(date_components.pop())
        month = int(date_components.pop())
        day = 1
        if date_components: day = int(date_components.pop())
        final_date = date(year,month,day)
        return final_date

    def run(self):
        fileaddr = "last_request.json"
        recall_processor = self
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
        results = recall_processor.fetch_recalls(last_request)
        print(recall_processor.recalls_worked, recall_processor.recalls_w_barcode, recall_processor.recalls_w_barcode/recall_processor.recalls_worked if recall_processor.recalls_worked else 0.0)
        dbs = SessLocal()
        db_utils.insert_recalls(dbs, results)
        dbs.close()
        with open(fileaddr,"w") as timesave:
            json.dump({"last_ts": time_now.timestamp()},timesave)
        return

if __name__ == '__main__':
    recall_processor = GermanRecall()
    recall_processor.run()