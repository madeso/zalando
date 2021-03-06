#!/usr/bin/env python3

import urllib.parse
import urllib.request
import argparse
import itertools
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


def download_file(link: str, target: str):
    folder = os.path.dirname(target)
    os.makedirs(folder, exist_ok=True)
    if os.path.exists(target):
        return
    print('Downloading image', link)
    print('to', target)
    try:
        with urllib.request.urlopen(link) as url_handle:
            data = url_handle.read()
            with open(target, 'wb') as output:
                output.write(data)
    except urllib.error.HTTPError as http_error:
        if http_error.code == 404:
            print('404 error when downloading', link)
        else:
            raise http_error


def get_cachedir() -> str:
    filedir = os.path.join(os.getcwd(), 'cache')
    os.makedirs(filedir, exist_ok=True)
    return filedir


def local_filename(link: str) -> str:
    filedir = get_cachedir()
    filename = urllib.parse.quote(link, '')
    path = os.path.join(filedir, filename)
    return path


def local_image(link: str, arg_folder = None) -> str:
    folder = arg_folder
    if folder is None:
        folder = get_cachedir()
    parsed = urllib.parse.urlparse(link)
    path = os.path.join(folder, 'images' + parsed.path)
    return path


def get_url_or_cache(link: str, status: str) -> str:
    path = local_filename(link)
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


class ArticleInfo:
    def __init__(self, material: typing.Dict[str, str], tyg: str):
        self.material = material
        self.tyg = tyg


class Article:
    def __init__(self, brand: str, name: str, url: str, media: str, info: typing.Optional[ArticleInfo]):
        self.brand = brand
        self.name = name
        self.url = url
        self.media = media
        self.info = info


class Store:
    def __init__(self, articles: typing.List[Article]):
        self.articles = articles


class JsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Store):
            return {'__store__': True, 'articles': obj.articles}
        if isinstance(obj, Article):
            return {'__article__': True, 'brand': obj.brand, 'name': obj.name, 'url': obj.url, 'media': obj.media, 'info': obj.info}
        if isinstance(obj, ArticleInfo):
            return {'__articleinfo__': True, 'material': obj.material, 'tyg': obj.tyg}
        return json.JSONEncoder.default(self, obj)


def as_types(dct):
    if '__store__' in dct:
        return Store(dct['articles'])
    if '__article__' in dct:
        return Article(dct['brand'], dct['name'], dct['url'], dct['media'], dct['info'])
    if '__articleinfo__' in dct:
        return ArticleInfo(dct['material'], dct['tyg'])
    return dct


def save_store(data: Store):
    with open('store.json', 'w') as file_handle:
        json.dump(data, file_handle, cls=JsonEncoder, sort_keys=True, indent=4)


def load_store() -> Store:
    with open('store.json', 'r') as file_handle:
        return json.load(file_handle, object_hook=as_types)


def article_from_article_soup(art, base_url: str, debug: bool, collect: bool) -> Article:
    brand_name = art['brand_name']
    name = art['name']
    url_key = art['url_key']
    media = first(art['media'])
    media_path = media['path']

    url = urllib.parse.urljoin(base_url, url_key + '.html')
    media_url = urllib.parse.urljoin('https://img01.ztat.net/article/', media_path)

    info = None
    if collect:
        print('Getting article info ', brand_name, name)
        info = get_article_info(url, url, False)

    if debug:
        write_json_dump('art', art)

    return Article(brand_name, name, url, media_url, info)


def list_articles(url: str, debug: bool, collect: bool) -> typing.List[Article]:
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
    return [article_from_article_soup(art, base_url, debug, collect) for art in articles]


def parse_material_string(material_string: str):
    """takes a string of '25% data' and returns ('data', '25%')"""
    data = material_string.split(' ', 2)
    data.reverse()
    return data


