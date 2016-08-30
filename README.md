ksp_stuff
=========

Various bits and pieces for KSP


rtplacer.py
A simple python script which helps build remotetech networks. 
The idea is that you put all your satelites on one launch vehicle 
in a lower orbit. Then you raise the AP to the network orbit.
Release the first satelite and circularize it's orbit,
warp until the orbital encounter is the right angle from that 
satelite and release the next.
RTPlacer will calculate how long you have to warp for and give
you are result both as number or orbits (of the launch vehicle)
and as a time.
If you run the script with no options it will ask you to enter
the values it needs. Alternatively you can type them on the 
commandline:

`rtplacer.py <period of LV> <period of first satelite> <number of satelites to place> <maximum number of phasing orbits>`

Orbital periods must be given as: dd:hh:mm:ss

The greater the maximum number of phasing orbits the closer to a perfect placement you are likely to get, but the longer
you will have to wait while timewarping.

~~KSPStoryMissions: custom missions for the KSPStoryMissions mod.~~
The mod this was for no longer exists. 

