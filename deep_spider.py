from bs4 import BeautifulSoup
from urllib.parse import *
import aiohttp
import asyncio
import requests
import os

user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
accept = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9'

def ensure_future(func):
    def wrapper(*args, **kwargs):
        return asyncio.ensure_future(func(*args, **kwargs))
    return wrapper

@ensure_future
async def get(url: str) -> bytes:
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit_per_host=50)) as session:
        async with session.get(url, headers={'user-agent': user_agent, 'accept': accept}) as res:
            return await res.read()

def run_async(tasks: list) -> list:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(tasks))
    return [t.result() for t in tasks]


class deep_spider:
    def __init__(self, url: str, folder = './'):
        response = requests.get(url)
        self.url = response.url
        if self.url[-1] == '/':
            self.url += 'index.html'
        elif self.url[-5:] != '.html':
            self.url += '/index.html'
        self.url_folder = self.url[:self.url.rfind('/')+1]
        self.parse = urlparse(self.url_folder)
        self.soup = BeautifulSoup(response.text, 'lxml')

        self.url_list = [self.url]
        self.url_deep_list = []
        self.tasks = []
        self.paths = []

        folder += '/' if folder[-1] != '/' else ''
        if not os.path.exists(folder):
            os.makedirs(folder)
        self.folder = folder

        self.print_mode = False

        self.download(self.url, self.soup)
        self.start_download()
        
    def start_download(self):
        if not self.tasks:
            return
        datas = run_async(self.tasks)
        self.tasks.clear()
        for path, data in zip(self.paths, datas):
            with open(path, 'wb') as f:
                f.write(data)
        self.paths.clear()

    def deep_select(self, selector: str, url: str = None, soup: BeautifulSoup = None):
        if url is None:
            url = self.url
        if soup is None:
            soup = self.soup

        urls = []
        for sel in soup.select(selector, href=True):
            href = urldefrag(sel['href']).url
            if not href:
                continue
            if href[:4] != 'http':
                href = urljoin(url, href)
            if href[-1] == '/':
                href += 'index.html'
            elif href[href.rfind('/'):].find('.') < 0:
                href += '/index.html'

            if href in self.url_list or self.parse.netloc != urlparse(href).netloc:
                continue
            self.url_list.append(href)
            
            urls.append(href)
            self.tasks.append(get(href))

        if not self.tasks:
            return

        htmls = run_async(self.tasks)
        self.tasks.clear()

        soups = []
        for url, html in zip(urls, htmls):
            soups.append(BeautifulSoup(html.decode(encoding='utf-8'), 'lxml'))
            self.download(url, soups[-1])
        self.start_download()
        
        for url, soup in zip(urls, soups):
            self.deep_select(selector, url, soup)

    def download(self, url: str = None, soup: BeautifulSoup = None):
        if url is None:
            url = self.url
        if soup is None:
            soup = BeautifulSoup(requests.get(url).text, 'lxml')

        if url[-1] == '/':
            url += 'index.html'
        if url.find(self.url_folder) == 0:
            file = url.replace(self.url_folder, '')
        else:
            file = url[url.find('//')+2:]
        file = file.replace(':', '_')
        folder = ''
        if file.find('/') > 0:
            folder = file[:file.rfind('/')]
            if not os.path.exists(self.folder + folder):
                os.makedirs(self.folder + folder)

        selectors = ['link', 'script', 'img']
        attributes = ['href', 'src']
        for sel in selectors:
            for set in soup.find_all(sel):
                for attr in attributes:
                    if set.has_attr(attr):
                        set[attr] = self._single_download(set[attr], url, folder)

        with open(self.folder + file, 'wb') as f:
            f.write(str(soup).encode('utf8'))

        if self.print_mode:
            print(file)

    def _single_download(self, url: str, url_base: str, folder: str):
        if url[:4] != 'http':
            url = urljoin(url_base, url)
        if url[-1] == '/':
            url += 'index.html'
        parse = urlparse(url)
        if parse.netloc == self.parse.netloc and parse.path.find(self.parse.path) == 0:
            filename = parse.path.replace(self.parse.path, '')
        else:
            filename = parse.netloc + parse.path
        filename = filename.replace(':', '_')
        url = url[:url.find(parse.path)+len(parse.path)]
        path = os.path.relpath('C:/'+filename+url[url.find(parse.path)+len(parse.path):], 'C:/'+folder)

        if url in self.url_list:
            return path
        if url in self.url_deep_list:
            return path
        self.url_deep_list.append(url)

        i = filename.rfind('/')
        if i > 0:
            if not os.path.exists(self.folder + filename[:i]):
                os.makedirs(self.folder + filename[:i])

        self.tasks.append(get(url))
        self.paths.append(self.folder + filename)

        return path


if __name__ == '__main__':
    url = 'https://pandas.pydata.org/docs/reference/'
    selector = 'div.bd-toc-item.navbar-nav a'

    hs = deep_spider(url, './pandas/')
    hs.print_mode = True
    hs.deep_select(selector)