def split_material_string(material_string: str):
    """takes a string of '10% dog, 20% cat' and returns a dict {'dog': '10%', 'cat': '20%'}"""
    material_list = dict(parse_material_string(m.strip()) for m in material_string.split(','))
    return material_list


def get_article_info(url: str, name: str, debug: bool) -> ArticleInfo:
    html_doc = get_url_or_cache(url, '')
    soup = BeautifulSoup(html_doc, 'html.parser')
    jsons = map_json_in_soup(soup)
    props = jsons['z-vegas-pdp-props']
    attributes = props['model']['articleInfo']['attributes']
    material_data = first((p['data'] for p in attributes if p['category'] == 'heading_material'))
    material_map = {d['name']: d['values'] for d in material_data}
    material = split_material_string(material_map['Material'])
    tyg = material_map.get('Tyg')
    if tyg is None:
        print('missing tyg for ', name)
        tyg = ''
        if debug:
            print('material map:')
            print(material_map)
            print()
    return ArticleInfo(material, tyg)


def handle_generate(args):
    articles = list_articles(args.url, False, args.collect)
    save_store(Store(articles))


def handle_list_articles(args):
    articles = list_articles(args.url, args.debug, False)
    if args.print:
        for art in articles:
            print(art.brand)
            print(art.name)
            print(art.url)
            print(art.media)
            print()
    print('Articles found:', len(articles))


def handle_print_article_info(args):
    info = get_article_info(args.url, '', args.debug)
    print('Material:', info.material)
    print('Tyg:', info.tyg)


def print_counter(counter, _):
    for c in counter:
        print(c, counter[c])
    print()


def handle_collect(args):
    articles = load_store().articles
    force = args.force

    write = False

    for article in articles:
        if force or article.info is None:
            print('Getting info from', article.url)
            info = get_article_info(article.url, article.url, False)
            write = True
            article.info = info

    if write:
        print('change detected, writing info')
        save_store(Store(articles))


def handle_make_images_local(_):
    articles = load_store().articles

    write = False

    for article in articles:
        if article.media.startswith('http'):
            new_url = local_image(article.media)
            download_file(article.media, new_url)
            write = True
            article.media = local_image(article.media, 'cache')

    if write:
        print('change detected, writing info')
        save_store(Store(articles))


def handle_list_materials_from_store(args):
    articles = load_store().articles
    counter = collections.Counter()

    for article in articles:
        if article.info is not None:
            counter.update(mat for mat in article.info.material)

    print_counter(counter, args)


def handle_list_tygs_from_store(args):
    articles = load_store().articles
    counter = collections.Counter()

    for article in articles:
        if article.info is not None:
            counter.update([article.info.tyg])

    print_counter(counter, args)


def filter_articles(articles: typing.List[Article], tyg: typing.Optional[str], material: typing.Optional[str]) -> typing.Iterable[Article]:
    articles_with_info = (article for article in articles if article.info is not None)
    articles_with_tyg = (article for article in articles_with_info if article.info.tyg.lower() == tyg.lower()) if tyg is not None else articles_with_info
    articles_with_material = (article for article in articles_with_tyg if material in article.info.material) if material is not None else articles_with_tyg
    return articles_with_material


class ArticleGroup:
    def __init__(self, value: str, articles: typing.List[Article]):
        self.value = value
        self.articles = articles


def int_parse(text: str):
    stripped = text.strip()
    if stripped.endswith('%'):
        stripped = stripped[:len(stripped)-1].strip()
    return int(stripped)


def group_articles(articles: typing.Iterable[Article], material: typing.Optional[str]) -> typing.Iterable[ArticleGroup]:
    if material is None:
        yield ArticleGroup('', list(articles))

    articles_list = list(articles)
    articles_list.sort(key=lambda article: int_parse(article.info.material[material]))
    articles_list.reverse()

    for key, group in itertools.groupby(articles_list, lambda article: article.info.material[material]):
        yield ArticleGroup(key + ' ' + material, list(group))


