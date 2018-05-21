#!/usr/bin/env python3
import os
import sys
import shutil
from glob import iglob
import json


PATHS={
    "mo": '{PREFIX}/drive_c/MO',
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
                

def updatelink(src, dest):
    if os.path.islink(dest):
        os.unlink(dest)
    os.symlink(src, dest)

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
    log = {'dirs': [], 'links': []}
    open('movfs4l_log.json','w').write(json.dumps(log, indent=4))


def dirsthatexist(p):
    updirs = {}
    for item in traverse(p, True):
        updirs[item.upper()] = item
    return updirs

def addvfslayer(p,l, log):
    updirs = dirsthatexist(p)
    for item in traverse(l, True):
        src = os.path.join(l, item)
        dest = os.path.join(p, item)
        if not os.path.exists(dest):
            if not item.upper() in list(updirs.keys()):
                print ('Creating directory: ',dest)
                os.makedirs(dest)
                log['dirs'].append(dest)
            else:
                src = os.path.join(p,updirs[item.upper()])
                print ('Linking directory "%s" to "%s"' %(src, dest))
                os.symlink(src , dest)
                log['links'].append(dest)
    for item in traverse(l):
        src = os.path.join(l, item)
        dest = os.path.join(p, item)
        if not os.path.isdir(src):
            print ('Updating link from "%s" to "%s"' %(src,dest))
            updatelink(src, dest)
            log['links'].append(dest)


if __name__ == '__main__':
    log = {'dirs': [], 'links': []}
    DATADIR=os.path.join(pathHdlr(PATHS['skyrim']),'Data')
    MO_PROFILE='Default'
    if len(sys.argv) > 1:
        MO_PROFILE=sys.argv[1]

    #Don't create an MO profile named UNVFS - or you'll break this functionality
    unvfs(DATADIR)
    if MO_PROFILE == 'UNVFS':
        sys.exit()

    PDIR=os.path.join(pathHdlr(PATHS['mo']),'profiles')
    PDIR=os.path.join(PDIR,MO_PROFILE)
    PLUGINS=os.path.join(PDIR,'plugins.txt')
    print ('Setting symlink from "%s" to "%s" for loadorder' %(PLUGINS,pathHdlr(PATHS['plugins.txt'])))
    updatelink(PLUGINS, pathHdlr(PATHS['plugins.txt']))

    print ('Parsing MO mods configuration')
    MODS=os.path.join(pathHdlr(PATHS['mo']),'mods')
    for modpath in [os.path.join(MODS,i[1:]).strip() for i in open(os.path.join(PDIR,'modlist.txt')).readlines() if i.startswith('+')]:
        addvfslayer(DATADIR,modpath, log)
    open('movfs4l_log.json','w').write(json.dumps(log, indent=4))

    print ('VFS layer created. Rerun this script to update. Run "%s UNMOUNT" to shut it down' %sys.argv[0])







