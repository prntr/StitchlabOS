# LinuxCNC Motion-Kernel Prototype Plan for StitchLAB Hybrid and OpenRSS

Date: 2026-05-09
Updated: 2026-05-14

## 1) Purpose

This plan defines an investigation track for using LinuxCNC as a motion kernel for StitchLAB Hybrid and StitchLAB OpenRSS.

It does not replace the current Klipper/Moonraker/Mainsail stack for StitchLAB Classic. The current Klipper path remains valuable for low-cost, accessible embroidery-machine retrofits. The LinuxCNC prototype exists to test whether a CNC/robotic realtime motion core is a better foundation for the future machine classes that need closed-loop motor control, native rotary axes, needle-position synchronization, foot-pedal operation, and multiple independent sewing actuators.

## 2) Working hypothesis

LinuxCNC is worth prototyping because the future StitchLAB requirements are closer to CNC/robotic motion than to normal 3D-printer motion:

- Hybrid embroidery/sewing needs continuous handwheel or sewing-motor control, not only discrete Z-axis stitch moves.
- The handwheel/needle phase should be a first-class rotary coordinate, sensor, or spindle-like realtime signal.
- XY hoop movement should be gated by actual needle phase, especially when using the original sewing motor or a closed-loop servo.
- Closed-loop drives such as ODrive, MKS servo boards, SimpleFOC-based actuators, or later industrial servos need fault, enable, encoder, and feedback integration beyond simple step counting.
- OpenRSS needs multiple coordinated and semi-independent actuators: needle, take-up lever, bobbin/hook, feed, thread tension, cutters, feeders, and sensors.

The investigation should answer whether LinuxCNC can become the realtime motion layer while StitchLAB keeps its existing strengths in UI, G-code generation, TurtleStitch/InkStitch workflows, and machine documentation.

## 3) Reference points

Primary docs checked for this plan:

- LinuxCNC INI configuration supports up to nine coordinate letters `X Y Z A B C U V W`; typical trivial kinematics map `JOINT_0 = X`, `JOINT_1 = Y`, `JOINT_2 = Z`, `JOINT_3 = A`, etc. Joints can be `LINEAR` or `ANGULAR`.
- LinuxCNC homing supports alignment by eye, switches, switch plus encoder index, and absolute encoders.
- LinuxCNC HAL is the realtime hardware abstraction layer for connecting motion, I/O, encoders, step generators, PID loops, and custom components.
- LinuxCNC HAL includes realtime components relevant to this prototype: `motion`, `stepgen`, `encoder`, `pid`, `bldc`, `pwmgen`, `hal_input`, and custom compiled components.
- LinuxCNC G-code uses axis words including `A`, `B`, `C`, `U`, `V`, and `W`; `G93` inverse-time feed can be useful when linear and angular axes are coordinated.
- ODrive documentation describes step/direction as simple but primitive/fragile, while the controller itself supports position, velocity, torque, filtered position, velocity ramp, and trajectory input modes.
- Remora provides an open-source LinuxCNC component and firmware path for using STM32, iMX RT1052, and RP2040-compatible controller boards with LinuxCNC.

Additional findings from the 2026-05-10 motion-stack discussion:

- Ruckig is not natively supported by LinuxCNC, grblHAL, or FluidNC. It is best understood as an optional online trajectory generator for a custom StitchLAB motion daemon, reactive control, pendant/gamepad jog, foot-pedal speed transitions, and OpenRSS multi-actuator coordination. It is not a complete machine controller and should not be the primary large-embroidery-file planner.
- Ruckig "online" means trajectory generation from the current state to a target state inside a control loop. It does not mean internet-connected. It recalculates local state-to-state moves when targets or sensor state change.
- Ruckig Community should not be treated as a local realtime planner for thousands of embroidery waypoints. A StitchLAB scheduler would still need to feed it stitch-by-stitch, phase-window-by-phase-window, or use it only for reactive modes.
- `libscurve` by Michel Wijnja/Grotius/Skynet is a small GPL2 C constant-jerk S-curve trajectory generator. It exposes `scurve_init`, `scurve_set_target_state`, and `scurve_update`, and outputs current position, velocity, and acceleration. It is useful as a realtime S-curve primitive, but not a full CNC planner.
- `linuxcnc_scurve_compact` is more significant than `libscurve` alone. It is a patched LinuxCNC trajectory planner module using `TPMOD=tpmod_scurve`, `libscurve`, and Clothoid3D/path blending helpers. It claims support for `XYZ`, `ABC`, and `UVW`, lookahead, a G-code ringbuffer, HAL telemetry pins, jog pins, S-curve motion, and rigid tapping/spindle-sync logic.
- `linuxcnc_scurve_compact` should be treated as a research branch, not production LinuxCNC. It patches LinuxCNC files and adds dependencies. It should be tested in simulation before any machine test.
- grblHAL is the strongest lightweight embedded comparison track. Current grblHAL sources include multi-axis configuration, plugin architecture, realtime command/status behavior, motor fault support, and newer 3rd-order acceleration / jerk support. It is still CNC-controller-shaped and would likely require a custom plugin or fork for robust needle-phase scheduling.
- FluidNC remains useful as a practical lightweight CNC baseline, but it is less interesting for Hybrid/OpenRSS research because it offers fewer hooks for closed-loop, phase-aware, or robotic coordination work.
- Moonraker/Mainsail should not be replaced directly by LinuxCNC or grblHAL. The better architecture is a backend-neutral StitchLAB gateway service (`stitchlabd`) that exposes the UI/controller API and delegates motion to backend adapters.

