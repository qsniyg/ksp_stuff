#!/usr/bin/env python3
import os
import sys
import shutil
#from glob import iglob
import re
try:
    # Much faster than python's default json module, makes reading and writing the log much quicker
    import ujson as json
except Exception:
    import json


# This setting adds small delays around I/O calls to prevent your system from freezing if using a HDD
IO_DELAY = True

PATHS = {
    # Set this to the root directory for the ModOrganizer app.
    # It should contain the folders 'mods', 'overwrite', and 'profiles'
    "MOROOT": '{PREFIX}/drive_c/users/{USERNAME}/Local Settings/Application Data/ModOrganizer/SkyrimLE',
    # You likely do not need to change these lines
    "mods": '{MOROOT}/mods/',
    "overwrite": '{MOROOT}/overwrite/',
    "profiles": '{MOROOT}/profiles/',

    # Set this to your Skyrim installation directory (it should contain TESV.exe)
    "skyrim": '{PREFIX}/drive_c/Steam/steamapps/common/Skyrim Special Edition',
    # You might need to change 'Skyrim Special Edition' to 'Skyrim' if not using SSE
    # If you don't disable the folders under "Desktop Integration" in winecfg, the plugins.txt path might be somewhere in your linux home directory instead
    # This is not the same directory that holds your save games.
    # You probably want to back up this file before running this the first time !
    "plugins.txt": '{PREFIX}/drive_c/users/{USERNAME}/Local Settings/Application Data/Skyrim Special Edition/plugins.txt'
}


PREFIX   = os.getenv('WINEPREFIX')
USERNAME = os.getenv('USER')


if IO_DELAY is True:
    import time

    def iodelay(s):
        time.sleep(s)
else:
    def iodelay(s):
        pass


use_lower = False
pathcache = {}


def normpath(path):
    return re.sub(r"/+", "/", path)


def winpath(path):
    if os.path.exists(path):
        return path
    path = normpath(path)
    if path == "/" or len(path) == 0:
        return path
    lower = path.lower()
    if lower in pathcache:
        return pathcache[lower]
    rpath = path.rstrip("/")
    parentpath = os.path.dirname(rpath)
    basename = os.path.basename(rpath)
    basename_lower = basename.lower()
    winparent = winpath(parentpath)
    if len(winparent) == 0:
        winparent = '.'
    lower = parentpath.lower()
    if lower not in pathcache:
        pathcache[lower] = winparent

    for file in os.listdir(winparent):
        if file.lower() == basename_lower:
            return os.path.join(winparent, file)

    return os.path.join(winparent, basename)


def traverse(rootDir, dirsonly=False):
    if not rootDir.endswith('/'):
        rootDir = '%s/' % rootDir
    for dirName, subdirList, fileList in os.walk(rootDir):
        iodelay(.001)
        for fname in fileList:
            if dirsonly:
                yield dirName.replace(rootDir, '')
            else:
                yield os.path.join(dirName.replace(rootDir, ''), fname)


def updatelink(src, dest, log):
    iodelay(.002)
    dest = winpath(dest)
    if os.path.islink(dest):
        os.unlink(dest)
    elif os.path.exists(dest):
        shutil.move(dest, '%s.unvfs' % dest)
        print ('Backing up ', dest)
        log['backups'].append(dest)
    log['links'].insert(0, dest)
    print ('Linking "%s" to "%s"' % (src, dest))
    os.symlink(src, dest)

def mktree(root, path, log):
    iodelay(0.001)
    tree = root
    for p in path.split('/'):
        tree = winpath(os.path.join(tree, p))
        if not os.path.isdir(tree):
            log['dirs'].insert(0, tree)
            print ('Creating directory ', tree)
            os.mkdir(tree)


def pathHdlr(p):
    p = (p
         .replace('{PREFIX}', PREFIX)
         .replace('{USERNAME}', USERNAME))

    if '{MOROOT}' in p:
        p = p.replace(
            '{MOROOT}',
            pathHdlr(PATHS["MOROOT"])
        )

    return p


def unvfs(p):
    if not os.path.exists('movfs4l_log.json'):
        return
    print("Reading JSON")
    log = json.loads(open('movfs4l_log.json').read())
    for l in log['links']:
        l = winpath(l)
        if os.path.islink(l):
            print ('Removing symlink ', l)
            iodelay(0.0005)
            os.unlink(l)
    for d in log['dirs']:
        d = winpath(d)
        if os.path.isdir(d):
            print ('Removing directory ', d)
            shutil.rmtree(d)
    for b in log.get('backups', []):
        b = winpath(b)
        shutil.move('%s.unvfs' % b, b)
    log = {'dirs': [], 'links': [], 'backups': []}
    open('movfs4l_log.json', 'w').write(json.dumps(log, indent=4))


def lowerpath(path):
    if not use_lower:
        return path
    else:
        return path.lower()


def addvfslayer(p,l, log):
    for item in traverse(l, True):
        mktree(p, lowerpath(item), log)
    for item in traverse(l):
        src = winpath(os.path.join(l, item))
        dest = winpath(os.path.join(p, lowerpath(item)))
        if not os.path.isdir(src):
            updatelink(src, dest, log)


def lowertree(dir):
    if not use_lower:
        return

    # renames all subforders of dir, not including dir itself
    def rename_all(root, items):
        for name in items:
            try:
                os.rename(os.path.join(root, name),
                          os.path.join(root, lowerpath(name)))
            except OSError:
                pass  # can't rename it, so what

    # starts from the bottom so paths further up remain valid after renaming
    for root, dirs, files in os.walk(dir, topdown=False):
        rename_all(root, dirs )
        rename_all(root, files)


if __name__ == '__main__':
    log = {'dirs': [], 'links': [], 'backups': []}
    DATADIR=os.path.join(pathHdlr(PATHS['skyrim']), 'Data')
    lowertree(DATADIR)
    MO_PROFILE='Default'
    if len(sys.argv) > 1:
        MO_PROFILE=sys.argv[1]

    #Don't create an MO profile named UNVFS - or you'll break this functionality
    unvfs(DATADIR)
    if MO_PROFILE == 'UNVFS':
        sys.exit()

    PDIR=os.path.join(pathHdlr(PATHS['profiles']),MO_PROFILE)
    PLUGINS=os.path.join(PDIR, 'plugins.txt')
    print ('Setting symlink from "%s" to "%s" for loadorder' % (PLUGINS, pathHdlr(PATHS['plugins.txt'])))
    updatelink(PLUGINS, pathHdlr(PATHS['plugins.txt']), log)

    print ('Parsing MO mods configuration')
    MODS=pathHdlr(PATHS['mods'])
    for modpath in reversed([os.path.join(MODS, i[1:]).strip() for i in open(os.path.join(PDIR, 'modlist.txt')).readlines() if i.startswith('+')]):
        addvfslayer(DATADIR, modpath, log)
    open('movfs4l_log.json', 'w').write(json.dumps(log, indent=4))

    print ('Parsing MO overwrite directory')
    OVS=pathHdlr(PATHS['overwrite'])
    addvfslayer(DATADIR, OVS, log)

    print ('VFS layer created. Rerun this script to update. Run "%s UNVFS" to shut it down' % sys.argv[0])
