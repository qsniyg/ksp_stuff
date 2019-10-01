#!/usr/bin/env python3
import os
import sys
import shutil
import re
import threading
import configparser
import copy
import subprocess
#import pprint
import time
try:
    # Much faster than python's default json module, makes reading and writing the log much quicker
    import ujson as json
except Exception:
    import json


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


def winepath(prefix, path):
    if "\\\\" in path:
        path = path.replace("\\\\", "/")
    elif "/" not in path:
        # good enough for now
        path = path.replace("\\", "/")

    match = re.search(r"^([a-z]:)", path.lower())
    if match:
        path = re.sub("^..", os.path.join(prefix, "dosdevices", match.group(1)), path)

    path = winpath(path)

    return path


def fullpath(path):
    return os.path.realpath(os.path.expanduser(path))

scriptdir = os.path.dirname(os.path.realpath(__file__))

def ioyield():
    iodelay(.00001)


def get_terminal_width():
    return shutil.get_terminal_size()[0]


def simple_copy(data):
    if type(data) == list:
        mylist = []

        for i in data:
            mylist.append(simple_copy(i))

        return mylist
    elif type(data) == dict:
        mydict = {}

        for i in data:
            mydict[i] = simple_copy(data[i])

        return mydict
    else:
        return data


def apply_variables(string, variables, processed={}):
    if type(string) != str:
        return string

    newstring = ""
    variable = None
    for x in string:
        if variable is not None:
            if x == "}":
                value = None

                if variable in processed:
                    if processed[variable] is None:
                        print("Variable loop (%s), exiting" % variable)
                        return sys.exit(1)
                    else:
                        value = processed[variable]

                if value is None:
                    processed[variable] = None
                    value = apply_variables(variables[variable], variables, processed)
                    processed[variable] = value

                newstring += value
                variable = None
            else:
                variable += x
            continue
        if x == "{":
            variable = ""
            continue
        newstring += x
    return newstring


def get_used_variables(string, variables, used_variables=[]):
    variable = None
    for x in string:
        if variable is not None:
            if x == "}":
                if variable not in used_variables:
                    used_variables.append(variable)

                    if variable in variables:
                        get_used_variables(variables[variable], variables, used_variables)
                variable = None
            else:
                variable += x
            continue
        if x == "{":
            variable = ""
            continue
    return used_variables


def fill_variables(variables):
    for var in variables:
        value = apply_variables(variables[var], variables)
        variables[var] = value
    return variables