Additional findings from the 2026-05-14 ZSK technical embroidery whitepaper reading:

- ZSK's F/W/K head distinction should be treated as process models for OpenRSS, not as hardware to copy directly. F-Head is the lockstitch baseline, W-Head is the technical-material placement model, and K-Head is an alternate chain/moss stitch model without a rotary hook.
- W-Head tailored fiber/wire/tube placement adds requirements beyond needle and hook synchronization: active technical-material feeding, material tension feedback, swing-foot or lateral placement control, stitch-distance/stroke parameters, and material-specific path limits such as minimum bend radius.
- Technical embroidery is a coupled material system: backing/stabilizer, top and bottom stitching threads, and technical material all affect speed, breakage, stitch quality, and allowed geometry.
- Automation options in commercial technical embroidery suggest later OpenRSS modules: roll-to-roll feed, pneumatic or controlled clamping, positioning encoders, optical/fiducial correction, automatic bobbin change, hot-air cutting, and component placement.
- Commercial benchmark speeds from the whitepaper are roughly F-Head 1000-1200 RPM, K-Head 700-750 RPM, and W-Head 800-850 RPM. These are long-term references, not initial prototype targets.

Sources:

- https://linuxcnc.org/docs/html/config/ini-config.html
- https://www.linuxcnc.org/docs/stable/html/config/ini-homing.html
- https://www.linuxcnc.org/docs/html/man/man3/intro.3hal.html
- https://linuxcnc.org/docs/stable/html/hal/components.html
- https://www.linuxcnc.org/docs/stable/html/hal/rtcomps.html
- https://linuxcnc.org/docs/html/gcode/overview.html
- https://linuxcnc.org/docs/html/gcode/g-code.html
- https://docs.odriverobotics.com/v/latest/manual/step-direction.html
- https://docs.odriverobotics.com/v/latest/manual/control.html
- https://remora-docs.readthedocs.io/en/latest/index.html
- https://github.com/pantor/ruckig
- https://docs.ruckig.com/
- https://codeberg.org/mikanet/libscurve
- https://codeberg.org/skynet/linuxcnc_scurve_compact
- https://github.com/grblHAL/core
- Local literature: (intern abgelegt, Nextcloud der Angewandten)

## 4) Prototype goals

### Main goal

Build a minimal LinuxCNC-based motion kernel that can run a StitchLAB-like embroidery cycle with:

- `X/Y` hoop motion.
- A handwheel or needle-phase axis/signal.
- Homing and limit handling.
- Needle-up gating for XY motion.
- Drive enable/fault handling.
- A path from simulation to bench electronics to machine tests.

### Secondary goals

- Compare LinuxCNC against the current Klipper motion model using measured results, not assumptions.
- Compare LinuxCNC stable/devel, LinuxCNC plus `tpmod_scurve`, and grblHAL as separate motion-kernel candidates.
- Identify where Ruckig or `libscurve` should be used as optional trajectory primitives rather than main machine controllers.
- Test whether existing StitchLAB-generated G-code can be adapted cleanly.
- Identify what belongs in the realtime layer and what should stay in higher-level StitchLAB tooling.
- Establish whether LinuxCNC can support OpenRSS multi-actuator experiments without a full rewrite later.

## 5) Non-goals

- Do not migrate StitchLAB Classic to LinuxCNC during this prototype.
- Do not build a full replacement for Mainsail/Moonraker UI yet, but do define the backend-neutral API layer that would replace Moonraker's role for LinuxCNC/grblHAL/Ruckig backends.
- Do not commit to one closed-loop drive vendor before the interface tests are complete.
- Do not try to solve full OpenRSS thread/tension physics inside LinuxCNC in the first prototype.
- Do not use the prototype machine with a needle and fabric until the no-needle safety tests pass.
- Do not assume an experimental S-curve branch is production safe until it passes reproducible build, simulation, and fault tests.

## 6) Proposed motion model

### Model A: handwheel as `A` rotary axis

This is the first prototype model.

- `X`: hoop horizontal linear axis.
- `Y`: hoop vertical linear axis.
- `A`: handwheel or needle phase as an angular axis.

In this model, one stitch is a coordinated move from the current `A` angle to the next full rotation. XY movement can be tested in coordinated G-code, and the A-axis feedback can be compared against commanded phase.

Advantages:

