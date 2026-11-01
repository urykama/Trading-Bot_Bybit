import json
import time
import urllib
import hmac
import hashlib
import requests


class Binance():
    methods = {
        # API-Key methods
        'serverTime': [0, 0, 'GET', 'v1/time'],
        'depth': [0, 0, 'GET', 'v1/depth'],
        'klines': [0, 0, 'GET', 'v1/klines'],
        'MarkPriceF': [0, 0, 'GET', 'v1/premiumIndex'],
        'ExchangeInfo': [0, 0, 'GET', 'v1/exchangeInfo'],
        'CheckServerTime': [0, 0, 'GET', 'v1/time'],
        # Test connectivity to the Rest API and get the current server time
        'TestConnectivity': [0, 0, 'GET', 'v1/ping'],
        # Test connectivity to the Rest API.

        'listenKey': [1, 0, 'POST', 'v1/listenKey'],
        'listenKeyPUT': [1, 0, 'PUT', 'v1/listenKey'],
        'KeepUDStream': [1, 0, 'PUT', 'v1/listenKey'],

        'NewOrderF': [1, 1, 'POST', 'v1/order'],
        'CancelOrderF': [1, 1, 'DELETE', 'v1/order'],
        'CancelAllOrd': [1, 1, 'DELETE', 'v1/allOpenOrders'],
        'CurAllOpenOrd': [1, 1, 'GET', 'v1/openOrders'],
        'AccountInfoF': [1, 1, 'GET', 'v2/account'],  # leverage
        # Get current account information.
        'LeverageBracket': [1, 1, 'GET', 'v1/leverageBracket'],  # leverage
        'PositionInfo': [1, 1, 'GET', 'v2/positionRisk'],  # leverage
        # Position Information V2 (USER_DATA)
        'GetIncomeHistoryF': [1, 1, 'GET', 'v1/income'],
        'CommisRateF': [1, 1, 'GET', 'v1/commissionRate']}

    def __init__(self):
        K = 'wJ4uvKey2ap2eVGu3jQnof4ABz5sflHcVWYSVNmgiTtS61GNcR09xzOWo6wt0Jz8'
        S = 'VsqwHLpr6UXlP1OaevLGMEe7mwwmg3TF8NuJnh3e8WZl6x2TKXXj5twCjfiK541z'
        self.API_KEY = K
        self.API_SECRET = bytearray(S, encoding='utf-8')
        self.shift_seconds = 0
        self.headers = {"X-MBX-APIKey": K}
        self.time = int(time.time() * 1000)
        res = requests.request(method='GET',
                               url='https://fapi.binance.com/fapi/v1/time')
        servTime = res.json()
        self.shift_seconds = (servTime['serverTime'] - self.time)
        print('Задержка сети: ', self.shift_seconds)

    def __getattr__(self, name):
        def wrapper(*args, **kwargs):
            kwargs.update(command=name)
            return self.call_api(**kwargs)

        return wrapper

    def call_api(self, **kwargs):
        command = kwargs.pop('command')
        url = 'https://fapi.binance.com/fapi/' + self.methods[command][3]
        payload = urllib.parse.urlencode(kwargs)
        if self.methods[command][0]:
            if self.methods[command][1]:
                kwargs.update({'timestamp':
                                   int(time.time() * 1000) + self.shift_seconds})
                payload = urllib.parse.urlencode(kwargs).encode('utf-8')
                sign = hmac.new(key=self.API_SECRET,
                                msg=payload,
                                digestmod=hashlib.sha256).hexdigest()
                payload = payload.decode("utf-8") + "&signature=" + str(sign)
            url += '?' + payload
            '''
            print()
            print(self.headers)
            print(self.methods[command][2])
            print(url)
            '''
            response = requests.request(headers=self.headers,
                                        method=self.methods[command][2],
                                        url=url)
        else:
            url += '?' + payload
            response = requests.request(method=self.methods[command][2],
                                        url=url)
        # print(response.text)
        if 'code' in response.text:
            te = response.json()
            if te['code'] != 200:
                print("ОШИБКА!")
                print(response.text)
                print("ОШИБКА83!")
        return response.json()


