from base64 import b64encode
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)


# Function to get access token
@app.get("/")
def get_access_token(scope=''):
    QI="emVuZGF5MS0yNDMyNjEyNDMwMzQyNDQ3NGU0Njc3NjEzMTU4NDMyZjc4NjM1MTZiNTg3MzU4NDMzNTRhNTA3Njc1MzM3MDQ1NzU1MjY1NzU2ZDQyNTg2OTc3NGE1MjQzNDI3Mjc2NDk1OTM3MzQ2ODU0Mzk0OTc0NDYyZTQ5NGI0MzI4MTEzMTQyMjkwMzg2NDQyOjNsVkdkNDdKV1hSNUFBa3M0ZVV5b1JoZ0cwc1BSWDI5ZDdNZGY1THE="
    URL="https://api-ce.kroger.com/v1/connect/oauth2/token"
    CREDS=f'Basic {QI}'
    CT="application/x-www-form-urlencoded"
    import  requests
    token=dict(requests.post(url=URL, headers={'Content-Type': CT,"Authorization":CREDS},data={"grant_type":"client_credentials","scope":"product.compact"}).json())["access_token"]
    return (token)
    if scope == '':
        scope = 'product.compact'
        auth_header = f"{CLIENT_ID}:{CLIENT_SECRET}".encode('utf-8')
        headers = {
            'Authorization': 'Basic ' + "emVuZGF5MS0yNDMyNjEyNDMwMzQyNDQ3NGU0Njc3NjEzMTU4NDMyZjc4NjM1MTZiNTg3MzU4NDMzNTRhNTA3Njc1MzM3MDQ1NzU1MjY1NzU2ZDQyNTg2OTc3NGE1MjQzNDI3Mjc2NDk1OTM3MzQ2ODU0Mzk0OTc0NDYyZTQ5NGI0MzI4MTEzMTQyMjkwMzg2NDQyOjNsVkdkNDdKV1hSNUFBa3M0ZVV5b1JoZ0cwc1BSWDI5ZDdNZGY1THE=",
            'Content-Type' : 'application/x-www-form-urlencoded'
        }
        data = {
            'grant_type': 'client_credentials',
            'scope': scope
        }
        
        response = requests.post('https://api-ce.kroger.com/v1/connect/oauth2/token', headers=headers, data=data)
        print(response.json())
        if response.status_code == 200:
            return response.json().get('access_token')
        return "fail"
    else:
        auth_header = f"{CLIENT_ID}:{CLIENT_SECRET}".encode('utf-8')
        headers = {
            'Authorization': 'Basic ' + str(b64encode(requests.utils.quote(auth_header)))[2:-1],
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'grant_type': 'client_credentials',
            'scope': scope
        }
        
        response = requests.post('https://api-ce.kroger.com/v1/connect/oauth2/token', headers=headers, data=data)
        
        if response.status_code == 200:
            return response.json().get('access_token')
        return "fail" 
@app.route('/get_tokens', methods=['POST'])
def get_tokens():
    # Get tokens
    general_token = get_access_token()
    product_token = get_access_token('product.compact')
    inventory_token = get_access_token('inventory.compact')

    # Return tokens as JSON response
    return jsonify({
        'General Token': general_token,
        'Product Token': product_token,
        'Inventory Token': inventory_token
    })

if __name__ == '__main__':
    app.run(host="0.0.0.0",port=8888)
