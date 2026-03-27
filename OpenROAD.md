- OpenROAD = Open Road to Automated Digital Layout (Realization of Autonomous Design)

- An open source physical design tool used to convert a synthesized digital circuit into a chip layout.

- working
  logic(RTL) in verilog(logic description) -> Convert Logic to Gates (Synthesis) tool used(Yosys) -> Physical Design (THIS IS WHERE OPENROAD FITS) -> Final Chip Layout (GDS file) using GDSII is the standard binary format for layout 

- come with:-
  OpenROAD (physical design engine)
  Yosys (synthesis)
  OpenSTA (timing)
  Makefile automation
  Tcl scripts
  Platform (PDK) support
  Benchmark designs

- Main Repository Structure
  OpenROAD-flow-scripts/
   └── flow/

- flow/designs/sky130/gcd/
  - gcd/
     ├── config.mk
     ├── constraint.sdc
     └── src/
          └── gcd.v

 | File      | Meaning              |
 | --------- | -------------------- |
 | .v        | RTL code             |
 | .sdc      | Timing constraints   |
 | config.mk | Design configuration |

 your generated Verilog will go here.

- flow/platform
        ├── sky130/
        ├── nangate45/
        └── asap7/

 These platforms contain:
  .lib → timing models
  .lef → cell dimensions
  tech.lef → metal layers
  RC models

Without platform files, OpenROAD cannot build layout.

- flow/scripts/
 Contains Tcl scripts like: tcl -> tool cmd. lang.
  ynth.tcl
  floorplan.tcl
  place.tcl
  cts.tcl
  route.tcl
  report.tcl

- flow/Makefile

  It automatically runs:
   Synthesis
   Floorplanning
   Placement
   Clock Tree Synthesis
   Routing
   Timing analysis
   GDS generation

  Makefile = flow controller.

 - results/
   Contains final design outputs
   .def
   .odb
   .gds

- How does OpenROAD automatically compress or arrange the design?
   Floorplan (Define Chip Size)
    OpenROAD first creates:
    Chip boundary
    Core area
    Power grid

   Global Placement (Main Compression Happens Here)
    It uses mathematical solvers (like:
     RePlAce algorithm
     Quadratic optimization
     Electrostatic analogy models)

    placement it minimizes a cost function: Cost = wire length + congestion + timing penalty

   Legalization
   Some cells may overlap slightly.

   OpenROAD fixes this:
    Aligns cells to placement rows
    Removes overlaps
    Keeps density controlled

   Timing-Driven Optimization
   If some signals are too slow.

   OpenROAD:
    Moves cells closer
    Inserts buffers
    Resizes gates

  This also changes layout slightly.

  Routing Optimization
  Routing tries to
   Use shortest metal paths
   Avoid congestion
   Follow metal layer rules
   If routing fails due to congestion:
   Placement is adjusted again.

