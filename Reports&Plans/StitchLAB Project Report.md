# StitchLAB Project Report

This report consolidates the current StitchLAB status and direction. It summarizes what is built, what is in progress, and the next planned steps across the three development strands.
 
## 1) Project purpose and scope

StitchLAB converts retired household sewing machines, or sewing machine parts into low-cost, open source embroidery or hybrid sewing/embroidery systems. The current hardware focus is on the Pfaff Tipmatic/Hobbymatic series, with a goal of supporting additional machine geometries. The system is built around 3D-printed parts, common 3D-printer components, and the Klipper firmware stack, with open embroidery workflows via Ink/Stitch and TurtleStitch. 

The project positions itself as an accessible entry point for education and DIY communities, prioritizing affordability, usability, modularity, and reproducible builds. 

StitchLAB is the current machine development of the research project stich(x) initiated by the Textil Department and Studio Praxistest at the University of applied Arts Vienna.   

Open diy embroidery machines based on household sewing machines aren't new. there are several well documented projects out there, many of the projects (like Embroiderino) are more affordable and capable in terms of pure embroidery performance than this project. At least at this point :)

Stitchlab has a diffrent objective. 
It is an ongiong research into the retrofit and upcycle of used sewing machines of verious geometries and configurations.
will evolve in its capabilties over time.
builds a community of coresearchers and builders.
works on low access documantation for the project
works on diffrent machine configurations and options you can choose from.
investigates the mechanical orchestration of the sewing mechanic
explores the bounderies of current sewing machine topologies 

### Features:
- lightly modified Klipper/Moonraker
- modifed and extended version of Mainsail aka StichLabOS
- G-Code viewer with preview,reposition and rotate functions of the embroidery   
- offline turtlestich integration. 
- Interface for custom external controllers (esp now based) 
- Webcam and Raspberry PiCam Support
- Automatic Wifi AccessPoint script for the use in unfamilar soroundings or classrooms/workshops with restricted internet.  

### Design decisions and diffrences 
many of the design decisions for the used software and hardware were made in the early stages of the project. They were driven by parts avaliblity and software expierence at the time of the first build. Some of the decisions where more delibarate.

The Linear Rods for the Gantry were parts from an old 3D printer. 
The many of the 3D printed components are remodeld or rearenged Prusa mini parts.   

Klipper and Mainsail as software where choosen because of good expierences with the whole stack, the huge active community, the modular approach and the support for a wide verity of hardware. the processing power of the raspberry pi in comparisson of a standalone microcontroller and the ability to run it on most linux or unix based systems together makes it intressting for further deveolpemt like AI enhancments etc. 

A deliberate Design decision: 
to Make it compact: gantry and electronics are directly mounted onto the sewing machine body using less parts and it can be carried! As good and functional all the other open designs are they are all bulky. StitchLAB wants to be the PRUSA mini of open Embroidery machines. 

A Key diffence and a major downside of the machine at this point is the approach choosen for the handwheel motor in comparison to the mantioned project embroiderino:


- **Embroiderino:** "Needle controls movement" (interrupt-driven)
- **StitchLAB:** "Movement controls needle" (sequential G-code)

**Key Insight:** The sewing machine motor runs continuously at controlled speed. XY movements are **triggered by needle position** - they only start when the needle reaches its apex (highest point), ensuring the needle is out of the fabric during hoop movement.

**Key Insight:** StitchLAB Classic has no feedback about actual needle position. Other than the Z endstop for homing. It assumes the stepper moves exactly as commanded. The Z-axis stepper **replaces the AC motor**, giving precise position control but no variable speed within a stitch cycle. StitchLAB moves XY and Z simultaneously in a single coordinated move. There's no "wait for needle up" - instead, the Z motor IS the needle, so moving Z=5mm means completing one stitch.
Community 

## 2) Development strands

### A. StitchLAB Classic (physical machine)
Focus: converting household sewing machines into embroidery machine. with 3D Printed Parts and 3D Printer Components suited for the Klipper 3D Printer Firmware. With a Customized Version of Mainsail as a Frontend.

