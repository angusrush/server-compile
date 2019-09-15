#!/usr/bin/python3
#
# server-compile compiles a latex document on a remote server to avoid frequent
# compilation on a laptop.
#
# Copyright (C) 2018 Angus Rush
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import argparse as ap
import subprocess as sp
import sys
import gzip as gz

LATEXMK_COMMAND = "latexmk -pdf -interaction=nonstopmode -synctex=1 -verbose -f"
SERVER_TARGET_DIR = '/tmp'

# Sync forward loc_filepath to remote_filepath on server servername, minus
# hidden subfolders.  Basically syntactic sugar for the command:
#
#     rsync -a -h --exclude=".[!.]*" --info=progress2 loc_filepath
#     servername:remote_filepath

def sync_forward(loc_filepath, remote_filepath, servername):
    forward_sync = sp.run("rsync -a -h --exclude=\".[!.]*\" --info=progress2 " \
            + loc_filepath + " " + servername + ":" + remote_filepath, shell=True)
    
    assert forward_sync.returncode == 0, "Forward rsync finished with nonzero exit code."
    return forward_sync.returncode

# Sync back remote_filepath to loc_filepath, minus hidden subfolders.
# Basically syntactic sugar for the command:
#
#     rsync -a -h --exclude="(.[!.]*|*.tex)" --info=progress2
#     servername:remote_filepath loc_filepath

def sync_back(remote_filepath, loc_filepath, servername):
    rsync_back = sp.run("rsync -a -h --exclude=\"(.[!.]*|*.tex)\" --info=progress2 " \
            + servername + ":" + remote_filepath + " " + loc_filepath, shell=True)

    assert rsync_back.returncode == 0, "Rsync back finished with nonzero exit code."
    return rsync_back.returncode

# Synctex files break when you move them. This function fixes the synctex file
# after copying it to the local folder by replacing all instances of
# SERVER_TARGET_DIR with current_directory, then making sure all the paths are
# still valid by getting rid of things like /./ and //

def sanitize_synctex(gzfile, current_directory, target_directory):
    fin = gz.open(gzfile, "rt")
    
    newlines = []
    for line in fin:
        newlines.append(os.path.normpath(line.replace(target_directory, current_directory)))
    
    fout = gz.open(gzfile, "wt")
    for line in newlines:
        fout.write(line)
    
    fin.close()
    fout.close()

# We will need a lot of folder information. For example, if __init__() 
# is called with argument
#
#    "/home/angus/latex/notes-public/category_theory/notes.tex"
#
# then the following variable assignments should occur.
#
# self.folder         = "/home/angus/latex/notes-public/category_theory"
# self.filename       = "notes.tex"
# self.stem           = "notes"
# self.extension      = ".tex"
# self.bottom_folders = "/home/angus/latex/notes-public"
# self.top_folder     = "category_theory"

class Filepath_info:
    def __init__(self, path):
        self.folder, self.filename = os.path.split(path)
        self.stem, self.extension = os.path.splitext(self.filename)
        self.bottom_folders, self.top_folder = os.path.split(self.folder)

def main():
    # Parse command line arguments
    parser = ap.ArgumentParser(description="Compile file.tex on remote server")
    parser.add_argument(
            metavar='/path/to/file.tex',
            dest='filepath',
            type=str,
            help="Absolute path to file.tex to be compiled")
    
    parser.add_argument(
            '--server',
            metavar='server',
            dest='servername',
            type=str,
            help="Name of server, e.g. angus-server.duckdns.org")
    
    args = parser.parse_args()
    fp = Filepath_info(args.filepath)
    server = args.servername

    # Sync fp.folder forward to server:SERVER_TARGET_DIR
    print("Syncing " + fp.folder + " to " + server + "...")
    sync_forward(fp.folder, SERVER_TARGET_DIR, server)

    # Get ready to run command on server
    latexmk_command = LATEXMK_COMMAND                      \
                    + " "                                  \
                    + fp.filename
    
    ssh_command     = "ssh "                               \
                    + server                               \
                    + " \""                                \
                    + "cd "                                \
                    + os.path.join(SERVER_TARGET_DIR, fp.top_folder) \
                    + " && "                               \
                    + latexmk_command                      \
                    + "\""
    

    # run ssh_command
    print(" ")
    print("--------------------------------------")
    print("----- latexmk output begins here -----")
    print("--------------------------------------")
    print(" ")
    latexmk_run = sp.run(ssh_command, shell=True)
    print(" ")
    print("--------------------------------------")
    print("------ latexmk output ends here ------")
    print("--------------------------------------")
    print(" ")
    
    if latexmk_run.returncode != 0:
        print("Server-side latexmk run finished with nonzero exit code. \
                Not syncing back.")
        sys.exit(1)
    else:
        print("latexmk run successful! Syncing back...")

    sync_back(os.path.join(SERVER_TARGET_DIR, fp.top_folder), fp.bottom_folders, server)

    # Fix fp.stem.synctex.gz
    synctex_gz_file = fp.stem + ".synctex.gz"

    print("Fiddling with " + synctex_gz_file + " to make synctex work...")
    sanitize_synctex(synctex_gz_file, fp.bottom_folders, SERVER_TARGET_DIR)
    print("Done! Exiting :)")

if __name__ == "__main__":
    main()
