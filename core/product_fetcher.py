from db.py_schema import CreateProduct
from decimal import Decimal
from pydantic import condecimal
import re

convert_weight_dict = { "g": Decimal(1),
                        "kg": Decimal(1000),
                        "oz": Decimal("28.349523125"),
                        "lbs": Decimal("453.59237")}

convert_fluid_dict = {"ml": Decimal(1),
                      "cl": Decimal(10),
                      "l": Decimal(1000),
                      "floz": Decimal("29.5735295625"),
                      "fl oz": Decimal("29.5735295625")}

def calc_unit(weight:str):
    unit = re.search(r"((g)|(kg)|(l)|(cl)|(ml)|(oz)|(fl\s*oz)|(lbs))",weight)
    if unit:
        unit = unit.group()
    else:
        unit = "g"
    return unit

def convert_to_g(weight,unit,density = Decimal(1)):
    if unit in list(convert_fluid_dict.keys()):
        weight = weight * convert_fluid_dict[unit] * density
    if unit in list(convert_weight_dict.keys()):
        weight = weight * convert_weight_dict[unit]
    return weight


class ProductFetcher(object):

    def fetch(self, EAN: int, lang: str) -> CreateProduct:
        raise NotImplementedError("Please implement this method")

    def _calc_net_weight(self, raw_weight: str) -> condecimal(max_digits = 8, decimal_places=2):
        raise NotImplementedError("Please implement this method")