#### State: 
Prerelease

### B. StitchLAB Hybrid (physical machine)
Uses most of the StitchLAB Classic Hardware and Software
Key changes to the StitchLAB Classic:
- Detachable gantry system with robust latch mechanism and easier adaptation to different machine geometries. 
- Sewing machine motor movment support under Klipper. Continious rotation of the Handwheel Motor with a Smart Footpedal for speed control.
- Mainsail integration for sewing-machine mode. 
- Magnetic encoder to the StitchLAB handwheel or Motor. The goal is to enable 
**Embroiderino-style needle synchronization** and **hybrid embroidery/sewing mode**.

#### State:
in active development with first functioning prototypes
 
### C. StitchLAB OpenRoboticSewingSystem (openRSS) (simulation / robotic system)
targets a fully electronic sewing machine architecture with independent actuators and real-time master controller.
- practilcal research into this new class of sewing robot endeffectors
- lets you controll all of the core functions for forming a stitch indipendently (needle, take-up, bobbin hook, and feed)
- measureing automating thread tension (Load Cell)
- longer term technical embroidery target: independent stitch-forming actuators plus material feeders, tension loops, auxiliary tools, and process-specific head models

#### State:
in active development with first mechanical components

## 3) Hardware stack of StitchLAb Classic and Hybrid (current prototypes)

### Hardware stack (parts and known part numbers)

- Base machines: Pfaff Tipmatic/Hobbymatic series, with,PFAFF Tipmatic 1037, PFAFF Varimatic 6085, PFAFF Hobbymatic 917, PFAFF tipmatic 1019 are used in current testing (!not all Pfaff Hobbymatic have the same Geometry and Motor position as the ones mentioned here!). 
- Motion: 2x NEMA17 steppers for XY + 1x NEMA23 stepper driving the handwheel/Z axis. 
- Handwheel drive ratio typical for PFAFF: 15-tooth drive pulley to 69-tooth handwheel (4.6:1 ratio). 
- Controller: BTT SKR Pico , BTT Manta E3EZ V1.0 or Mellow Fly 5D (Klipper) 
- Compute: Raspberry Pi 4 (a Raspberry Pi 5 Compute Module is in testing on the Manta E3EZ) for Klipper/Moonraker/Mainsail. 
- Cooling: Noctua NF-A4x10 24V PWM fan wiring is documented. 
- 3D printed parts: 0.4 mm nozzle, 0.2 mm layer height; PETG recommended for parts near hot motors. 
- External controllers (optional): StitchLAB Dongle (ESP32-C3), StitchLabController based on Lilygo T4 S3 + Adafruit Mini I2C Gamepad (partly functional prototype), SmartFootPedal (concept), TurtleStitchBot(concept with first stages of code). 

### Extra Parts for Hybrid Mode :
AS 5600 magnetic encoder 

### Roadmap and next steps (Hardware / Mechanical): 
- Detachable gantry with latch and connector system. 
- Improved Z motor mount and LED mounting.
- Smaller hoop option (printable on Prusa mini/Bambulab A1 mini and) additional frame variants. 
- Adapting electonics case to a wider Board selction
- Support for the AC to DC Motor conversion used by the Embroiderino project. So its possible to use the original Motor of the sewing machine (Detailed in Information about the conversion are shown in the Embroiderino)  
- Further develop the second design study with linear rails but the same directly on the machine mounted gantry style. Should result in stiffer more Robust gantry System to support heavier Garments.

## 4) Current system architecture (StitchLAB OS)

StitchLAB OS provides the software "glue" between Klipper/Moonraker and the custom Mainsail UI. Current components and status: 

### EmbroideryControlPanel (Mainsail UI): 
Done, talks to Moonraker for stitch controls. 
Klipper embroidery macros: Done, includes needle model and stitch commands. 

