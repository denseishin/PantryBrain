from core.product_fetcher import ProductFetcher, calc_unit, convert_to_g
from db.py_schema import CreateProduct
import openfoodfacts, datetime, re
from pydantic import condecimal
from decimal import Decimal

class OpenFoodFactFetcher(ProductFetcher):

    fetchengine = openfoodfacts.products

    def fetch(self, EAN: int) -> CreateProduct:
        product = self.fetchengine.get_product(str(EAN).zfill(13))
        newProduct = CreateProduct(last_update=datetime.datetime.now(datetime.timezone.utc),EAN=EAN,
                                   product_name="", producer = "",
                                   net_weight = Decimal(0), source=0)
        if "product" in product.keys():
            newProduct.product_name = product["product"].get("product_name","")
            newProduct.producer = product["product"].get("brands","")
            quantity = product["product"].get("quantity", "")
            newProduct.net_weight = self._calc_net_weight(quantity)
            newProduct.source = 1
        return newProduct

    def _calc_net_weight(self, raw_weight: str) -> condecimal(max_digits = 8, decimal_places=2):
        raw_weight = raw_weight.replace(",",".")
        multi_weight_s = ""
        multi_weight = Decimal(0)
        single_weight_s = ""
        weight = Decimal(0)
        #for weights like (12x 1.5g)
        multi_weight_occ = re.search(r"(\(\d+\s*x\s*\d+\.*\d*\s*((g)|(kg)|(l)|(cl)|(ml)|(oz)|(fl\s*oz)|(lbs))\))",raw_weight)
        density = Decimal(1)
        if multi_weight_occ:
            multi_weight_s = multi_weight_occ.group()
            operands = multi_weight_s.split("x")
            m_unit = calc_unit(operands[1].strip(") "))
            left_op = Decimal(operands[0].strip("( "))
            right_op = Decimal(operands[1].strip(") ").replace(m_unit,"").strip())
            multi_weight = left_op * right_op
            multi_weight = convert_to_g(multi_weight, m_unit)
        single_weight_occ = re.search(r"^(\d+\.*\d*\s*((g)|(kg)|(l)|(cl)|(ml)|(oz)|(fl\s*oz)|(lbs)))",raw_weight)
        if single_weight_occ:
            single_weight_s = single_weight_occ.group()
            unit = calc_unit(single_weight_s)
            weight = Decimal(single_weight_s.replace(unit,"").strip())
            weight = convert_to_g(weight,unit)
        if multi_weight > weight:
            weight = multi_weight
        weight = weight.quantize(Decimal("1.00"))
        return weight


if __name__ == "__main__":
    fetcher = OpenFoodFactFetcher()
    test = fetcher.fetch(7622210421968)
    print(test)