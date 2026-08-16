# =====================================================================================
#          FILE: Kicad.py
#
#         USAGE: ---
#
#   DESCRIPTION: It calls kicad schematic
#
#       OPTIONS: ---
#  REQUIREMENTS: ---
#          BUGS: ---
#         NOTES: ---
#        AUTHOR: Fahim Khan, fahim.elex@gmail.com
#      MODIFIED: Rahul Paknikar
#                Partha Singh Roy
#                Rishabh Jain, 2r10j5@gmail.com
#  ORGANIZATION: eSim Team at FOSSEE, IIT Bombay
#       CREATED: Tuesday 17 February 2015
#      REVISION: Monday 3 August 2026
# =====================================================================================

import os
import glob
import shutil
import sys
from . import Validation
from configuration.Appconfig import Appconfig
from . import Worker
from PyQt5 import QtWidgets


class Kicad:
    """
    This class called the Kicad Schematic, KicadtoNgspice Converter, Layout
    editor and Footprint Editor
    Initialise validation, appconfig and dockarea

    @params
        :dockarea   => passed from DockArea in frontEnd folder, consists
                        of all functions for dockarea

    @return
    """

    def __init__(self, dockarea):
        self.obj_validation = Validation.Validation()
        self.obj_appconfig = Appconfig()
        self.obj_dockarea = dockarea
        self.obj_workThread = Worker.WorkerThread(None)
        self.obj_workThread.commandFailed.connect(self._command_failed)

    def _command_failed(self, command):
        """Show a friendly error when an external command cannot be started."""
        QtWidgets.QMessageBox.warning(
            None, "Unable to Launch Application",
            "The following command could not be started:\n\n"
            + command +
            "\n\nThe required application may not be installed."
        )

    def check_open_schematic(self):
        """
        This function checks if any of the project's schematic is open or not

        @params

        @return
            True        => If the project's schematic is not open
            False       => If the project's schematic is open
        """
        if self.obj_workThread:
            procList = self.obj_workThread.get_proc_threads()[:]
            if procList:
                for proc in procList:
                    if proc.poll() is None:
                        return True
                    else:
                        self.obj_workThread.get_proc_threads().remove(proc)

        return False

    def _find_schematic_editor(self):
        """
        Locate the KiCad schematic editor executable installed on this
        system. The binary name differs across KiCad versions and install
        layouts, so nothing is hardcoded as ``eeschema``.

        Candidates are searched in priority order:
          * ``eeschema`` -- the dedicated schematic editor shipped with
            KiCad (4.x through 8.x) on PATH.
          * ``kicad`` -- the KiCad 6+ project manager, which can also open
            a schematic file directly.
          * Well-known install locations on Windows, macOS and Linux.

        @return
            The absolute path of a runnable executable, or ``None`` if no
            KiCad schematic editor could be found.
        """
        candidates = []

        # 1. Names on PATH (covers package installs on Linux/macOS and
        #    any correctly configured Windows PATH).
        for name in ("eeschema", "kicad"):
            found = shutil.which(name)
            if found:
                candidates.append(found)

        # 2. Windows default install layout:
        #    C:\Program Files\KiCad\<version>\bin\eeschema.exe
        if os.name == 'nt':
            for base in ("C:\\Program Files\\KiCad",
                         "C:\\Program Files (x86)\\KiCad"):
                for pattern in (os.path.join(base, "*", "bin", "eeschema.exe"),
                                os.path.join(base, "*", "bin", "kicad.exe")):
                    candidates.extend(glob.glob(pattern))

        # 3. macOS application bundle.
        if sys.platform == 'darwin':
            bundle = "/Applications/KiCad/KiCad.app/Contents/MacOS"
            candidates.extend([
                os.path.join(bundle, "eeschema"),
                os.path.join(bundle, "kicad"),
            ])

        # 4. Common Linux locations not on PATH.
        for path in ("/usr/bin/eeschema", "/usr/bin/kicad",
                     "/usr/local/bin/eeschema", "/usr/local/bin/kicad"):
            candidates.append(path)

        # Return the first candidate that actually exists and is executable.
        for candidate in candidates:
            if candidate and os.path.isfile(candidate) \
                    and os.access(candidate, os.X_OK):
                return candidate

        return None

    def _schematic_file(self, proj_dir):
        """
        Resolve the schematic file for a project directory.

        KiCad v6+ uses ``.kicad_sch``; older KiCad uses ``.sch``. The root
        sheet is expected to share the project folder name.

        @params
            :proj_dir   => absolute path of the project directory

        @return
            The absolute path of the existing schematic file, or ``None``
            if no schematic file exists for the project.
        """
        proj_name = os.path.basename(proj_dir)
        base = os.path.join(proj_dir, proj_name)
        for ext in (".kicad_sch", ".sch"):
            path = base + ext
            if os.path.isfile(path):
                return path
        return None

    def openSchematic(self):
        """
        This function create command to open Kicad schematic after
        appropriate validation checks

        @params

        @return
        """
        print("Function : Open Kicad Schematic")
        self.projDir = self.obj_appconfig.current_project["ProjectName"]
        try:
            self.obj_appconfig.print_info(
                'Kicad Schematic is called for project ' + self.projDir)
        except BaseException:
            pass

        # Validating if current project is available or not
        if not self.obj_validation.validateKicad(self.projDir):
            QtWidgets.QMessageBox.warning(
                None, "No Project Selected",
                "Please select the project first. You can either create "
                "a new project or open an existing project."
            )
            self.obj_appconfig.print_warning(
                'Please select the project first. You can either ' +
                'create new project or open an existing project')
            return

        self.projDir = os.path.abspath(self.projDir)

        # Verify the schematic file exists before doing anything else.
        sch_file = self._schematic_file(self.projDir)
        if not sch_file:
            QtWidgets.QMessageBox.warning(
                None, "Schematic Not Found",
                "No schematic file was found for the project\n\n"
                + self.projDir +
                "\n\nExpected a file named\n"
                + os.path.basename(self.projDir) + ".kicad_sch\nor\n"
                + os.path.basename(self.projDir) + ".sch"
            )
            self.obj_appconfig.print_error(
                'Schematic file not found for project ' + self.projDir)
            return

        # Detect the installed KiCad schematic editor. Do not hardcode
        # ``eeschema``: the correct binary depends on the installed KiCad
        # version and platform.
        editor = self._find_schematic_editor()
        if not editor:
            QtWidgets.QMessageBox.warning(
                None, "KiCad Not Found",
                "The KiCad schematic editor could not be found on this "
                "system.\n\n"
                "Please install KiCad and try again."
            )
            self.obj_appconfig.print_error(
                'KiCad schematic editor not found for project ' +
                self.projDir)
            return

        self.cmd = '"' + editor + '" "' + sch_file + '"'
        self.obj_workThread.args = self.cmd
        self.obj_workThread.start()

    '''
    # Commenting as it is no longer needed as PCB and Layout will open from
    # eeschema
    def openFootprint(self):
        """
        This function create command to open Footprint editor
        """
        print "Kicad Foot print Editor called"
        self.projDir = self.obj_appconfig.current_project["ProjectName"]
        try:
            self.obj_appconfig.print_info('Kicad Footprint Editor is called'
            + 'for project : ' + self.projDir)
        except:
            pass
        #Validating if current project is available or not

        if self.obj_validation.validateKicad(self.projDir):
            #print "calling Kicad FootPrint Editor ",self.projDir
            self.projName = os.path.basename(self.projDir)
            self.project = os.path.join(self.projDir,self.projName)

            #Creating a command to run
            self.cmd = "cvpcb "+self.project+".net "
            self.obj_workThread = Worker.WorkerThread(self.cmd)
            self.obj_workThread.start()

        else:
            self.msg = QtWidgets.QErrorMessage()
            self.msg.setModal(True)
            self.msg.setWindowTitle("Error Message")
            self.msg.showMessage('Please select the project first. You can'
            + 'either create new project or open an existing project')
            self.msg.exec_()
            self.obj_appconfig.print_warning('Please select the project'
            + 'first. You can either create new project or open an existing'
            + 'project')

    def openLayout(self):
        """
        This function create command to open Layout editor
        """
        print "Kicad Layout is called"
        self.projDir = self.obj_appconfig.current_project["ProjectName"]
        try:
            self.obj_appconfig.print_info('PCB Layout is called for project : '
            + self.projDir)
        except:
            pass
        #Validating if current project is available or not
        if self.obj_validation.validateKicad(self.projDir):
            print "calling Kicad schematic ",self.projDir
            self.projName = os.path.basename(self.projDir)
            self.project = os.path.join(self.projDir,self.projName)

            #Creating a command to run
            self.cmd = "pcbnew "+self.project+".net "
            self.obj_workThread = Worker.WorkerThread(self.cmd)
            self.obj_workThread.start()

        else:
            self.msg = QtWidgets.QErrorMessage()
            self.msg.setModal(True)
            self.msg.setWindowTitle("Error Message")
            self.msg.showMessage('Please select the project first. You can'
            + 'either create new project or open an existing project')
            self.msg.exec_()
            self.obj_appconfig.print_warning('Please select the project'
            + 'first. You can either create new project or open an existing'
            + 'project')
    '''

    def openKicadToNgspice(self):
        """
        This function create command to validate and then call
        KicadToNgSPice converter from DockArea file

        @params

        @return
        """
        print("Function: Open Kicad to Ngspice Converter")

        self.projDir = self.obj_appconfig.current_project["ProjectName"]
        try:
            self.obj_appconfig.print_info(
                'Kicad to Ngspice Conversion is called')
            self.obj_appconfig.print_info('Current Project is ' + self.projDir)
        except BaseException:
            pass
        # Validating if current project is available or not
        if self.obj_validation.validateKicad(self.projDir):
            # Checking if project has .cir file or not
            if self.obj_validation.validateCir(self.projDir):
                self.projName = os.path.basename(self.projDir)
                self.project = os.path.join(self.projDir, self.projName)

                # Creating a command to run
                """
                self.cmd = ("python3  ../kicadtoNgspice/KicadtoNgspice.py "
                + "self.project+".cir ")
                self.obj_workThread = Worker.WorkerThread(self.cmd)
                self.obj_workThread.start()
                """
                var = self.project + ".cir"
                self.obj_dockarea.kicadToNgspiceEditor(var)

            else:
                self.msg = QtWidgets.QErrorMessage()
                self.msg.setModal(True)
                self.msg.setWindowTitle("Error Message")
                self.msg.showMessage(
                    'The project does not contain any Kicad netlist file ' +
                    'for conversion.')
                self.obj_appconfig.print_error(
                    'The project does not contain any Kicad netlist file ' +
                    'for conversion.')
                self.msg.exec_()

        else:
            self.msg = QtWidgets.QErrorMessage()
            self.msg.setModal(True)
            self.msg.setWindowTitle("Error Message")
            self.msg.showMessage(
                'Please select the project first. You can either ' +
                'create new project or open an existing project')
            self.msg.exec_()
            self.obj_appconfig.print_warning(
                'Please select the project first. You can either ' +
                'create new project or open an existing project')
