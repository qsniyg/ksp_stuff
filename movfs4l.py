#!/usr/bin/env python3
import os
import sys
import shutil
import re
import threading
import configparser
import copy
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
            "vfs_meta_log"
        ]
    },

    "GenericBethesda": {
        "inherit": "Generic",

        "shortname": "Unknown",

        "vars": {
            "default_profile": "Default",
            "plugins_txt": "{gameappdata}/plugins.txt"
        },

        "vfs": [
            {
                "dest": "{game_path}/Data",
                "path": "[mods]",
                "name": "mods"
            },

            {
                "dest": "{plugins_txt}",
                "path": "{mo_profile}/plugins.txt",
                "name": "plugins list"
            }
        ]
    },

    "Skyrim": {
        "inherit": "GenericBethesda",

        "shortname": "Skyrim",

        "vars": {
            "gameappdata": "{localappdata}/Skyrim",
        }
    },

    "Skyrim Special Edition": {
        "inherit": "GenericBethesda",

        "shortname": "SkyrimSE",

        "vars": {
            "gameappdata": "{localappdata}/Skyrim Special Edition",
            "loadorder_txt": "{gameappdata}/loadorder.txt"
        },

        "vfs": [
            {
                "dest": "{loadorder_txt}",
                "path": "{mo_profile}/loadorder.txt",
                "name": "load order"
            }
        ]
    },

    "Fallout 4": {
        "inherit": "Skyrim Special Edition",

        "shortname": "Fallout4",

        "vars": {
            "gameappdata": "{localappdata}/Fallout4"
        }
    }
}


def get_game_from_moroot(variables):
    moini = os.path.join(variables["mo_gameroot"], "ModOrganizer.ini")

    config = configparser.ConfigParser()
    config.read(moini)

    variables["game_name"] = config["General"]["gameName"]
    variables["game_type"] = variables["game_name"]
    variables["game_path"] = winepath(variables["wineprefix"], config["General"]["gamePath"])

    if variables["game_type"] not in game_infos:
        variables["game_type"] = "GenericBethesda"
        print("Unknown game: %s" % variables["game_type"])
        print("Defaulting to GenericBethesda. You will have to manually enter `gameappdata' in the configuration.")


def fill_game_info(variables, game_type=None):
    if game_type is None:
        if variables["game_type"] not in game_infos:
            print("Unknown game type `%s', exiting." % variables["game_type"])
            return sys.exit(1)
        game_type = variables["game_type"]

    game_info = game_infos[game_type]

    if "neededvars" not in game_info:
        game_info["neededvars"] = []
    if "vfs" not in game_info:
        game_info["vfs"] = []

    for var in game_info["vars"]:
        if var not in variables:
            variables[var] = game_info["vars"][var]

    if "inherit" in game_info:
        inherited = fill_game_info(variables, game_info["inherit"])
        game_info["vfs"] = inherited["vfs"] + game_info["vfs"]

        for entry in inherited.get("neededvars", []):
            if entry not in game_info["neededvars"]:
                game_info["neededvars"].append(entry)

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
            print("Too many users in %s, use the `wineuser' configuration option to specify the user." % variables["wineprefix"])
            error = True
        elif len(users) == 0:
            print("No users under %s?" % variables["wineprefix"])
            error = True

        if error:
            print("The script may still succeed if using a portable ModOrganizer setup, but you will need to manually set `localappdata'.")
            return None

        variables["wineuser"] = users[0]

    if "winehome" not in variables:
        winehome = winpath(os.path.join(usersdir, variables["wineuser"]))
        if os.path.exists(winehome):
            variables["winehome"] = winehome


def find_localappdata(variables):
    # https://github.com/wine-mirror/wine/blob/f0ad5b5c546d17b281aef13fde996cda08d0c14e/dlls/shell32/shellpath.c
    searchpaths = [
        "Local AppData",
        "Local Settings/Application Data",
        "AppData/Local"
    ]

    if "winehome" not in variables:
        return

    for path in searchpaths:
        fullpath = winpath(os.path.join(variables["winehome"], path))
        if os.path.exists(fullpath):
            variables["localappdata"] = fullpath
            break


def find_mo_installroot(variables):
    if "mo_installroot" in variables:
        return variables["mo_installroot"]

    installroot = winpath(os.path.join(variables["wineprefix"], "drive_c", "Modding", "MO2"))
    if os.path.exists(installroot):
        variables["mo_installroot"] = installroot
        return installroot

    print("Can't find MO installation path in current wineprefix (%s)\n" % variables["wineprefix"])
    print("Either change WINEPREFIX or use the `mo_installroot' configuration option to specify a custom installation location.")
    return None


def find_mo_games(variables):
    if "mo_installroot" not in variables:
        return []

    # Portable installation, don't look further
    if os.path.exists(winpath(os.path.join(variables["mo_installroot"], "ModOrganizer.ini"))):
        return [variables["mo_installroot"]]

    if "winehome" in variables:
        moroot = winpath(os.path.join(variables["winehome"], "Local Settings", "Application Data", "ModOrganizer"))
        if os.path.exists(moroot):
            games = []
            for game in os.listdir(moroot):
                fullgamedir = os.path.join(moroot, game)
                if os.path.exists(winpath(os.path.join(fullgamedir, "ModOrganizer.ini"))):
                    games.append(fullgamedir)
            return games

    return []