game_infos = {
    "Generic": {
        "vars": {
            "default_profile": "Default",
            "vfs_meta_log": "{game_path}/movfs4l_log.json"
        },

        "shortname": "Unknown",

        "neededvars": [
            "default_profile",
            "vfs_meta_log",
            "wineprefix"
        ]
    },

    "GenericBethesda": {
        "inherit": "Generic",

        "shortname": "Unknown",

        "vars": {
            "default_profile": "Default",
            "plugins_txt": "{gameappdata}/plugins.txt",
            "loadorder_txt": "{gameappdata}/loadorder.txt",
            "game_userdir": "{mygames_root}/{game_shortname}",
            "game_datadir": "{game_path}/Data"
        },

        "vfs": [
            {
                "dest": "{game_datadir}",
                "path": "[mods]",
                "name": "mods"
            },

            {
                "dest": "{plugins_txt}",
                "path": "{mo_profile}/plugins.txt",
                "name": "plugins list"
            },

            {
                "dest": "{loadorder_txt}",
                "path": "{mo_profile}/loadorder.txt",
                "name": "load order"
                #"disabled": True
            },

            {
                "dest": "{game_userdir}",
                "path": "[inis]",
                "name": "INI configuration files"
            }
        ]
    },

    "Morrowind": {
        "inherit": "GenericBethesda",

        "shortname": "Morrowind",

        "vars": {
            "game_userdir": "{game_path}",
            "game_datadir": "{game_path}/Data Files",
            "gameappdata": "{localappdata}/Morrowind",
        },

        "inis": [
            "Morrowind.ini"
        ]
    },

    "Oblivion": {
        "inherit": "GenericBethesda",

        "shortname": "Oblivion",

        "vars": {
            "gameappdata": "{localappdata}/Oblivion",
        },

        "inis": [
            "oblivion.ini",
            "oblivionprefs.ini"
        ]
    },

    "Skyrim": {
        "inherit": "GenericBethesda",

        "shortname": "Skyrim",

        "vars": {
            "gameappdata": "{localappdata}/Skyrim",
        },

        "inis": [
            "skyrim.ini",
            "skyrimprefs.ini"
        ]
    },

    "Enderal": {
        "inherit": "GenericBethesda",

        "shortname": "Enderal",

        "vars": {
            "gameappdata": "{localappdata}/enderal",
        },

        "inis": [
            "enderal.ini",
            "enderalprefs.ini"
        ]
    },

    "Skyrim Special Edition": {
        "inherit": "GenericBethesda",

        "shortname": "SkyrimSE",

        "vars": {
            "gameappdata": "{localappdata}/Skyrim Special Edition",
            "game_userdir": "{mygames_root}/Skyrim Special Edition"
        },

        "inis": [
            "skyrim.ini",
            "skyrimprefs.ini",
            "skyrimcustom.ini"
        ]
    },

    "Skyrim VR": {
        "inherit": "GenericBethesda",

        "shortname": "SkyrimVR",

        "vars": {
            "gameappdata": "{localappdata}/Skyrim VR",
        },

        "inis": [
            "skyrimvr.ini",
            "skyrimprefs.ini"
        ]
    },

    "Fallout 3": {
        "inherit": "GenericBethesda",

        "shortname": "Fallout3",

        "vars": {
            "gameappdata": "{localappdata}/Fallout3"
        },

        "inis": [
            "fallout.ini",
            "falloutprefs.ini",
            "custom.ini",
            "GECKCustom.ini",
            "GECKPrefs.ini"
        ]
    },

    "New Vegas": {
        "inherit": "Fallout 3",

        "shortname": "FalloutNV",

        "vars": {
            "gameappdata": "{localappdata}/FalloutNV"
        }
    },

    "TTW": {
        "inherit": "FalloutNV",

        "shortname": "FalloutTTW",

        "vars": {
            "game_userdir": "{mygames_root}/FalloutNV",
            "gameappdata": "{localappdata}/FalloutNV"
        }
    },

    "Fallout 4": {
        "inherit": "GenericBethesda",

        "shortname": "Fallout4",

        "vars": {
            "gameappdata": "{localappdata}/Fallout4"
        },

        "inis": [
            "fallout4.ini",
            "fallout4prefs.ini",
            "fallout4custom.ini"
        ]
    },

    "Fallout 4 VR": {
        "inherit": "Fallout4",

        "shortname": "Fallout4VR",

        "vars": {
            "gameappdata": "{localappdata}/Fallout4VR"
        }
    }
}

game_binaries = [
    "TESV.exe",
    "SkyrimSE.exe",
    "SkyrimVR.exe",
    "Morrowind.exe",
    "Oblivion.exe",
    "Fallout3.exe",
    "FalloutNV.exe",
    "Fallout4.exe",
    "Fallout4VR.exe",

    "Nemesis Unlimited Behavior Engine.exe"
]

game_binaries_csv = ",".join(game_binaries)


def get_game_from_moroot(variables):
    moini = os.path.join(variables["mo_gameroot"], "ModOrganizer.ini")

    config = configparser.ConfigParser()
    config.read(moini)

    variables["game_name"] = config["General"]["gameName"]
    variables["game_type"] = variables["game_name"]
    variables["game_path"] = winepath(variables["wineprefix"], config["General"]["gamePath"])

    if variables["game_type"] not in game_infos:
        variables["game_type"] = "GenericBethesda"
        pwarn("Unknown game: %s" % variables["game_type"])
        pwarn("Defaulting to GenericBethesda. You will have to manually enter `gameappdata' in the configuration.")


