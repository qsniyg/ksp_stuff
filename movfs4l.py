#!/usr/bin/env python3
import os
import sys
import shutil
from glob import iglob


PATHS={
    "mods": '{PREFIX}/drive_c/MO/mods',
    "profiles": '{PREFIX}/drive_c/MO/profiles',
    "gamedir": '{PREFIX}/drive_c/Steam/steamapps/common/Skyrim Special Edition',
    "plugins.txt": '{PREFIX}/drive_c/users/metalpoet/Local Settings/Application Data/Skyrim Special Edition/Plugins.txt'
}
#NOTE: If you don't disable the folders under "Desktop Integration" in winecfg the plugins.txt path with be somewhere in your linux home directory instead
#DOUBLENOTE: You probably want to back up the above file before running this the first time ! 

PREFIX=os.getenv('WINEPREFIX')


def updatelink(src, dest):
    if os.path.islink(dest):
        os.unlink(dest)
    elif os.path.exists(dest):
        shutil.move(dest,'%s.unvfs' %dest)
        print ('Backing up ',dest)
    print ('Linking "%s" to "%s"' %(src,dest))
    os.symlink(src, dest)


def pathHdlr (p):
    return p.replace('{PREFIX}', PREFIX)

def unvfs(p):
    os.system('fusermount -u %s' %p)

if __name__ == '__main__':
    log = {'dirs': [], 'links': [], 'backups': []}
    DATADIR=os.path.join(pathHdlr(PATHS['gamedir']),'Data')
    PRISTINEDIR='%s.PRISTINE' %DATADIR
    if not os.path.isdir(PRISTINEDIR):
        os.rename(DATADIR,PRISTINEDIR)
        os.mkdir(DATADIR)
    elif len(os.listdir(DATADIR)):
        print ("Error: %s exists but %s is not empty ! " % (PRISTINEDIR, DATADIR))
        sys.exit(1)
    if os.system('ciopfs --help'):
        print ('Error: you need CIOPFS to use this script.')
        sys.exit(1)
    #lowertree(DATADIR)
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
    updatelink(PLUGINS, pathHdlr(PATHS['plugins.txt']))

    print ('Parsing MO mods configuration')
    MODS=pathHdlr(PATHS['mods'])
    CMD='ciopfs "%s"' %PRISTINEDIR
    for modpath in reversed([os.path.join(MODS,i[1:]).strip() for i in open(os.path.join(PDIR,'modlist.txt')).readlines() if i.startswith('+')]):
        CMD='%s "%s"' %(CMD,modpath)
    CMD='%s "%s"' %(CMD,DATADIR)
    print ('Running: %s' %CMD)
    os.system(CMD)

    print ('VFS layer created. Rerun this script to update. Run "%s UNVFS" to shut it down' %sys.argv[0])







