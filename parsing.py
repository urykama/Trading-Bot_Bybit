import requests
from bs4 import BeautifulSoup

# Вставьте ваш актуальный токен (он живет 10 минут)
token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiIsImtpZCI6ImlkLWFwaS50cmFkZXJzZGlhcmllcy5jb20ta2V5LTEifQ.eyJpc3MiOiJpZC1hcGkudHJhZGVyc2RpYXJpZXMuY29tIiwiYXVkIjoidHJhZGVyc2RpYXJpZXMiLCJpYXQiOjE3OTMxMTMwMjAsImV4cCI6MTc5MzExMzYyMCwic3ViIjoxOTQwMTAsInVzZXIiOnsiZW1haWwiOiJ1cnlrYW1hQGdtYWlsLmNvbSIsImVtYWlsVmVyaWZpZWQiOnRydWUsInRlbGVncmFtSWQiOm51bGwsInRlbGVncmFtVXNlcm5hbWUiOm51bGx9fQ.xk-L1FSjSArxmzYlwXwzposUrxNBxBgo-xujkwf39dxMVoloKcIc6-mXAPIZbLzT3agwjOy7hu2RYpF-Uaj1jA"

# Ссылка на страницу скринера (проверьте точный URL, скорее всего https://tradersdiaries.com/ru/screener или /screener)
url = "https://tradersdiaries.com/ru/screener"

headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "accept-language": "ru,en;q=0.9,be;q=0.8",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 YaBrowser/26.10.0.0 Safari/537.36",
    "x-authorization": token
}

# Делаем GET запрос к самой странице
response = requests.get(url, headers=headers)

if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')

    # Находим группу "Волатильность"
    # Ищем таблицу с классом table-screener, внутри которой есть группа group-volatility
    volatility_group = soup.find('table', class_='table-screener', string=False)

    # Если найти по таблице сложно, ищем по классу группы
    volatility_section = soup.find('tbody', class_='group-volatility')

    if volatility_section:
        # Находим все строки (tr) внутри этой группы
        rows = volatility_section.find_all('tr', class_='row')

        print(f"{'Монета':<15} | {'5M':<10} | {'1H':<10} | {'1D':<10}")
        print("-" * 50)

        for row in rows:
            try:
                # 1. Название монеты (внутри td class="symbol" -> div class="symbol-overflow")
                symbol_td = row.find('td', class_='symbol')
                if symbol_td:
                    symbol = symbol_td.find('div', class_='symbol-overflow').text.strip()
                else:
                    continue  # Пропускаем, если не нашли монету

                # 2. Значения волатильности (все td с классом "value")
                values = row.find_all('td', class_='value')

                if len(values) >= 3:
                    vol_5m = values[0].text.strip()
                    vol_1h = values[1].text.strip()
                    vol_1d = values[2].text.strip()

                    print(f"{symbol:<15} | {vol_5m:<10} | {vol_1h:<10} | {vol_1d:<10}")

            except Exception as e:
                # Если какая-то строка сломалась, просто идем дальше
                continue
    else:
        print(
            "Не удалось найти блок с классом 'group-volatility'. Возможно, изменилась верстка или данные грузятся через JS.")

else:
    print(f"Ошибка при загрузке страницы: {response.status_code}")
    print("Возможно, истек токен или неверный URL.")