def print_article_as_html_card(article: Article):
    print('<div class="card">')
    print('    <img src="{}" class="card-img-top">'.format(article.media))
    print('    <div class="card-body">')
    print('        <h5 class="card-title">{}</h5>'.format(article.brand))
    print('        <p class="card-text">{}</p>'.format(article.name))
    print('        <a href="{}" class="btn btn-primary">Go</a>'.format(article.url))
    print('    </div>')
    print('</div>')


def pad(mylist, count):
    return [item for item, _ in itertools.zip_longest(mylist, range(count))]

def paginate(mylist, count):
    return [pad(mylist[i:i+count], count) for i in range(0, len(mylist), count)]


def handle_write_html(args):
    articles = filter_articles(load_store().articles, tyg=args.tyg, material=args.material)
    grouped_articles = group_articles(articles, args.material)

    print('<!doctype html>')
    print('<html lang="en">')
    print('<head>')
    print('    <meta charset="utf-8">')
    print('    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">')
    print('    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.5.3/dist/css/bootstrap.min.css" integrity="sha384-TX8t27EcRE3e/ihU7zmQxVncDAy5uIKz4rEkgIXeMed4M0jlfIDPvg6uqKI2xXr2" crossorigin="anonymous">')
    print('    <title>Hello, world!</title>')
    print('</head>')
    print('<body>')
    print('    <div class="container">')
    for group in grouped_articles:
        pages = paginate(list(group.articles), 3)
        print('<h3>{}</h3>'.format(group.value))
        for page in pages:
            print('        <div class="row">')
            for article in page:
                print('            <div class="col-sm">')
                if article is not None:
                    print_article_as_html_card(article)
                print('            </div>')
            print('        </div>')
    print('    </div>')
    print('    <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js" integrity="sha384-DfXdz2htPH0lsSSs5nCTpuj/zy4C+OGpamoFVy38MVBnE+IbbVYUew+OrCXaRkfj" crossorigin="anonymous"></script>')
    print('    <script src="https://cdn.jsdelivr.net/npm/bootstrap@4.5.3/dist/js/bootstrap.bundle.min.js" integrity="sha384-ho+j7jyWK8fNQe+A12Hb8AhRq26LrZ/JpcUGGOn+Y7RsweNrtN/tE3MoK7ZeZDyx" crossorigin="anonymous"></script>')
    print('</body>')
    print('</html>')


def handle_write(args):
    articles = filter_articles(load_store().articles, tyg=args.tyg, material=args.material)
    grouped_articles = group_articles(articles, args.material)

    for group in grouped_articles:
        print(group.value)
        pages = paginate(list(group.articles), 3)
        for page in pages:
            for article in page:
                if article is not None:
                    print(' ', article.brand, article.name)
            print()


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
    sub.add_argument('--collect', action='store_true')
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
    sub.add_argument('--debug', action='store_true')
    sub.set_defaults(func=handle_print_article_info)

    sub = subs.add_parser('list-materials')
    sub.set_defaults(func=handle_list_materials_from_store)

    sub = subs.add_parser('list-tygs')
    sub.set_defaults(func=handle_list_tygs_from_store)

    sub = subs.add_parser('write')
    sub.add_argument('--tyg')
    sub.add_argument('--material')
    sub.set_defaults(func=handle_write)

    sub = subs.add_parser('html')
    sub.add_argument('--tyg')
    sub.add_argument('--material')
    sub.set_defaults(func=handle_write_html)

    sub = subs.add_parser('collect')
    sub.add_argument('--force', action='store_true')
    sub.set_defaults(func=handle_collect)

    sub = subs.add_parser('local-image')
    sub.add_argument('--force', action='store_true')
    sub.set_defaults(func=handle_make_images_local)

    args = parser.parse_args()
    if args.func is None:
        parser.print_help()
    else:
        args.func(args)


if __name__ == "__main__":
    main()
