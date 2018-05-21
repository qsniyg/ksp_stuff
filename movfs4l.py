#!/usr/bin/env python3
import os
import sys
import shutil

PATHS={
	"mo": '{PREFIX}/drive_c/MO',
	"skyrim": '{PREFIX}/drive_c/Steam/steamapps/common/Skyrim Special Edition',
	"plugins.txt": '{PREFIX}/drive_c/users/metalpoet/Local Settings/Application Data/Skyrim Special Edition/Plugins.txt'
}
#NOTE: If you don't disable the folders under "Desktop Integration" in winecfg the plugins.txt path with be somewhere in your linux home directory instead
#DOUBLENOTE: You probably want to back up the above file before running this the first time ! 

PREFIX=os.getenv('WINEPREFIX')

def pathHdlr (p):
	return p.replace('{PREFIX}', PREFIX)

def unmount(p,pp):
	os.system('fusermount -u "%s"' % p)
	os.rmdir(p)
	shutil.move(PRISTINE,MOUNTPATH)

if __name__ == '__main__':
	MOUNTPATH=os.path.join(pathHdlr(PATHS['skyrim']),'Data')
	PRISTINE=os.path.join(pathHdlr(PATHS['skyrim']),'Data.real')
	MO_PROFILE='Default'
	if len(sys.argv) > 1:
		MO_PROFILE=sys.argv[1]

	#Don't create an MO profile named UNMOUNT - or you'll break this functionality
	if MO_PROFILE == 'UNMOUNT':
		unmount(MOUNTPATH,PRISTINE)
		sys.exit()
	#Ensure old mounts are cleared
	if os.system('mount | grep "%s"' % MOUNTPATH) == 0:
		print ("Previous VFS layer found unmounting")
		unmount(MOUNTPATH,PRISTINE)
	if not os.path.isdir(PRISTINE):
		#Move the REAL Data directory to Data.real and create a new empty Data directory for mounting on
		shutil.move(MOUNTPATH, PRISTINE)
		os.mkdir(MOUNTPATH)

	PDIR=os.path.join(pathHdlr(PATHS['mo']),'profiles')
	PDIR=os.path.join(PDIR,MO_PROFILE)
	PLUGINS=os.path.join(PDIR,'plugins.txt')
	print ('Setting symlink from "%s" to "%s" for loadorder' %(PLUGINS,pathHdlr(PATHS['plugins.txt'])))
	os.unlink(pathHdlr(PATHS['plugins.txt']))
	os.symlink(PLUGINS, pathHdlr(PATHS['plugins.txt']))

	print ('Parsing MO mods configuration')
	MODS=os.path.join(pathHdlr(PATHS['mo']),'mods')
	MODPATHS = [os.path.join(MODS,i[1:]).strip() for i in open(os.path.join(PDIR,'modlist.txt')).readlines() if i.startswith('+')]
	MODPATHS = ' '.join(['"%s"' %i for i in MODPATHS])
	CMD='mhddfs "%s" %s "%s"' %(PRISTINE,MODPATHS, MOUNTPATH)
	print ('Running: ',CMD)
	if os.system(CMD):
		print ("An error occured !")
		sys.exit(1)
	print ('VFS layer created. Rerun this script to update. Run "%s UNMOUNT" to shut it down' %sys.argv[0])







