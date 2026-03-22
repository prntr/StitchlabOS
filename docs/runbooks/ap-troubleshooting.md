# AP Mode Troubleshooting

> Troubleshooting guide for Mainsail access when Pi is in Access Point (AP) mode via AccessPopup.

## Quick Reference

| Item | Value |
|------|-------|
| AP Profile | `AccessPopup` |
| AP IP | `192.168.50.5` |
| AP SSID | `Stitchlab` |
| AP Password | `praxistest` |
| Mainsail Port | `80` |
| Moonraker Port | `7125` |

## Known Issues

### Issue 1: Mainsail Shows "Remote Mode" Message

**Symptom:** Browser shows "Hello and welcome to the remote mode of Mainsail!" when accessing via IP.

**Root Cause:** `config.json` has `instancesDB: "browser"` instead of `"moonraker"`.

When `instancesDB` is `"browser"`:
- Mainsail shows the "Add Printer" dialog (remote mode)
- User must manually add printers
- This is intentional for multi-printer setups

When `instancesDB` is `"moonraker"` (stock default):
- Mainsail auto-connects to Moonraker at the same host
- No remote mode dialog
- Single printer, local access

**Files to Check:**
- `/home/pi/mainsail/config.json` - Check `instancesDB` value

**Fix:**
```bash
cat > /home/pi/mainsail/config.json << 'EOF'
{
    "defaultLocale": "en",
    "defaultMode": "dark",
    "defaultTheme": "mainsail",
    "hostname": null,
    "port": 7125,
    "path": null,
    "instancesDB": "moonraker",
    "instances": []
}
EOF
```

**Source:** `TheSelectPrinterDialog.vue:226` - Remote mode UI only shows when `instancesDB === 'browser'`

**Browser Cache Issue:** Mainsail uses a service worker that aggressively caches. After config changes:
1. Open DevTools (F12) → Application → Service Workers → Unregister all
2. Application → Storage → Clear site data
3. Close tab completely, reopen in incognito window

---

### Issue 1b: CORS Error When Accessing via IP

**Symptom:** Browser console shows CORS errors when accessing `http://192.168.50.5`.

**Root Cause:** Moonraker's `cors_domains` doesn't include IP address patterns.

**Required CORS for IP Access:**
```ini
# In moonraker.conf [authorization] section
cors_domains:
    http://*
    https://*
    *://*.local
    *://*.lan
```

**Verification:**
```bash
grep -A10 "cors_domains" /home/pi/printer_data/config/moonraker.conf
sudo systemctl restart moonraker
```

---

### Issue 2: `stitchlab.local` Doesn't Resolve in AP Mode

**Symptom:** `ping stitchlab.local` returns old/wrong IP or fails.

**Root Cause:** In AP mode the Pi may end up with multiple network interfaces/addresses over time (WiFi client, AP, ethernet, etc.). mDNS can advertise more than one address for `stitchlab.local`, and some clients will cache or pick an address that is **not reachable** from the AP subnet.

**Important:** `.local` is handled via mDNS (multicast) on most operating systems. That means a dnsmasq “static DNS” entry generally will **not** override `.local` on many clients.

**Common gotcha:** If the Pi is also connected to a “normal” network (WiFi client / Ethernet, e.g. `192.168.0.x`), many clients will resolve `stitchlab.local` to that address. That’s not reachable from the AP subnet (`192.168.50.0/24`) unless the client is also on the `192.168.0.x` network.

#### macOS: Can Join AP, But Cannot Open Mainsail (Safari/Firefox)

This is almost always one of:
- macOS resolves `stitchlab.local` to the *old* (WiFi/Ethernet) IP (mDNS cache / multiple A records)
- a VPN route hijacks `192.168.50.0/24`
- a proxy setting forces HTTP traffic through a non-reachable proxy

Start with the “truth test” (bypasses DNS):
```bash
curl -I http://192.168.50.5/
```
Tip: type the full `http://192.168.50.5/` URL in the browser to avoid “HTTPS-first” auto-upgrades.

If `http://192.168.50.5` works but `http://stitchlab.local` doesn’t:
```bash
# Show what macOS currently resolves
dns-sd -G v4 stitchlab.local

# Flush caches
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
```

If you have AP-mode DNS configured, prefer the non-mDNS name:
```bash
# Uses normal DNS (via the AP’s dnsmasq), not mDNS
dscacheutil -q host -a name stitchlab.lan
```

