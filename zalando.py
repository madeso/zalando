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


class Store:
    def __init__(self, url: str, items: typing.List[str]):
        self.items = items
        self.url = url


class JsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Store):
            return {'__store__': True, 'url': obj.url, 'items': obj.items}
        return json.JSONEncoder.default(self, obj)


def as_types(dct):
    if '__store__' in dct:
        return Store(dct['items'], dct['url'])
    return dct


def save_store(data: Store):
    with open('store.json', 'w') as file_handle:
        json.dump(data, file_handle, cls=JsonEncoder, sort_keys=True, indent=4)


def load_store() -> Store:
    with open('store.json', 'r') as file_handle:
        return json.load(file_handle, object_hook=as_types)


def list_all_cdata(data: str) -> typing.Iterable[typing.Any]:
    for cdata_match in re_cdata.finditer(data):
        cdata = json.loads(cdata_match.group(1))
        yield cdata


def first(list_or_iterable):
    for item in list_or_iterable:
        return item
    return None


def map_json_in_soup(soup):
    script_elements = [t for t in soup.find_all('script') if t.has_attr('type') and t['type'] == 'application/json']
    json_map = {a['id']: first(list_all_cdata(str(a.string))) for a in script_elements}
    return json_map


def debug_dump_map(jsons):
    for key in jsons:
        with open('dump-' + key + '.json', 'w') as file_handle:
            json.dump(jsons[key], file_handle, sort_keys=True, indent=4)


class Article:
    def __init__(self, brand: str, name: str, key: str, media: str):
        self.brand = brand
        self.name = name
        self.key = key
        self.media = media


def list_articles(url: str) -> typing.List[Article]:
    html_doc = get_url_or_cache(url, '')
    soup = BeautifulSoup(html_doc, 'html.parser')
    # print(soup.prettify())
    # <script id="z-nvg-cognac-props" type="application/json">
    jsons = map_json_in_soup(soup)
    props = jsons['z-nvg-cognac-props']
    articles = props['articles']
    return [Article(art['brand_name'], art['name'], art['url_key'], first(art['media'])['path']) for art in articles]


def handle_list_articles(args):
    articles = list_articles(args.url)
    if args.print:
        for art in articles:
            print(art.brand)
            print(art.name)
            print(art.key)
            print(art.media)
            print()
    print('Articles found:', len(articles))


def handle_debug(args):
    url = args.url
    html_doc = get_url_or_cache(url, '')
    soup = BeautifulSoup(html_doc, 'html.parser')
    # print(soup.prettify())
    # <script id="z-nvg-cognac-props" type="application/json">
    jsons = map_json_in_soup(soup)
    props = jsons['z-nvg-cognac-props']
    articles = props['articles']
    for art in articles:
        media = first(art['media'])
        print(art['brand_name'])
        print(art['name'])
        print(art['url_key'])
        print(media['path'])
        print()
        print()
    print(len(articles))
    print()
    debug_dump_map(jsons)


def main():
    parser = argparse.ArgumentParser()
    parser.set_defaults(func=None)

    subs = parser.add_subparsers(help='sub command')

    sub = subs.add_parser('debug')
    sub.add_argument('url')
    sub.set_defaults(func=handle_debug)

    sub = subs.add_parser('list-articles')
    sub.add_argument('url')
    sub.add_argument('--print', action='store_true')
    sub.set_defaults(func=handle_list_articles)

    args = parser.parse_args()
    if args.func is None:
        parser.print_help()
    else:
        args.func(args)


if __name__ == "__main__":
    main()