def fill_game_info(variables, game_type=None):
    if game_type is None:
        if variables["game_type"] not in game_infos:
            perr("Unknown game type `%s', exiting." % variables["game_type"])
            return sys.exit(1)
        game_type = variables["game_type"]

    game_info = simple_copy(game_infos[game_type])

    if "shortname" in game_info and "game_shortname" not in variables:
        variables["game_shortname"] = game_info["shortname"]

    if "neededvars" not in game_info:
        game_info["neededvars"] = []
    if "vfs" not in game_info:
        game_info["vfs"] = []
    if "inis" not in game_info:
        game_info["inis"] = []

    for var in game_info["vars"]:
        if var not in variables:
            variables[var] = simple_copy(game_info["vars"][var])

    if "inherit" in game_info:
        inherited = fill_game_info(variables, game_info["inherit"])

        for entry in inherited["vfs"]:
            can_add = True
            for entry1 in game_info["vfs"]:
                if entry1["dest"] == entry["dest"] and entry1["path"] == entry["path"]:
                    can_add = False
                    break
            if can_add:
                game_info["vfs"].append(entry)

        for entry in inherited.get("neededvars", []):
            if entry not in game_info["neededvars"]:
                game_info["neededvars"].append(entry)

        for entry in inherited.get("inis", []):
            if entry not in game_info["inis"]:
                game_info["inis"].append(entry)

    # Remove duplicate entries (disabled for now as it's useless, and breaks overwrites)
    """old_vfs = game_info["vfs"]
    game_info["vfs"] = []
    for entry in reversed(old_vfs):
        skip = False
        for gi_entry in game_info["vfs"]:
            if entry["dest"] == gi_entry["dest"]:
                skip = True
                break
        if skip:
            continue
        game_info["vfs"].insert(0, entry)"""

    return game_info


def get_wine_user(variables):
    usersdir = winpath(os.path.join(variables["wineprefix"], "drive_c", "users"))

    if "wineuser" not in variables:
        users = []
        for user in os.listdir(usersdir):
            if user.lower() != "public":
                users.append(user)

        error = False
        if len(users) > 1:
            pwarn("Too many users in %s, use `--wineuser' to specify the user." % variables["wineprefix"])
            error = True
        elif len(users) == 0:
            pwarn("No users under %s?" % variables["wineprefix"])
            error = True

        if error:
            pwarn("The script may still succeed if using a portable ModOrganizer setup, but you will need to manually set `localappdata'.")
            return None

        variables["wineuser"] = users[0]

    if "winehome" not in variables:
        winehome = winpath(os.path.join(usersdir, variables["wineuser"]))
        if os.path.exists(winehome):
            variables["winehome"] = winehome
        else:
            pwarn("`%s' does not exist" % winehome)


def find_localappdata(variables):
    # https://github.com/wine-mirror/wine/blob/f0ad5b5c546d17b281aef13fde996cda08d0c14e/dlls/shell32/shellpath.c
    searchpaths = [
        "Local AppData",
        "Local Settings/Application Data",
        "AppData/Local"
    ]

    if "winehome" not in variables:
        return

    if "localappdata" in variables:
        return

    for path in searchpaths:
        fullpath = winpath(os.path.join(variables["winehome"], path))
        if os.path.exists(fullpath):
            # TODO: maybe check if ModOrganizer exists under it?
            variables["localappdata"] = fullpath
            break


def find_mygames(variables):
    searchpaths = [
        "My Documents",
        "Documents"
    ]

    if "winehome" not in variables:
        return

    if "mygames_root" in variables:
        return

    for path in searchpaths:
        fullpath = winpath(os.path.join(variables["winehome"], path, "My Games"))
        if os.path.exists(fullpath):
            variables["mygames_root"] = fullpath
            break