If `dns-sd` shows an `IF` of `-1` and a very low TTL, you are likely seeing a cached entry (not a fresh answer from the AP).
In that case, verify mDNS is actually working on the AP:
```bash
# Should list services/devices seen via mDNS on the current network
dns-sd -B _workstation._tcp local.

# Check that you don't have a hard override
sudo grep -n 'stitchlab' /etc/hosts || true
```

If `/etc/hosts` contains a stale line like `192.168.0.131 stitchlab.local`, it will override mDNS and break AP-mode access via `.local`.
Fix (macOS):
```bash
sudo cp /etc/hosts /etc/hosts.bak
sudo sed -i '' '/\\sstitchlab\\.local\\b/d' /etc/hosts
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder

# Verify system resolution (this uses the system resolver, unlike dns-sd)
dscacheutil -q host -a name stitchlab.local
```

If mDNS browsing shows nothing on the AP, look for macOS firewall / VPN & Filters / network security tools blocking UDP 5353 multicast.
You can also sanity-check which interface you’re actually using:
```bash
route -n get 192.168.50.5
route -n get 192.168.0.131
```

If `http://192.168.50.5` does *not* work, check routing and proxy first:
```bash
# Ensure traffic goes via Wi-Fi (en0), not a VPN (utun*)
route -n get 192.168.50.5

# Check system proxy settings used by Safari (and often Firefox)
scutil --proxy
```

If there’s a VPN route conflict (route shows `utun*`), disconnect VPN (or change the AP subnet in the `AccessPopup` profile to a range your VPN doesn’t claim).

**Client-Side DNS Cache:**
```bash
# macOS - flush DNS
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder

# Check what IP is resolving
dns-sd -G v4 stitchlab.local
```

**Pi-Side Avahi Config:**
```bash
# Find which interface has the AP IP (usually `wlan0`, sometimes `uap0`)
ip -4 -o addr show | grep '192.168.50.5'

# Restrict Avahi to the AP interface so it advertises only the AP-reachable IP
# (replace wlan0 with the interface you found above)
sudo sed -i 's/^allow-interfaces=.*/allow-interfaces=wlan0/' /etc/avahi/avahi-daemon.conf || true
grep -q '^allow-interfaces=' /etc/avahi/avahi-daemon.conf || sudo sed -i '/^use-ipv6=yes/a allow-interfaces=wlan0' /etc/avahi/avahi-daemon.conf

# Alternative (often enough): just stop advertising on ethernet
# (use this if your "wrong" IP is on `eth0`, e.g. 192.168.0.x)
# sudo sed -i 's/^deny-interfaces=.*/deny-interfaces=eth0/' /etc/avahi/avahi-daemon.conf || true
# grep -q '^deny-interfaces=' /etc/avahi/avahi-daemon.conf || sudo sed -i '/^use-ipv6=yes/a deny-interfaces=eth0' /etc/avahi/avahi-daemon.conf

# (Optional) Enable reflector for AP mode
sudo sed -i 's/^#enable-reflector=no/enable-reflector=yes/' /etc/avahi/avahi-daemon.conf
grep "enable-reflector" /etc/avahi/avahi-daemon.conf
sudo systemctl restart avahi-daemon
```

**Alternative - Static DNS via dnsmasq (use a non-`.local` name like `stitchlab.lan`):**
```bash
# Create dnsmasq override for AP
sudo mkdir -p /etc/NetworkManager/dnsmasq-shared.d
cat | sudo tee /etc/NetworkManager/dnsmasq-shared.d/local-dns.conf << 'EOF'
address=/stitchlab.lan/192.168.50.5
address=/stitchlab/192.168.50.5
# Included for clients that do not treat `.local` as mDNS.
address=/stitchlab.local/192.168.50.5
EOF
sudo systemctl restart NetworkManager
```

**Then access Mainsail in AP mode via:**
- `http://192.168.50.5/` (always works)
- `http://stitchlab.lan/` (stable DNS in AP mode)

---

### Issue 3: Mainsail HTML Loads But Shows "Cannot Connect to Moonraker"

**Symptom:** Page loads but displays connection error with wrong IP (e.g., `192.168.0.131:7125`).

**Root Cause:** `config.json` has hardcoded hostname instead of `null`.

**Check:**
```bash
cat /home/pi/mainsail/config.json
```

**Expected Config (Stock):**
```json
{
    "defaultLocale": "en",
    "defaultMode": "dark",
    "defaultTheme": "mainsail",
    "hostname": null,
    "port": 7125,
    "path": null,
    "instancesDB": "moonraker",
    "instances": []
}
```

