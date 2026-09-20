# Praxistest StitchLab  
Ausgediente Haushaltsnähmaschinen werden durch den Einsatz 3D gedruckter Teile, 3D-Druckerkomponenten  und dem 3D-Drucker „Betriebssystems“ Klipper zu einer kompakten, kostengünstigen und niederschwelligen Open Source Stickmaschinen verwandelt. Das Projekt basiert derzeit auf den Nähmaschinen der Pfaff Tipmatic/Hobbymatic Serie, soll aber in Zukunft möglichst viele Haushaltsnähmaschinen Typen unterstützen.   
  
Das StitchLAB wurde vom Studio Praxistest und der Schneiderei der Kunstpädagogik an der Universität für angewandte Kunst mit dem Ziel entwickelt, Bildungseinrichtungen und der DIY Community einen Einstieg in die Welt der Stickerei so einfach und günstig wie möglich zu gestalten.   
  
Projektstand.  
Die ersten funktionalen Prototypen befinden sich bereits in der Erprobung   
Die Stickmaschine bietet hier viele Vorteile in der Vermittlung durch ihren einfachen Aufbau.   
Ein Anbau aus 3D gedruckten Teilen, 3D-Druckerkomponenten die mit dem 3D-Drucker "Betriebssystem" Klipper  und den offenen Sticksoftwareumgebungen Ink/Stitch (PlugIn für Inkscape) und TurtleStitch die Fähigkeiten einer Einsteiger Stickmaschine erhalten.   
  
und sieht sich selbst als Teil einer Initiative   
  
### Bestehende Open Source Embroidery Projeke  
  
