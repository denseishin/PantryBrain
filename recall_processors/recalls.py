from datetime import datetime
from db import py_schema

class RecallFetcher(object):
    _api_url: str

    def fetch_recalls(self, start_: datetime) -> list[py_schema.AddRecall]:
        pass
    
    def run(self):
        pass