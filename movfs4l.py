#!/usr/bin/env python3
import os
import sys
import shutil
import re
import threading
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

    if os.path.isdir(winparent):
        for file in os.listdir(winparent):
            if file.lower() == basename_lower:
                return os.path.join(winparent, file)

    return os.path.join(winparent, basename)


def ioyield():
    iodelay(.00001)


def get_terminal_width():
    return shutil.get_terminal_size()[0]


prettyprint_total = 0
prettyprint_current = 0
prettyprint_text = ""
prettyprint_lock = threading.Lock()
prettyprint_stop = False

def prettyprint(progress, text):
    global prettyprint_current, prettyprint_text, prettyprint_lock

    prettyprint_lock.acquire()
    prettyprint_current = progress
    prettyprint_text = text
    prettyprint_lock.release()


def pretty_print():
    global prettyprint_lock
    prettyprint_lock.acquire()
    header = "[" + str(prettyprint_current) + "/" + str(prettyprint_total) + "] "
    text = prettyprint_text
    prettyprint_lock.release()

    if text is None:
        return False

    width = get_terminal_width()
    width -= len(header) + 1
    text = text[:width]
    for i in range(width - len(text)):
        text += " "
    sys.stdout.write("\r" + header + text)
    return True


def clear_line():
    width = get_terminal_width()
    text = ""
    for i in range(width - 1):
        text += " "
    sys.stdout.write("\r" + text + "\r")


def prettyprint_thread():
    printed = False
    while not prettyprint_stop:
        if pretty_print():
            printed = True
        time.sleep(0.1)

    if pretty_print():
        printed = True

    if printed:
        clear_line()


def start_prettyprint():
    global prettyprint_current, prettyprint_stop, prettyprint_text
    prettyprint_current = 0
    prettyprint_stop = False
    prettyprint_text = None

    t = threading.Thread(target=prettyprint_thread)
    t.start()
    return t


def stop_prettyprint(t):
    global prettyprint_lock, prettyprint_stop
    prettyprint_lock.acquire()
    prettyprint_stop = True
    prettyprint_lock.release()
    t.join()


plog_indent = 0
def plog(string):
    text = ""
    color = "32"  # green
    if plog_indent > 0:
        text += " "
        for i in range(plog_indent - 1):
            text += "  "
        text += "-> "
        color = "34"  # blue
    else:
        text += "* "
    text += "\33[" + color + "m"
    text += string
    text += "\33[0m"
    print(text)


vfs = {
    "type": "dir",
    "name": "",
    "items": {}
}
vfs_total = 0
vfs_progress = 0

def add_vfs_item(rootDir, vfs):
    global vfs_total

    for item in os.listdir(rootDir):
        ioyield()
        real_path = os.path.join(rootDir, item)
        vfs_hash = item.upper()

        if vfs_hash not in vfs:
            vfs[vfs_hash] = {}
            vfs_total += 1

        vfs[vfs_hash]["name"] = item

        if os.path.isdir(real_path):
            vfs[vfs_hash]["type"] = "dir"

            if "items" not in vfs[vfs_hash]:
                vfs[vfs_hash]["items"] = {}

            add_vfs_item(real_path, vfs[vfs_hash]["items"])
        else:
            vfs[vfs_hash]["type"] = "file"
            vfs[vfs_hash]["location"] = real_path


def add_vfs_layer(rootDir):
    global vfs
    add_vfs_item(rootDir, vfs["items"])


def apply_vfs(vfs, rootDir, vfs_path, log):
    global vfs_progress
    prettyprint(vfs_progress, vfs_path)
    vfs_progress += 1

    output = os.path.join(rootDir, vfs_path)

    if vfs["type"] == "file":
        updatelink(winpath(vfs["location"]), output, log)
        return

    if vfs["type"] == "dir":
        mktree(rootDir, vfs_path, log)
        for item in vfs["items"]:
            item_obj = vfs["items"][item]
            apply_vfs(item_obj, rootDir, os.path.join(vfs_path, item_obj["name"]), log)



