#!/bin/bash
if test $# -eq 0 ; then
	echo "Simple script to package up the custom missions into zip files ready to extract from your GameData folder."
	echo "Usage $0 <missionpackdirectory>"
	exit 0
fi

MISSIONPACK=$1
TEMPDIR=/tmp/$MISSIONPACK
#Clean out any old tempdir
rm -fr $TEMPDIR
mkdir -p $TEMPDIR/GameData/KSPStoryMissions/PluginData/KSPStoryMissions/
cp $MISSIONPACK/*.cfg $MISSIONPACK/README.* $TEMPDIR/GameData/KSPStoryMissions/PluginData/KSPStoryMissions
cd $TEMPDIR
zip -r $MISSIONPACK.zip *

echo "Zip file is located at $TEMPDIR/$MISSIONPACK.zip"

