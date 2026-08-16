#!/usr/bin/env python3

# ============================================================
#      FILE:     OpenROAD.py
#
#   DESCRIPTION: This file is used to connect OpenROAD GUI
#
#        AUTHOR: Rishabh Jain, 2r10j5@gmail.com
#    MAINTAINED: Sumanto Kar, sumantokar@iitb.ac.in
#  ORGANIZATION: eSim Team at FOSSEE, IIT Bombay
#       CREATED: Monday 2 March 2026
#      REVISION: Monday 3 Aug 2026
# ============================================================

import json
import os
import shutil
import subprocess
import sys
import traceback
from datetime import datetime

from PyQt5 import QtCore, QtWidgets, QtGui

from configuration.Appconfig import Appconfig
from maker.OpenROAD import OpenROADFlow


class OpenROADWorker(QtCore.QObject):

    progressChanged = QtCore.pyqtSignal(int)
    statusChanged = QtCore.pyqtSignal(str)
    logMessage = QtCore.pyqtSignal(str)
    flowCompleted = QtCore.pyqtSignal(dict)
    flowFailed = QtCore.pyqtSignal(str)

    def __init__(self, design_name, verilog_file, platform,
                 output_dir, sdc_file=None, cir_file=None):
        super().__init__()
        self.design_name = design_name
        self.verilog_file = verilog_file
        self.platform = platform
        self.output_dir = output_dir
        self.sdc_file = sdc_file
        self.cir_file = cir_file
        self._cancel = False
        self._process = None

    def cancel(self):
        self._cancel = True
        if self._process is not None:
            try:
                self._process.terminate()
            except Exception:
                pass

    def _ts(self, level, msg):
        return f"[{datetime.now().strftime('%H:%M:%S')}] {level}: {msg}"

    def _emit_log(self, level, msg):
        self.logMessage.emit(self._ts(level, msg))

    @QtCore.pyqtSlot()
    def run(self):
        try:
            design_name = self.design_name
            verilog_file = self.verilog_file
            output_dir = self.output_dir
            platform = self.platform
            sdc_file = self.sdc_file
            cir_file = self.cir_file

            if cir_file and cir_file.endswith(".cir"):
                self._emit_log("INFO", "Starting Netlist to RTL conversion")
                self.statusChanged.emit("Converting netlist to RTL...")
                self.progressChanged.emit(5)

                netlist_script = os.path.join(
                    os.path.dirname(__file__), "..", "maker", "netlist2rtl.py"
                )
                netlist_script = os.path.normpath(netlist_script)
                cmd = [sys.executable, netlist_script, cir_file]
                self._process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
                )
                for line in self._process.stdout:
                    if self._cancel:
                        self._process.terminate()
                        self.flowFailed.emit("Flow cancelled by user")
                        return
                    stripped = line.strip()
                    if stripped:
                        self._emit_log("INFO", stripped)
                self._process.wait()

                if self._cancel:
                    self.flowFailed.emit("Flow cancelled by user")
                    return
                if self._process.returncode != 0:
                    self.flowFailed.emit("Netlist to RTL conversion failed")
                    return

                design_name = os.path.basename(cir_file).replace(".cir", "")
                verilog_file = os.path.join(output_dir, design_name + ".v")

                if not os.path.exists(verilog_file):
                    self.flowFailed.emit(
                        f"Generated Verilog not found: {verilog_file}"
                    )
                    return

                self._emit_log("SUCCESS", "RTL Generated")
                self.statusChanged.emit("RTL generated")
                self.progressChanged.emit(15)

            if self._cancel:
                self.flowFailed.emit("Flow cancelled by user")
                return

            flow = OpenROADFlow(design_name, verilog_file, platform)
            flow.project_dir = output_dir

            self._emit_log("INFO", "Checking ORFS installation")
            self.statusChanged.emit("Checking ORFS...")
            self.progressChanged.emit(20)
            flow.check_orfs()

            if self._cancel:
                self.flowFailed.emit("Flow cancelled by user")
                return

            self._emit_log("INFO", "Creating design structure")
            self.statusChanged.emit("Creating design structure...")
            self.progressChanged.emit(30)
            flow.create_structure()

            if self._cancel:
                self.flowFailed.emit("Flow cancelled by user")
                return

            self._emit_log("INFO", "Copying Verilog file")
            self.statusChanged.emit("Copying Verilog...")
            self.progressChanged.emit(40)
            flow.copy_verilog()

            if self._cancel:
                self.flowFailed.emit("Flow cancelled by user")
                return

            if sdc_file and os.path.isfile(sdc_file):
                self._emit_log("INFO", "Copying SDC constraints")
                sdc_dest = os.path.join(
                    flow.design_dir, "constraint.sdc"
                )
                import shutil
                shutil.copy(sdc_file, sdc_dest)
                self._emit_log("SUCCESS", f"SDC copied: {sdc_dest}")
            else:
                self._emit_log("INFO", "Generating SDC constraints")
                self.statusChanged.emit("Generating constraints...")
                self.progressChanged.emit(50)
                flow.generate_sdc()

            if self._cancel:
                self.flowFailed.emit("Flow cancelled by user")
                return

            self._emit_log("INFO", "Generating config.mk")
            self.statusChanged.emit("Generating configuration...")
            self.progressChanged.emit(60)
            flow.generate_config()

            if self._cancel:
                self.flowFailed.emit("Flow cancelled by user")
                return

            self._emit_log("INFO", "Starting OpenROAD flow")
            self.statusChanged.emit("Running Synthesis...")
            self.progressChanged.emit(65)

            cmd = [
                "make",
                f"DESIGN_CONFIG=./designs/{platform}/{design_name}/config.mk",
            ]
            self._process = subprocess.Popen(
                cmd,
                cwd=flow.flow_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            stage_map = {
                "synthesis": "Running Synthesis...",
                "floorplan": "Floorplanning...",
                "placement": "Placement...",
                "cts": "CTS...",
                "routing": "Routing...",
                "gds": "Generating GDS...",
            }
            line_count = 0

            for line in self._process.stdout:
                if self._cancel:
                    self._process.terminate()
                    self.flowFailed.emit("Flow cancelled by user")
                    return
                stripped = line.strip()
                if stripped:
                    self._emit_log("INFO", stripped)
                line_lower = line.lower()
                for key, stage in stage_map.items():
                    if key in line_lower:
                        self.statusChanged.emit(stage)
                if line_count % 50 == 0:
                    p = min(65 + int((line_count / 5000.0) * 25), 89)
                    self.progressChanged.emit(p)
                line_count += 1

            self._process.wait()

            if self._cancel:
                self.flowFailed.emit("Flow cancelled by user")
                return
            if self._process.returncode != 0:
                self.flowFailed.emit("OpenROAD flow failed")
                return

            self._process = None

            self._emit_log("INFO", "Collecting outputs")
            self.statusChanged.emit("Collecting outputs...")
            self.progressChanged.emit(92)
            flow.collect_outputs()

            outputs = {
                "gds": os.path.join(output_dir, design_name + ".gds"),
                "def": os.path.join(output_dir, design_name + ".def"),
                "v": os.path.join(output_dir, design_name + ".v"),
                "sdc": os.path.join(output_dir, design_name + ".sdc"),
                "spef": os.path.join(output_dir, design_name + ".spef"),
                "logs": os.path.join(output_dir, "logs"),
                "reports": os.path.join(output_dir, "reports"),
                "project_dir": output_dir,
            }

            self._emit_log("SUCCESS", "GDS Generated")
            self.statusChanged.emit("Completed")
            self.progressChanged.emit(100)
            self.flowCompleted.emit(outputs)

        except FileNotFoundError as e:
            self._emit_log("ERROR", str(e))
            self.flowFailed.emit(str(e))
        except RuntimeError as e:
            self._emit_log("ERROR", str(e))
            self.flowFailed.emit(str(e))
        except Exception as e:
            self._emit_log("ERROR", f"{e}\n{traceback.format_exc()}")
            self.flowFailed.emit(str(e))

    def __del__(self):
        self._cancel = True
        if self._process is not None:
            try:
                self._process.terminate()
            except Exception:
                pass


class OpenROADWidget(QtWidgets.QWidget):

    WORKFLOW_CIR = 0
    WORKFLOW_RTL = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.obj_appconfig = Appconfig()
        self.worker = None
        self.thread = None
        self.flow_running = False
        self._displayed_project = None
        self._init_ui()
        self._update_project_info()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)

        project_group = QtWidgets.QGroupBox("Current Project")
        project_layout = QtWidgets.QFormLayout()
        project_layout.setSpacing(3)
        self.project_name_label = QtWidgets.QLabel("No project selected")
        self.project_name_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.project_folder_label = QtWidgets.QLabel("")
        self.project_folder_label.setWordWrap(True)
        project_layout.addRow("Name:", self.project_name_label)
        project_layout.addRow("Folder:", self.project_folder_label)
        project_group.setLayout(project_layout)
        layout.addWidget(project_group)

        pdk_group = QtWidgets.QGroupBox("Technology Platform (PDK)")
        pdk_layout = QtWidgets.QVBoxLayout()
        pdk_layout.setSpacing(3)
        self.pdk_combo = QtWidgets.QComboBox()
        self._populate_pdk()
        self.pdk_combo.currentIndexChanged.connect(self._save_pdk_preference)
        pdk_layout.addWidget(self.pdk_combo)
        pdk_group.setLayout(pdk_layout)
        layout.addWidget(pdk_group)

        workflow_group = QtWidgets.QGroupBox("Input Workflow")
        workflow_layout = QtWidgets.QVBoxLayout()
        workflow_layout.setSpacing(3)

        workflow_radio_layout = QtWidgets.QHBoxLayout()
        self.workflow_cir_radio = QtWidgets.QRadioButton("eSim Schematic (.cir)")
        self.workflow_rtl_radio = QtWidgets.QRadioButton("RTL Design (.v / .vhdl)")
        self.workflow_cir_radio.setChecked(True)
        self.workflow_rtl_radio.toggled.connect(self._on_workflow_changed)
        workflow_radio_layout.addWidget(self.workflow_cir_radio)
        workflow_radio_layout.addWidget(self.workflow_rtl_radio)
        workflow_layout.addLayout(workflow_radio_layout)

        self.input_file_layout = QtWidgets.QFormLayout()
        self.input_file_layout.setSpacing(3)

        self.input_file_edit = QtWidgets.QLineEdit()
        self.input_file_edit.setReadOnly(True)
        self.input_file_edit.setPlaceholderText("Browse for .cir file...")
        self.input_browse_btn = QtWidgets.QPushButton("Browse")
        self.input_browse_btn.clicked.connect(self._browse_input)
        input_row = QtWidgets.QHBoxLayout()
        input_row.addWidget(self.input_file_edit)
        input_row.addWidget(self.input_browse_btn)
        self.input_file_layout.addRow("Main File:", input_row)

        self.file_type_label = QtWidgets.QLabel("")
        self.file_type_label.setStyleSheet(
            "color: #2e7d32; font-weight: bold; font-size: 11px;"
        )
        self.input_file_layout.addRow("", self.file_type_label)

        self.sdc_file_edit = QtWidgets.QLineEdit()
        self.sdc_file_edit.setReadOnly(True)
        self.sdc_file_edit.setPlaceholderText("Optional: browse for .sdc file...")
        self.sdc_browse_btn = QtWidgets.QPushButton("Browse")
        self.sdc_browse_btn.clicked.connect(self._browse_sdc)
        sdc_row = QtWidgets.QHBoxLayout()
        sdc_row.addWidget(self.sdc_file_edit)
        sdc_row.addWidget(self.sdc_browse_btn)
        self.input_file_layout.addRow("SDC File:", sdc_row)
        self.sdc_file_edit.setVisible(False)
        self.sdc_browse_btn.setVisible(False)
        self.input_file_layout_label = None

        workflow_layout.addLayout(self.input_file_layout)
        workflow_group.setLayout(workflow_layout)
        layout.addWidget(workflow_group)

        output_group = QtWidgets.QGroupBox("Output Folder")
        output_layout = QtWidgets.QHBoxLayout()
        output_layout.setSpacing(3)
        self.output_dir_edit = QtWidgets.QLineEdit()
        self.output_dir_edit.setReadOnly(True)
        self.output_dir_edit.setPlaceholderText("Default: current project folder")
        self.output_browse_btn = QtWidgets.QPushButton("Browse")
        self.output_browse_btn.clicked.connect(self._browse_output)
        output_layout.addWidget(self.output_dir_edit)
        output_layout.addWidget(self.output_browse_btn)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        flow_group = QtWidgets.QGroupBox("Flow Progress")
        flow_layout = QtWidgets.QVBoxLayout()
        flow_layout.setSpacing(3)
        self.stage_label = QtWidgets.QLabel("Ready")
        self.stage_label.setStyleSheet("font-weight: bold; color: #555;")
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        flow_layout.addWidget(self.stage_label)
        flow_layout.addWidget(self.progress_bar)
        flow_group.setLayout(flow_layout)
        layout.addWidget(flow_group)

        console_group = QtWidgets.QGroupBox("Console")
        console_layout = QtWidgets.QVBoxLayout()
        console_layout.setContentsMargins(2, 2, 2, 2)
        self.console = QtWidgets.QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QtGui.QFont("Courier New", 9))
        self.console.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #d4d4d4;"
            " border: 1px solid #555; }"
        )
        console_layout.addWidget(self.console)
        console_group.setLayout(console_layout)
        layout.addWidget(console_group, 1)

        tools_layout = QtWidgets.QHBoxLayout()
        tools_layout.setSpacing(5)

        self.run_btn = QtWidgets.QPushButton(" Run Flow")
        self.run_btn.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay)
        )
        self.run_btn.setMinimumHeight(30)
        self.run_btn.clicked.connect(self._run_flow)
        self.run_btn.setStyleSheet(
            "QPushButton { background-color: #2e7d32; color: white;"
            " font-weight: bold; border-radius: 4px; padding: 5px 14px; }"
            " QPushButton:hover { background-color: #1b5e20; }"
            " QPushButton:disabled { background-color: #ccc; color: #888; }"
        )

        self.cancel_btn = QtWidgets.QPushButton(" Cancel")
        self.cancel_btn.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.SP_MediaStop)
        )
        self.cancel_btn.setMinimumHeight(30)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_flow)
        self.cancel_btn.setStyleSheet(
            "QPushButton { background-color: #c62828; color: white;"
            " font-weight: bold; border-radius: 4px; padding: 5px 14px; }"
            " QPushButton:hover { background-color: #b71c1c; }"
            " QPushButton:disabled { background-color: #ccc; color: #888; }"
        )

        self.open_gui_btn = QtWidgets.QPushButton(" Open OpenROAD")
        self.open_gui_btn.setMinimumHeight(30)
        self.open_gui_btn.setEnabled(True)
        self.open_gui_btn.clicked.connect(self._open_gui)
        self.open_gui_btn.setStyleSheet(
            "QPushButton { background-color: #1565c0; color: white;"
            " border-radius: 4px; padding: 5px 14px; }"
            " QPushButton:hover { background-color: #0d47a1; }"
            " QPushButton:disabled { background-color: #ccc; color: #888; }"
        )

        self.open_klayout_btn = QtWidgets.QPushButton(" KLayout")
        self.open_klayout_btn.setMinimumHeight(30)
        self.open_klayout_btn.setEnabled(True)
        self.open_klayout_btn.clicked.connect(self._open_klayout)
        self.open_klayout_btn.setStyleSheet(
            "QPushButton { background-color: #6a1b9a; color: white;"
            " border-radius: 4px; padding: 5px 14px; }"
            " QPushButton:hover { background-color: #4a148c; }"
            " QPushButton:disabled { background-color: #ccc; color: #888; }"
        )

        self.clear_btn = QtWidgets.QPushButton(" Clear Console")
        self.clear_btn.setMinimumHeight(30)
        self.clear_btn.clicked.connect(self._clear_runtime)
        self.clear_btn.setStyleSheet(
            "QPushButton { background-color: #546e7a; color: white;"
            " border-radius: 4px; padding: 5px 14px; }"
            " QPushButton:hover { background-color: #37474f; }"
        )

        tools_layout.addWidget(self.run_btn)
        tools_layout.addWidget(self.cancel_btn)
        tools_layout.addWidget(self.open_gui_btn)
        tools_layout.addWidget(self.open_klayout_btn)
        tools_layout.addStretch()
        tools_layout.addWidget(self.clear_btn)
        layout.addLayout(tools_layout)

        self.setLayout(layout)

    def _on_workflow_changed(self):
        rtl_mode = self.workflow_rtl_radio.isChecked()
        self.sdc_file_edit.setVisible(rtl_mode)
        self.sdc_browse_btn.setVisible(rtl_mode)
        if rtl_mode:
            self.input_file_edit.setPlaceholderText(
                "Browse for .v or .vhdl file..."
            )
        else:
            self.input_file_edit.setPlaceholderText(
                "Browse for .cir file..."
            )
        self.input_file_edit.clear()
        self.file_type_label.setText("")

    def _populate_pdk(self):
        self.pdk_combo.blockSignals(True)
        self.pdk_combo.clear()
        platforms = OpenROADFlow.detect_platforms()
        if not platforms:
            self.pdk_combo.addItem(OpenROADFlow.default_platform())
            self.pdk_combo.setEnabled(False)
            self.pdk_combo.blockSignals(False)
            return
        self.pdk_combo.setEnabled(True)
        default = OpenROADFlow.default_platform()
        for p in platforms:
            display = p + " (Default)" if p == default else p
            self.pdk_combo.addItem(display, p)
        settings = QtCore.QSettings("eSim", "OpenROAD")
        saved = settings.value("pdk", "")
        idx = -1
        if saved:
            for i in range(self.pdk_combo.count()):
                if self.pdk_combo.itemData(i) == saved or self.pdk_combo.itemText(i) == saved:
                    idx = i
                    break
        if idx >= 0:
            self.pdk_combo.setCurrentIndex(idx)
        elif default in platforms:
            for i in range(self.pdk_combo.count()):
                if self.pdk_combo.itemData(i) == default:
                    self.pdk_combo.setCurrentIndex(i)
                    break
        self.pdk_combo.blockSignals(False)

    def _save_pdk_preference(self):
        if self.pdk_combo.count() == 0:
            return
        data = self.pdk_combo.itemData(self.pdk_combo.currentIndex())
        pdk = data if data else self.pdk_combo.currentText()
        settings = QtCore.QSettings("eSim", "OpenROAD")
        settings.setValue("pdk", pdk)
        settings.sync()

    def set_project(self, proj_dir):
        """Switch the widget to a different project directory."""
        proj_dir = os.path.abspath(proj_dir)
        if not os.path.isdir(proj_dir):
            return
        old = self._displayed_project
        if old and os.path.normpath(old) == os.path.normpath(proj_dir):
            return
        self.obj_appconfig.current_project["ProjectName"] = proj_dir
        self._displayed_project = proj_dir
        cur_out = self.output_dir_edit.text().strip()
        if (not cur_out
                or (old and os.path.normpath(cur_out) == os.path.normpath(old))):
            self.output_dir_edit.setText(proj_dir)
        self._update_project_info()
        self.input_file_edit.clear()
        self.sdc_file_edit.clear()
        self.file_type_label.setText("")
        self.console.clear()
        self.progress_bar.setValue(0)
        self.stage_label.setText("Ready")
        self.obj_appconfig.save_current_project()

    def _update_project_info(self):
        proj = self.obj_appconfig.current_project
        proj_dir = proj.get("ProjectName")
        if proj_dir:
            self._displayed_project = proj_dir
            self.project_name_label.setText(os.path.basename(proj_dir))
            self.project_folder_label.setText(proj_dir)
            if not self.output_dir_edit.text():
                self.output_dir_edit.setText(proj_dir)
            self._update_explorer_for_dir(proj_dir)
        else:
            self.project_name_label.setText("No project selected")
            self.project_folder_label.setText("")

    def _clear_runtime(self):
        """
        Clear the console and reset the run-time widgets (progress bar,
        stage/status label and cancel button) while leaving the project
        information, PDK, input/output and workflow settings untouched.
        """
        self.console.clear()
        self.progress_bar.setValue(0)
        self.stage_label.setText("Ready")
        if hasattr(self, 'cancel_btn'):
            self.cancel_btn.setEnabled(False)

    def _browse_input(self):
        proj = self.obj_appconfig.current_project
        proj_dir = proj.get("ProjectName")
        if not proj_dir:
            proj_dir = os.path.expanduser("~")
        rtl_mode = self.workflow_rtl_radio.isChecked()
        if rtl_mode:
            filter_str = "RTL Files (*.v *.vhdl);;Verilog (*.v);;VHDL (*.vhdl)"
        else:
            filter_str = "Ngspice Netlist (*.cir)"
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Input File", proj_dir, filter_str,
        )
        if not file_path:
            return
        self.input_file_edit.setText(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".cir":
            self.file_type_label.setText("eSim Schematic")
            self.file_type_label.setStyleSheet(
                "color: #2e7d32; font-weight: bold; font-size: 11px;"
            )
        elif ext == ".v":
            self.file_type_label.setText("Verilog RTL")
            self.file_type_label.setStyleSheet(
                "color: #1565c0; font-weight: bold; font-size: 11px;"
            )
        elif ext == ".vhdl":
            self.file_type_label.setText("VHDL RTL")
            self.file_type_label.setStyleSheet(
                "color: #1565c0; font-weight: bold; font-size: 11px;"
            )
        else:
            self.file_type_label.setText("")
        file_dir = os.path.dirname(file_path)
        if file_dir != proj_dir:
            self.obj_appconfig.current_project['ProjectName'] = file_dir
            self._update_project_info()
            self._update_explorer_for_dir(file_dir)
            self.obj_appconfig.save_current_project()

    def _browse_sdc(self):
        proj = self.obj_appconfig.current_project
        proj_dir = proj.get("ProjectName")
        if not proj_dir:
            return
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select SDC File", proj_dir, "SDC Files (*.sdc)",
        )
        if file_path:
            self.sdc_file_edit.setText(file_path)

    def _browse_output(self):
        proj = self.obj_appconfig.current_project
        proj_dir = proj.get("ProjectName")
        start_dir = proj_dir if proj_dir else os.path.expanduser("~")
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Output Folder", start_dir
        )
        if dir_path:
            self.output_dir_edit.setText(dir_path)
            self._update_explorer_for_dir(dir_path)

    def _prune_project_explorer(self):
        pe = self.obj_appconfig.project_explorer
        if not pe:
            return
        keys = sorted(pe.keys(), key=len)
        to_del = []
        for i, k1 in enumerate(keys):
            for k2 in keys[i + 1 :]:
                if k2.startswith(k1 + os.sep):
                    to_del.append(k2)
                elif k1.startswith(k2 + os.sep):
                    to_del.append(k1)
        for k in to_del:
            pe.pop(k, None)
        if to_del:
            json.dump(
                pe,
                open(self.obj_appconfig.dictPath["path"], 'w'),
            )

    def _update_explorer_for_dir(self, directory):
        if not os.path.isdir(directory):
            return
        if directory not in self.obj_appconfig.project_explorer:
            try:
                self.obj_appconfig.project_explorer[directory] = os.listdir(directory)
            except PermissionError:
                return
        self._prune_project_explorer()
        app = self.window()
        if hasattr(app, 'obj_Mainview') and hasattr(app.obj_Mainview, 'obj_projectExplorer'):
            app.obj_Mainview.obj_projectExplorer.rebuildFromConfig()

    def _append_log(self, msg):
        color_map = {
            "ERROR": "#f44336",
            "WARNING": "#ff9800",
            "SUCCESS": "#4caf50",
            "INFO": "#2196f3",
        }
        color = "#d4d4d4"
        for key, c in color_map.items():
            if key in msg:
                color = c
                break
        self.console.append(f'<span style="color:{color}">{msg}</span>')

    def _set_ui_busy(self, busy):
        self.flow_running = busy
        self.run_btn.setEnabled(not busy)
        self.cancel_btn.setEnabled(busy)
        self.input_browse_btn.setEnabled(not busy)
        self.output_browse_btn.setEnabled(not busy)
        self.workflow_cir_radio.setEnabled(not busy)
        self.workflow_rtl_radio.setEnabled(not busy)

    def _run_flow(self):
        proj = self.obj_appconfig.current_project
        proj_dir = proj.get("ProjectName")

        file_path = self.input_file_edit.text()
        if not file_path or not os.path.isfile(file_path):
            QtWidgets.QMessageBox.warning(
                self, "No File", "Please select an input file first."
            )
            return

        if not proj_dir or not os.path.isdir(proj_dir):
            proj_dir = os.path.dirname(file_path)
            proj['ProjectName'] = proj_dir

        ext = os.path.splitext(file_path)[1].lower()
        rtl_mode = self.workflow_rtl_radio.isChecked()

        if rtl_mode:
            if ext not in (".v", ".vhdl"):
                QtWidgets.QMessageBox.critical(
                    self, "Wrong File",
                    "Workflow requires a .v or .vhdl file."
                )
                return
        else:
            if ext != ".cir":
                QtWidgets.QMessageBox.critical(
                    self, "Wrong File",
                    "Workflow requires a .cir file."
                )
                return

        sdc_path = self.sdc_file_edit.text().strip()
        if sdc_path and not os.path.isfile(sdc_path):
            QtWidgets.QMessageBox.warning(
                self, "SDC Not Found", f"SDC file not found:\n{sdc_path}"
            )
            return

        idx = self.pdk_combo.currentIndex()
        data = self.pdk_combo.itemData(idx)
        platform = data if data else self.pdk_combo.currentText()
        valid_platforms = OpenROADFlow.detect_platforms()
        if valid_platforms and platform not in valid_platforms:
            QtWidgets.QMessageBox.critical(
                self, "Invalid PDK",
                f"Platform '{platform}' is not installed.\n"
                f"Installed: {', '.join(valid_platforms) if valid_platforms else 'none'}"
            )
            return

        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            output_dir = proj_dir
        if not os.path.isdir(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Output Error",
                    f"Cannot create output folder:\n{output_dir}\n{e}"
                )
                return

        self._update_project_info()
        self.console.clear()
        self.progress_bar.setValue(0)
        self.stage_label.setText("Preparing...")

        if ext == ".cir":
            cir_file = file_path
            design_name = os.path.basename(cir_file).replace(".cir", "")
            verilog_file = os.path.join(output_dir, design_name + ".v")
            sdc_use = None
        else:
            cir_file = None
            design_name = os.path.basename(file_path).rsplit(".", 1)[0]
            verilog_file = file_path
            sdc_use = sdc_path if sdc_path else None

        self._set_ui_busy(True)

        self.thread = QtCore.QThread(self)
        self.worker = OpenROADWorker(
            design_name, verilog_file, platform,
            output_dir, sdc_use, cir_file,
        )
        self.worker.moveToThread(self.thread)

        self.worker.progressChanged.connect(self.progress_bar.setValue)
        self.worker.statusChanged.connect(self.stage_label.setText)
        self.worker.logMessage.connect(self._append_log)
        self.worker.flowCompleted.connect(self._on_flow_completed)
        self.worker.flowFailed.connect(self._on_flow_failed)

        def cleanup():
            if self.thread is not None:
                self.thread.quit()
                self.thread.wait()
                self.thread = None
            self.worker = None
            self._set_ui_busy(False)

        self.worker.flowCompleted.connect(cleanup)
        self.worker.flowFailed.connect(cleanup)

        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def _cancel_flow(self):
        if self.worker is not None:
            self.worker.cancel()
        self.stage_label.setText("Cancelling...")
        self._append_log(
            f"[{datetime.now().strftime('%H:%M:%S')}] WARNING: Flow cancelled by user"
        )
        self.cancel_btn.setEnabled(False)

    def _on_flow_completed(self, outputs):
        self.stage_label.setText("Completed")
        self.progress_bar.setValue(100)
        output_dir = outputs.get("project_dir", "")
        if output_dir and os.path.isdir(output_dir):
            try:
                self.obj_appconfig.project_explorer[output_dir] = os.listdir(
                    output_dir
                )
            except PermissionError:
                pass
            else:
                json.dump(
                    self.obj_appconfig.project_explorer,
                    open(self.obj_appconfig.dictPath["path"], 'w'),
                )
            app = self.window()
            if hasattr(app, 'obj_Mainview') and hasattr(app.obj_Mainview, 'obj_projectExplorer'):
                app.obj_Mainview.obj_projectExplorer.rebuildFromConfig()

    def _on_flow_failed(self, error):
        self._set_ui_busy(False)
        is_cancel = "cancelled" in error.lower()
        self.stage_label.setText("Cancelled" if is_cancel else "Failed")
        self.cancel_btn.setEnabled(False)
        if not is_cancel:
            QtWidgets.QMessageBox.critical(
                self, "Flow Failed",
                f"OpenROAD flow failed:\n\n{error}"
            )

    def _open_gui(self):
        orfs_root = OpenROADFlow.orfs_root_path()
        candidates = [
            os.path.join(orfs_root, "tools", "install", "OpenROAD", "bin", "openroad"),
            os.path.join(orfs_root, "tools", "OpenROAD", "build", "bin", "openroad"),
        ]
        openroad_bin = shutil.which("openroad")
        if openroad_bin:
            candidates.append(openroad_bin)
        for path in candidates:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                try:
                    subprocess.Popen([path, "-gui"])
                    return
                except Exception:
                    continue
        QtWidgets.QMessageBox.warning(
            self, "Not Found",
            "OpenROAD GUI not found.\n"
            f"Expected at:\n  {candidates[0]}"
        )

    def _open_klayout(self):
        proj = self.obj_appconfig.current_project
        proj_dir = proj.get("ProjectName", "")
        gds_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open GDS File in KLayout",
            proj_dir if proj_dir else os.path.expanduser("~"),
            "GDS Files (*.gds);;All Files (*)",
        )
        if not gds_path:
            return
        try:
            subprocess.Popen(["klayout", gds_path])
        except FileNotFoundError:
            QtWidgets.QMessageBox.warning(
                self, "Not Found",
                "KLayout not found. Is KLayout installed?"
            )