def find_mo_installroot(variables):
    if "mo_installroot" in variables:
        variables["mo_installroot"] = winepath(variables["wineprefix"], variables["mo_installroot"])
        if not os.path.exists(variables["mo_installroot"]):
            pwarn("Specified ModOrganizer installation path (%s) does not exist" % variables["mo_installroot"])
        return variables["mo_installroot"]

    installroot = winpath(os.path.join(variables["wineprefix"], "drive_c", "Modding", "MO2"))
    if os.path.exists(installroot):
        variables["mo_installroot"] = installroot
        return installroot

    pwarn("Unable to find ModOrganizer installation path in current wineprefix (%s)" % variables["wineprefix"])
    pwarn("Either set WINEPREFIX if ModOrganizer is installed in another prefix, %s" %
          "or use the `--mo_installroot' option if ModOrganizer is installed to somewhere other than `C:\Modding\MO2'.")
    return None



def find_mo_games(variables):
    if "mo_installroot" not in variables:
        return []

    # Portable installation, don't look further
    if os.path.exists(winpath(os.path.join(variables["mo_installroot"], "ModOrganizer.ini"))):
        return [variables["mo_installroot"]]

    if "localappdata" in variables:
        moroot = winpath(os.path.join(variables["localappdata"], "ModOrganizer"))
        if os.path.exists(moroot):
            games = []
            for game in os.listdir(moroot):
                fullgamedir = os.path.join(moroot, game)
                if os.path.exists(winpath(os.path.join(fullgamedir, "ModOrganizer.ini"))):
                    games.append(fullgamedir)
            return games
    else:
        pwarn("`localappdata' is missing")

    return []


def get_base_variables(variables):
    for var in os.environ:
        if var.startswith("MO_"):
            varname = var[3:]
            if varname not in variables:
                variables[varname] = os.environ[var]


def get_default_variables(variables):
    defaults = {
        "iodelay": "true",
        "mo_profile": "{mo_gameroot}/profiles/{profile}",
        "mo_mods": "{mo_gameroot}/mods",
        "mo_overwrite": "{mo_gameroot}/overwrite",
        "link_inis": "false",
        "fake_inis": "false"
    }

    for var in defaults:
        if var not in variables:
            variables[var] = defaults[var]

    if "wineprefix" not in variables:
        if "WINEPREFIX" in os.environ:
            variables["wineprefix"] = os.environ["WINEPREFIX"]
        else:
            variables["wineprefix"] = os.path.expanduser("~/.wine")



def generate_game_config(variables, gameinfo):
    used_variables = [
        "mo_gameroot",
        "game_type"
    ]

    for entry in gameinfo.get("neededvars", []):
        if entry not in used_variables:
            used_variables.append(entry)

    for entry in gameinfo["vfs"]:
        if "disabled" in entry:
            continue

        get_used_variables(entry["dest"], variables, used_variables)
        get_used_variables(entry["path"], variables, used_variables)

    config = {}
    for var in used_variables:
        if var in variables:
            config[var] = variables[var]

    return config


games = {}
game = None


def parse_config(variables):
    orig_variables = None
    regenerate_config = False
    if variables.get("generate_config", False) is True:
        regenerate_config = True
        orig_variables = simple_copy(variables)

    inipath = os.path.join(scriptdir, "config.ini")
    if not os.path.exists(inipath):
        return generate_config(variables, inipath)

    plog("Parsing configuration file")
    config = configparser.ConfigParser()
    config.read(inipath)

    get_base_variables(variables)

    generalvars = {}
    if "general" in config:
        for var in config["general"]:
            if var not in variables:
                variables[var] = config["general"][var]
                generalvars[var] = True

    base_variables = variables

    for var in config:
        if not var.startswith("game/"):
            continue

        variables = simple_copy(base_variables)

        mogame = var[len("game/"):]
        mogame_config = config[var]

        for mvar in mogame_config:
            if mvar not in variables or mvar in generalvars:
                variables[mvar] = simple_copy(mogame_config[mvar])

        game_info = fill_game_info(variables)
        game_info["vars"] = simple_copy(variables)
        games[mogame] = game_info

    if regenerate_config:
        generate_config(orig_variables, inipath, config)


