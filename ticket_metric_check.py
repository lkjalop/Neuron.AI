from prometheus_client import REGISTRY
import sys, pathlib
sys.path.insert(0,str(pathlib.Path('src').resolve()))
from core.tickets import store
from core import metrics
print('Has transitions counter object:', metrics.TICKET_TRANSITIONS_TOTAL)
print('Internal name now:', getattr(metrics.TICKET_TRANSITIONS_TOTAL,'_name',None))
print('Collector registered names present?', hasattr(REGISTRY,'_names_to_collectors'))
if hasattr(REGISTRY,'_names_to_collectors'):
    print('Registered keys:', list(getattr(REGISTRY,'_names_to_collectors').keys())[:50])
T=store.create_ticket(None,'low',4)
store.update_ticket(T.id,status='ack')
store.update_ticket(T.id,status='in_progress')
store.update_ticket(T.id,status='closed')
print('After transitions collect scan:')
for m in REGISTRY.collect():
    if m.name=='neuron_ticket_transitions_total':
        print('FOUND metric family:')
        for s in m.samples:
            if s.name=='neuron_ticket_transitions_total':
                print(s.labels,s.value)
        break
else:
    print('NOT_FOUND')
