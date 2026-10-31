# Proposal: machines that coexist on the workshop hotspot (beta5)

> **Status:** proposal, not implemented. Written 2026-09-29 from the second
> hardware run (image `20260927-814dd93`, report
> `docs/reports/2026-09-28-20260927-814dd93-commissioning.md`) and a read of
> the same machine from the Pixel 7 Pro workshop hotspot
> (`Android/Pixel7Pro/docs/stitchlab-status.md`, section "A beta4 machine on
> StitchlabSRV, 2026-09-29"; that section calls the machine beta4, but it ran
> `20260927-814dd93`).

A workshop runs four to six machines on one hotspot, `StitchlabSRV` (the
Pixel 7 Pro). Every card currently comes up with the same identity. This
proposal covers what beta5 needs so that several machines can share that
hotspot, and the `live_jogd` start failure seen on the same machine.

---

## 1. A unique hostname without a human step

**Now.** The build writes one fixed name: `DIST_HOSTNAME` and
`BASE_OVERRIDE_HOSTNAME` in `stitchlabos/image/src/config`, and
`STITCHLABOS_HOSTNAME` in the stitchlabos module, all `stitchlab`. A second
machine on the same hotspot collides; Avahi renames one of them to
`stitchlab-2.local`, and which one wins depends on boot order, so the kiosk
shows names that do not map to a physical machine.

**Proposal.** A oneshot unit, `stitchlab-hostname.service`, runs once on first
boot:

- If the hostname is still the image default `stitchlab`, set it to
  `stitchlab-<last four hex digits of /proc/device-tree/serial-number>`, for
  example `stitchlab-3f2a`, with `hostnamectl` and in `/etc/hosts`.
- If anything else set a name (Imager customisation, cloud-init user-data, a
  human), leave it alone.
- Run before `avahi-daemon.service`, so the first announcement already
  carries the final name, and after cloud-init's init stage, so a name from
  Imager is seen.

The name derives from the board, so it survives reflashing the same Pi and can
be printed on a label. Four hex digits make a clash between six machines
unlikely (about 1 in 4 400); the unit logs the name it chose.

**To verify on hardware.** `/etc/cloud/cloud.cfg` runs `set_hostname` and
`update_hostname` with `preserve_hostname: false`. Raspberry Pi's cloud-init
`25.2-1~bpo13+1+rpt20` says it honours a hostname changed with `hostnamectl`
on later boots; check that the new name survives two reboots.

**Commissioning.** `11-commissioning.md` step 2 gets one line: the machine's
name is `stitchlab-xxxx`, shown on the Pixel kiosk and on the label; rename it
with `sudo hostnamectl set-hostname` if the workshop numbers its machines.

## 2. The fallback access point carries the same suffix

Every machine that finds no known network raises the same AP, `Stitchlab` at
`192.168.50.5` (`stitchlabos/image/src/modules/accesspopup/start_chroot_script`).
Two machines in fallback mode in one room broadcast the same SSID, and a user
who joins `Stitchlab` reaches whichever one answers. The workshop hotspot was
renamed to `StitchlabSRV` on 2026-09-27 for this reason.

**Proposal.** The unit from section 1 also sets the AP profile's SSID to the
same suffix (`Stitchlab-3f2a`), so the SSID, the hostname and the label agree.
The AP's address can stay `192.168.50.5`: only one machine is reached per AP.

## 3. Joining `StitchlabSRV`

A machine needs a saved NetworkManager profile for the hotspot; AccessPopup
then prefers it over the fallback AP (seen on 2026-09-28: its timer switched
from the AP to `StitchlabSRV` on its own). The password is not in any repo and
must not be.

Two ways, both without new code:

- **Imager customisation** on the `--repo …/os_list.json` path can write the
  Wi-Fi network into the card. It is greyed out for *Use custom*.
- **Settings → Wi-Fi** in Mainsail, once the two defects below are fixed.

The Wi-Fi manager has two defects that the 2026-09-28 run hit exactly on this
path:

- **Save and connect creates two profiles.** `submitNetworkForm` awaits the
  store action `addNetwork`, but that action only emits and returns
  (`mainsail/src/store/server/wifiManager/actions.ts`), so `connect` goes out
  at the same moment. `_handle_connect` finds no saved profile yet and runs
  `nmcli device wifi connect`, which creates its own; `add_network` creates a
  second one with the same name. `wifi_status.sh` and `wifi_profiles.sh` then
  read both and emit a raw newline inside the SSID, and `server.wifi.status`
  and `server.wifi.profiles` fail. Fix: make `addNetwork` wait for the reply;
  let `_handle_connect` look up an existing profile with `nmcli` itself, not
  through the script; have the scripts select by UUID.
- **AP mode from the Wi-Fi page does not hold.** `_handle_ap_enable` brings
  up the `AccessPopup` profile but leaves `AccessPopup.timer` running; the
  next timer run (every 2 minutes, 11 s later in the run) sees a known network
  and leaves the AP. AccessPopup's own `accesspopup -a` stops the timer first,
  and a plain `accesspopup` run restarts it. Fix: call those two, which needs
  both added to `/etc/sudoers.d/020-stitchlab-wifi`.

## 4. `live_jogd` ends up `failed` from normal clicks

**Seen.** With no dongle plugged in, Moonraker reported `live_jogd`
`active_state: failed`. The journal of 2026-09-28 (times BST):

| Time | Event |
|---|---|
| 23:20:51 | start 1 (Controller menu, *Play*); the `ExecCondition` waits up to 30 s for `/dev/stitchlab-dongle` |
| 23:21:03 | *Refresh* sends `machine.services.restart`; systemd kills the waiting condition: `Failed with result 'signal'`, start 2 |
| 23:21:33 | `No StitchLab dongle … not starting`, `Skipped due to 'exec-condition'`, unit inactive |
| 23:24:04 | start 3 |
| 23:24:11 | killed again, then `Start request repeated too quickly`, unit `failed` |
| 23:24:16, 23:24:18 | further starts refused |

The daemon never ran; Klipper, Moonraker and the unit's dependencies were
fine. `StartLimitBurst=3` in `StartLimitIntervalSec=300` was meant to stop a
crashing daemon, but it counts every start, including the user's clicks, and
every click during the 30-second wait kills the condition. The unit then stays
`failed` until the next start after the window. The panel shows "No controller
paired", "Service offline", "Controller service is not running", and never
says that no dongle is plugged in.

**Proposal.**

1. Replace the 30-second `ExecCondition` loop with
   `ConditionPathExists=/dev/stitchlab-dongle`. It is checked at once, there is
   no process to kill, and a skip is not a failure.
2. Let the dongle start the unit: add `TAG+="systemd",
   ENV{SYSTEMD_WANTS}="live_jogd.service"` to
   `99-stitchlab-dongle.rules`, so plugging in the dongle is enough and the
   wait for a just-plugged dongle is no longer needed. The rule's comment still
   says ESP32-C3; `303a:1001` is Espressif's USB serial/JTAG ID, which the
   ESP32-C6 dongle uses as well.
3. Drop the start limit (`StartLimitIntervalSec=0`) and slow a crashing
   daemon down instead: `Restart=on-failure`, `RestartSec=3`,
   `RestartSteps=5`, `RestartMaxDelaySec=300` (systemd 257 on the image).
   A crash loop then backs off to one start every five minutes rather than
   ending in a `failed` state that only a later click clears.
4. In the Controller menu, show "No dongle connected" when
   `/dev/stitchlab-dongle` is absent, instead of "Service offline".

**To verify.** Whether systemd 257 counts a condition-skipped start toward the
start limit. It tests the limit before conditions, so skips probably count;
with step 3 that no longer matters, but the test decides whether steps 1 and 2
alone would be enough.

## 5. `.local` on Android

Android phones on the hotspot, and Chrome on the Pixel, did not resolve
`stitchlab.local`; a Mac did, and phones reached Mainsail by address. No
StitchLabOS document promises `.local` on phones. `11-commissioning.md` gives
`http://stitchlab.local` with the AP address as the alternative; add one
sentence there that Android needs the address, and that on the workshop
hotspot the Pixel kiosk shows it as a QR code.

## Order

1. Section 4 (`live_jogd`): small, self-contained, testable without the
   hotspot.
2. Section 3 (Wi-Fi manager defects): blocks joining the hotspot from the UI.
3. Sections 1 and 2 (hostname and AP suffix): one unit, then one hardware run
   with two cards on `StitchlabSRV`.
4. Section 5: one sentence.