def generate_config(variables, inipath, config=None):
    global plog_indent

    plog("Generating configuration file")
    plog_indent += 1

    get_base_variables(variables)
    get_default_variables(variables)

    get_wine_user(variables)
    find_localappdata(variables)
    find_mo_installroot(variables)
    find_mygames(variables)
    games = find_mo_games(variables)

    if len(games) == 0:
        perr("Unable to find any games")
        sys.exit(1)

    if config is None:
        config = configparser.ConfigParser()

        config["general"] = {
            "iodelay": True,
            "link_inis": True,
            "fake_inis": False
        }

    for game_path in games:
        gamename = os.path.basename(game_path)
        variables["mo_gameroot"] = game_path
        get_game_from_moroot(variables)

        gameinfo = fill_game_info(variables)

        if os.path.exists(winpath(os.path.join(game_path, "ModOrganizer.exe"))):
            # portable installation
            gamename = gameinfo["shortname"]

        plog("Detected game '%s' at %s" % (
            gamename, variables["game_path"]
        ))

        if not os.path.exists(winpath(variables["game_path"])):
            plog_indent += 1
            pwarn("Does not exist, skipping")
            plog_indent -= 1
            continue

        keyname = "game/" + gamename

        if keyname not in config:
            config[keyname] = generate_game_config(variables, gameinfo)

    with open(inipath, 'w') as inifile:
        config.write(inifile)

    plog_indent -= 1
    plog("Written auto-generated configuration to `config.ini'. %s" % (
        "Please check the file, then run this script again."
    ))
    plog("You can also re-run this for other installations by using `--generate_config'")
    sys.exit(0)


def detect_game():
    cwd = os.getcwd()
    for game in games:
        game_info = games[game]
        game_path = fullpath(game_info["vars"]["game_path"])
        if game_path in cwd:
            return game
    return None


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
def plog(string, **kwargs):
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
    if "level" in kwargs:
        if kwargs["level"] == "warn":
            color = "33" # yellow
        elif kwargs["level"] == "error":
            color = "31" # red
    text += "\33[" + color + "m"
    text += string
    text += "\33[0m"
    print(text)


def pwarn(string, **kwargs):
    kwargs["level"] = "warn"
    plog(string, **kwargs)


def perr(string, **kwargs):
    kwargs["level"] = "error"
    plog(string, **kwargs)

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


vfs_log = {'dirs': [], 'links': [], 'backups': []}


def get_fake_inis(variables):
    # TODO: this only works for .inis that are in the same directory as the mod
    if parsebool(variables.get("fake_inis", "false")) is not True:
        return []

    modlist = get_modpaths(variables)
    fakeinis = []

    for mod in modlist:
        modpath = winpath(os.path.join(args["mo_mods"], mod))

        plugins = []
        inis = []
        for file_ in os.listdir(modpath):
            lowerfile = file_.lower()

            if lowerfile.endswith(".esm") or lowerfile.endswith(".esp"):
                plugins.append(file_[:-4])

            if lowerfile.endswith(".ini"):
                inis.append(lowerfile[:-4])

        for plugin in plugins:
            if plugin.lower() not in inis:
                fakeinis.append(plugin + ".INI")

    return fakeinis


def write_winevfs_file(variables):
    modlist = get_modpaths(variables)
    fakeinis = get_fake_inis(variables)

    filecontents = []

    filecontents.append("?full=" + game_binaries_csv)

    for entry in game["vfs"]:
        if "disabled" in entry:
            continue

        if entry["path"] == "[inis]" and parsebool(variables.get("link_inis", "false")) is not True:
            continue
        if entry["path"] == "[mods]":
            for ini in fakeinis:
                filecontents.append("R")
                filecontents.append(winpath(os.path.join(entry["dest"], ini)))
                filecontents.append("/dev/null")
            for mod in modlist:
                filecontents.append("R")
                filecontents.append(winpath(entry["dest"]))
                filecontents.append(winpath(os.path.join(args["mo_mods"], mod)))
            filecontents.append("W")
            filecontents.append(winpath(entry["dest"]))
            filecontents.append(winpath(variables["mo_overwrite"]))
        elif entry["path"] == "[inis]":
            for ini in game.get("inis", []):
                filecontents.append("R")
                filecontents.append(winpath(os.path.join(entry["dest"], ini)))
                filecontents.append(winpath(os.path.join(variables["mo_profile"], ini)))
        else:
            filecontents.append("R")
            filecontents.append(winpath(entry["dest"]))
            filecontents.append(winpath(entry["path"]))

    filecontents.append("")

    with open("/tmp/.movfs4l_winevfs", 'w') as f:
        f.write("\n".join(filecontents))



