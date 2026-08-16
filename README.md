# OpenROAD in eSim

Integration of the **OpenROAD** physical design engine into **eSim** (an open-source EDA tool by FOSSEE, IIT Bombay). This plugin lets you take a circuit designed in the eSim schematic editor and drive it all the way to a silicon-ready **GDSII layout** through the **OpenROAD Flow Scripts (ORFS)** — without leaving the eSim environment.

## Overview

OpenROAD is the **Open** **R**oad to **A**utomated **D**igital **L**ayout — an open-source physical design tool that converts a synthesized digital circuit into a chip layout.

```
logic (RTL) in Verilog  ->  Synthesis (Yosys)  ->  Physical Design (OpenROAD)  ->  Final Chip Layout (GDS)
```

This project glues eSim to that flow:

- Converts an eSim schematic netlist (`.cir`) into behavioral Verilog (`.v`) — the **Netlist2RTL** converter.
- Packages the Verilog into an ORFS design directory (auto-generates `config.mk` and `constraint.sdc`).
- Runs the full RTL-to-GDSII flow via `make` under the hood.
- Collects the outputs (`.gds`, `.def`, `.v`, `.spef`, logs, reports) back into the eSim project folder.
- Launches the **OpenROAD GUI** and **KLayout** to inspect the resulting layout.

## Features

- Two input workflows:
  1. **eSim Schematic (`.cir`)** — automatically converted to RTL (currently supports **Half Adder** and **Full Adder**).
  2. **RTL Design (`.v` / `.vhdl`)** — bring your own Verilog/VHDL, with optional SDC constraints.
- One-click **ORFS installer** (`setup/orfs-setup.py`) that builds OpenROAD, Yosys and kepler-formal from source.
- PDK (platform) selection with persisted preference (default: `sky130hd`).
- Live progress bar, stage/status tracking and a color-coded console during the flow.
- Cancel-safe flow execution on a background thread (no UI freeze).
- Automatic output collection: `.gds`, `.def`, `.v`, `.sdc`, `.spef`, plus `logs/` and `reports/`.
- One-click launch of the OpenROAD GUI and KLayout.

## Design Flow

```
User [.cir]                          <- eSim schematic (user input)
   |
   v
Netlist2RTL [.cir -> .v (RTL)]       <- made by this plugin (Half Adder / Full Adder)
   |
   v
User [.v / .vhdl / .sdc]             <- or user-provided RTL
   |
   v
PDK [.lef, .lib]                      <- IHP 130nm / Skywater 130nm / FreePDK / etc.
   |
   v
Yosys [.v (Gate-Level Netlist)]       <- synthesis
   |
   v
OpenROAD Engine                       <- physical design (floorplan, place, CTS, route)
   |   outputs: .v, .odb, .spef, .gds
   v
KLayout [.gds]                        <- layout viewing (user input via KLayout GUI)
```

The ORFS flow stages run automatically:

| Stage | Description |
| ----- | ----------- |
| Synthesis | RTL to gate-level netlist (Yosys) |
| Floorplan | Chip boundary, core area, power grid |
| Global Placement | Cell placement (quadratic/electrostatic solvers) |
| Legalization | Overlap removal, row alignment, density control |
| CTS | Clock tree synthesis |
| Routing | Global + detailed routing, metal-layer-aware |
| Timing analysis | OpenSTA timing reports |
| GDS generation | Final layout stream-out |

## Repository Structure

```text
OpenROAD-in-eSim/
├── src/                       # Plugin source (Python / PyQt5)
│   ├── frontEnd/              # GUI widgets (OpenROAD panel, dock, project explorer)
│   ├── maker/                 # netlist2rtl.py, OpenROAD.py (ORFS flow driver)
│   ├── configuration/         # App configuration
│   ├── projManagement/        # Project / KiCad / worker management
│   └── ngspiceSimulation/     # Ngspice widgets & plotting
├── setup/                     # Installers & guides
│   ├── eSim-2.5.py            # Downloads & installs eSim 2.5
│   ├── orfs-setup.py          # One-click ORFS (OpenROAD + Yosys + kepler-formal) installer
│   └── README.md              # Installation guide (Ubuntu 22.04 LTS)
├── install-doc/               # Detailed install docs
│   ├── Ubuntu/22.04-LTS/      # Build OpenROAD on Ubuntu 22.04
│   ├── Docker/Win-11/         # OpenROAD via Docker + WSL2 on Windows 11
│   └── ORFS/                  # OpenROAD-flow-scripts setup
├── library/                   # Bundled tools (e.g. KLayout .deb)
├── examples/                  # Half Adder & Full Adder eSim projects + ORFS results
├── architecture/              # Flow/workflow diagrams
└── images/                    # Screenshots / logos
```

