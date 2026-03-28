from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import pandas as pd

query = "свадебное агентство москва"

driver = webdriver.Chrome()
driver.get(f"https://yandex.ru/maps/?text={query}")

time.sleep(5)

results = []

cards = driver.find_elements(By.CLASS_NAME, "search-business-snippet-view")

for card in cards[:50]:
    try:
        card.click()
        time.sleep(2)

        name = driver.find_element(By.CLASS_NAME, "orgpage-header-view__header").text
        
        try:
            phone = driver.find_element(By.CLASS_NAME, "business-contacts-view__phone-number").text
        except:
            phone = ""

        try:
            site = driver.find_element(By.CLASS_NAME, "business-urls-view__link").get_attribute("href")
        except:
            site = ""

        try:
            address = driver.find_element(By.CLASS_NAME, "orgpage-header-view__address").text
        except:
            address = ""

        results.append({
            "name": name,
            "phone": phone,
            "site": site,
            "address": address
        })

    except:
        pass

df = pd.DataFrame(results)
df.to_csv("agencies_moscow.csv", index=False)

driver.quit()