def apply_game_vfs(variables):
    global prettyprint_total, vfs_log

    fakeinis = get_fake_inis(variables)

    for entry in game["vfs"]:
        if "disabled" in entry:
            continue

        if entry["path"] == "[inis]" and parsebool(variables.get("link_inis", "false")) is not True:
            continue

        plog("Linking %s" % entry["name"])
        if entry["path"] == "[mods]":
            for ini in fakeinis:
                updatelink("/dev/null", winpath(os.path.join(entry["dest"], ini)), vfs_log)

            prettyprint_total = vfs_total
            t = start_prettyprint()
            apply_vfs(vfs, entry["dest"], "", vfs_log)
            stop_prettyprint(t)
        elif entry["path"] == "[inis]":
            for ini in game.get("inis", []):
                updatelink(winpath(os.path.join(variables["mo_profile"], ini)),
                           winpath(os.path.join(entry["dest"], ini)), vfs_log)
        else:
            updatelink(entry["path"], entry["dest"], vfs_log)


def write_vfs_log():
    plog('Writing log')
    with open(game["vars"]["vfs_meta_log"], 'w') as logfile:
        logfile.write(json.dumps(vfs_log))


def updatelink(src, dest, log):
    iodelay(0.0015)
    dest = winpath(dest)
    if os.path.islink(dest):
        os.unlink(dest)
    elif os.path.exists(dest):
        shutil.move(dest, '%s.unvfs' % dest)
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


def unvfs(p):
    global prettyprint_total

    logpath = winpath(game["vars"]["vfs_meta_log"])
    if not os.path.exists(logpath):
        return

    plog("Reading VFS meta log")

    log = {}

    with open(logpath) as logfile:
        log = json.loads(logfile.read())

    head = p + "/"

    plog("Removing links")
    prettyprint_total = len(log['links'])
    t = start_prettyprint()
    i = 1
    for l in log['links']:
        l = winpath(l)
        if os.path.islink(l):
            prettyprint(i, l.replace(head, ""))
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
            if not os.listdir(d):
                prettyprint(i, d.replace(head, ""))
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

    with open(logpath, 'w') as logfile:
        logfile.write(json.dumps(log))


def get_modpaths(args):
    modpaths = []

    lines = []
    with open(winpath(os.path.join(args["mo_profile"], 'modlist.txt'))) as f:
        lines = f.readlines()

    for i in lines:
        if i.startswith('+'):  # only enabled mods
            modpaths.append(i[1:].strip())

    reversed_modpaths = list(reversed(modpaths))
    return reversed_modpaths


def parsebool(value):
    lowervalue = value.lower().strip()
    if lowervalue == "true":
        return True
    if lowervalue == "false":
        return False
    return value


boolargs = [
    "unvfs",
    "generate_config"
]

swallowargs = [
    "run"
]

def parseargs():
    currentarg = None
    variables = {}
    in_swallow = None
    for arg in sys.argv[1:]:
        if in_swallow is not None:
            variables[in_swallow].append(arg)
            continue
        if arg.startswith("--") and currentarg is None:
            currentarg = arg[2:]
            if currentarg.lower() in boolargs:
                variables[currentarg] = True
                currentarg = None
            elif currentarg.lower() in swallowargs:
                variables[currentarg] = []
                in_swallow = currentarg
                continue
        elif currentarg is not None:
            variables[currentarg] = arg
            currentarg = None
    return variables