- Maps directly to LinuxCNC's native angular-axis model.
- Makes rotary homing/indexing explicit.
- Allows stepper, closed-loop stepper, or BLDC servo handwheel tests.
- Keeps current StitchLAB G-code concepts understandable.

Open question:

- Whether `A` should be wrapped `0-360` for UI/phase display or continuous for stitch counting. The likely answer is continuous internally with a derived modulo phase signal for needle-up/needle-down logic.

### Model B: handwheel as spindle-like continuous motor

This is the second prototype model.

- `X/Y`: hoop axes.
- Handwheel motor: continuous controlled motor with encoder phase.
- Needle-up signal: HAL phase window or sensor input.
- XY motion: allowed only in a safe phase window.

This model is closer to Embroiderino and commercial embroidery machines: the needle/motor runs continuously, and hoop moves are synchronized to actual needle position.

Advantages:

- Better fit for original sewing motor, DC motor conversion, foot pedal mode, and high stitch rate.
- Better separation between sewing rhythm and hoop path.
- More realistic for Hybrid.

Open question:

- Whether LinuxCNC's standard spindle synchronization, HAL gating, or a custom realtime component is the cleanest implementation.

### Model C: OpenRSS multi-actuator model

This is not the first prototype, but the LinuxCNC setup should not block it.

Possible axis/signal allocation:

- `X/Y`: fabric or hoop motion.
- `A`: needle bar phase.
- `B`: take-up lever phase.
- `C`: hook/bobbin phase.
- `U/V/W` or HAL-only actuators: feed, thread tension, swing foot, technical-material feeder, clamp pressure/state, cutter, colorizer, sequin/part feeder.

OpenRSS will likely need custom kinematics and HAL components rather than only ordinary G-code axes.

The ZSK W-Head process makes this especially clear: tailored fiber, wire, or tube placement is not only an `X/Y/A` stitch cycle. It needs a process layer that can coordinate material feed rate, tension, stitch distance, stroke/swing, and path curvature limits with the stitch-forming cycle.

### Model D: phase master plus electronic cam tables

This is the likely deeper OpenRSS model.

- A master stitch phase `phi` defines the stitch cycle.
- Needle, take-up lever, hook/bobbin, feed, and thread-tension targets are functions of `phi`.
- Technical embroidery process devices may be functions of both `phi` and path state: tangent, curvature, stitch distance, material diameter/tow size, bend radius, and target tension.
- LinuxCNC HAL components or a custom StitchLAB realtime component implement electronic cam relationships.
- Ruckig or `libscurve` may be used for transitions between cycle rates, safe stops, or mode changes, not for every point of a large embroidery file.

This model should be evaluated only after the simpler `XYA` and spindle-like models are understood.

## 7) Motion-planner candidates

### Candidate 1: LinuxCNC stable/devel planner

Use this as the baseline LinuxCNC reference.

Strengths:

- Native joints/axes, homing, HAL, encoder feedback, drive faults, UI/API interfaces.
- Mature machine-control and safety model.
- Good target for `X/Y/A` Hybrid tests.

Risks:

- Larger deployment footprint than Klipper/grblHAL.
- S-curve availability depends on LinuxCNC version/branch and must be verified on the exact install.
- UI is CNC-focused, not StitchLAB-focused.

### Candidate 2: LinuxCNC plus `tpmod_scurve`

Use this as the S-curve research track.

Observed repo features:

- LinuxCNC trajectory planner module configured by `TPMOD=tpmod_scurve`.
- S-curve profile generation through `libscurve`.
- Clothoid3D/path blending helpers.
- Claimed support for `XYZ`, `ABC`, and `UVW`.
- Lookahead and a G-code ringbuffer.
- HAL pins for current velocity, acceleration, target position, segment progress, buffer depth, following error, maximum jerk, feed override, jog pins, and diagnostic timing.
- Rigid tapping/spindle-sync code that may be conceptually relevant to needle-phase synchronization.

Initial configuration pattern:

```ini
[TRAJ]
TPMOD = tpmod_scurve
DEFAULT_LINEAR_VELOCITY = 30.48
MAX_LINEAR_VELOCITY = 53.34
DEFAULT_LINEAR_ACCELERATION = 508
MAX_LINEAR_ACCELERATION = 508
```

Recommended G-code mode for testing:

```gcode
G64 P0.01 Q0.0
```

Research questions:

- Does `tpmod_scurve` handle many tiny embroidery stitch segments without filtering or corrupting geometry?
- Does path blending preserve embroidery accuracy, especially at corners and small stitch lengths?
- Can `A` rotary motion remain synchronized with `X/Y` motion?
- Can its HAL pins expose enough status for phase-window decisions?
- Does the rigid-tapping/spindle-sync structure provide a useful pattern for "needle phase controls XY release"?
- How repeatable is installation from a clean LinuxCNC clone?

Risks:

- It patches LinuxCNC internals and is not upstream production LinuxCNC.
- Extra dependencies and licensing notes need review before any redistributed image/package.
- It may be excellent for research but too fragile for a community build.

