"""Allocate an order's recorded payment total for display; never reprice old orders."""
from decimal import Decimal,ROUND_HALF_UP
def lines(items,total):
    weights=[Decimal(str(r['price']))*r['quantity'] for r in items]
    whole=sum(weights);remaining=Decimal(str(total));result=[]
    for index,(item,weight) in enumerate(zip(items,weights)):
        net=remaining if index==len(items)-1 else (Decimal(str(total))*weight/whole).quantize(Decimal('.01'),rounding=ROUND_HALF_UP) if whole else Decimal(0)
        net=min(remaining,net);remaining-=net
        result.append(dict(item,original_total=float(weight),net_total=float(net)))
    return result