**Fix:**
```bash
cat > /home/pi/mainsail/config.json << 'EOF'
{
    "defaultLocale": "en",
    "defaultMode": "dark",
    "defaultTheme": "mainsail",
    "hostname": null,
    "port": 7125,
    "path": null,
    "instancesDB": "moonraker",
    "instances": []
}
EOF
```

**Key Points:**
- `hostname: null` → Uses `window.location.hostname` (browser's current host)
- `instancesDB: "moonraker"` → Auto-connects to local Moonraker (RECOMMENDED)
- `instancesDB: "browser"` → Shows remote mode dialog, requires manual printer add

---

### Issue 4: Services Running But Not Accessible

**Symptom:** `curl` works on Pi but browser can't connect.

**Diagnostic Commands (on Pi):**
```bash
# Check services
sudo systemctl status nginx moonraker klipper

# Check nginx listening
ss -tlnp | grep :80

# Check moonraker listening
ss -tlnp | grep :7125

# Test locally
curl -I http://localhost
curl http://localhost:7125/server/info

# Get current IP
hostname -I
```

**Check AP Configuration:**
```bash
nmcli connection show AccessPopup | grep -E 'ipv4\.(addresses|method)'
# Expected: ipv4.method: shared, ipv4.addresses: 192.168.50.5/24
```

---

## Configuration Files

| File | Location | Purpose |
|------|----------|---------|
| `moonraker.conf` | `/home/pi/printer_data/config/moonraker.conf` | CORS, trusted clients |
| `config.json` | `/home/pi/mainsail/config.json` | Frontend Moonraker connection |
| `avahi-daemon.conf` | `/etc/avahi/avahi-daemon.conf` | mDNS/hostname resolution |
| `AccessPopup` | NetworkManager connection profile | AP settings (SSID, IP, password) |

---

## Diagnostic Checklist

### From Pi (via SSH)

```bash
# 1. Services running?
systemctl status nginx moonraker klipper | grep Active

# 2. Ports listening?
ss -tlnp | grep -E ':(80|7125)'

# 3. AP active?
nmcli connection show --active | grep AccessPopup

# 4. Current IP?
hostname -I

# 5. Config correct?
cat /home/pi/mainsail/config.json | grep hostname
grep -A5 "cors_domains" /home/pi/printer_data/config/moonraker.conf

# 6. Local connectivity?
curl -I http://localhost
curl -I http://$(hostname -I | awk '{print $1}')
```

### From Client Device (connected to AP)

```bash
# 1. Got IP from AP?
# Should be 192.168.50.x
ipconfig getifaddr en0  # macOS
ip addr show wlan0      # Linux

# 2. Can reach Pi?
ping 192.168.50.5

# 3. Can reach nginx?
curl -I http://192.168.50.5

# 4. Can reach moonraker?
curl http://192.168.50.5:7125/server/info

# 5. DNS resolution?
dns-sd -G v4 stitchlab.local  # macOS
```

---

## Stock vs Custom Configuration

| Setting | Stock Mainsail | StitchLab (Recommended) |
|---------|---------------|-------------------------|
| `config.json hostname` | `null` | `null` |
| `config.json instancesDB` | `moonraker` | `moonraker` |
| `cors_domains` | `*://*.local`, `*://*.lan` | Add `http://*` for IP access |
| `trusted_clients` | Private ranges | Same |

**Important:** Use `instancesDB: "moonraker"` for single-printer setups. Using `"browser"` triggers remote mode dialog.

---

## Related Documentation

- [Mainsail Remote Mode](https://docs.mainsail.xyz/remotemode)
- [Moonraker Authorization](https://moonraker.readthedocs.io/en/latest/configuration/#authorization)
- [AccessPopup - RaspberryConnect](https://www.raspberryconnect.com/projects/65-raspberrypi-hotspot-accesspoints/203-automated-switching-accesspoint-wifi-network)
- [05-configuration.md](../05-configuration.md) - Ports and endpoints
- [06-troubleshooting.md](../06-troubleshooting.md) - General troubleshooting

---

## Resolution Summary

**Root Cause Found:** The "remote mode" message appears because `instancesDB` was set to `"browser"` instead of `"moonraker"`.

**Source Code Reference:** [TheSelectPrinterDialog.vue:226](../../mainsail/src/components/TheSelectPrinterDialog.vue#L226)
```vue
<template v-if="instancesDB === 'browser'">
    <!-- Remote mode dialog shown here -->
</template>
```

**The Fix:**
1. Set `instancesDB: "moonraker"` in `/home/pi/mainsail/config.json`
2. Set `hostname: null` to use dynamic host detection
3. Add `http://*` to `cors_domains` in moonraker.conf for IP access
4. Clear browser cache/service worker after changes