def get_base_variables(variables):
    if "WINEPREFIX" in os.environ:
        variables["wineprefix"] = os.environ["WINEPREFIX"]
    else:
        variables["wineprefix"] = os.path.expanduser("~/.wine")

    for var in os.environ:
        if var.startswith("MO_"):
            varname = var[3:]
            if varname not in variables:
                variables[varname] = os.environ[var]

    if "mo_profile" not in variables:
        variables["mo_profile"] = "{mo_gameroot}/profiles/{profile}"
    if "mo_mods" not in variables:
        variables["mo_mods"] = "{mo_gameroot}/mods"
    if "mo_overwrite" not in variables:
        variables["mo_overwrite"] = "{mo_gameroot}/overwrite"


def generate_game_config(variables, gameinfo):
    used_variables = [
        "mo_gameroot",
        "game_type"
    ]

    for entry in gameinfo.get("neededvars", []):
        if entry not in used_variables:
            used_variables.append(entry)

    for entry in gameinfo["vfs"]:
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
        orig_variables = copy.deepcopy(variables)

    inipath = os.path.join(scriptdir, "config.ini")
    if not os.path.exists(inipath):
        return generate_config(variables, inipath)

    config = configparser.ConfigParser()
    config.read(inipath)

    get_base_variables(variables)

    if "default" in config:
        for var in config["default"]:
            if var not in variables:
                variables[var] = config["default"][var]

    base_variables = variables

    for var in config:
        if not var.startswith("game/"):
            continue

        variables = copy.deepcopy(base_variables)

        mogame = var[len("game/"):]
        mogame_config = config[var]

        for mvar in mogame_config:
            if mvar not in variables:
                variables[mvar] = mogame_config[mvar]

        game_info = fill_game_info(variables)
        game_info["vars"] = variables
        games[mogame] = game_info

    if regenerate_config:
        generate_config(orig_variables, inipath, config)


def generate_config(variables, inipath, config=None):
    get_base_variables(variables)

    get_wine_user(variables)
    find_localappdata(variables)
    find_mo_installroot(variables)
    games = find_mo_games(variables)

    if len(games) == 0:
        print("Unable to find any games")
        sys.exit(1)

    if config is None:
        config = configparser.ConfigParser()

        config["general"] = {
            "iodelay": True
        }

    for game_path in games:
        gamename = os.path.basename(game_path)
        variables["mo_gameroot"] = game_path
        get_game_from_moroot(variables)

        gameinfo = fill_game_info(variables)

        if gamename == "MO2":
            # portable installation
            gamename = gameinfo["shortname"]

        keyname = "game/" + gamename

        if keyname not in config:
            config[keyname] = generate_game_config(variables, gameinfo)

    with open(inipath, 'w') as inifile:
        config.write(inifile)

    print("Written auto-generated configuration to config.ini. Please check the file, then run this script again.")
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


vfs_log = {'dirs': [], 'links': [], 'backups': []}

def apply_game_vfs():
    global prettyprint_total, vfs_log

    for entry in game["vfs"]:
        plog("Linking %s" % entry["name"])
        if entry["path"] == "[mods]":
            prettyprint_total = vfs_total
            t = start_prettyprint()
            apply_vfs(vfs, entry["dest"], "", vfs_log)
            stop_prettyprint(t)
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

def parseargs():
    currentarg = None
    variables = {}
    for arg in sys.argv[1:]:
        if arg.startswith("--") and currentarg is None:
            currentarg = arg[2:]
            if currentarg.lower() in boolargs:
                variables[currentarg] = True
                currentarg = None
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
        game = games[game]

    if game is None:
        print("Unable to detect game")
        sys.exit(0)

    args = game["vars"]
    profile = None
    if "profile" in args:
        profile = args["profile"]
    if profile is None:
        profile = args.get("default_profile", "Default")

    args["profile"] = profile

    fill_variables(args)

    if not os.path.exists(winpath(args["mo_profile"])):
        print("Profile directory does not exist: %s" % args["mo_profile"])
        sys.exit(1)

    for entry in game["vfs"]:
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

    plog('Removing VFS layer')
    for entry in game["vfs"]:
        if entry["path"] == "[mods]":
            plog_indent += 1
            unvfs(entry["dest"])
            plog_indent -= 1

    if "unvfs" in args and args["unvfs"] is True:
        sys.exit(0)

    plog('Parsing MO mods configuration')
    modpaths = []
    for i in open(winpath(os.path.join(args["mo_profile"], 'modlist.txt'))).readlines():
        if i.startswith('+'):  # only enabled mods
            modpaths.append(i[1:].strip())

    modpaths = list(reversed(modpaths))

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

    apply_game_vfs()
    write_vfs_log()

    print("")
    plog('VFS layer created. Run "%s --game %s --profile %s --unvfs" to shut it down (run this before running Mod Organizer again)' % (
        sys.argv[0],
        gamename,
        profile
    ))
