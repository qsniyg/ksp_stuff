#!/usr/bin/env python
import sys
from datetime import  timedelta

def ksp_time(seconds):
    m,s = divmod(seconds,60)
    h,m = divmod(m,60)
    return "%dh%02dm%02ds" % (h, m, s)

if __name__ == '__main__':
    print "RTPlacer is a tool to help you set up RemoteTech networks."
    print "Using a single vehicle to set up a number of satelites equidistant from each other in orbit."
    print "To use raise the AP of the delivery vehicle to match the target orbit but do not circularize."
    print "Release the first satelite and circularize the orbit. Then enter the orbital periods below."
    print "The script will calculate how long you must timewarp before releasing the next satelite."
    print "Then after releasing it, simply warp the same amount for each subsequent satelite."    
    if not sys.argv:
        O1 = raw_input("Enter the orbital period of delivery vehicle [dd:hh:mm:ss]: ")
        O2 = raw_input("Enter the orbital period the last satelite placed[dd:hh:mm:ss]: ")
        N = raw_input("How many satelites will you be placing")
        M = raw_input("Maximum number of orbits")
    else:
        O1, O2, N, M = sys.argv[1:]
    print
    print
    degs = 360/int(N)
    O1 = [int(i) for i in O1.split(':')]
    O2 = [int(i) for i in O2.split(':')]
    period1 = timedelta(days=O1[0],hours=O1[1],minutes=O1[2],seconds=O1[3])
    period2 = timedelta(days=O2[0],hours=O2[1],minutes=O2[2],seconds=O2[3])

    orbit_ratio = period1.total_seconds() / period2.total_seconds()

    delivery_orbits = 0
    done = False

    degrees_per_orbit = 360 * orbit_ratio
    max_orbits = int(M)
    orbits = 0
    satelite_has_moved = 0
    nearest = 360
    target = 0
    print "Satelite moves %s degrees after every launch vehicle orbit" %int(degrees_per_orbit)
    print "Satelites must be %s degrees appart" %int(degs)
    while not done:
        orbits += 1
        satelite_has_moved += degrees_per_orbit
        if satelite_has_moved > 360:
            satelite_has_moved -= 360
        difference = abs(satelite_has_moved - degs)
        if  difference < nearest:
            nearest = difference
            target = orbits
        done = orbits == max_orbits or nearest == degs
    if nearest == degs:
        print "Exact match after %s orbits." % target
    else:
        print "Closest match is offset %s degrees after %s orbits" % (int(nearest), target)
    timewarp = timedelta(seconds=((target*period1.total_seconds())- (period1.total_seconds()/4))).total_seconds()

    print "Timewarp for: %s ( %ss )" %(ksp_time(timewarp), timewarp)