### G-Code Studio:
A Embroidery G-Code viewer 
A variation of the pre existing G-Code viewer panel for previewing 3D-prints. the three.js component got replaced by the 2D Graphics of Paper.js. Additional features useful for Embroidery G-Code manipulation where added

### StitchLAB Live Control 
- live_jogd daemon: Done, USB serial + HTTP/WebSocket control working; installed but not auto-started. The Mainsail Controller menu starts/stops it through Moonraker on demand.
- StitchLAB Dongle (ESP32-C3): Done, ESP-NOW + serial API. 
- StitchLAB Controller (LVGL + joystick): Test Version Done. In Development: Bidirectionl information.
- TheControllerMenu UI: Done for status/pairing/service lifecycle and Live Control gate; active motion behavior still needs focused controller-link testing.
- Browser to live_jogd WebSocket: Done on port 7150 after user-triggered service start.

### TurtleStitch offline integration
Done, served on the Pi and integrated with Moonraker file API i (via nginx on port 3000). 
- TurtleStitch project files are saved/loaded directly on the Pi via the Moonraker file API. 
- TurtleStitch project files can be inported from online Turtlestitch
- Gcode can directly be send to Mainsail and be stitched

### WiFi manager
 Implemented as a Moonraker extension with scan/connect/AP endpoints to this script 
https://www.raspberryconnect.com/projects/65-raspberrypi-hotspot-accesspoints/203-automated-switching-accesspoint-wifi-network
 Tinkered solution which has do be refined. The automatic wifi access point which scans for known networks every two minutes and if not found, opens up AP, is not ideal on a system with timeing constraints.    
Better Solution small Touch LCD with a user interface for PI Network Manager 
This cant be implemted in the frontend directly because its browser based. 

### Firmware / Control / UI
- Sewing machine motor control under Klipper. 
- Mainsail UI mode for sewing (not just embroidery). 
- External controller integrations 

### Toolchain for Raspberry Pi Image 
A Raspberry Pi Software Image for easy Installation on a new System via Raspberry Pi Imager


## 5) Known constraints and build requirements

The project is in active development and at this point the target audience are users with prior experience in 3D printing, electronics, and mechanical assembly. Builders should expect: 
- 3D printing (PETG recommended for heat-prone parts). 
- SD card flashing, Klipper/Moonraker installation, and cabling. 
- CAD modifications when using untested sewing machine models. 
- A time-intensive build with no kit support planned at this time. 

### Biref steps for the build
1. Select a compatible sewing machine (Pfaff Tipmatic/Hobbymatic series currently validated). 
2. Print mechanical parts with the specified settings (0.4 mm nozzle, 0.2 mm layer height, PETG for heat-exposed parts). 
3. Assemble the XY gantry and mount it to the machine frame; verify clearance and the reduced embroidery area trade-off. 
4. Install steppers and handwheel drive (2x NEMA17 for XY, 1x NEMAA23 for handwheel/Z, 15T to 69T pulley ratio). 
5. Wire electronics (SKR Pico or any other 3D printer board supported by klipper + Raspberry Pi 4 + fans  and verify PWM fan wiring. 
6. Install Klipper/Moonraker/Mainsail, deploy embroidery macros, and include them in the printer config.
7. Deploy the StitchLAB Mainsail UI and validate extras (Embroidery panel, G-Code Studio, TurtleStitch offline if used). 
8. Calibrate needle motion: set rotation_distance based on handwheel ratio, verify UP/DOWN positions, and run homing and stitch macros. )

## 6) StitchLAB OpenRSS (simulation and research detail)

targets a fully electronic sewing machine architecture with independent actuators (for the four core functions to form a stitch on sewing machine: needle movement, take-up lever, bobbin and hook) and real-time master controller.

### State of Developent 

A testplatform similar to Sam Callishs Sewing Endeffector is already under construction

- needle motion, take-up lever mechanics are done
- thread tension, thread routing an bobbin/hook drive are missing  