[Embroiderino towards open source embroidery - LordOvervolt.com](https://lordovervolt.com/embroidery)  
  
[https://gitlab.com/markol/embroiderino/-/tree/master/control_app?ref_type=heads](https://gitlab.com/markol/embroiderino/-/tree/master/control_app?ref_type=heads)  
  
 https://builds.openbuilds.com/builds/diy-embroidery-machine-v2.8630/  
* https://lordovervolt.com/embroidery  
* https://inkstitch.org/de/tutorials/embroidery-machine/  
  
### Designüberlegungen  
  
Stitchlab Nähmaschine Bei einer sonst funktionsfähigen Pfaff Hobbymatic 917 fiel der Motor aus  
Dem Aluminiumguss-Gestell der Nähmaschine bot sich als Ausgangspunkt für die Aufhängung der X und Y Achse. Einer der wesentlichen Gründe die X-Achse an die Innenseite des Rahmens zu platzieren.   
Diese Lösung hat für das Anwendungsfeld einige Vorzüge. Durch die direkte Montage der Stickeinheit an der Nähmaschine bleibt die Maschine relativ kompakt und benötigt keine weiteren Aufbauten. Dadurch kommt das System mit wesentlich weniger Komponenten aus, als die derzeitige OpenSource Lösungen. Die Teile sind schneller gedruckt und aufgebaut.Ein  Nachteil dieser Lösung ist die dadurch eingeschränkte Stickfläche.   
  
Die Stickmaschine bietet sich besonders als erstes CNC/ 3D Drucker Projekt an da es weniger Ansprüche an die Genauigkeit und Kalibrierung stellt als ein zb ein 3D Drucker Bausatz.   
  
### Mögliche Weiterentwicklungen:  
  
Freihandsticken   
Bräuchte ein eigenes Controller Board, um eine Bedienung per Fußpedal zu ermöglichen. Der Motor müsste vom Pico Board entkoppelt und an einen eigens für diese Funktion eingerichteten Microcontroller gekoppelt werden.   
  
Fernbedienung   
Game Controller zur Bedienung der Stickmaschine   
  
  
3D Druckteile  
  
  
Z MotorMount  
Bessere motor Aufhängung In der Motorachse gedreht um servo drive und den m4 schrauben mehr platz zu geben, montage des z motors stabiler zu machen.    
  
LED Licht stabiler  
  
Abnehmbares gentry  
  
kleiner Rahmen  
  
  
  
  
### Hardware Resources:  
  
PICO Wiring   
[https://docs.vorondesign.com/build/electrical/v0_skr_pico_wiring.html](https://docs.vorondesign.com/build/electrical/v0_skr_pico_wiring.html)  
  
  
## Technik:  
  
### Rotation Distance Z:  
rotation_distance = <full_steps_per_rotation> * <microsteps> / <steps_per_mm>  
  
  
Für NEMA 17 StitchLAB 917  
15 Zähne Drive Pulley und 69Zähne Handrad  
200*16=3200  
steps per mm sind gleich eine ganze rotation am handrad also  
200*16*4,6 =14720  
  
3200/14720= 0,2173913043 und jetzt hihihi  
1/4,6 = 0,2173913043  
  
1mm = 0,2173913043  
rotation_distance 0.2174  
5mm = 1,0869565215  
rotation_distance 1.087  
  
  
### stitchLAB 917 run on prntrlab SKR Mini  
SSH  
user: praxistest@prntrlab.local  
pw: (nicht im Repo — siehe Passwortmanager)  
  
### stitchLAB run on SKR Pico  
user: [pi@stichlab.local](mailto:pi@stichlab.local)  
Pw: Standardpasswort des Images, siehe README  
  
## Moonraker API /Network Control  
### Python Desktop  
###    
  
### ToDos CAD  
- [ ] Kerbe im Hoop  
- [ ] Auf und Zu Beschriftung   
- [x] QuickRelease  
###   
## Tutorials  
1. Aufbau der Maschine   
- [ ]   
1. Einrichten der Maschine   
## Ink/Stitch… Preset:  
##   
### Start G Code  
Neopixel Flashing Pink than 100 White     
##    
### End GCode   
Neopixel Lightshow than 50% White    
Message: Stitching Finished!   
  
  
- [x] Interface Mainsail  
- [ ] Unterfaden Oberfaden …   
- [ ] Koordinatensystem … wo ist null und in welche Richtung bewegen sich die Achsen   
- [ ] Homing  
- [ ]   
  
  
## Klipper Install  
[https://www.youtube.com/watch?v=ZOL-motmkos](https://www.youtube.com/watch?v=ZOL-motmkos)  
  
Ih host is known than  /Users/reza/.ssh/known_hosts   
****Install RP4****  
  
  
- [ ] **Download**  
**[https://www.raspberrypi.com/software/](https://www.raspberrypi.com/software/)**  
  
- [ ] Insert   
SD Card (Siehe Specs)  
  
- [ ] Wähle:  
RPI Version (Raspberry Pi 4 )  
RPI OS ( Neueste mit Desktop=  
SD Karte  
  
- [ ] dann Einstellungen Wählen für Wlan und  
  
- [ ] SSH (nicht vergessen! im nächster Reiter)    
  
- [ ] SSH into Pi  
  
- [ ] Install Kiauh  
[https://github.com/dw-0/kiauh](https://github.com/dw-0/kiauh)  
  
  
  
- [ ] **sudo nano /boot/firmware/config.txt**  
  
add  
  
**dtoverlay=disable-bt**  
**enable_uart=1**  
  
**Save end Exit**  
  
  
  
sudo systemctl disable --now bluetooth.service  
  
  
**sudo reboot**  
```

sudo nano /boot/config.txt
sudo nano /boot/firmware/config.txt

dtoverlay=pi3-miniuart-bt
dtoverlay=disable-bt

sudo systemctl disable hciuart.service
sudo systemctl disable bluetooth.service

sudo nano /boot/cmdline.txt
sudo nano /boot/firmware/cmdline.txt

```
```


```
```
Cd klipper

```
  
Delete    
#praxistest #stitchlab #uni #smarttextil  
 #doku   
  
### Installation mit geklonter SD-Karte   
* Hostname ändern:   
[https://www.elektronik-kompendium.de/sites/raspberry-pi/2007021.htm](https://www.elektronik-kompendium.de/sites/raspberry-pi/2007021.htm)  
[https://tunethepi.de/hostname-am-raspberry-pi-aendern/](https://tunethepi.de/hostname-am-raspberry-pi-aendern/)  
* AP (WLAN) Name ändern:  
 [https://www.raspberryconnect.com/index.php?option=com_content&view=article&id=203:automated-switching-accesspoint-wifi-network&catid=65:raspberrypi-hotspot-accesspoints](https://www.raspberryconnect.com/index.php?option=com_content&view=article&id=203:automated-switching-accesspoint-wifi-network&catid=65:raspberrypi-hotspot-accesspoints)  
cd AccessPopup  
sudo ./installconfig.sh  
[https://www.youtube.com/watch?v=ZOL-motmkos](https://www.youtube.com/watch?v=ZOL-motmkos)  
  
  
  
Min 16  
* Verbinden mit SKR Pico  
  
cd klipper  
Make  
CyberDuck sftp verbinden und /out klipper UF2 auf das skr pico flaschen.  
 Oder falls klipper.uf2 schon vorhanden direkt auf skr pico ziehen.  
  
Wenn das pico per gpios an das rpi angebunden ist dann sollte es funktionieren da ttyAMA0 als Adresse verwendet wird und keine usb ID    
[mcu]  
serial: /dev/ttyAMA0  
restart_method: command     
  
  
### Beschriftung 3D Komponenten   
  
Nähmaschinentyp:   
P1 ( pfaff tipmatic…)  
Bauteilgruppe:   
X ( X Achse)  
Bauteilnummer:  
1 (erstes Bauteil der Gruppe  
Bauteilversion:  
V1.4 ( Version 4 der ersten Generation)  
    
Ergibt P1 **X1** V1.4  
  
### Noctua NF-A4x10 24v PWM und andrer 4PIN Lüfter  
  
Schwarz: GND   
Gelb: 24V  
Blau: GPIO 20 (PWM)    
Grün: offen  
  
```
[output_pin always_on_fan]
pin: gpio20     # z.B. ar9 oder PA8
pwm: True                 # PWM statt einfachen Digital-Ausgang
value: 0.5               # Duty-Cycle 95 %
shutdown_value: 0      # Bei MCU-Shutdown ebenfalls 95 %
cycle_time: 0.01         # PWM-Intervall

```
  
##   
## Hinweis:   
Dieses Projekt befindet sich noch in Entwicklung, es richtet sich derzeit an Personen die bereits Erfahrung mit ähnlichen Projekten (Voron/DIY 3D Printer und ähnliches) haben. Dinge müssen gedruckt, Software installiert, SD Karten geflasht, Kabel gekrimpt und gelötet werden. Wenn keine der bereits getesteten Nähmaschinen (Liste Link) zum Einsatz kommt, braucht es darüber hinaus CAD Kenntnisse um einzelne 3D Teile anzupassen. Inklusive Einkauf und Druck der Teile ist es ein  Zeitlich umfassendes Projekt. Derzeit sind keine Kits oder ähnliches geplant. Wir geben uns Mühe die Anleitungen möglichst klar und Fehlerfrei zu halten aber können für nicht garantieren. Es gibt derzeit eine Handvoll funktionierender Maschinen um Software und Komponenten zu Testen. Der Bau erfolgt auf eigene Gefahr und setzt in vielen Bereichen Fachwissen voraus.   
  
Selfcheck:  
  
3D Printing:  
Do I know the following Terms: Slicer,  Infill, Support, Brim, Layer height, STEP, .stl   
Have you ever 3D printed something?  
Only if you want to change Parts or want to have 3D View of all the Components:   
Have I worked with CAD Software (Fusion360, Shapr3D, FreeCAD)? Do I know, how to Import STEP files into CAD?  
  
Mechanic:  
Have you ever Build Mechanic Mechanisms in Lego Technik, DIY Kits, Bikes, etc?  
  
      
  
  
   
   
  
             
## Druckanweisung  
  
  
Alle Teile werden mit 0,4 Nozzle und 0,2 Schichthöhe gedruckt.   
Material: Je nach eingesetzten Motoren, können diese aber ziemlich heiß werden, und es empfiehlt zumindest alle Teile, die mit dem 	in Berührung kommen mit PETG zu drucken. Da PETG höheren Temperaturen standhält.   
  
     
  
Die mit einem ROTEN Punkt markierten Teile sollten in PETG und möglichst Stark (mind. 4 Wandstärken, 30% Infill),   
  
  
  
  
## TODOs:  
  
### Software:  
  
- [ ] Beispiele für TurtleStitch runterladen und auf dem RPI verfügbar machen  
- [ ] TurtleStitch Sketch auf dem RPI speichern, TurtleStitch Zugang zum RPI Festplatte geben  
- [ ] TurtleStitch Motive vor dem Export zentrieren. 1. Min Max Koordinaten des Motives bestimmen 2.Mite berechnen. 3. Alle Koordinaten für das neue Zentrum berechnen.  
- [ ] Mainsail um ein GUI Element zur Positionierung von Motiven im Stickrahmen erweitern  
- [ ] Mainsails XYZ GUI Element an die Anforderungen einer Stickmaschine anpassen.   
- [ ] Mainsail um ein GUI Element zur Auswahl des WLANs erstellen   
- [ ] GamePad Python auf Bluetooth umschreiben.   
- [ ]   
- [ ]   
  
  
## Credits:  
Belt Tension  
[https://www.printables.com/model/391353-prusa-mini-x-end-revised/files](https://www.printables.com/model/391353-prusa-mini-x-end-revised/files)  
Prusa Mini  
Klipper/Moonraker   
Mainsail  
Raspberry Pi  
AccessPopup  
Turtle Stitch  
  
  
```
xcxxccxxc
sdsdsdsfsffdfs

```
  
  
