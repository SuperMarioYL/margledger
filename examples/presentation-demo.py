import json
from margledger.ledger import RawIteration,build_ledger
from margledger.oracle import TestResult
from margledger.stop import recommend
rows=[RawIteration(iter=i+1,input_tokens=1000,output_tokens=100,wall_s=1.0,test_result=TestResult(total=passed)) for i,passed in enumerate([1,3,3,3])]
ledger=build_ledger(rows);rec=recommend(ledger,epsilon=0,k=2)
print(json.dumps({'marginal_values':[r.marginal_value for r in ledger],'cumulative_tokens':ledger[-1].cumulative_tokens,'recommendation':rec.as_dict()},indent=2))
