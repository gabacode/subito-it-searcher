import json
import os
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup, Tag

from services.telegram import TelegramService


class QueryManager:
    def __init__(self, telegram: TelegramService):
        self.queries = dict()
        self.dbFile = "searches.tracked"
        self.telegram = telegram

    def load_queries(self):
        """A function to load the queries from the json file"""
        if not os.path.isfile(self.dbFile):
            return

        with open(self.dbFile) as file:
            self.queries = json.load(file)

    def save_queries(self):
        """A function to save the queries"""
        with open(self.dbFile, 'w') as file:
            file.write(json.dumps(self.queries))

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

    def run_query(self, url, name, notify, minPrice, maxPrice):
        """A function to run a query

        Arguments
        ---------
        url: str
            the url to run the query on
        name: str
            the name of the query
        notify: bool
            whether to send notifications or not
        minPrice: str
            the minimum price to search for
        maxPrice: str
            the maximum price to search for

        Example usage
        -------------
        >>> self.run_query("https://www.subito.it/annunci-italia/vendita/usato/?q=auto", "query", True, 100, "null")
        """
        print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + " running query (\"{}\" - {})...".format(name, url))

        products_deleted = False

        page = requests.get(url)
        soup = BeautifulSoup(page.text, 'html.parser')

        product_list_items = soup.find_all('div', class_=re.compile(r'item-card'))
        msg = []

        for product in product_list_items:
            title = product.find('h2').string
            try:
                price = product.find('p', class_=re.compile(r'price')).contents[0]
                price = str(price)
                # check if the span tag exists
                price_soup = BeautifulSoup(price, 'html.parser')
                if type(price_soup) == Tag:
                    continue
                # at the moment (20.5.2021) the price is under the 'p' tag with 'span' inside if shipping available
                price = int(price.replace('.', '')[:-2])
            except AttributeError:
                price = "Unknown price"
            link = product.find('a').get('href')

            sold = product.find('span', re.compile(r'item-sold-badge'))

            # check if the product has already been sold
            if sold is not None:
                # if the product has previously been saved remove it from the file
                if self.queries.get(name).get(url).get(minPrice).get(maxPrice).get(link):
                    del self.queries[name][url][minPrice][maxPrice][link]
                    products_deleted = True
                continue

            try:
                town = product.find('span', re.compile(r'town')).string
                city = product.find('span', re.compile(r'city')).string
                location = town + city
            except AttributeError:
                print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + " Unknown location for item %s" % title)
                location = "Unknown location"
            if minPrice == "null" or price == "Unknown price" or price >= int(minPrice):
                if maxPrice == "null" or price == "Unknown price" or price <= int(maxPrice):
                    if not self.queries.get(name).get(url).get(minPrice).get(maxPrice).get(link):  # found a new element
                        tmp = (
                                datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + "\n"
                                + str(price) + "\n"
                                + title + "\n"
                                + location + "\n"
                                + link + '\n'
                        )
                        msg.append(tmp)
                        self.queries[name][url][minPrice][maxPrice][link] = {'title': title, 'price': price,
                                                                             'location': location}
                        print(datetime.now().strftime("%Y-%m-%d, %H:%M:%S") + " Adding result:", title, "-", price, "-",
                              location)

        if len(msg) > 0:
            if notify:
                if self.telegram.is_telegram_active():
                    self.telegram.send_telegram_messages(msg)
                print("\n".join(msg))
                print('\n{} new elements have been found.'.format(len(msg)))
            self.save_queries()
        else:
            print('\nAll lists are already up to date.')

            # if at least one search was deleted, update the search file
            if products_deleted:
                self.save_queries()

        # print("queries file saved: ", queries)

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
