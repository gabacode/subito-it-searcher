import json
import os
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from services.telegram import TelegramService


class QueryManager:
    def __init__(self, telegram: TelegramService):
        self.queries = dict()
        self.dbFile = "searches.tracked"
        self.telegram = telegram
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session = self._create_session()

    def _create_session(self):
        """Create a requests session with retry strategy"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.headers.update(self.headers)
        return session

    def load_queries(self):
        """A function to load the queries from the json file"""
        if not os.path.isfile(self.dbFile):
            return

        with open(self.dbFile) as file:
            self.queries = json.load(file)

    def save_queries(self):
        """A function to save the queries"""
        print(f"Attempting to save queries to {self.dbFile}")
        with open(self.dbFile, 'w') as file:
            file.write(json.dumps(self.queries))
        print("Save completed")

    def add(self, url, name, minPrice, maxPrice):
        """ A function to add a new query

        Arguments
        ---------
        url: str
            the url to run the query on
        name: str
            the name of the query
        minPrice: str
            the minimum price to search for
        maxPrice: str
            the maximum price to search for

        Example usage
        -------------
        >>> self.add("https://www.subito.it/annunci-italia/vendita/usato/?q=auto", "auto", "100", "null")
        """
        # If the query has already been added previously, delete it
        if self.queries.get(name):
            self.delete(name)

        self.queries[name] = {url: {minPrice: {maxPrice: {}}}}

    def delete(self, toDelete):
        """A function to delete a query

        Arguments
        ---------
        toDelete: str
            the query to delete

        Example usage
        -------------
        >>> self.delete("query")
        """
        self.queries.pop(toDelete)

    def print_queries(self):
        """A function to print the queries"""
        for search in self.queries.items():
            print("\nsearch: ", search[0])
            for query_url in search[1]:
                print("query url:", query_url)
                for url in search[1].items():
                    for minP in url[1].items():
                        for maxP in minP[1].items():
                            for result in maxP[1].items():
                                print("\n", result[1].get('title'), ":", result[1].get('price'), "-->",
                                      result[1].get('location'))
                                print(" ", result[0])

    def print_sitrep(self):
        """A function to print a compact list of trackings"""
        i = 1
        for search in self.queries.items():
            print('\n{}) search: {}'.format(i, search[0]))
            for query_url in search[1].items():
                for minP in query_url[1].items():
                    for maxP in minP[1].items():
                        print("query url:", query_url[0], " ", end='')
                        if minP[0] != "null":
                            print(minP[0], "<", end='')
                        if minP[0] != "null" or maxP[0] != "null":
                            print(" price ", end='')
                        if maxP[0] != "null":
                            print("<", maxP[0], end='')
                        print("\n")
            i += 1

    def _make_request(self, url, attempt, retry_delay):
        """Handle the HTTP request with retries and validation"""
        time.sleep(retry_delay + (attempt * 1))
        response = self.session.get(url, timeout=10)
        response.raise_for_status()

        if 'Access Denied' in response.text:
            raise ValueError(f"Access denied on attempt {attempt + 1}")

        return response

    @staticmethod
    def _parse_price(price_element, title):
        """Extract and parse price from a product element"""
        if not price_element:
            print(f"No price found for item {title}")
            return None

        price_text = price_element.get_text().strip()
        price = ''.join(c for c in price_text if c.isdigit() or c == '.')

        if not price:
            print(f"Could not extract numeric price from {price_text} for item {title}")
            return None

        return int(float(price))

    @staticmethod
    def _parse_location(product, title):
        """Extract location information from a product element"""
        try:
            town = product.find('span', re.compile(r'town')).string
            city = product.find('span', re.compile(r'city')).string
            return town + city
        except AttributeError:
            print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + f" Unknown location for item {title}")
            return "Unknown location"

    def _handle_product(self, product, name, url, minPrice, maxPrice):
        """Process a single product and return message if it's new"""
        title = product.find('h2').string

        try:
            price_element = product.find('p', class_=re.compile(r'price'))
            price = self._parse_price(price_element, title)
            if price is None:
                return None, False
        except (AttributeError, ValueError) as e:
            print(f"Error parsing price for item {title}: {str(e)}")
            price = "Unknown price"

        link = product.find('a').get('href')

        # Handle sold items
        sold = product.find('span', re.compile(r'item-sold-badge'))
        if sold is not None:
            if self.queries.get(name).get(url).get(minPrice).get(maxPrice).get(link):
                del self.queries[name][url][minPrice][maxPrice][link]
                return None, True
            return None, False

        location = self._parse_location(product, title)

        # Check price constraints
        if minPrice != "null" and price != "Unknown price" and price < int(minPrice):
            return None, False
        if maxPrice != "null" and price != "Unknown price" and price > int(maxPrice):
            return None, False

        # Check if this is a new item
        if self.queries.get(name).get(url).get(minPrice).get(maxPrice).get(link):
            return None, False

        # Create message for new item
        msg = (
                datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + "\n"
                + str(price) + "\n"
                + title + "\n"
                + location + "\n"
                + link + '\n'
        )

        # Store the new item
        self.queries[name][url][minPrice][maxPrice][link] = {
            'title': title,
            'price': price,
            'location': location
        }

        print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + f" Adding result: {title} - {price} - {location}")
        return msg, False

    def run_query(self, url, name, notify, minPrice, maxPrice):
        """Main query execution method"""
        print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + f" running query (\"{name}\" - {url})...")

        products_deleted = False
        max_retries = 5
        retry_delay = 3

        for attempt in range(max_retries):
            try:
                response = self._make_request(url, attempt, retry_delay)
                soup = BeautifulSoup(response.text, 'html.parser')
                product_list_items = soup.find_all('div', class_=re.compile(r'item-card'))

                print(f"Found {len(product_list_items)} items")
                if len(product_list_items) == 0:
                    print("No products found, might be a detection issue. Response preview:")
                    print(response.text[:500])
                    continue

                messages = []
                for product in product_list_items:
                    msg, deleted = self._handle_product(product, name, url, minPrice, maxPrice)
                    if msg:
                        messages.append(msg)
                    products_deleted = products_deleted or deleted

                if messages:
                    if notify:
                        if self.telegram.is_telegram_active():
                            self.telegram.send_telegram_messages(messages)
                        print("\n".join(messages))
                        print(f'\n{len(messages)} new elements have been found.')
                    self.save_queries()
                else:
                    print('\nAll lists are already up to date.')
                    if products_deleted:
                        self.save_queries()

                break

            except requests.exceptions.RequestException as e:
                print(f"Request failed on attempt {attempt + 1}: {str(e)}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(retry_delay * (attempt + 1))

            except Exception as e:
                print(f"Unexpected error on attempt {attempt + 1}: {str(e)}")
                if attempt == max_retries - 1:
                    raise

    def refresh(self, notify: bool):
        """A function to refresh the queries

        Arguments
        ---------
        notify: bool
            whether to send notifications or not

        Example usage
        -------------
        >>> self.refresh(True)   # Refresh queries and send notifications
        >>> self.refresh(False)  # Refresh queries and don't send notifications
        """
        try:
            for search in self.queries.items():
                for url in search[1].items():
                    for minP in url[1].items():
                        for maxP in minP[1].items():
                            self.run_query(url[0], search[0], notify, minP[0], maxP[0])
        except requests.exceptions.ConnectionError:
            print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + " ***Connection error***")
        except requests.exceptions.Timeout:
            print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + " ***Server timeout error***")
        except requests.exceptions.HTTPError:
            print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + " ***HTTP error***")
        except Exception as e:
            print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + " " + str(e))

    def __del__(self):
        """Cleanup method to properly close the session"""
        if hasattr(self, 'session'):
            self.session.close()
