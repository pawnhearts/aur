from bs4 import BeautifulSoup
from aiohttp import ClientSession
import asyncio
import os
from tinydb import TinyDB, Query
from contextlib import contextmanager
from loguru import logger
import time


db = TinyDB('aur.tinydb')
queue = []


async def get_text(url, **kwargs):
    try:
        async with ClientSession() as sess:
            async with sess.get(url, **kwargs) as resp:
                if resp.status == 200:
                    return await resp.text()
    except Exception as e:
        loguru.exception(e)

async def get_json(sess, url, **kwargs):
    try:
        async with sess.get(url, **kwargs) as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception as e:
        loguru.exception(e)

async def pkg_list():
        f = await get_text('https://aur.archlinux.org/packages.gz')
        res = [line.strip() for line in f.splitlines() if not line.startswith('#')]
        logger.info(f'Got list of {len(res)} packages')
        return res

async def pkg_info(names):
    async with ClientSession() as sess:
        params = [('v', 5), ('type', 'info')] + [('arg[]', name) for name in names]
        res = await get_json(sess, f'https://aur.archlinux.org/rpc.php', params=params)
        if not res:
            return
        res = res['results']
        return {pkg['Name']: pkg for pkg in res}

async def update_depends(pkg):
    deps = pkg['Depends'] + pkg.get('MakeDepends', [])
    for dep in deps:
        dep = dep.split('=')[0]
        if dep not in repos:
            queue.append(dep)



async def update_pkg(pkg, get_pkgbuild=True):
    name = pkg['Name']
    q = Query()
    if not pkg:
        return
    pkg['built'] = 0
    if db.search((q.Name == name) & (q.Version == pkg['Version'])):
        return
    logger.info(f'Adding {name}')
    db.remove(q.Name == name)
    db.insert(pkg)
    # if os.path.exists(name):
    #     shutil.rmtree(name)
    if get_pkgbuild:
        if not os.path.exists(name):
            os.mkdir(name)
            pkgbuild = await get_text(f'https://aur.archlinux.org/cgit/aur.git/plain/PKGBUILD?h={name}')
            if pkgbuild:
                with open(os.path.join(name, 'PKGBUILD'), 'w') as f:
                    f.write(pkgbuild)
                logger.info(f'Added pkgbuild {name}')
            else:
                db.update({'built': -1}, q.Name == name)
                logger.error(f'Bad pkgbuild {name}')
                return
        await update_depends(pkg)

async def update_all_db():
    queue.extend(await pkg_list())
    while True:
        chunk = [queue.pop() for _ in range(50) if queue]
        pkgs = await pkg_info(chunk)
        await asyncio.gather(*[update_pkg(pkg) for pkg in pkgs.values()])

async def update_popular():
    queue.extend(await get_popular())
    while True:
        chunk = [queue.pop() for _ in range(50) if queue]
        pkgs = await pkg_info(chunk)
        await asyncio.gather(*[update_pkg(pkg) for pkg in pkgs.values()])

async def update_lastupdated():
    queue.extend(await get_lastupdated())
    while True:
        chunk = [queue.pop() for _ in range(50) if queue]
        pkgs = await pkg_info(chunk)
        await asyncio.gather(*[update_pkg(pkg) for pkg in pkgs.values()])


async def get_page(sorting='p', n=0):
    def parse(d):
        cols = ['name', 'version', 'votes', 'popularity', 'desc', 'maintainer']
        d = BeautifulSoup(d, 'lxml')
        for row in d('tr')[1:]:
            row = row('td')
            pkg = {col: row[i].text.strip() for i, col in enumerate(cols)}
            yield pkg
    i = n*250
    url = 'https://aur.archlinux.org/packages/?O={offset}&SeB=nd&SB={sorting}&SO=a&PP=250&do_Search=Go'
    data = await get_text(url.format(offset=i, sorting=sorting))
    logger.info(f'Got page {n} of {sorting}')
    return list(parse(data))

def names(lst):
    return [pkg['name'] for pkg in lst]


async def get_popular():
    return list(set(sum(map(names, await asyncio.gather(*[get_page(sorting, n) for sorting in ('p', 'v') for n in range(0,11)])), [])))

async def get_lastupdated():
    return sum(map(names, await asyncio.gather(*[get_page('l', n) for n in range(0,11)])), [])

def get_ver(name):
    q = Query()
    if res := db.search(q.Name == name):
        return res[0]['Version']

def get_repos():
    return [l.split()[1] for l in os.popen('pacman -Sl').readlines()]

repos = get_repos()


#git clone https://aur.archlinux.org/package_name.git
#$ curl -L -O https://aur.archlinux.org/cgit/aur.git/snapshot/package_name.tar.gz

def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(update_popular())

main()


