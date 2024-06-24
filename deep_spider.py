from bs4 import BeautifulSoup
from urllib.parse import *
import requests
import aiohttp
import asyncio
import os
import shutil


def main():
    url = input('url: ')
    folder = input('folder: ')
    selectors = ['a', 'link', 'script', 'img', 'meta']
    attributes = ['href', 'src', 'content']
    
    print()
    
    ds = deep_spider(url, folder=folder, print_mode=True, log_mode=True)
    ds.deep_select(selectors, attributes)

    print('Download complete!')



class deep_spider:
    
    html_parser = 'lxml'
    top_folder = 'saved'
    log_folder = 'logs'
    link_attr = {'href'}
    paths = set()
    select_same_netloc = True
    select_same_paths = False
    file_exts = {'.html', '.css', '.js', '.svg', '.png', '.jpg', 'ico'}

    @staticmethod
    def __check_folder(path: str) -> str:
        folder = os.path.dirname(path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)
        return folder
    
    @classmethod
    def __path_correction(cls,
                          path: str,
                          olds: tuple = (':', '*', '?', '"', '<', '>', '|'),
                          new: str = '_',
                        ) -> str:
        path = path.replace('\\', '/')
        while path.find('//') != -1:
            path = path.replace('//', '/')
        for old in olds:
            path = path.replace(old, new)
        return path


    def __init__(self,
                 url: str,
                 folder: str = 'spider',
                 print_mode: bool = False,
                 log_mode: bool = False,
                ) -> None:
        response = requests.get(url)
        url = response.url
        url = url.replace('\\', '/')
        parse = urlparse(url)._replace(query='', fragment='')
        if not parse.path.endswith('.html') or not parse.path.endswith('/'):
            parse = parse._replace(path=os.path.join(parse.path, '/'))
        url = urlunparse(parse)
        url_dirname = os.path.dirname(url)
        self.parse_dir = urlparse(url_dirname)
        
        self.folder = os.path.join(self.top_folder, folder)
        if os.path.exists(self.folder):
            shutil.rmtree(self.folder)
        
        self.print_mode = print_mode
        
        self.log_mode = log_mode
        if log_mode:
            self.log_filepath = os.path.join(self.log_folder, self.__path_correction(folder, new='').replace('/', '_') + '_log.txt')
            if os.path.exists(self.log_filepath):
                os.remove(self.log_filepath)
        
        self.__init_urls()
        self.urls['htmls'].append(url)
        self.urls['path'][parse.netloc] = {}
        self.urls['path'][parse.netloc][parse.path] = self.__parse_to_path(parse)
        self.async_req = async_request()
        
        if print_mode:
            print('url', url)
            print('folder:', self.folder)
            print('path:', self.urls['path'][parse.netloc][parse.path])
    
    def deep_select(self,
                    selectors: list = ['a', 'link'],
                    attributes: list = ['href', 'src'],
                    ) -> None:
        while self.urls['htmls']:
            url_curr = self.urls['htmls'].pop()
            response = requests.get(url_curr)
            soup = BeautifulSoup(response.text, self.html_parser)
            for selector in selectors:
                for element in soup.select(selector):
                    for attr in attributes:
                        if not attr in element.attrs:
                            continue
                        parse = urlparse(urljoin(url_curr, element[attr]))
                        if os.path.splitext(parse.path)[1] == '' and not attr in self.link_attr and not parse.path[-1] in {'/', '\\'}:
                            continue
                        if parse.netloc not in self.urls['path']:
                            self.urls['path'][parse.netloc] = {}
                        if parse.path in self.urls['path'][parse.netloc]:
                            element[attr] = self.urls['path'][parse.netloc][parse.path] + parse.query + parse.fragment
                            continue
                        self.__url_append(urlunparse(parse._replace(query='', fragment='')))
                        path = self.__parse_to_path(parse)
                        element[attr] = path + parse.query + parse.fragment
            
            if self.urls['elements']:
                datas = self.async_req.start_async(self.urls['tasks'])
                for url_elem, data in zip(self.urls['elements'], datas):
                    parse = urlparse(url_elem)
                    self.__save_data(url_elem, self.urls['path'][parse.netloc][parse.path], data)
                self.urls['elements'].clear()
                self.urls['tasks'].clear()
            
            if self.print_mode:
                parse = urlparse(url_curr)
                print(f'{url_curr} -> {self.urls["path"][parse.netloc][parse.path]}')
            
            self.__save_data(url_curr, self.urls['path'][parse.netloc][parse.path], str(soup).encode())
    
    
    def __init_urls(self):
        self.urls = {}
        self.urls['path'] = {}
        self.urls['htmls'] = []
        self.urls['elements'] = []
        self.urls['tasks'] = []
    
    def __url_append(self, url: str) -> None:
        parse = urlparse(url)
        if os.path.splitext(url)[1] in {'', '.html'}:
            if not self.select_same_netloc or parse.netloc == self.parse_dir.netloc:
                if not self.select_same_paths or parse.path.find(self.parse_dir.path) == 0:
                    self.urls['htmls'].append(url)
                    return

        self.urls['elements'].append(url)
        self.urls['tasks'].append(async_request.get(url))

    def __save_data(self, url: str, path: str, data: bytes) -> None:
        path = os.path.join(self.folder, path)
        self.__check_folder(path)
        
        if self.log_mode:
            with open(self.log_filepath, 'a') as f:
                f.write(f'{url} -> {path}\n')
        
        with open(path, 'wb') as f:
            f.write(data)

    def __parse_to_path(self, parse: ParseResult) -> str:
        if parse.netloc not in self.urls['path']:
            self.urls['path'][parse.netloc] = {}
        if parse.path in self.urls['path'][parse.netloc]:
            return self.urls['path'][parse.netloc][parse.path]
        
        if parse.netloc == self.parse_dir.netloc and parse.path.find(self.parse_dir.path) == 0:
            path = parse.path.replace(self.parse_dir.path, '', 1)
        else:
            path = parse.netloc + parse.path
        
        if os.path.splitext(path)[1] not in self.file_exts:
            path = os.path.join(path, 'index.html')
        
        while path.startswith('/') or path.startswith('\\'):
            path = path[1:]
        
        path = self.__path_correction(path)
        
        self.urls['path'][parse.netloc][parse.path] = path
        return path



class async_request:
    
    host_num = 10
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
    accept = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"

    @staticmethod
    def __ensure_future(func):
        def wrapper(*args, **kwargs):
            return asyncio.ensure_future(func(*args, **kwargs))
        return wrapper

    @classmethod
    @__ensure_future
    async def get(cls, url: str) -> bytes:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit_per_host=cls.host_num)) as session:
            async with session.get(url, headers={'user-agent': cls.user_agent, 'accept': cls.accept}) as res:
                return await res.read()

    @staticmethod
    def start_async(tasks: list) -> list:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.wait(tasks))
        result = []
        for t in tasks:
            try:
                r = t.result()
            except:
                r = b'Error: 404 Not Found\n'
            result.append(r)
        return result


if __name__ == '__main__':
    main()