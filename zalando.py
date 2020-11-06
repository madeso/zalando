#!/usr/bin/env python3

import urllib.parse
import urllib.request
import argparse
import typing
import json
import collections
import re
import os
from bs4 import BeautifulSoup


re_cdata = re.compile(r'<!\[CDATA\[(.*?)\]\]>')


def download_url(link: str, status: str) -> str:
    status_text = '' if len(status)==0 else '({})'.format(status)
    print('Requesting url{}: {}'.format(status_text, link))
    try:
        with urllib.request.urlopen(link) as url_handle:
            data = url_handle.read()
            return data.decode('utf-8')
    except urllib.error.HTTPError as http_error:
        if http_error.code == 404:
            print('404 error')
            return ''
        else:
            raise http_error


def get_cachedir() -> str:
    filedir = os.path.join(os.getcwd(), 'cache')
    os.makedirs(filedir, exist_ok=True)
    return filedir


def get_url_or_cache(link: str, status: str) -> str:
    filedir = get_cachedir()
    filename = urllib.parse.quote(link, '')
    path = os.path.join(filedir, filename)
    if os.path.exists(path):
        with open(path, 'rb') as file_handle:
            return file_handle.read().decode('utf-8')
    else:
        data = download_url(link, status)
        with open(path, 'wb') as file_handle:
            file_handle.write(data.encode('utf-8'))
        return data


def list_all_cdata(data: str) -> typing.Iterable[typing.Any]:
    """list all cdata strings in a soup string
    it should probably be a single get but this works for now"""
    for cdata_match in re_cdata.finditer(data):
        cdata = json.loads(cdata_match.group(1))
        yield cdata


def first(list_or_iterable):
    for item in list_or_iterable:
        return item
    return None


def map_json_in_soup(soup):
    """return a map of id  to json for all json scripts in soup"""
    script_elements = [t for t in soup.find_all('script') if t.has_attr('type') and t.has_attr('id') and t['type'] == 'application/json']
    json_map = {a['id']: first(list_all_cdata(str(a.string))) for a in script_elements}
    return json_map


def write_json_dump(key, jsons):
    with open('dump-' + key + '.json', 'w') as file_handle:
        json.dump(jsons, file_handle, sort_keys=True, indent=4)


def debug_dump_map(jsons):
    """write all json maps to dump- files in root"""
    for key in jsons:
        write_json_dump(key, jsons[key])


class Article:
    def __init__(self, brand: str, name: str, key: str, media: str):
        self.brand = brand
        self.name = name
        self.key = key
        self.media = media


class ArticleInfo:
    def __init__(self, material: typing.Dict[str, str], tyg: str):
        self.material = material
        self.tyg = tyg


class Store:
    def __init__(self, articles: typing.List[Article]):
        self.articles = articles


class JsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Store):
            return {'__store__': True, 'articles': obj.articles}
        if isinstance(obj, Article):
            return {'__article__': True, 'brand': obj.brand, 'name': obj.name, 'key': obj.key, 'media': obj.media}
        return json.JSONEncoder.default(self, obj)


def as_types(dct):
    if '__store__' in dct:
        return Store(dct['articles'])
    if '__article__' in dct:
        return Store(dct['brand'], dct['name'], dct['key'], dct['media'])
    return dct


def save_store(data: Store):
    with open('store.json', 'w') as file_handle:
        json.dump(data, file_handle, cls=JsonEncoder, sort_keys=True, indent=4)


def load_store() -> Store:
    with open('store.json', 'r') as file_handle:
        return json.load(file_handle, object_hook=as_types)


def article_from_article_soup(art, base_url: str, debug: bool) -> Article:
    brand_name = art['brand_name']
    name = art['name']
    url_key = art['url_key']
    media = first(art['media'])
    media_path = media['path']

    url = urllib.parse.urljoin(base_url, url_key + '.html')
    media_url = urllib.parse.urljoin('https://img01.ztat.net/article/', media_path)

    if debug:
        write_json_dump('art', art)

    return Article(brand_name, name, url, media_url)


def list_articles(url: str, debug: bool) -> typing.List[Article]:
    html_doc = get_url_or_cache(url, '')
    soup = BeautifulSoup(html_doc, 'html.parser')
    url_data = urllib.parse.urlparse(url)
    base_url = urllib.parse.urlunparse((url_data.scheme, url_data.netloc, '', '', '', ''))
    if debug:
        print('base_url', base_url)
    jsons = map_json_in_soup(soup)
    props = jsons['z-nvg-cognac-props']
    articles = props['articles']
    if debug:
        articles_orig = articles
        articles = [first(articles_orig)]
    return [article_from_article_soup(art, base_url, debug) for art in articles]


def parse_material_string(material_string: str):
    """takes a string of '25% data' and returns ('data', '25%')"""
    data = material_string.split(' ', 2)
    data.reverse()
    return data

def split_material_string(material_string: str):
    """takes a string of '10% dog, 20% cat' and returns a dict {'dog': '10%', 'cat': '20%'}"""
    material_list = dict(parse_material_string(m.strip()) for m in material_string.split(','))
    return material_list


def get_article_info(url: str) -> ArticleInfo:
    html_doc = get_url_or_cache(url, '')
    soup = BeautifulSoup(html_doc, 'html.parser')
    jsons = map_json_in_soup(soup)
    props = jsons['z-vegas-pdp-props']
    attributes = props['model']['articleInfo']['attributes']
    material_data = first((p['data'] for p in attributes if p['category'] == 'heading_material'))
    material_map = {d['name']: d['values'] for d in material_data}
    material = split_material_string(material_map['Material'])
    tyg = material_map['Tyg']
    return ArticleInfo(material, tyg)


def handle_generate(args):
    articles = list_articles(args.url, False)
    save_store(Store(articles))


def handle_list_articles(args):
    articles = list_articles(args.url, args.debug)
    if args.print:
        for art in articles:
            print(art.brand)
            print(art.name)
            print(art.key)
            print(art.media)
            print()
    print('Articles found:', len(articles))


def handle_print_article_info(args):
    info = get_article_info(args.url)
    print('Material:', info.material)
    print('Tyg:', info.tyg)


def handle_debug(args):
    url = args.url
    html_doc = get_url_or_cache(url, '')
    soup = BeautifulSoup(html_doc, 'html.parser')
    print(soup.prettify())


def main():
    parser = argparse.ArgumentParser()
    parser.set_defaults(func=None)

    subs = parser.add_subparsers(help='sub command')

    sub = subs.add_parser('generate')
    sub.add_argument('url')
    sub.set_defaults(func=handle_generate)

    sub = subs.add_parser('debug')
    sub.add_argument('url')
    sub.set_defaults(func=handle_debug)

    sub = subs.add_parser('list-articles')
    sub.add_argument('url')
    sub.add_argument('--print', action='store_true')
    sub.add_argument('--debug', action='store_true')
    sub.set_defaults(func=handle_list_articles)

    sub = subs.add_parser('print-article-info')
    sub.add_argument('url')
    sub.set_defaults(func=handle_print_article_info)

    args = parser.parse_args()
    if args.func is None:
        parser.print_help()
    else:
        args.func(args)


if __name__ == "__main__":
    main()
