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
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit_per_host=10)) as session:
        async with session.get(url, headers={'user-agent': user_agent, 'accept': accept}) as res:
            return await res.read()

def run_async(tasks: list) -> list:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(tasks))
    return [t.result() for t in tasks]


class deep_spider:
    def __init__(self, url: str, folder: str = None, print_mode: bool = False, log_mode: bool = False, selectors: list[str] = None, select_attributes: list[str] = None):
        response = requests.get(url)
        self.url = response.url
        if self.url[-1] == '/':
            self.url += 'index.html'
        elif self.url[-5:] != '.html':
            self.url += '/index.html'
        self.url_folder = self.url[:self.url.rfind('/')+1]
        self.parse = urlparse(self.url_folder)
        self.soup = BeautifulSoup(response.text, 'lxml')

        self.url_set = {self.url}
        self.deep_url_set = set()
        self.tasks = []
        self.paths = []

        if not folder:
            folder = './html/'
        folder += '/' if folder[-1] != '/' else ''
        if not os.path.exists(folder):
            os.makedirs(folder)
        self.folder = folder

        self.print_mode = print_mode
        self.log_mode = log_mode
        if log_mode:
            self.log_filename = self.folder.replace('/', '_') + 'log.txt'
        self.selectors = selectors if selectors else ['link', 'script', 'img']
        self.select_attributes = select_attributes if select_attributes else ['href', 'src']

        self.download(self.url, self.soup)
        self.start_download()

    def start_download(self):
        if not self.tasks:
            return
        datas = run_async(self.tasks)
        self.tasks.clear()
        for path, data in zip(self.paths, datas):
            i = path.rfind('/')
            if i > 0:
                if not os.path.exists(path[:i]):
                    os.makedirs(path[:i])
            with open(path, 'wb') as f:
                f.write(data)
        self.paths.clear()

    def deep_select(self, selector: str, url: str = None, soup: BeautifulSoup = None):
        if url is None:
            url = self.url
        if soup is None:
            soup = BeautifulSoup(requests.get(url).text, 'lxml')

        urls = []
        for sel in soup.select(selector, href=True):
            if not sel.has_attr('href'):
                continue
            href = self._url_correct(sel['href'], url)
            if href in self.url_set or self.parse.netloc != urlparse(href).netloc:
                continue
            self.url_set.add(href)
            
            urls.append(href)
            self.tasks.append(get(href))

        if not self.tasks:
            return

        htmls = run_async(self.tasks)
        self.tasks.clear()

        soups = []
        for url, html in zip(urls, htmls):
            try:
                bs = BeautifulSoup(html.decode(encoding='utf-8'), 'lxml')
                soups.append(bs)
                self.download(url, bs)
            except:
                with open(self.folder + self.get_filepath(url)[0], 'wb') as f:
                    f.write(html)
        self.start_download()
        
        for url, soup in zip(urls, soups):
            self.deep_select(selector, url, soup)

    def get_filepath(self, url: str) -> (str, str):
        parse = urlparse(url)
        if parse.netloc == self.parse.netloc and parse.path.find(self.parse.path) == 0:
            if self.parse.path != '/':
                filepath = parse.path.replace(self.parse.path, '')
            else:
                filepath = parse.path[1:]
        else:
            filepath = parse.netloc + parse.path
        filepath = filepath.replace(':', '_')
        url = url[:url.find(parse.path)+len(parse.path)]

        folder = ''
        if '/' in filepath:
            folder = filepath[:filepath.rfind('/')]
            if not os.path.exists(self.folder + folder):
                os.makedirs(self.folder + folder)
        return filepath, folder


    def download(self, url: str = None, soup: BeautifulSoup = None):
        if url is None:
            url = self.url
        if soup is None:
            soup = BeautifulSoup(requests.get(url).text, 'lxml')

        filepath, folder = self.get_filepath(url)

        for sel in self.selectors:
            for set in soup.select(sel):
                for attr in self.select_attributes:
                    if set.has_attr(attr) and not set[attr].startswith('data:') and not set[attr].startswith('http'):
                        set[attr] = self._single_download(set[attr], url, folder)

        with open(self.folder + filepath, 'wb') as f:
            f.write(str(soup).encode('utf8'))


    def _single_download(self, url_curr: str, url_base: str, folder: str) -> str:
        url = self._url_correct(url_curr, url_base)
        parse = urlparse(url)
        if parse.netloc == self.parse.netloc and parse.path.find(self.parse.path) == 0:
            if self.parse.path != '/':
                filename = parse.path.replace(self.parse.path, '')
            else:
                filename = parse.path[1:]
        else:
            filename = parse.netloc + parse.path
        filename = filename.replace(':', '_')
        path = os.path.relpath('C:/'+filename+url[url.find(parse.path)+len(parse.path):], 'C:/'+folder)
        url = url[:url.find(parse.path)+len(parse.path)]

        if not url:
            return url_curr
        if url in self.url_set:
            return path
        if url in self.deep_url_set:
            return path
        self.deep_url_set.add(url)

        self.tasks.append(get(url))
        self.paths.append(self.folder + filename)

        if self.print_mode:
            print(url)
        if self.log_mode:
            with open(self.log_filename, 'a') as f:
                f.write(url + '\n')

        return path
    
    def _url_correct(self, url: str, url_base: str) -> str:
        file_ext = ['.html', '.css', '.js', '.svg', '.png', '.jpg']
        if not url:
            return url
        url = url.replace('\\', '/')
        parse = urlparse(url)
        if parse.scheme == '':
            url = urljoin(url_base, url)
            parse = urlparse(url)
        for ext in file_ext:
            if ext in url:
                return url
        index = '/index.html' if parse.path == '' or parse.path[-1] != '/' else 'index.html'
        url = urlunparse(parse._replace(path = parse.path + index))
        return url


if __name__ == '__main__':
    url = input('url: ')
    foldername = input('folder name: ')
    selectors = ['link', 'script', 'a', 'img']
    attributes = ['href', 'src']
    selector = 'a'

    ds = deep_spider(url, folder=foldername, log_mode=True, selectors=selectors, select_attributes=attributes)
    ds.deep_select(selector)
