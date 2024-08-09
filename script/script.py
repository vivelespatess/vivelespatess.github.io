from flask import Flask, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from datetime import datetime
import threading
import time

app = Flask(__name__)
CORS(app)  # Activer CORS pour toutes les routes

# Variables globales pour stocker les taux de change
exchange_rates = {}
last_update_time = None

# Fonctions pour récupérer les taux de change
def fetch_google_rate():
    try:
        url = 'https://www.google.com/search?client=firefox-b-d&q=eur+ars+'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            rate_span = soup.find('span', class_='DFlfde SwHCTb')
            if rate_span:
                rate_text = rate_span.get_text(strip=True)
                cleaned_rate_text = rate_text.replace('\u202F', '').replace('\u202f', '').replace(',', '.')
                rate_match = re.search(r'[\d.]+', cleaned_rate_text)
                if rate_match:
                    rate = float(rate_match.group())
                    print(f"[{datetime.now()}] Google rate: {rate}")
                    return rate
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching Google rate: {e}")
    return None

def fetch_xoom_rate():
    try:
        url = 'https://www.xoom.com/argentina/send-money'
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            rate_div = soup.find('div', class_='js-exchange-rate')
            if rate_div:
                rate_text = rate_div.find('p').get_text(strip=True)
                rate_match = re.search(r'[\d,]+\.\d+', rate_text)
                if rate_match:
                    rate = rate_match.group().replace(',', '')
                    print(f"[{datetime.now()}] Xoom rate: {rate}")
                    return float(rate)
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching Xoom rate: {e}")
    return None

def fetch_wu_rate():
    try:
        url = 'https://www.westernunion.com/fr/fr/send-money-to-argentina.html'
        options = webdriver.FirefoxOptions()
        options.add_argument('--headless')
        driver = webdriver.Firefox(options=options)
        try:
            driver.get(url)
            try:
                rate_span = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "fx-to"))
                )
                def rate_is_valid(driver):
                    element_text = rate_span.text
                    return bool(re.search(r'\d+\.\d+', element_text))
                WebDriverWait(driver, 30).until(rate_is_valid)
                rate = rate_span.text
                cleaned_rate = re.search(r'\d+\.\d+', rate).group()
                print(f"[{datetime.now()}] Western Union rate: {cleaned_rate}")
                return float(cleaned_rate)
            except TimeoutException:
                print(f"[{datetime.now()}] Le taux de change n'a pas pu être trouvé dans le délai imparti ou n'est pas valide.")
        finally:
            driver.quit()
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching Western Union rate: {e}")
    return None

def fetch_remitly_rate():
    try:
        url = 'https://www.remitly.com/fr/fr/argentina/pricing'
        options = webdriver.FirefoxOptions()
        options.add_argument('--headless')
        driver = webdriver.Firefox(options=options)
        try:
            driver.get(url)
            rate_div = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.f4cg11h.ftw2f3l"))
            )
            rate_text = rate_div.text
            cleaned_rate_text = rate_text.replace('\u202F', '').replace(' ', '').replace('1 EUR = ', '')
            rate_match = re.search(r'[\d,.]+', cleaned_rate_text)
            if rate_match:
                rate = rate_match.group()
                rate = rate.replace('.', '')  # Supprimer les points des milliers
                rate = rate.replace(',', '.')  # Remplacer la virgule par un point pour les décimales
                print(f"[{datetime.now()}] Remitly rate: {rate}")
                return float(rate)
        finally:
            driver.quit()
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching Remitly rate: {e}")
    return None

def update_exchange_rates():
    global exchange_rates, last_update_time
    while True:
        try:
            google_rate = fetch_google_rate()
            xoom_rate = fetch_xoom_rate()
            wu_rate = fetch_wu_rate()
            remitly_rate = fetch_remitly_rate()

            if google_rate:
                exchange_rates['google_rate'] = google_rate
                if xoom_rate:
                    exchange_rates['xoom_rate'] = xoom_rate
                    exchange_rates['xoom_variation'] = ((xoom_rate - google_rate) / google_rate) * 100
                if wu_rate:
                    exchange_rates['wu_rate'] = wu_rate
                    exchange_rates['wu_variation'] = ((wu_rate - google_rate) / google_rate) * 100
                if remitly_rate:
                    exchange_rates['remitly_rate'] = remitly_rate
                    exchange_rates['remitly_variation'] = ((remitly_rate - google_rate) / google_rate) * 100
                last_update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            else:
                print(f"[{datetime.now()}] Impossible de trouver le taux de change Google.")
        except Exception as e:
            print(f"[{datetime.now()}] Error updating exchange rates: {e}")
        time.sleep(600)  # Attendre 10 minutes

@app.route('/api/rates', methods=['GET'])
def get_rates():
    global exchange_rates, last_update_time
    if exchange_rates:
        results = exchange_rates.copy()
        results['last_test'] = last_update_time
        print(results)  # Ajoutez ceci pour vérifier les données envoyées
        return jsonify(results)
    else:
        return jsonify({"error": "No exchange rates available"}), 500

if __name__ == '__main__':
    # Démarrer le thread pour mettre à jour les taux de change
    update_thread = threading.Thread(target=update_exchange_rates)
    update_thread.daemon = True
    update_thread.start()

    app.run(debug=True)
