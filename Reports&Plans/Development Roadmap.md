# Development Roadmap  
  
## What happened so far  
  
  
## stitch (x) Software and Hardware Development   
  
  
Goals:   
Three main branches of development:  
* StitchLAB Classic Old Sewing into Embroidery   
* StitchLAB Hybrid Old Sewing Machine into Hybrid Digital Sewing Embroidery Machines  
* StitchLAB Robot. An entirly new Class of digital Sewing and Embroidery machines.      
Upcycle Household Sewing Machines to Hybrid digital Sewing and Embroidery Machines.   
  
Hardware  
  
  
Current Development Goals  
### StitchLAB Hybrid   
Give StitchLAB the capability to be a hybrid digital sewing and embroidery machine   
  
Needed Dev:  
- [ ] Detachable Gantry  
    - [ ] Latch mechanism  
    * with necessary clamping force  
    * Easily adaptable to other sewing machine geometries than the currently used Pfaff  
    - [ ] Electronic Connector   
    * Easy to use cheap and reliable : )  
- [ ] Sewing machine Motor Control under Klipper  
- [ ] Mainsail integration of the Sewing Machine Mode  
###   
### StitchLAB DEV  
Modular Robotic Sewing System  
  
[https://github.com/prntr/stitchLABsim](https://github.com/prntr/stitchLABsim)  

Motion-kernel research:
- [ ] Investigate LinuxCNC as realtime motion core for StitchLAB Hybrid and OpenRSS: [LinuxCNC Motion-Kernel Prototype Plan](LinuxCNC%20Motion%20Kernel%20Prototype%20Plan.md)
  
  
### StitchLAB OS  
Modules for Mainsail to get the functionality of a dedicated sewing and stitching frontend.  
  
Custom Modules to the Frontend:  
  
* Needle Control   
a set of klipper macros and tools to control the position of the needle   
  
* G-Code Studio  
A Penal in Mainsail/Stitchlab OS to preview and manipulate embroideries  
  
* TurtleStitch offline on the RPI   
Bridge to Klipper:   
- [x] Gcode Export to Klipper  
- [ ] Gcode Export to Computer  
- [x] Import Projects from Computer (Saved from TurtleStitch)  
- [x] Naming and Saving TurtleStitch Project on the RPI   
- [ ]  Guidelines for Custom Blocks to interact with the Machine (Snap Websocket support?)     
  
* Wifi/AP control (implemented but a technical bad/patched solution, AccessPopup script gets controlled via Moonraker Module)   
better longterm Solution small I2C Display with a custom Interface controlling the Network Manager of the Pi.      
  
* Klipper Live Control  
Support for ESP based custom build external Controllers.  
  
StitchLAB Dongle connects external Handhelds, Controllers and other HCI devices with Klipper/Moonraker, over a ESP NOW based bidirectional protocol. Wich adapts the communication and the user interaction depending on the controller type  
  
    * StitchLAB Controller V1 Micro GamePAD with touch display based on Lilygo T4 S3 and Adafruit Mini I2C Gamepad  
  
    * SmartFootPedal lets you control Stitchlab like regular machine.   
  
    * TurtleStitchBot based on the concept of the first turtle its a Playful toy which introduces you to programming of graphics over a simplified commands and a reduced user interface. Lets you export the drawing to stitchlab, lets you program it later on with TurtleStitch?      
  
    * Ottobock Muscle Electrode Controller  
  
  
Development:  
  
Visual Studio Code, with a set of Code Agents following Mainsail, Klipper/ MoonrakerDevelopment Guidelines.  
  
#stitchlab  