Diffrent closed loop motor configurations and their implemtation in the current software stack are evaluated, which will also benefit the StitchLAB Hybrid.

- custom closed loop stepper with magnetic encoder and custom klipper firmware on the mcu
- MKS 42 & 57D Servo Board for Nema 17 and Nema 23 Stepper Motors with closed loop FOC support and CAN or RS485 communication interfaces
- DIYed closed loop BLDC motor based servo with simpleFOC 
- Odrive BLDC Motor Driver with closed loop, FOC and trajectory support. 

### Technical embroidery requirements from ZSK whitepaper

Source read in OpenRSS context: Dr. Topher Anderson, ZSK Stickmaschinen, "A Guide to Technical Embroidery", 2020.

Important findings for OpenRSS:
- F-Head embroidery is the relevant commercial lockstitch baseline: needle, rotary hook/bobbin, upper thread, lower thread, high stitch rate, and high positional accuracy. This maps directly to the current OpenRSS stitch-forming actuator set.
- W-Head embroidery is the most important expansion model for technical embroidery. It places wires, fibers, tubes, tapes, fiber optics, or other technical material onto a backing material and fixes it with stitches. This requires more than a sewing core: active material feeding, material tension sensing/control, a swing foot or equivalent lateral placement actuator, and material-specific path constraints.
- K-Head embroidery is useful as an alternate stitch-family model. It uses a hooked needle and loop/chain formation without a rotary hook, so it is relevant when comparing lockstitch, chainstitch, and moss/chenille demand-side thread models.
- Technical embroidery is a material system, not only a stitch system: backing/stabilizer, top/bottom stitching threads, and technical material all affect speed, reliability, thread breaks, bend radius, stitch distance, and stitch quality.
- ZSK automation options point to later OpenRSS modules: pneumatic/even clamping, roll-to-roll feed, positioning encoders, optical/fiducial positioning, automatic bobbin change, hot-air cutting, and electronic component placement.
- Commercial reference speeds are roughly F-Head 1000-1200 RPM, K-Head 700-750 RPM, and W-Head 800-850 RPM. Treat these as long-term reference points, not early prototype targets.

OpenRSS implication: the architecture should not stop at an electronic sewing machine core. The deeper model is a phase-master machine where needle, take-up, hook/bobbin, feed, tension, material feeder, clamp state, cutter, and placement tools can be synchronized or monitored around stitch phase.


### StitchLABsim 
StitchLABsim is the simulation strand of Open RSS so new machine architectures can be designed and validated in software before hardware is built. 

