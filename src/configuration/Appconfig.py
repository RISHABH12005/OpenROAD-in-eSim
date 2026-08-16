# ================================================================================
#          FILE: Appconfig.py
#
#         USAGE: ---
#
#   DESCRIPTION: This define all configuration used in Application.
#
#       OPTIONS: ---
#  REQUIREMENTS: ---
#          BUGS: ---
#         NOTES: ---
#        AUTHOR: Fahim Khan, fahim.elex@gmail.com
#      MODIFIED: Rahul Paknikar, rahulp@iitb.ac.in 
#                Rishabh Jain, 2r10j5@gmai.com
#  ORGANIZATION: eSim Team at FOSSEE, IIT Bombay
#       CREATED: Tuesday 24 February 2015
#      REVISION: Monday 3 August 2026
# ================================================================================

from PyQt5 import QtCore, QtWidgets
import os
import json
from configparser import ConfigParser


class Appconfig(QtWidgets.QWidget):
    """
    All configuration goes here.
    May change in future for code optimization.

    This class also contains function for
    - Printing error.
    - Showing warnings.
    - Displaying information.
    """

    # Home directory
    if os.name == 'nt':
        user_home = os.path.join('library', 'config')
    else:
        user_home = os.path.expanduser('~')

    try:
        file = open(os.path.join(
            user_home, ".esim/workspace.txt"), 'r'
        )
        workspace_check, home = file.readline().split(' ', 1)
        file.close()
    except IOError:
        home = os.path.join(os.path.expanduser("~"), "eSim-Workspace")
        workspace_check = 0

    default_workspace = {"workspace": home}
    # Current Project detail
    current_project = {"ProjectName": None}
    # Current Subcircuit detail
    current_subcircuit = {"SubcircuitName": None}
    # Workspace detail
    workspace_text = "eSim stores your project in a folder called "
    workspace_text += "eSim-Workspace. You can choose a different "
    workspace_text += "workspace folder to use for this session."

    procThread_list = []
    proc_dict = {}  # hold pids of all external windows of the current project
    dock_dict = {}  # holds all dockwidgets
    dictPath = {"path": os.path.join(
        default_workspace["workspace"], ".projectExplorer.txt")
    }

    noteArea = {"Note": []}

    parser_esim = ConfigParser()
    parser_esim.read(
        os.path.join(user_home, '.esim', 'config.ini')
    )

    # Try catch added, since eSim cannot be accessed under parser for Win10
    try:
        modelica_map_json = parser_esim.get('eSim', 'MODELICA_MAP_JSON')
    except BaseException as e:
        print("Cannot access Modelica map file --- .esim folder")
        print(str(e))

    try:
        project_explorer = json.load(open(dictPath["path"]))
    except BaseException:
        project_explorer = {}
    process_obj = []

    def __init__(self):
        super(Appconfig, self).__init__()

        # Application Details
        self._APPLICATION = 'eSim'
        self._VERSION = '2.5'
        self._AUTHOR = 'Fahim'
        self._REVISION = 'Rahul, Sumanto'

        # Application geometry setting
        self._app_xpos = 100
        self._app_ypos = 100
        self._app_width = 600
        self._app_heigth = 400

    def get_last_project(self):
        """Return the last opened project path (may no longer exist)."""
        try:
            settings = QtCore.QSettings("eSim", "eSim")
            path = settings.value("last_project", "")
            if not path:
                return None
            return str(path)
        except BaseException:
            return None

    def save_current_project(self):
        """Persist the current project path so it survives a restart."""
        try:
            settings = QtCore.QSettings("eSim", "eSim")
            path = self.current_project.get("ProjectName")
            settings.setValue("last_project", path or "")
            settings.sync()
        except BaseException:
            pass

    def restore_current_project(self):
        """Restore the last project if it still exists on disk."""
        path = self.get_last_project()
        if path and os.path.isdir(path):
            self.current_project["ProjectName"] = path
            return path
        return None

    def print_info(self, info):
        self.noteArea['Note'].append('[INFO]: ' + info)

    def print_warning(self, warning):
        self.noteArea['Note'].append('[WARNING]: ' + warning)

    def print_error(self, error):
        self.noteArea['Note'].append('[ERROR]: ' + error)
