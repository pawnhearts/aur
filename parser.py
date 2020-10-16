from bs4 import BeautifulSoup
import requests
import os
import sqlite3
from tinydb import TinyDB, Query
from contextlib import contextmanager
from loguru import logger
import time


conn = None
os.chdir(os.path.dirname(__file__))
db = TinyDB('aur.tinydb')


def pkg_list():
    f = requests.get('https://aur.archlinux.org/packages.gz').text
    res = [line.strip() for line in f.splitlines() if not line.startswith('#')]
    logger.info(f'Got list of {len(res)} packages')
    return res

def pkg_info(name):
    res = requests.get(f'https://aur.archlinux.org/rpc.php?v=5&type=info&arg%5B%5D={name}').json()['results']
    if len(res) == 0:
        logger.error(f'{name} not found')
        return
    elif len(res) > 1:
        logger.error(f'{name} has name results')
        logger.info(res)
        return
    return res[0]

def update_db(lst):
    q = Query()
    for name in lst:
        pkg = pkg_info(name)
        if not pkg:
            continue
        pkg['built'] = 0
        if db.search((q.name == name) & (q.Version == pkg['Version'])):
            continue
        logger.info(f'Adding {name}')
        db.remove(q.name == name)
        db.insert(pkg)
        # if os.path.exists(name):
        #     shutil.rmtree(name)
        if not os.path.exists(name):
            os.mkdir(name)
        pkgbuild = requests.get(f'https://aur.archlinux.org/cgit/aur.git/plain/PKGBUILD?h={name}').text
        with open(os.path.join(name, 'PKGBUILD'), 'w') as f:
            f.write(pkgbuild)

def update_all_db():
    update_db(pkg_list())

def update_popular():
    lst = get_popular()
    logger.info(lst)
    update_db(lst)

def update_lastupdated():
    lst = get_lastupdated()
    logger.info(lst)
    update_db(lst)

def parse(d):
    cols = ['name', 'version', 'votes', 'popularity', 'desc', 'maintainer']
    d = BeautifulSoup(d, 'lxml')
    for row in d('tr')[1:]:
        row = row('td')
        pkg = {col: row[i].text.strip() for i, col in enumerate(cols)}
        yield pkg


def get_pages(sorting='p'):
    url = 'https://aur.archlinux.org/packages/?O={offset}&SeB=nd&SB={sorting}&SO=a&PP=250&do_Search=Go'
    for i in range(0, 2251, 250):
        data = requests.get(url.format(offset=i, sorting=sorting)).text
        for pkg in parse(data):
            yield pkg

def get_popular():
    pkgs = set()
    for sorting in ('p', 'v'):
        for pkg in get_pages(sorting):
            pkgs.add(pkg['name'])
    return pkgs

def get_lastupdated():
    for pkg in get_pages('l'):
        yield pkg['name'], pkg['version']

def get_ver(name):
    q = Query()
    if res := db.search(q.Name == name):
        return res[0]['Version']

#git clone https://aur.archlinux.org/package_name.git
#$ curl -L -O https://aur.archlinux.org/cgit/aur.git/snapshot/package_name.tar.gz



def init():
    global conn
    if not os.path.exists('aur.sqlite'):
        conn = sqlite3.connect('aur.sqlite')
        conn.execute('create table packages(name, version, votes, popularity, desc, maintainer, built integer default 0)')
        conn.commit()
    else:
        conn = sqlite3.connect('aur.sqlite')
    return conn


def set_built(name, val):
    conn.execute('update packages set built=? where name=?', (val, name,))
    conn.commit()


@contextmanager
def cd(path):
    cwd = os.getcwd()
    os.chdir(path)
    yield
    os.chdir(cwd)

def prepare_chroot(update=True):
    path = os.path.abspath('chroot')
    os.environ['CHROOT'] = path
    if not os.path.exists(os.path.join(path, 'root')):
        logger.info('making chroot in {}'.format(path))
        os.system('mkarchroot $CHROOT/root base-devel')
    if update:
        logger.info('updating chroot')
        os.system('arch-nspawn $CHROOT/root pacman -Syu')


def build(name, version=None):
    if not version:
        version = get_ver(name)
        if not version:
            logger.error(f"Can't find version for {name}")
            return
    logger.info(f'building {name} {version}')
    path = '{}-{}'.format(name, version)
    build_deps(name, version)
    with cd(path):
        if os.system('makechrootpkg -c -r $CHROOT -- -si --noconfirm') != 0:
            logger.error('building {} failed'.format(name))
            set_built(name, -1)
            return
        os.system('cp $CHROOT/$USER/var/lib/pacman/local/{}/desc .'.format(path))
        set_built(name, time.time())
        logger.info('building {} success'.format(name))


def build_deps(name, version):
    path = '{}-{}'.format(name, version)
    aur_deps = []
    with cd(path):
        deps = [l.split('=', 1)[1].strip() for l in os.popen('makepkg --printsrcinfo').readlines() if 'depends =' in l]
        logger.info(f'deps for {name}: {deps} ')
        for dep in deps:
            if os.system('arch-nspawn $CHROOT/root pacman -Si {} &> /dev/null'.format(dep)) != 0:
                aur_deps.append(dep)
    logger.info(f'aurdeps for {name}: {aur_deps}')
    for dep in aur_deps:
        build(dep)




def main():
    init()
    prepare_chroot()
    get_pages()

if __name__ == '__main__':
    main()
