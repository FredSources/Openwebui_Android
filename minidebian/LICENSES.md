# Licences — rootfs mini-Debian trixie arm64

## Binaire `proot`

`proot` est distribué sous licence **GPL-2.0-or-later** (GPL v2 ou toute version
ultérieure). Source amont : <https://github.com/termux/proot>. Le binaire fourni
ici est celui de Termux (`/data/data/com.termux/files/usr/bin/proot`, ELF aarch64,
interpréteur `/system/bin/linker64`).

## `proot-distro` (référence, non embarqué)

`proot-distro` est distribué sous licence **GPL-3.0-only**. Il n'est pas copié
dans ce dossier ; il sert uniquement de référence d'intégration pour le fork
Android. Source amont : <https://github.com/termux/proot-distro>.

## Bibliothèques compagnons

- `libtalloc.so.2` — licence **LGPL-3.0-or-later** (projet Samba, talloc).
- `libandroid-shmem.so` — licence **MIT** (projet Termux termux-shm /
  libandroid-shmem).

## Debian trixie

Le rootfs est construit à partir des paquets officiels de **Debian 13 « trixie »**
via `mmdebstrap`. Chaque paquet embarque ses propres mentions de copyright dans
`/usr/share/doc/<paquet>/copyright` ; ces fichiers ont été retirés de l'image
finale pour limiter sa taille, mais les textes de licence complets restent
accessibles depuis les sources Debian :

- Debian Free Software Guidelines : <https://www.debian.org/social_contract#guidelines>
- Debian copyrights par paquet : <https://packages.debian.org/trixie/>
- Licences courantes conservées dans le rootfs : `/usr/share/common-licenses/`
  (GPL-2, GPL-3, LGPL-2.1, LGPL-3, Apache-2.0, BSD, Artistic, MPL-1.1, etc.).

Aucun code propriétaire n'est inclus. Les marques Debian et Termux appartiennent
à leurs détenteurs respectifs.