if __name__ == '__main__':
    args = parseargs()
    parse_config(args)

    game = args.get("game", None)
    gamename = None
    if game is None:
        game = detect_game()

    if game is not None:
        gamename = game
        game = games[gamename]

    if game is None:
        perr("Unable to detect game (use `--game' to specify)")
        sys.exit(0)

    args = game["vars"]
    profile = None
    if "profile" in args:
        profile = args["profile"]
    if profile is None:
        profile = args.get("default_profile", "Default")

    args["profile"] = profile
    plog("Using profile `%s'" % args["profile"])

    get_default_variables(args)
    fill_variables(args)

    if not os.path.exists(winpath(args["mo_profile"])):
        perr("Profile directory does not exist: %s" % args["mo_profile"])
        sys.exit(1)

    for entry in game["vfs"]:
        if "disabled" in entry:
            continue

        entry["dest"] = apply_variables(entry["dest"], args)
        entry["path"] = apply_variables(entry["path"], args)

    IO_DELAY = False
    if "iodelay" in game["vars"]:
        IO_DELAY = parsebool(game["vars"]["iodelay"])
        if type(IO_DELAY) is not bool:
            IO_DELAY = True

    if IO_DELAY is True:
        def iodelay(s):
            time.sleep(s)

    if "run" in game["vars"]:
        if "winevfs" not in game["vars"]:
            perr("winevfs cannot be found, specify with the `winevfs' option")
            sys.exit(1)

        if "cwd" not in game["vars"]:
            game["vars"]["cwd"] = game["vars"]["game_path"]
        os.chdir(game["vars"]["cwd"])

        write_winevfs_file(args)

        os.environ["WINEVFS_VFSFILE"] = "/tmp/.movfs4l_winevfs"
        os.environ["WINEPREFIX"] = game["vars"]["wineprefix"]

        commandline = [game["vars"]["winevfs"]] + game["vars"]["run"]

        pwarn("Running `wineserver -w', this will hang until all wine processes have quit")
        pwarn("Do not run ModOrganizer until all wine processes are finished")
        subprocess.call(["wineserver", "-w"], env=os.environ)
        subprocess.call(["wineserver", "-k"], env=os.environ)

        status = subprocess.call(commandline, env=os.environ)

        pwarn("Running `wineserver -w', this will hang until all wine processes have quit")
        pwarn("Do not run ModOrganizer until all wine processes are finished")
        subprocess.call(["wineserver", "-w"], env=os.environ)
        subprocess.call(["wineserver", "-k"], env=os.environ)
        plog("Finished")

        sys.exit(status)

    plog('Removing VFS layer')
    for entry in game["vfs"]:
        if "disabled" in entry:
            continue

        if entry["path"] == "[mods]":
            plog_indent += 1
            unvfs(entry["dest"])
            plog_indent -= 1

    if "unvfs" in args and args["unvfs"] is True:
        sys.exit(0)

    plog('Parsing MO mods configuration')
    """modpaths = []
    for i in open(winpath(os.path.join(args["mo_profile"], 'modlist.txt'))).readlines():
        if i.startswith('+'):  # only enabled mods
            modpaths.append(i[1:].strip())

    modpaths = list(reversed(modpaths))"""
    modpaths = get_modpaths(args)

    plog('Creating VFS index')
    prettyprint_total = len(modpaths) + 1
    i = 1
    t = start_prettyprint()

    for modname in modpaths:
        prettyprint(i, modname)
        add_vfs_layer(winpath(os.path.join(args["mo_mods"], modname)).strip())
        i += 1

    prettyprint(i, "(Overwrite)")
    add_vfs_layer(winpath(args["mo_overwrite"]))
    i += 1

    stop_prettyprint(t)

    apply_game_vfs(args)
    write_vfs_log()

    print("")
    plog('VFS layer created. Run "%s --game \'%s\' --profile \'%s\' --unvfs" to shut it down (run this before running Mod Organizer again)' % (
        sys.argv[0],
        gamename,
        profile
    ))
