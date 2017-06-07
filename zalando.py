#!/usr/bin/env python3

import urllib.request
import re
import itertools

base = 'https://www.zalando.se'

def geturl(link):
    with urllib.request.urlopen(link) as f:
        data = f.read()
        return data.decode('utf-8')

#  class="catalogArticlesList_imageBox"
resubsite = re.compile(r'<a href="([^"]+)"\s+class="catalogArticlesList_imageBox')
resubsitenext = re.compile(r'<a class="catalogPagination_button catalogPagination_button-next"\s+href="([^"]+)"')

def getsubsites(url):
    data = geturl(base + url)
    for r in resubsite.finditer(data):
        yield r.group(1)
    for r in resubsitenext.finditer(data):
        next = r.group(1)
        for s in getsubsites(next):
            yield s


# data":[{"name":"Material","values":"98% Bomull, 2% Elastan"}]
redata = re.compile(r'data":\[{"name":"Material","values":"([^"]+)"}]')
regallery = re.compile(r'"gallery":"([^"]+)"')

def getdata(url):
    data = geturl(base + url)
    r = redata.search(data)
    ga = regallery.search(data)
    if ga is not None:
        ga = ga.group(1)
    if r:
        return r.group(1).split(','), ga
    else:
        return [], None


renumber = re.compile(r'[0123456789]+')


class Item:
    def __init__(self, url, materials, gallery):
        self.url = url
        self.materials = materials
        self.gallery = gallery

    def get_material(self, mat):
        for m in self.materials:
            if m.lower().endswith(mat):
                number = renumber.search(m)
                if number:
                    return int(number.group(0))
        return None


def getalldata(url):
    for s in getsubsites(url):
        d, g = getdata(s)
        yield Item(s, d, g)

def all_with_material(url, material):
    for d in getalldata(url):
        value = d.get_material(material)
        if value is not None:
            yield d.url, value, d.gallery

def tohtml(sorted, material):
    print('<html>')
    print('<head><title>')
    print(material)
    print('</title><link rel="stylesheet" type="text/css" href="style.css"></head>')
    print('<body>')
    print('<div class="container">')
    last = 0
    for d in sorted:
        p = d[1]
        if last != p:
            print('<div class="percent">')
            print(p)
            print('</div>')
            last = p
        print('<div class="result">')
        print('<!-- {} -->'.format(p))
        print('<a href="{}">'.format(base + d[0]))
        print('<img src="{}">'.format(d[2]))
        print('</a>')
        print('</div>')
    print('</div>')
    print('</body>')
    print('</html>')


def main():
    url = '/man-klader-byxor-shorts/?upper_material=bomull'
    material = 'elastan'

    data = all_with_material(url, material)
    sorted = list(data) #list(itertools.islice(data, 5))
    sorted.sort(key=lambda t: t[1], reverse=True)

    tohtml(sorted, material)


if __name__ == "__main__":
    main()