### Candidate 3: grblHAL lightweight comparison

Use this as the lightweight embedded comparison track.

Strengths:

- Much lighter than LinuxCNC.
- 32-bit MCU focused.
- Multi-axis configuration depending on driver/board support.
- Plugin architecture.
- Realtime status, alarm, jog, and G-code streaming model.
- Newer 3rd-order acceleration / jerk work makes it more relevant than classic Grbl.

Risks:

- Still CNC-controller-shaped.
- Needle-phase-aware scheduling likely requires a custom plugin or fork.
- Closed-loop drives are usually still external black boxes unless custom feedback/fault integration is added.
- Less natural than LinuxCNC for OpenRSS multi-actuator feedback and realtime signal wiring.

### Candidate 4: Ruckig optional reactive layer

Use Ruckig for local, online, sensor-reactive trajectories, not as the main large embroidery file planner.

Good uses:

- Gamepad/pendant jog smoothing.
- Foot-pedal speed changes.
- Controlled stop and restart.
- OpenRSS actuator transitions.
- Stitch-rate changes while maintaining bounded velocity, acceleration, and jerk.

Poor uses:

- Feeding an entire large embroidery file as thousands of waypoints.
- Replacing homing, drive faults, E-stop, file handling, or machine state.

### Candidate 5: `libscurve` optional primitive

Use `libscurve` where a very small C S-curve primitive is enough.

Good uses:

- MCU-side or realtime C jog smoothing.
- Foot-pedal speed ramping.
- Controlled stop primitive.
- Experiments inside a custom LinuxCNC HAL component or StitchLAB daemon.

Poor uses:

- Full multi-axis path planning.
- Large embroidery lookahead.
- Backend-neutral UI or machine state.

## 8) Candidate hardware paths

### Path 1: PC or Raspberry Pi 5 + LinuxCNC simulator

Use this for the first phase.

- No motion hardware.
- Create LinuxCNC configs for `XYA`.
- Create both a stock/devel LinuxCNC config and a `tpmod_scurve` config if the S-curve build is reproducible.
- Test G-code generation, homing behavior, UI visibility, and HAL logic in simulation.

### Path 2: LinuxCNC + step/dir controller board

Use this for the first bench electronics phase.

- LinuxCNC software stepgen, Remora, Mesa, or another supported I/O path outputs step/dir.
- Drive options: standard stepper driver, MKS closed-loop stepper board, ODrive in step/dir mode, or another servo drive accepting step/dir.
- Drive feedback/fault lines must be wired back into LinuxCNC where possible.

This path is closest to current 3D-printer hardware, but it risks reducing smart drives to black-box step counters.

### Path 3: LinuxCNC + richer drive command interface

Investigate after basic step/dir proof works.

- ODrive via CAN, serial/USB helper, or HAL userspace/realtime bridge.
- Industrial servo via analog velocity/torque command plus encoder feedback.
- SimpleFOC or custom BLDC controller with explicit phase/velocity feedback.

This path is more work, but it better tests the value of LinuxCNC as a real closed-loop motion core.

### Path 4: LinuxCNC + Remora

Remora is interesting because it targets inexpensive controller boards and keeps the low-cost StitchLAB hardware philosophy closer than Mesa-only industrial builds.

Investigation tasks:

- Check current Remora board support for available hardware.
- Test latency and step timing for `XYA`.
- Verify limit switch, encoder/index, analog input, and fault input support.
- Decide whether Remora is stable enough for an education/community machine or only for research prototypes.

### Path 5: grblHAL controller board

Use this for the lightweight comparison phase.

- Select a grblHAL-supported board with enough axes and IO for `X/Y/A`, endstops, E-stop, drive faults, and needle index.
- Enable and verify 3rd-order acceleration / jerk settings on the exact build.
- Test G-code streaming, planner buffer behavior, realtime commands, status reports, alarms, homing, and jog.
- Decide whether a custom plugin can safely implement needle-phase scheduling.

### Path 6: custom Ruckig or `libscurve` motion daemon plus MCU bridge

Use this only after baseline LinuxCNC/grblHAL behavior is understood.

- Host process generates setpoints or velocity targets.
- MCU bridge owns deterministic step timing, encoder timestamping, watchdog, and hard IO.
- Ruckig or `libscurve` is used for local transitions, not whole-file planning.

## 9) Required I/O map

Minimum prototype inputs:

- E-stop.
- X min/endstop.
- Y min/endstop.
- A index or needle-up sensor.
- Optional A quadrature/absolute encoder.
- Drive fault input for each powered axis.
- Foot pedal analog or PWM input for Hybrid tests.

Minimum prototype outputs:

- X step/dir/enable.
- Y step/dir/enable.
- A step/dir/enable or velocity/torque command.
- Drive reset/clear-fault where supported.
- Sewing motor enable for continuous-mode tests.
- Optional status outputs for lamps, solenoids, cutter, or feeder.

