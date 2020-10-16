import os, sys
from contextlib import contextmanager

# yay -Sa --noprovides --answerdiff=None --answerclean=None vim-plug

@contextmanager
def cd(path):
    cwd = os.getcwd()
    os.chdir(path)
    yield
    os.chdir(cwd)

def build(name):
    print('build', name)
    if not os.path.exists(name):
        if os.system(f'git clone https://aur.archlinux.org/{name}.git') != 0:
            raise Exception(f'{name} not found')
    with cd(name):
        srcinfo = {l.split('=', 1)[0].strip(): l.split('=', 1)[1].strip()
                   for l in os.popen('makepkg --printsrcinfo').readlines()
                   if '=' in l}
        # respath = f"{srcinfo.get('pkgname', srcinfo.get('pkgbase'))}-{srcinfo['pkgver']}-{srcinfo['pkgrel']}"
        respath = os.path.basename(os.popen('makepkg --packagelist').readline().rsplit('-', 1)[0])
        aur_deps = []
        deps = srcinfo.get('depends', '').split()
        for dep in deps:
            if os.system(f'pacman -Sp {dep} &> /dev/null') != 0:
                aur_deps.append(dep)
    print(aur_deps)
    for dep in aur_deps:
        build(dep)
    with cd(name):
        if os.system('makepkg -sf --noconfirm'):
            raise Exception(f'{name} build failed')
        f = os.popen('makepkg --packagelist').readline().strip()
        os.system(f'repo-add  /mnt/repo/aur/os/x86_64/aur.db.tar.gz "{f}"')
        os.system(f'cp "{f}" /mnt/repo/aur/os/x86_64/')
    # os.system(f'cp -r /var/lib/pacman/local/{respath} {name}/')

if __name__ == '__main__':
    build(sys.argv[1])
