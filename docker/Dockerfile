FROM greyltc/archlinux
LABEL Name=aur

RUN echo 'Server = http://mirror.yandex.ru/archlinux/$repo/os/$arch'  > /etc/pacman.d/mirrorlist
RUN pacman -Syu --noconfirm --needed base base-devel
RUN pacman -Syu --noconfirm jq pacutils git wget shellcheck vim vifm devtools bash-completion man-db man-pages zsh
RUN ln -fs /usr/share/zoneinfo/Europe/Moscow /etc/localtime

ARG USERNAME=aur
RUN useradd -m -s /bin/bash aur
RUN install -o aur -dm755 /home/aur/.local && \
    install -o aur -dm755 /home/aur/.local/bin
ENV PATH "/home/${USERNAME}/.local/bin:$PATH"

# locales
RUN echo en_US.UTF-8 UTF-8 > /etc/locale.gen && locale-gen
ENV LANG en_US.UTF-8

# sudoers
RUN echo aur ALL=\(root\) NOPASSWD: /usr/bin/pacman > /etc/sudoers.d/aur-pacman && \
    chmod 0440 /etc/sudoers.d/aur-pacman
# local repository
ARG REPO_DB=/home/custompkgs/custom.db.tar.gz
RUN install -o aur -dm755 /home/custompkgs && \
    sudo -u aur repo-add $REPO_DB

ARG PACMAN_CONF=/etc/pacman.conf
RUN perl -0777 -pi -e 's/#(\[custom\])\n#(SigLevel.*)\n#(Server.*)\n/$1\n$2\n$3\n/' $PACMAN_CONF && \
    pacsync custom
RUN git clone https://github.com/AladW/aurutils
RUN bash -c 'chown -R aur aurutils;cd aurutils/makepkg; sudo -u aur makepkg -si --noconfirm'

CMD ["/bin/bash"]