Derived realtime signals:

- `needle_phase_deg`.
- `needle_up_window`.
- `needle_down_window`.
- `xy_motion_allowed`.
- `stitch_counter`.
- `phase_error`.
- `drive_fault_any`.

## 10) Backend-neutral system layers

The current Klipper path uses Mainsail/StitchLAB OS plus Moonraker as the browser API and service layer. LinuxCNC and grblHAL should not directly replace the whole product layer. The proposed architecture is:

```text
StitchLAB OS frontend
        -> stitchlabd HTTP/WebSocket API
        -> MotionBackend adapter
              KlipperAdapter
              LinuxCNCAdapter
              GrblHALAdapter
              RuckigAdapter
        -> motion controller / motion daemon
```

`stitchlabd` should own:

- WebSocket status stream for the UI.
- File upload, file list, job metadata, and preview metadata.
- Machine mode: embroidery, sewing, service, OpenRSS.
- Controller/dongle state, pairing, RSSI, battery/status, and UI feedback.
- Job start, pause, resume, cancel.
- Homing, jog, single-stitch, sewing-speed, and mode commands.
- Safety-state aggregation from motion backend, dongle, gantry detect, and drive faults.
- Settings database and backend adapter selection.

LinuxCNC should own:

- Realtime motion.
- Homing/index and joint/axis limits.
- Encoder feedback and phase signals.
- Drive faults and E-stop chain.
- Step generation or servo command path.
- HAL logic for `needle_phase`, `needle_up_window`, and machine interlocks.

grblHAL should own:

- Embedded G-code execution and motion planning.
- Step generation.
- Homing, limits, alarms, and basic jog.
- Realtime status and commands.

Ruckig/custom backend should own:

- Local state-to-state trajectory generation.
- Reactive transitions.
- Setpoint generation for an MCU or smart-drive bridge.

The current `live_jogd` should evolve into, or be wrapped by, this backend-neutral service. The controller/dongle protocol should remain product-level StitchLAB infrastructure rather than LinuxCNC-specific or grblHAL-specific code.

Backend-neutral command surface:

```text
jog_xy(vx, vy)
stop_motion()
emergency_stop()
set_sewing_speed(spm)
single_stitch()
home(axis)
set_mode(sewing | embroidery | service | openrss)
query_machine_state()
```

Backend adapters translate these commands:

- Klipper: Moonraker HTTP/WebSocket plus G-code macros.
- LinuxCNC: Python/NML command/status/error channels, HAL pins, and/or `halui`.
- grblHAL: serial/TCP stream, realtime commands, status parser, alarm/error parser, and custom plugin hooks where needed.
- Ruckig/custom: direct motion-daemon calls plus MCU/drive bridge.

## 11) Development phases

### Phase 0: specification and safety model

Deliverables:

- Define the first machine geometry: travel, units, axis directions, handwheel ratio, and safe needle phase window.
- Decide initial motor/drive for the A axis.
- Write a first LinuxCNC signal table for E-stop, homing, drive enable, drive fault, needle phase, and XY gate.
- Define the first `stitchlabd` backend-neutral command/status contract.
- Define what condition immediately disables motion.

Exit criteria:

- No unresolved safety-critical signal paths.
- Agreement on Model A as the first test, with Model B kept as the Hybrid target.
- Agreement that controller/dongle UX stays above the motion backend, not inside LinuxCNC/grblHAL.

### Phase 1: LinuxCNC simulation config

Deliverables:

- A LinuxCNC `XYA` sim config.
- Trivial kinematics with `X`, `Y`, and angular `A`.
- Example G-code generated from a small embroidery pattern.
- A HAL simulation signal for needle phase and needle-up window.
- If feasible, a second sim config using `TPMOD=tpmod_scurve`.
- First notes on whether standard LinuxCNC preview and controls are usable enough for development.

Tests:

- Homing simulation.
- Run 10, 100, and 1000 stitch files.
- Verify `A` phase modulo logic.
- Verify inverse-time feed experiments for coordinated `XYA` moves.
- Test `G64 P0.01 Q0.0` and measure whether small stitch segments are preserved.
- Compare stock/devel planner behavior against `tpmod_scurve` behavior if available.

Exit criteria:

- The simulation can run a generated embroidery sequence without confusing axis semantics.
- The team can inspect commanded `A`, derived needle phase, and XY motion timing.
- The team knows whether `tpmod_scurve` is worth moving to bench hardware.

### Phase 2: one-axis handwheel bench

Deliverables:

- One physical rotary axis on the bench.
- A motor, encoder or index sensor, drive enable, and drive fault input.
- LinuxCNC homing/indexing of the rotary axis.
- Measurement of commanded vs actual phase.

Candidate tests:

- Stepper driver open-loop baseline.
- Closed-loop stepper board in step/dir mode.
- ODrive in step/dir mode.
- ODrive or other servo in velocity/position mode if a usable LinuxCNC interface is available.
- `libscurve` or Ruckig-only speed transition simulation for comparison, without coupling it to machine control yet.

