#!/usr/bin/env python3

import urllib.parse
import urllib.request
import argparse
import typing
import json
import os


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


def handle_generate(args):
    # root: str
    root = args.url
    base = 'https://www.zalando.se'
    url = '/man-klader-byxor-shorts/?upper_material=bomull'
    print(root)

    if not root.startswith(base):
        print('Invalid url')
        return

    url = root[len(base):]
    if url.endswith('/'):
        url = url[:len(url)-1]

    items = collect_data(base, url)
    save_store(Store(url, items))


def handle_debug(args):
    url = args.url
    print(url)


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

    args = parser.parse_args()
    if args.func is None:
        parser.print_help()
    else:
        args.func(args)


if __name__ == "__main__":
    main()
