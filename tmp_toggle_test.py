import os
from fastapi.testclient import TestClient
os.environ['ADMIN_API_KEY']='adminkey'
from core.main import app
c=TestClient(app)
resp=c.post('/snn/toggle',json={'enabled':True},headers={'x-api-key':'adminkey'})
print('Status',resp.status_code)
print(resp.text)