Exit criteria:

- Repeatable homing/index.
- Known phase error at target stitch rates.
- Drive fault propagates into LinuxCNC and disables motion.
- Clear recommendation for the first machine-mounted A-axis hardware.
- Clear decision whether LinuxCNC HAL, drive firmware, or a custom daemon should own handwheel velocity transitions.

### Phase 3: XY gantry bench without needle

Deliverables:

- Physical `X/Y` gantry under LinuxCNC.
- Rotary A-axis or simulated needle phase.
- Realtime `xy_motion_allowed` signal.
- Test embroidery jobs with the needle removed or no fabric installed.

Tests:

- XY motion with A coordinated as an axis.
- XY motion gated by a needle-up signal.
- Feed-rate and acceleration sweeps.
- Emergency stop during XY move and during A rotation.
- Power cycle and re-home behavior.
- `tpmod_scurve` versus stock/devel planner comparison for many tiny stitch segments.
- grblHAL comparison test on the same or equivalent `XYA` motion if hardware is available.

Exit criteria:

- XY never moves outside the configured safe phase window in gated tests.
- Faults stop the machine predictably.
- Position and phase logs are good enough for comparison with Klipper.
- S-curve/blending settings are either accepted with measurable accuracy or rejected for embroidery path fidelity.

### Phase 4: Hybrid machine no-thread test

Deliverables:

- LinuxCNC controls a real StitchLAB Hybrid prototype.
- Needle installed only after dry tests are stable.
- Foot pedal input appears in HAL and can command or scale handwheel speed in the continuous-mode model.
- First comparison against Klipper Classic behavior.

Tests:

- No-thread stitch cycle at low speed.
- Slow continuous motor mode with XY gating.
- Foot-pedal speed control.
- Long-jump movement behavior.
- Recovery after pause, stop, and fault.
- Pendant/gamepad jog through the backend-neutral controller service.
- Foot-pedal command path through HAL/backend adapter rather than backend-specific UI code.

Exit criteria:

- Demonstrated safe needle-up XY movement.
- Demonstrated continuous or semi-continuous handwheel operation.
- Measured stitch rate, phase accuracy, missed-step/following-error behavior, and usability.
- The same StitchLAB controller service can command at least two backends in principle, even if only one is physically wired.

### Phase 5: OpenRSS expansion test

Deliverables:

- Add one extra sewing actuator beyond the handwheel, likely take-up lever or hook/bobbin phase.
- Add one auxiliary technical-embroidery process actuator or sensor in simulation or bench form, such as a thread/material tension sensor, technical-material feeder, swing-foot axis, or clamp-state input.
- Decide whether this actuator is a coordinated axis, a HAL component, or a custom kinematics element.
- Feed measured actuator phase data back into StitchLABsim.
- Define the first process-parameter schema for OpenRSS jobs: stitch family, backing material, thread/material type, stitch distance, stitch width/stroke, target tension, and minimum bend radius.

Exit criteria:

- LinuxCNC can coordinate or monitor at least two sewing-phase actuators.
- The prototype can log at least one process variable beyond phase and position, such as thread tension, feeder error, clamp state, or swing-foot position.
- The prototype reveals whether OpenRSS should use LinuxCNC alone, LinuxCNC plus ROS 2, or a custom embedded realtime controller.
- Ruckig/`libscurve` has been evaluated for transitions between OpenRSS phase profiles, not as the large embroidery planner.

## 12) Evaluation criteria

LinuxCNC is a strong candidate if the prototype demonstrates:

- Native and understandable `XYA` machine configuration.
- Reliable homing and index handling for the handwheel/needle phase.
- Clean drive fault and E-stop behavior.
- Encoder feedback can be used in the realtime control path.
- XY motion can be phase-gated without brittle userspace timing.
- Closed-loop drives can be integrated with more useful feedback than step/dir alone.
- Existing StitchLAB G-code workflows can be adapted without losing the education-friendly workflow.
- The added complexity is justified by safety, speed, synchronization, or future OpenRSS capability.
- At least one auxiliary OpenRSS process device can be represented cleanly as a HAL signal/component or coordinated axis without making the job format backend-specific.
- `tpmod_scurve` or LinuxCNC devel S-curve improves motion smoothness without damaging stitch accuracy.
- Foot pedal, pendant/gamepad, and controller status can be routed through a backend-neutral StitchLAB service.

LinuxCNC is not a good fit if:

- The UI and deployment cost become too high for the project audience.
- Closed-loop drive integration still ends up as black-box step/dir only.
- Needle synchronization requires fragile custom patches instead of maintainable HAL components.
- The system cannot be packaged into a reproducible image or setup script.
- The prototype cannot maintain clearer safety behavior than Klipper.
- Experimental planner patches are too hard to build, package, or maintain.
- StitchLAB-specific controller UX becomes trapped inside LinuxCNC UI/HAL code instead of remaining portable.