Current model status:
- **Supply-side first atempt complete**: thread-contour model computes actual take-up P(phi) from guide/lever/needle trajectories. 
- **Demand-side missing**: required take-up P'(phi) from stitch geometry (loop formation, hook/looper, bobbin wrapping, material thickness) is not implemented yet. 
- Implement demand-side stitch geometry models (P'(phi)) for lockstitch and chainstitch. 
- Add hook/looper kinematics and loop formation geometry. 
- Extend contour below the needle to capture loop/bobbin wrapping. 
- Validate against literature formulas and experimental measurements. 
- Add technical embroidery process constraints from F/W/K-head workflows: stitch distance, stitch width/stroke, material bend radius, feeder lag, clamp/backing stiffness, and material tension limits.

Key capabilities already implemented but not tested:
- 2D geometric thread path modeling with contour length xi(phi) and take-up P(phi). 
- Visualization tools and runnable examples. 

Planned features:
- Tension modeling (spring-damper-friction). 
- 3D contour support. 
- Stitch geometry library and optimization tools to match P(phi) ~ P'(phi). 
- Process models for lockstitch/F-Head, W-Head tailored fiber/wire/tube placement, and K-Head chain/moss stitch variants.
- Metadata schema for technical materials: thread type, backing type, technical material diameter/tow size, stiffness, bend radius, target tension, stitch distance, and stroke/swing settings.

### Research for the StitchLAB OpenRSS

https://arxiv.org/html/2503.00249v1

#### Technical embroidery literature
- ZSK Stickmaschinen / Dr. Topher Anderson, "A Guide to Technical Embroidery", 2020. Local file: (intern abgelegt, Nextcloud der Angewandten)

#### Open Source
- Robotic Sewing Endeffector 
http://samcalisch.com
https://gitlab.cba.mit.edu/calischs/stitch
https://fab.cba.mit.edu/classes/863.16/doc/tutorials/sewing/sewing.html


#### Comnercial  
- Selina 
https://www.silana.com/
A robotic Sewing Startup based in Vienna 

- Sewbo
https://www.sewbo.com


## 7) Workflows and tooling in active use

- Klipper + Moonraker + Mainsail as the core control stack. Katapult Bootloader for remote flashing of the connected MCUs 
- Development targets: local simulator (virtual Klipper printer) and dev Pi deployment. 
- Visual Studio Code with Github Copilot and Claude Code as coding agents 

## 8) Planed Software and Hardware Add Ons 
### PicturetoStichlab add-on 
PicturetoStichlab is a two-stage add-on effort that targets the same goal: turning images into embroidery G-code for StitchLAB. 

- **Stage A (RPIcam2Embroidery):** live camera capture + vectorization + stitch digitization + Moonraker upload via a Flask API and Vue frontend. 
- **Stage B (IMG2SVG2SITCH):** offline CLI pipeline that produces higher-fidelity SVG and generates outline/fill G-code with previews. 
- **Integration intent:** Stage A is the real-time pipeline for the StitchLAB Pi; Stage B can serve as a higher-quality SVG preprocessing step for more powerful computers than the Pi

#### State
functioning code prototypes which need refinment and GUI integration 

### Future ideas and plans in their scetch pahse:
- Sequins and part feeder  
a automatic feeder mechanism for sequins and other object like elctronic parts which can be sewn in autmatically.  
- automatic under thread cutter
 as retrofit for StichLAB Classic and Hybrid 
 as Component for the Stitchlab OpenRSS 
 
 - StitchLAB Colorizer
 automatic micro predyeing of the thread in coordination with the colors of embroidery motive. the classical approach to multicolor embroidery is to pysically change the thread manually in single needle systems and automatically multi head machines. 

with automatic micro predying a single needle machine could realize multicolor embroidery without yarn changes or the cost of a multihead machine. Similar to the predying and than weaving technique Ikat. The Colors and their position of the embroidery motive define which section of the thread needs which color. a white thread could be could be colored for a small section of the thread by for example an inkjet printer head, while the embroidery machine is running.  

- Automatic camera mount for PicturetoStitchlab and rasterizing Microscope features
https://gitlab.cba.mit.edu/calischs/zundscope

## 9) Software from other contributors of the project
- Annas StitchPAD

## 10) Open-source ecosystem references

### Open Embroidery Machines
Existing open-source embroidery projects are referenced for context and inspiration:
- Embroiderino (project and control app). 
https://gitlab.com/markol/embroiderino
https://github.com/MakerMylo/Embroiderino
https://www.hackster.io/spaceforone/arduino-based-embroidery-machine-2f2f69
https://lordovervolt.com/embroidery
Detailed discription of the ac dc motor conversion driver .
https://www.st.com/resource/en/application_note/cd00003829-improved-universal-motor-drive-stmicroelectronics.pdf

- DIY Embroidery Machine V2
https://builds.openbuilds.com/builds/diy-embroidery-machine-v2.8630/

- Embroidotron
https://juanluisvn.com/projects/embroidotron/

### Open Embroidery Software
- Ink Stitch 
https://inkstitch.org/tutorials/embroidery-machine/
https://github.com/inkstitch/inkstitch

- Turtle Stitch 
https://www.turtlestitch.org/run
https://github.com/backface/turtlestitch

- EmbroidePy
a collection of embroidery related software tools 
https://github.com/EmbroidePy
https://github.com/EmbroidePy/pyembroidery
by 
https://github.com/abey79






