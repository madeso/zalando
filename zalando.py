#!/usr/bin/env python3

import urllib.request
import re
import argparse
import typing
import json
import collections

#  class="catalogArticlesList_imageBox"
resubsite = re.compile(r'<a class="z-nvg-cognac_imageLink-OPGGa" href="([^"]+)"')
resubsite_alt = re.compile(r'href="([^"]+)"\s+class="catalogArticlesList_imageBox"')
# "next_page_path":"\u002Fman-klader-jeans\u002F?p=2"
resubsitenext_json = re.compile(r'"next_page_path":"([^"]+)')
# <a class="catalogPagination_button catalogPagination_button-next" href="/man-klader-jeans/?p=2">
resubsitenext = re.compile(r'catalogPagination_button-next" href="([^"]+)')
# data":[{"name":"Material","values":"98% Bomull, 2% Elastan"}]
redata = re.compile(r'"Material\: ([^"]+)')
regallery = re.compile(r'"gallery":"([^"]+)"')
renumber = re.compile(r'[0123456789]+')
rematerial = re.compile(r'[0123456789]+% ([a-zA-Z]+)')


def clean_json_string(url: str) -> str:
    return url.replace('\\u002F', '/')


def geturl(link: str) -> str:
    print('Requesting url ', link)
    with urllib.request.urlopen(link) as f:
        data = f.read()
        return data.decode('utf-8')


def find_all_pages(base: str, url: str) -> typing.Iterable[str]:
    print('Getting subsites from', url)
    data = geturl(base + url)
    count = 0
    for r in resubsite.finditer(data):
        count += 1
        yield r.group(1)
    for r in resubsite_alt.finditer(data):
        count += 1
        yield r.group(1)
    #  print(data.find('next_page_path'))
    print(count)
    if count == -75:
        with open('url.html', 'w') as f:
            f.write(data)
    for r in resubsitenext_json.finditer(data):
        next = clean_json_string(r.group(1))
        print('Grabbing more... (json)')
        for s in find_all_pages(base, next):
            yield s
    for r in resubsitenext.finditer(data):
        next = r.group(1)
        print('Grabbing more... (html)')
        for s in find_all_pages(base, next):
            yield s


class Item:
    def __init__(self, url: str, materials: typing.List[str], gallery: typing.Optional[str]):
        self.url = url
        self.materials = materials
        self.gallery = gallery

    def get_material(self, mat: str) -> typing.Optional[int]:
        for m in self.materials:
            if m.lower().endswith(mat):
                number = renumber.search(m)
                if number:
                    return int(number.group(0))
        return None


def collect_single_item(base: str, url: str) -> Item:
    data = geturl(base + url)
    r = redata.search(data)
    ga = regallery.search(data)
    if ga is not None:
        ga = ga.group(1)

    if r:
        return Item(url, r.group(1).split(','), ga)
    else:
        print('Unable to detect data in', url)
        return Item(url, [], None)



def collect_items(base: str, items: typing.Iterable[str]) -> typing.Iterable[Item]:
    for url in items:
        yield collect_single_item(base, url)


class Result:
    def __init__(self, url: str, value: int, gallery: str, data: Item):
        self.url = url
        self.value = value
        self.gallery = gallery
        self.item = data


def all_with_material(items: typing.Iterable[Item], material: str) -> typing.Iterable[Result]:
    for d in items:
        value = d.get_material(material)
        if value is not None:
            yield Result(d.url, value, d.gallery, d)


def tohtml(base: str, sorted: typing.Iterable[Result], material: str, out):
    print('<html>', file=out)
    print('<head><title>', file=out)
    print(material, file=out)
    print('</title><link rel="stylesheet" type="text/css" href="style.css"></head>', file=out)
    print('<body>', file=out)
    print('<div class="container">', file=out)
    last = 0
    for d in sorted:
        p = d.value
        if last != p:
            print('<div class="percent">', file=out)
            print(p, file=out)
            print('</div>', file=out)
            last = p
        print('<div class="result">', file=out)
        print('<!-- {} -->'.format(p), file=out)
        print('<a href="{}">'.format(base + d.url), file=out)
        print('<img src="{}">'.format(d.gallery), file=out)
        print('</a>', file=out)
        print('</div>', file=out)
    print('</div>', file=out)
    print('</body>', file=out)
    print('</html>', file=out)


def collect_data(base: str, url: str) -> typing.List[Item]:
    print('')
    print('Getting all pages...')
    pages = list(find_all_pages(base, url))
    print('{} pages found'.format(len(pages)))

    print('')
    print('Getting all items...')
    items = list(collect_items(base, pages))
    print('{} items found'.format(len(items)))

    return items


def selective_print(items: typing.List[Item], material: str, base: str, out):
    print('')
    print('Getting all materials....')
    data = list(all_with_material(items, material))
    print('{} items selected'.format(len(data)))

    print('')
    print('Sorting....')
    data.sort(key=lambda t: t.value, reverse=True)

    print('')
    print('Printing to html')
    tohtml(base, data, material, out)


class Store:
    def __init__(self, items: typing.List[Item], base: str):
        self.items = items
        self.base = base


class JsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Store):
            return {'__store__': True, 'base': obj.base, 'items': obj.items}
        if isinstance(obj, Item):
            return {'__item__': True, 'url': obj.url, 'gallery': obj.gallery, 'materials': obj.materials}
        return json.JSONEncoder.default(self, obj)


def store_list(data: Store):
    with open('store.json', 'w') as f:
        json.dump(data, f, cls=JsonEncoder, sort_keys=True, indent=4)


def as_types(dct):
    if '__store__' in dct:
        return Store(dct['items'], dct['base'])
    if '__item__' in dct:
        return Item(dct['url'], dct['materials'], dct['gallery'])
    return dct


def load_list() -> Store:
    with open('store.json', 'r') as f:
        return json.load(f, object_hook=as_types)


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
    store_list(Store(items, base))


def handle_print(args):
    store = load_list()

    selective_print(store.items, args.material, store.base, args.out)
    pass


def handle_search(args):
    store = load_list()
    data = list(all_with_material(store.items, args.material))
    print('{} items found'.format(len(data)))
    for found in data:
        print(store.base + found.url)


def get_material_names(materials: typing.List[str]) -> typing.Iterable[str]:
    for m in materials:
        ga = rematerial.search(m)
        if ga is not None:
            yield ga.group(1)
        else:
            print('Invalid material', m)


def handle_list(args):
    store = load_list()

    materials = []

    for it in store.items:
        for mat in get_material_names(it.materials):
            materials.append(mat)

    counted = collections.Counter(materials)
    for name, count in counted.items():
        print('{}: {}'.format(name, count))



def main():
    parser = argparse.ArgumentParser()
    parser.set_defaults(func=None)

    subs = parser.add_subparsers(help='sub command')

    sub = subs.add_parser('generate')
    sub.add_argument('url')
    sub.set_defaults(func=handle_generate)

    sub = subs.add_parser('list')
    sub.set_defaults(func=handle_list)

    sub = subs.add_parser('search')
    sub.add_argument('material')
    sub.set_defaults(func=handle_search)

    sub = subs.add_parser('print')
    sub.add_argument('material')
    sub.add_argument('out', type=argparse.FileType('w'))
    sub.set_defaults(func=handle_print)

    args = parser.parse_args()
    if args.func is None:
        parser.print_help()
    else:
        args.func(args)


if __name__ == "__main__":
    main()
