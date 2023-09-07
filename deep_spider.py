from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse, urljoin
import os


class deep_spider:
    def __init__(self, url: str, folder = './'):
        response = requests.get(url)
        self.url = response.url
        self.url += 'index.html' if response.url[-1] == '/' else ''
        self.url_folder = self.url[:self.url.rfind('/')+1]
        self.parse = urlparse(self.url)
        self.soup = BeautifulSoup(response.text, 'lxml')
        self.url_list = [self.url]
        self.url_deep_list = []

        if not os.path.exists(folder):
            os.makedirs(folder)
        if folder[-1] != '/':
            folder += '/'
        self.folder = folder

        self.print_mode = False

        self.download(self.url, self.soup)

    def deep_select(self, selector: str, url: str = None, soup: BeautifulSoup = None):
        if url is None:
            url = self.url
        if soup is None:
            soup = self.soup

        data_list = []
        for sel in soup.select(selector, href=True):
            href = sel['href']
            if href[:4] != 'http':
                href = urljoin(url, href)
            if href in self.url_list:
                continue
            self.url_list.append(href)
            soup_next = BeautifulSoup(requests.get(href).text, 'lxml')
            data_list.append((href, soup_next))

        for href, soup_next in data_list:
            self.download(href, soup_next)
            self.deep_select(selector, href, soup_next)

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
        folder = ''
        if file.find('/') > 0:
            folder = file[:file.rfind('/')]
            if not os.path.exists(self.folder + folder):
                os.makedirs(self.folder + folder)

        if self.print_mode:
            print(file)

        for link in soup.select('link', href=True):
            link['href'] = self._single_download(link['href'], url, folder)

        for script in soup.find_all('script', {'src': True}):
            script['src'] = self._single_download(script['src'], url, folder)

        open(self.folder + file, 'wb').write(str(soup).encode('utf8'))

    def _single_download(self, url_curr: str, url_base: str, folder: str):
        if url_curr[:4] != 'http':
            url_curr = urljoin(url_base, url_curr)
        parse = urlparse(url_curr)
        if parse.netloc == self.parse.netloc and parse.path.find(self.parse.path) == 0:
            filename = parse.path.replace(self.parse.path, '')
        else:
            filename = parse.netloc + parse.path
        link = url_curr[:url_curr.find(parse.path)+len(parse.path)]
        path = os.path.relpath('C:/'+filename+url_curr[url_curr.find(parse.path)+len(parse.path):], 'C:/'+folder)

        if link in self.url_list:
            return path
        if link in self.url_deep_list:
            return path
        self.url_deep_list.append(link)

        if filename.find('/') > 0:
            if not os.path.exists(self.folder + filename[:filename.rfind('/')]):
                os.makedirs(self.folder + filename[:filename.rfind('/')])
        open(self.folder + filename, 'wb').write(requests.get(link).content)
        return path


if __name__ == '__main__':
    url = 'https://numpy.org/doc/stable/reference/'
    selector = 'div.bd-toc-item.active a'

    hs = deep_spider(url, './numpy/')
    hs.print_mode = True
    hs.deep_select(selector)
