# movfs4l.py

movfs4l (Mod Organizer Virtual FileSystem For Linux) is a workaround for using MO2 under Linux,
until USVFS is properly supported under Wine.

Please note that Mod Organizer 1 (and older versions of MO2) work fine under Wine. This tool
is only meant as a way to be able to mod Bethesda games with later versions of MO2, which feature
significant performance improvements as well as new features that can significantly improve
the experience of modding Skyrim/Fallout.

Right now, there are 2 supported methods:

 * Symlink
   * Pros:
     * Well-tested
     * No extra setup needed
   * Cons:
     * Slow to setup and tear down
     * You need to tear down the symlink setup before running MO2, and set it up again
       in order to run Skyrim with mods
     * For Skyrim, you will have to run tools like FNIS and Nemesis each time you set it up
       * BodySlide can thankfully be set to output to the overwrite directory, but an extra
         step is needed to do this.
     * Symlinks are broken under wine 4.8 (this is fixed in later versions)
 * [winevfs](https://github.com/qsniyg/winevfs)
   * Pros:
     * Very fast to load and zero tear down needed
     * Doesn't pollute your mod directory
     * Only need to run FNIS/Nemesis when needed, other tools also work like they would under USVFS
     * *Possibly* faster performance than native Wine (unless using Linux 5.3's case insensitivity for EXT4)
   * Cons:
     * Requires compiling and installing a 3rd-party program (winevfs)
     * Currently not very well tested
     * *Possibly* slower performance due to an extra layer added over all filesystem calls
     * Currently some issues with heavily multi-threaded applications (Nemesis is affected)
     * Slightly higher memory usage (shouldn't be too significant)
     * Requires all wine applications to be closed before and after running a program with it.
       Since wineserver needs to be hooked by winevfs, if any program using the hooked wineserver
       is not run with winevfs, **serious** problems can occur. MO2 can wipe out your entire profile.

Some of the cons (especially for winevfs) might be resolved later, but this is the current state of
the project.

## Using it

Older versions of this script had paths hardcoded into the script. This meant you had to have
a separate copy of the script for every Bethesda game you wanted to mod.

Newer versions use an automatically generated configuration file, which you can manually edit later if
needed.

In order to determine which games you have installed, it needs to find the Mod Organizer local
data path (`--mo_gameroot`). It might be able to detect this automatically, if `WINEPREFIX` is set
correctly, and if MO2 is installed to C:\Modding\MO2 (the default installation location). If not,
you will need to specify the installation root manually.

To generate the configuration for the first time (i.e. if `config.ini` does not exist), simply run:

    python3 movfs4l.py

If you want to automatically update the configuration, for example if you have another prefix with
ModOrganizer, or if you have added a new game to an existing prefix, ensure you have specified
the variables correctly (`WINEPREFIX`, `--mo_gameroot`, etc), run:

    python3 movfs4l.py --generate_config

### With symlinks

To setup a symlinked "VFS", run it specifying the game (not needed if running from the game's directory)
and profile (not needed if `Default`, or whatever value `default_profile` is set to):

    python3 movfs4l.py --game "Skyrim" --profile Default

Do not run MO2 while the symlinked "VFS" is active, this can cause issues with your profile.
When you want to run MO2 again, run the same command again, this time with `--unvfs`:

    python3 movfs4l.py --game "Skyrim" --profile Default --unvfs

This will remove the symlinks, allowing you to run MO2.

### With winevfs

Compile winevfs [as shown in the project's description](https://github.com/qsniyg/winevfs), then
specify the location to `bin/winevfs` in config.ini, for example:

```
[general]
...
winevfs = /home/username/winevfs/build/bin/winevfs
```

Then for running an executable in the game's top-level directory (such as the game itself):

    python3 movfs4l.py --game Skyrim --profile Default --run wine Skyrim.exe

Replace `wine` with proton's wine (e.g. `--run ~/.steam/steam/steamapps/common/Proton\ 4.11/dist/bin/wine Skyrim.exe`),
if needed. Any linux program can be run (with varying degrees of success), think of `--run` like using `sudo`.

If running an application not in the game's directory, you will need to set the CWD (current working directory)
through the `--cwd` option:

    python3 movfs4l.py --game Skyrim --profile Default --cwd ~/Downloads/Bodyslide --run wine Bodyslide.exe

**A few important notes regarding winevfs:**

 * Winevfs hooks into wineserver. Make sure _all_ wine applications are closed before using winevfs
   * Make sure all wine applications are closed _after_ finishing with winevfs as well. **Do not run Mod Organizer until the hooked wineserver is killed**
   * If you set wineprefix correctly in the configuration, both of these should be automatically handled by movfs4l.py,
     but it never hurts to double-check with a process monitor.
 * Winevfs is still in development. Most applications are tested to work (Skyrim, Fallout 4/NV, FNIS, BodySlide),
   but there are still a few that don't (notably Nemesis Unlimited Behavior Engine, due to thread races I have not yet fixed).
   If you run across any problems using it, please leave an issue [in the issue tracker](https://github.com/qsniyg/winevfs/issues).
 * Never run Mod Organizer with winevfs. Mod Organizer should always be run completely separate from movfs4l.py.

## Why ...?

### Why not use an older version of Mod Organizer?

If you don't have any issues with using an older version of MO, then there is no need for you
to use this tool. Personally, I found that using older versions made the experience of adding
and removing mods significantly more cumbersome as the amount of mods I used increased.

### Why create this instead of making USVFS work under Wine?

I am still investigating why USVFS doesn't work under Wine, but I have spent time maintaining
this project (and created winevfs) as a workaround, until a proper solution is found and implemented.

USVFS works by replacing various low-level filesystem related functions provided by Windows,
some of which are not exposed to any public API. Wine has been increasingly implementing these
functions, and organizing its codebase to match the way Windows works. Since USVFS only replaces
a few key functions (other functions under Windows internally call these functions), Wine has to
match the way Windows works internally in order for USVFS to function properly.

Even if I were to find a solution, it can take a relatively long time for the changes to land
their way into Wine. Thankfully however, there have been improvements in this area. It is now able
to properly load USVFS and some elementary apps (such as explorer++, included in MO 2.2) are able
to run, although directory listing doesn't appear to work yet.

### Why not integrate this into Mod Organizer?

Hard/Sym links could be integrated into MO, if the devs were interested in working on this.

Developing for MO under Linux is quite difficult due to the entire way it's built. Not only
would their build system have to be significantly modified, multiple subprojects have to be
patched as well. In other words, there's pretty much no way a Linux user can make any code
contributions to it, unless using a Windows virtual machine with Visual Studio installed.

Winevfs cannot be integrated, as wineserver itself has to be hooked, which requires MO
to be closed. It could be possible to hook Windows calls, similarly to how USVFS works,
but at this point we're just creating a version of USVFS that temporarily works under Wine,
but likely not under Windows.

### Why is setting this up so complicated?

Hopefully it's easier now, but non-standard paths can always cause headaches in usability.

There are plans
[to create a GUI](https://github.com/ajventer/ksp_stuff/issues/22) that will simplify using
this, but it could take a relatively significant amount of time to implement it.

I'd definitely appreciate some help with this one :)