def updatelink(src, dest, log):
    iodelay(0.0015)
    dest = winpath(dest)
    if os.path.islink(dest):
        os.unlink(dest)
    elif os.path.exists(dest):
        shutil.move(dest, '%s.unvfs' % dest)
        #print ('Backing up ', dest)
        log['backups'].append(dest)
    log['links'].insert(0, dest)
    #print ('Linking "%s" to "%s"' % (src, dest))

    # wine can't handle symlinked exes (but dlls are fine)
    if src.lower().endswith(".exe"):
        shutil.copyfile(src, dest)
    else:
        os.symlink(src, dest)


def mktree(root, path, log):
    iodelay(0.001)
    tree = root
    for p in path.split('/'):
        tree = winpath(os.path.join(tree, p))
        if not os.path.isdir(tree):
            log['dirs'].insert(0, tree)
            #print ('Creating directory ', tree)
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
    global prettyprint_total

    if not os.path.exists('movfs4l_log.json'):
        return

    plog("Reading movfs4l_log.json")

    log = json.loads(open('movfs4l_log.json').read())

    head = p + "/"

    plog("Removing links")
    prettyprint_total = len(log['links'])
    t = start_prettyprint()
    i = 1
    for l in log['links']:
        l = winpath(l)
        if os.path.islink(l):
            prettyprint(i, l.replace(head, ""))
            #print ('Removing symlink ', l)
            iodelay(0.0005)
            os.unlink(l)
        i += 1
    stop_prettyprint(t)

    plog("Removing directories")
    prettyprint_total = len(log['dirs'])
    t = start_prettyprint()
    i = 1
    for d in log['dirs']:
        d = winpath(d)
        if os.path.isdir(d):
            prettyprint(i, d.replace(head, ""))
            #print ('Removing directory ', d)
            shutil.rmtree(d)
        i += 1
    stop_prettyprint(t)

    plog("Restoring backups")
    prettyprint_total = len(log['backups'])
    t = start_prettyprint()
    i = 1
    for b in log.get('backups', []):
        b = winpath(b)
        prettyprint(i, b.replace(head, ""))
        shutil.move('%s.unvfs' % b, b)
        i += 1
    stop_prettyprint(t)

    plog("Clearing log")
    log = {'dirs': [], 'links': [], 'backups': []}
    open('movfs4l_log.json', 'w').write(json.dumps(log, indent=4))


def lowerpath(path):
    if not use_lower:
        return path
    else:
        return path.lower()


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
    plog('Removing VFS layer')
    plog_indent += 1
    unvfs(DATADIR)
    plog_indent -= 1
    if MO_PROFILE == 'UNVFS':
        sys.exit()

    PDIR=os.path.join(pathHdlr(PATHS['profiles']),MO_PROFILE)
    PLUGINS=os.path.join(PDIR, 'plugins.txt')

    plog('Parsing MO mods configuration')
    MODS=pathHdlr(PATHS['mods'])
    modpaths = list(reversed([i[1:].strip() for i in open(os.path.join(PDIR, 'modlist.txt')).readlines() if i.startswith('+')]))

    plog('Creating VFS index')
    prettyprint_total = len(modpaths) + 1
    i = 1
    t = start_prettyprint()

    for modname in modpaths:
        prettyprint(i, modname)
        add_vfs_layer(os.path.join(MODS, modname).strip())
        i += 1

    prettyprint(i, "(Overwrite)")
    add_vfs_layer(pathHdlr(PATHS['overwrite']))
    i += 1

    stop_prettyprint(t)

    plog('Applying VFS')
    prettyprint_total = vfs_total
    t = start_prettyprint()
    apply_vfs(vfs, DATADIR, "", log)
    stop_prettyprint(t)

    plog('Writing log')
    open('movfs4l_log.json', 'w').write(json.dumps(log, indent=4))

    plog('Linking loadorder')
    updatelink(PLUGINS, pathHdlr(PATHS['plugins.txt']), log)

    print("")
    plog('VFS layer created. Rerun this script to update. Run "%s UNVFS" to shut it down' % sys.argv[0])
