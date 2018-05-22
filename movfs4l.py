#!/usr/bin/env python3
import os
import sys
import shutil
from glob import iglob
import json


PATHS={
    "mods": '{PREFIX}/drive_c/MO/mods',
    "profiles": '{PREFIX}/drive_c/MO/profiles',
    "skyrim": '{PREFIX}/drive_c/Steam/steamapps/common/Skyrim Special Edition',
    "plugins.txt": '{PREFIX}/drive_c/users/metalpoet/Local Settings/Application Data/Skyrim Special Edition/Plugins.txt'
}
#NOTE: If you don't disable the folders under "Desktop Integration" in winecfg the plugins.txt path with be somewhere in your linux home directory instead
#DOUBLENOTE: You probably want to back up the above file before running this the first time ! 

PREFIX=os.getenv('WINEPREFIX')

def traverse(rootDir, dirsonly=False):
    if not rootDir.endswith('/'):
        rootDir = '%s/' % rootDir
    for dirName, subdirList, fileList in os.walk(rootDir):
        for fname in fileList:
            if dirsonly:
                yield dirName.replace(rootDir,'')
            else:
                yield os.path.join(dirName.replace(rootDir,''),fname) 
                

def updatelink(src, dest, log):
    if os.path.islink(dest):
        os.unlink(dest)
    elif os.path.exists(dest):
        shutil.move(dest,'%s.UNVFS' %dest)
        print ('Backing up ',dest)
        log['backups'].append(dest)
    log['links'].insert(0, dest)
    print ('Linking "%s" to "%s"' %(src,dest))
    os.symlink(src, dest)

def mktree(root, path, log):
    tree = root
    for p in path.split('/'):
        tree = os.path.join(tree,p)
        if not os.path.isdir(tree):
            log['dirs'].insert(0,tree)
            print ('Creating directory ',tree)
            os.mkdir(tree)


def pathHdlr (p):
    return p.replace('{PREFIX}', PREFIX)

def unvfs(p):
    if not os.path.exists('movfs4l_log.json'):
        return
    log = json.loads(open('movfs4l_log.json').read())
    for l in log['links']:
        if os.path.islink(l):
            print ('Removing symlink ', l)
            os.unlink(l)
    for d in log['dirs']:
        if os.path.isdir(d):
            print ('Removing directory ', d)
            shutil.rmtree(d)
    for b in log.get('backups', []):
        shutil.move(b,b.replace('.UNVFS',''))
    log = {'dirs': [], 'links': [], 'backups': []}
    open('movfs4l_log.json','w').write(json.dumps(log, indent=4))



def addvfslayer(p,l, log):
    for item in traverse(l, True):
        mktree(p, item.lower(), log)  
    for item in traverse(l):
        src = os.path.join(l, item)
        dest = os.path.join(p, item.lower())
        if not os.path.isdir(src):
            updatelink(src, dest, log)

def lowertree(dir):
    # renames all subforders of dir, not including dir itself
    def rename_all( root, items):
        for name in items:
            try:
                os.rename( os.path.join(root, name), 
                                    os.path.join(root, name.lower()))
            except OSError:
                pass # can't rename it, so what

    # starts from the bottom so paths further up remain valid after renaming
    for root, dirs, files in os.walk( dir, topdown=False ):
        rename_all( root, dirs )
        rename_all( root, files)


if __name__ == '__main__':
    log = {'dirs': [], 'links': [], 'backups': []}
    DATADIR=os.path.join(pathHdlr(PATHS['skyrim']),'Data')
    lowertree(DATADIR)
    MO_PROFILE='Default'
    if len(sys.argv) > 1:
        MO_PROFILE=sys.argv[1]

    #Don't create an MO profile named UNVFS - or you'll break this functionality
    unvfs(DATADIR)
    if MO_PROFILE == 'UNVFS':
        sys.exit()

    PDIR=os.path.join(pathHdlr(PATHS['profiles']),MO_PROFILE)
    PLUGINS=os.path.join(PDIR,'plugins.txt')
    print ('Setting symlink from "%s" to "%s" for loadorder' %(PLUGINS,pathHdlr(PATHS['plugins.txt'])))
    updatelink(PLUGINS, pathHdlr(PATHS['plugins.txt']), log)

    print ('Parsing MO mods configuration')
    MODS=pathHdlr(PATHS['mods'])
    for modpath in [os.path.join(MODS,i[1:]).strip() for i in open(os.path.join(PDIR,'modlist.txt')).readlines() if i.startswith('+')]:
        addvfslayer(DATADIR,modpath, log)
    open('movfs4l_log.json','w').write(json.dumps(log, indent=4))

    print ('VFS layer created. Rerun this script to update. Run "%s UNMOUNT" to shut it down' %sys.argv[0])