class BinanceSpot():
    methods = {
        # API-Key methods
        'serverTime': [0, 0, 'GET', 'v3/time'],
        'depth': [0, 0, 'GET', 'v3/depth'],
        'klines': [0, 0, 'GET', 'v3/klines'],
        'MarkPrice': [0, 0, 'GET', 'v1/premiumIndex'],
        'ExchangeInfo': [0, 0, 'GET', 'v3/exchangeInfo'],
        'CheckServerTime': [0, 0, 'GET', 'v3/time'],
        # Test connectivity to the Rest API and get the current server time
        'TestConnectivity': [0, 0, 'GET', 'v3/ping'],
        # Test connectivity to the Rest API.

        'listenKey': [1, 0, 'POST', 'v3/listenKey'],
        'listenKeyPUT': [1, 0, 'PUT', 'v3/userDataStream'],
        'KeepUDStream': [1, 0, 'PUT', 'v3/userDataStream'],

        'NewOrderF': [1, 1, 'POST', 'v1/order'],
        'CancelOrderF': [1, 1, 'DELETE', 'v1/order'],
        'CancelAllOrd': [1, 1, 'DELETE', 'v1/allOpenOrders'],
        'CurAllOpenOrd': [1, 1, 'GET', 'v1/openOrders'],
        'AccountInfoF': [1, 1, 'GET', 'v2/account'],  # leverage
        # Get current account information.
        'LeverageBracket': [1, 1, 'GET', 'v1/leverageBracket'],  # leverage
        'PositionInfo': [1, 1, 'GET', 'v2/positionRisk'],  # leverage
        # Position Information V2 (USER_DATA)
        'GetIncomeHistoryF': [1, 1, 'GET', 'v1/income'],
        'CommisRateF': [1, 1, 'GET', 'v1/commissionRate']}

    def __init__(self):
        K = 'G1MOh5vv2rGppBbQKJ4XBahCPbCWPR8bpr5GiKXNRz4ChtglOfrKRLqpziXb7Tpd'
        S = 'HZTQ8UkwtJW2PKqm2RbgadIOMOypHNi7crXR8cK8K3SrPWGV8BMPwnehFDEJOfBM'
        self.API_KEY = K
        self.API_SECRET = bytearray(S, encoding='utf-8')
        self.shift_seconds = 0
        self.headers = {"X-MBX-APIKey": K}
        self.time = int(time.time() * 1000)
        res = requests.request(method='GET',
                               url='https://api.binance.com/api/v3/time')
        servTime = res.json()
        self.shift_seconds = (servTime['serverTime'] - self.time)
        print('Задержка сети: ', self.shift_seconds)

    def __getattr__(self, name):
        def wrapper(*args, **kwargs):
            kwargs.update(command=name)
            return self.call_api(**kwargs)

        return wrapper

    def call_api(self, **kwargs):
        command = kwargs.pop('command')
        url = 'https://api.binance.com/api/' + self.methods[command][3]
        payload = urllib.parse.urlencode(kwargs)
        if self.methods[command][0]:
            if self.methods[command][1]:
                kwargs.update({'timestamp':
                                   int(time.time() * 1000) + self.shift_seconds})
                payload = urllib.parse.urlencode(kwargs).encode('utf-8')
                sign = hmac.new(key=self.API_SECRET,
                                msg=payload,
                                digestmod=hashlib.sha256).hexdigest()
                payload = payload.decode("utf-8") + "&signature=" + str(sign)
            url += '?' + payload
            '''
            print()
            print(self.headers)
            print(self.methods[command][2])
            print(url)
            '''
            response = requests.request(headers=self.headers,
                                        method=self.methods[command][2],
                                        url=url)
        else:
            url += '?' + payload
            response = requests.request(method=self.methods[command][2],
                                        url=url)
        if 'code' in response.text:
            te = response.json()
            if te['code'] != 200:
                print("ОШИБКА!")
                print(response.text)
                print("ОШИБКА83!")
        return response.json()