grblHAL is a strong lightweight candidate if:

- `X/Y/A` motion, homing, alarms, jog, and S-curve/jerk settings work reliably on affordable hardware.
- A custom plugin or extension can implement needle-phase scheduling cleanly.
- It can report enough status for StitchLAB OS and controller devices.

grblHAL is not a good fit if:

- Needle-phase scheduling requires fragile planner forks.
- Closed-loop feedback and drive faults remain too opaque.
- OpenRSS needs outgrow the CNC-shaped embedded model quickly.

Ruckig/`libscurve` is a strong optional layer if:

- It improves reactive modes: foot pedal, jog, safe stop, OpenRSS phase transitions.
- It stays below a clean StitchLAB scheduler interface.

Ruckig/`libscurve` is not a good main planner if:

- It needs to own whole embroidery files, file streaming, homing, E-stop, or machine UI.

## 13) Data to collect

For each hardware phase, record:

- Maximum reliable stitch rate.
- Needle phase error at low, medium, and high speed.
- XY move duration vs needle-up window.
- Take-up, hook/bobbin, or auxiliary actuator phase error when present.
- Thread or technical-material tension, including peak, average, oscillation, and fault thresholds.
- Material feeder command vs measured motion or spool speed when present.
- Swing-foot/stroke position and timing when present.
- Clamp state, backing tension, or frame repeatability when present.
- Material/path constraint violations, especially minimum bend radius and dense small-stitch regions.
- Homing repeatability.
- Following error or drive error events.
- CPU load and realtime latency.
- E-stop response behavior.
- Fault recovery steps.
- G-code conversion issues.
- Setup complexity and documentation burden.
- Planner cycle time, worst-case cycle time, and buffer depth.
- S-curve jerk settings, acceleration extrema, and observed vibration.
- Segment filtering or geometry deviation caused by `G64`, `Q`, clothoid blending, or path smoothing.
- Backend API latency for jog, pedal, stop, and E-stop command paths.
- Controller/dongle reconnect and watchdog behavior independent of backend.
- Process-specific failure events: thread break, material break, feeder stall, bobbin-out, tension-out-of-range, and clamp/fiducial mismatch.

## 14) Software deliverables

Recommended folder/repo outputs:

- `linuxcnc/stitchlab_hybrid_sim/`
- `linuxcnc/stitchlab_hybrid_bench_a_axis/`
- `linuxcnc/stitchlab_hybrid_xy_a/`
- `linuxcnc/stitchlab_hybrid_xy_a_scurve/`
- `grblhal/stitchlab_hybrid_xy_a/`
- `stitchlabd/`
- `linuxcnc/hal_components/`
- `linuxcnc/test_gcode/`
- `linuxcnc/notes/`

Expected files:

- LinuxCNC `.ini` files.
- LinuxCNC `.hal` files.
- Custom HAL components if needed.
- Test G-code files.
- G-code conversion notes from current StitchLAB/TurtleStitch output.
- Wiring diagrams.
- Safety checklist.
- Phase and position measurement logs.
- Process measurement logs for tension, feeder, clamp, and auxiliary actuator tests.
- Backend adapter stubs for Klipper, LinuxCNC, grblHAL, and Ruckig/custom.
- `stitchlabd` HTTP/WebSocket API draft.
- OpenRSS process-parameter schema draft for F-Head/lockstitch, W-Head tailored placement, and K-Head chain/moss variants.

## 15) G-code strategy

Start with a minimal dialect that does not depend on Klipper macros.

Example Model A stitch concept:

```gcode
G21 G90
G93
G1 X10.000 Y5.000 A360.000 F120
G1 X10.500 Y5.200 A720.000 F120
G1 X11.000 Y5.400 A1080.000 F120
M2
```

This treats `A` as continuous handwheel rotation. The G-code generator should also emit metadata comments for stitch number, jump/travel type, and color/tool changes.

For LinuxCNC S-curve tests, explicitly test path control settings:

```gcode
G64 P0.01 Q0.0
```

Do not assume blending is harmless. Embroidery path fidelity must be measured because small stitch segments and sharp corners can be altered by path tolerance or segment filtering. `Q0.0` should be tested first because the `tpmod_scurve` docs warn that omitting `Q` or using `Q > 0` can filter tiny segments or alter geometry.

For Model B, the G-code may become mostly XY path commands while HAL or a custom component synchronizes release of each move to the needle-up window. This needs investigation; it may require queueing logic outside ordinary RS274 G-code.

For grblHAL, the G-code strategy must also include streaming behavior:

- Planner-buffer fill strategy.
- Realtime feed hold/resume.
- Alarm recovery.
- Status report normalization into `stitchlabd`.

## 16) UI and integration strategy

The first prototype can use LinuxCNC's existing UI and command tools. Do not build a StitchLAB UI until the motion questions are answered.

Later integration options:

- Keep LinuxCNC UI for development and only export measurement data back to reports.
- Build `stitchlabd` as the backend-neutral web bridge for job upload/start/stop/status if LinuxCNC or grblHAL proves viable.
- Keep Mainsail/StitchLAB OS as the Klipper UI only, and create a separate StitchLAB LinuxCNC frontend later.
- Investigate whether parts of G-Code Studio and TurtleStitch export can target Klipper, LinuxCNC, and grblHAL through the same job model.
- Keep controller/dongle UX in StitchLAB OS and `stitchlabd`, not in LinuxCNC Axis/QtVCP or grblHAL firmware.

## 17) Risks and mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LinuxCNC setup is less accessible than Klipper | Hurts education/community adoption | Keep Classic on Klipper; evaluate image/script-based setup only after prototype success |
| Realtime Linux tuning consumes too much time | Slows research | Start in sim, then use known-supported hardware paths |
| Closed-loop drives only use step/dir | Limited benefit over Klipper | Require drive fault/feedback tests; investigate richer interfaces in Phase 2 |
| Needle gating is difficult inside ordinary G-code | May need custom HAL/component work | Treat Model B as explicit research; do not force it into plain G-code if the model is wrong |
| LinuxCNC UI is CNC-focused, not embroidery-focused | Poor user experience | Delay UI judgment; first evaluate motion kernel only |
| Mixed units for linear XY and angular A are confusing | Bad G-code and tuning errors | Use clear unit conventions and test `G93` inverse-time moves |
| High-voltage sewing motor control is unsafe | Hardware risk | Keep initial tests on low-voltage motors or isolated bench hardware |
| `tpmod_scurve` is experimental/patched LinuxCNC | Maintenance and packaging risk | Treat as research track; require clean-build instructions and simulator tests before machine use |
| S-curve/path blending changes stitch geometry | Embroidery quality risk | Test `G64 P/Q` settings on known patterns and compare output path error |
| grblHAL requires custom phase plugin | Firmware maintenance risk | Scope a small proof first: needle index, hold/release, alarm behavior |
| Ruckig waypoint limitations are misunderstood | Wrong architecture | Use Ruckig only for local online moves and reactive transitions unless a separate planner/scheduler exists |
| Controller UX couples to one backend | Blocks future backends | Put controller/dongle state in `stitchlabd`; keep backend adapters narrow |
| License/package issues in experimental S-curve repos | Redistribution risk | Review licenses before shipping images or binaries |
| OpenRSS expands into too many auxiliary tools at once | Prototype loses focus | Add one stitch actuator and one process variable first; keep W/K/F-head models as job metadata and simulation targets until bench hardware exists |
| Material handling is treated as non-realtime | Thread/material breakage and poor stitch quality | Put tension, feeder, clamp, and swing-foot signals on the realtime side when they affect stitch timing or safety |

## 18) Decision gate

After Phase 4, make a documented decision:

1. Keep LinuxCNC as an OpenRSS research-only platform.
2. Use LinuxCNC for StitchLAB Hybrid and keep Klipper for StitchLAB Classic.
3. Use LinuxCNC plus `tpmod_scurve` for continued research only, but not community builds.
4. Use grblHAL as the lightweight Hybrid motion kernel and keep LinuxCNC for OpenRSS research.
5. Continue with Klipper plus custom MCU/drive firmware instead of LinuxCNC.
6. Split the system: LinuxCNC/grblHAL/custom motion for realtime motion, StitchLAB software for UI/workflow.

The decision should be based on measured synchronization, stitch accuracy, fault behavior, speed, planner smoothness, setup complexity, packageability, and how much custom code is required.

## 19) Immediate next actions

1. Create a LinuxCNC simulator config for `X/Y/A`.
2. Create a second LinuxCNC simulation attempt using `TPMOD=tpmod_scurve` from `linuxcnc_scurve_compact`.
3. Generate tiny, medium, and large LinuxCNC-compatible test embroidery files from existing StitchLAB coordinates.
4. Define the A-axis phase convention: `0 deg = needle up`, `180 deg = needle down`, continuous positive rotation counts stitches.
5. Test `G64 P0.01 Q0.0` against known small-stitch patterns and measure geometry deviation.
6. Draft the `stitchlabd` backend-neutral command/status API.
7. Choose the first bench A-axis hardware: standard stepper baseline plus one closed-loop candidate.
8. Write the first HAL signal map for `needle_phase`, `needle_up_window`, `xy_motion_allowed`, `drive_fault_any`, and `estop`.
9. Scope a grblHAL `X/Y/A` comparison test with the same generated G-code.
10. Scope where Ruckig or `libscurve` could be used for foot-pedal/jog transitions without owning the main embroidery planner.
11. Draft the OpenRSS process-parameter schema using F-Head lockstitch, W-Head tailored placement, and K-Head chain/moss stitch as the first three process families.
12. Choose the first auxiliary process measurement for Phase 5, preferably thread/material tension because it affects lockstitch reliability and W-Head feeding.
13. Record results in this document or a follow-up test report.