## Installation

> **Platform:** Ubuntu 22.04 LTS (x86_64) is required. See `setup/README.md` for the full guide, or `install-doc/` for alternative setups (OpenROAD build from source on Ubuntu, or Docker + WSL2 on Windows 11).

### 1. Clone the repository

```bash
git clone https://github.com/RISHABH12005/OpenROAD-in-eSim.git
cd OpenROAD-in-eSim
```

### 2. Install eSim 2.5

```bash
cd setup
python3 eSim-2.5.py          # downloads, extracts, and offers to run install-eSim.sh
```

### 3. Build OpenROAD Flow Scripts (ORFS)

```bash
python3 orfs-setup.py        # builds OpenROAD + Yosys + kepler-formal, installs KLayout,
                             # and verifies with a GCD test flow (can take 1-4 hours)
```

If the build fails, delete the existing `OpenROAD-flow-scripts` folder and re-run:

```bash
python3 orfs-setup.py --force
```

### 4. Run eSim

```bash
esim        # or double-click the eSim desktop icon
```

The **OpenROAD** panel is available inside the eSim GUI.

## Usage

1. Open an eSim project (or create one from an example).
2. In the **OpenROAD** dock widget:
   - Pick the input workflow: **eSim Schematic (`.cir`)** or **RTL Design (`.v` / `.vhdl`)**.
   - Browse for the input file (`.sdc` optional for the RTL workflow).
   - Choose the **Technology Platform (PDK)** (default: `sky130hd`).
   - Select an output folder (defaults to the project folder).
3. Click **Run Flow** and watch the live progress in the console.
4. When complete, the layout outputs are collected into your project folder.
5. Use **Open OpenROAD** to inspect in the OpenROAD GUI, or **KLayout** to open a `.gds`.

### Viewing layouts in the OpenROAD GUI

```bash
cd ~/OpenROAD-flow-scripts/flow
openroad -gui
```

Half Adder:

```tcl
read_lef platforms/sky130hd/lef/sky130_fd_sc_hd.tlef
read_lef platforms/sky130hd/lef/sky130_fd_sc_hd_merged.lef
read_def results/sky130hd/Half_Adder/base/6_final.def
gui::fit
```

Full Adder:

```tcl
read_lef platforms/sky130hd/lef/sky130_fd_sc_hd.tlef
read_lef platforms/sky130hd/lef/sky130_fd_sc_hd_merged.lef
read_def results/sky130hd/FullAdder/base/6_final.def
gui::fit
```

## Examples

Pre-built examples are included in [`examples/`](examples/):

- `Half_Adder/` — eSim project (`.cir`, `.sch`, `.proj`) plus OpenROAD results (`.gds`, `.def`, `.v`, `.spef`, `.sdc`, logs, reports).
- `FullAdder/` — the same for a full adder with carry-in.
- `orfs/` — raw ORFS run directories with stage-by-stage logs and reports.

## Command Line Usage

Netlist → RTL conversion:

```bash
python3 src/maker/netlist2rtl.py examples/Half_Adder/Half_Adder.cir.out
```

Run the ORFS flow directly:

```bash
python3 src/maker/OpenROAD.py <design_name> <verilog_file>
```

## Documentation

- [`setup/README.md`](setup/README.md) — full installation guide (Ubuntu 22.04 LTS).
- [`install-doc/ORFS/`](install-doc/ORFS/README.md) — OpenROAD-flow-scripts setup.
- [`install-doc/Ubuntu/22.04-LTS/`](install-doc/Ubuntu/22.04-LTS/README.md) — building OpenROAD from source on Ubuntu.
- [`install-doc/Docker/Win-11/`](install-doc/Docker/Win-11/README.md) — OpenROAD on Windows 11 via Docker + WSL2.
- [`architecture/`](architecture/README.md) — detailed flow diagram.
- [`install-doc/README.md`](install-doc/README.md) — background on the OpenROAD physical design flow.

## Credits

Developed by **Rishabh Jain** for the eSim team at **FOSSEE, IIT Bombay**. Maintained by Sumanto Kar. Built on the [OpenROAD Project](https://theopenroadproject.org/), [Yosys](https://yosyshq.net/yosys/), [KLayout](https://www.klayout.de/) and [eSim](https://esim.fossee.in/).

## License

See the [LICENSE](LICENSE) file.