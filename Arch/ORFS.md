# Workflow of the GUI o fthe ORFS to eSim:-
```text

			   User [.cir] <- {Made by User input}
			   	|
			   	↓
			Netlist2RTL [.cir -> .v (RTL)]  ]-> {Made by Me support for *Half Adder & Full Adder (.cir file)*}
				|				    /
				↓				  ↙																														  ___
			  User [.v (Behavioral); .vhdl; .sdc] <- {Or Made by User input if they have ther own file}														 |
			 	|																																			 |		
			 	↓																																			 |
    IHP 130nm / Skywater 130nm / FreePDK / etc. (PDK) [.lef(Physical Blueprint), .lib(Electrical Spec Sheet)]			    								 |
				|																																			 |
				↓																																			 |
			  Yosys [.v (Gate-Level Netlist)]																												 |
			  	|																																			 |-> {Made by ORFS}|
			  	↓																																			 |
		OpenROAD Engine [.v (Post Layout Netlist); .odb (Save Full Internal State); .spef (Used for Time check); .gds] <- {User input using OpenROAD GUI}	 |
				|																								   |										 |
				↓			                             _________________________________________________________↙											 |
			 Klayout [.gds(Physical Layout Blueprint)] ↙																									 |
			 	|																																			 |
			 	 ↘ {User input using Klayout GUI}																										  ___|
```
