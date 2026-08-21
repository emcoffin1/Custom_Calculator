# Conversions Calculator

A small, on-demand GTK 3 calculator for Linux desktops. It runs natively through GTK on KDE Plasma Wayland and on X11 desktops such as Linux Mint Cinnamon. It provides arithmetic, algebra/calculus, engineering calculations, and unit conversion.

The Basic tab is a structured scientific/algebra calculator. The Advanced tab adds numerical definite integrals, derivatives at a point, and finite summations using `x` as their expression variable. Advanced calculus expressions are displayed in textbook notation—with limits around `∫` and `Σ`, `dx`, and a stacked derivative—while a hidden semantic translation is used for evaluation. Both tabs use real editable math slots, arrow navigation, Ctrl+Z/`↶` undo, and hover hints for typed shortcuts.

## Run it

```bash
~/.config/conversions_calculator/launch.sh
```

The repository can be cloned anywhere; runtime state is kept outside the checkout at:

```text
${XDG_CONFIG_HOME:-~/.config}/conversions-calculator/state.json
```

An existing `state.json` beside `app.py` is read once as a migration source, so current settings are retained after updating.

## Clone and install

On Linux Mint, Ubuntu, Kubuntu, or KDE neon:

```bash
git clone YOUR_REPOSITORY_URL conversions-calculator
cd conversions-calculator
./install.sh --install-deps
```

After dependencies are installed, future updates are simply:

```bash
git pull
./launch.sh
```

`install.sh` creates a desktop launcher and the command `~/.local/bin/conversions-calculator`; it does not copy the source tree, so a later `git pull` updates the installed application immediately. If dependencies are already present, run `./install.sh` without `--install-deps`.

Required runtime packages are Python 3, PyGObject, GTK 3, and WebKitGTK 4.1. On non-apt distributions, install their equivalent packages and run `./launch.sh` directly.

Press Escape or click `×` to exit. Use Ctrl+Tab to switch tabs.

Launching the command again while the window is open toggles it closed. This lets one Cinnamon or Plasma global shortcut act as both open and close; duplicate calculator windows are prevented.

The selected tab, conversion dropdowns, and Engineering discipline/calculation/input/unit selections are restored on the next launch.

Switching tabs immediately focuses that tab's primary input.

The Engineering tab provides unit-aware Electrical, Mechanical, Structural, Fluids, Thermal, General, and Propulsion calculations. Its searchable data-driven registry currently contains 88 tools. Values are converted to coherent SI units internally, then displayed in the selected output unit.

Electrical tools include a combined external/internal IPC-2221 PCB trace page with a default 10 °C rise and optional automatic resistance, plus a live copper AWG/voltage-drop page. Propulsion is an Engineering discipline containing ideal-gas isentropic flow ratios, area ratio, static conditions, speed of sound, and velocity. A top-level switch controls whether entered values persist; tabs, dropdowns, and units always persist.

The Wire page includes a compact scrollable AWG reference popover with diameter, area, copper resistance at 20 °C, and the calculator's screening-current estimate. The estimate is not a universal ampacity; installation conditions and applicable code still govern conductor selection.

## Compact productivity tools

Secondary features stay hidden in footer popovers so the default window remains 470 pixels wide:

- `⌕` or **Ctrl+K** searches every calculation, formula, description, discipline, conversion category, and favorite.
- `◷` or **Ctrl+H** opens bounded, deduplicated history. Activating an entry restores its tab, fields, and units.
- **Ctrl+D** favorites the current Engineering calculation. Favorites have their own Engineering group and rank first in search.
- Click a result to copy it. Right-click for number-only/scientific/engineering formats, a reproducible report, sending the value to either calculator, or storing it as `ans`.
- **Ctrl+Shift+C** copies the current result.
- `⋮` changes result precision from 3–10 significant digits. This is the only display preference.

History and named variables persist only while **Save values** is enabled. Favorites, selected units/dropdowns, tab position, and result precision always persist.

For a read-only terminal health summary, run `python3 app.py --diagnostics`.

## Flexible input

Engineering fields accept a plain number in the selected dropdown unit or an explicit unit:

```text
4.7 kΩ
250 uA
3/8 in
12 V ±5%
12 V +/- 0.2 V
```

Typed units are dimension-checked; for example, a voltage cannot be entered in a length field. The Convert tab also accepts values such as `12 in` and updates its source unit automatically.

Basic and Advanced support safe named numeric variables:

```text
Vin=24
Vin/2
```

Basic and Advanced also accept dimension-checked unit arithmetic:

```text
3 ft + 200 mm
12 V / 220 Ω
5 A * 14 V
```

Names of constants, functions, and the calculus variable `x` are reserved. Expressions continue to use the restricted AST evaluator and cannot execute Python code.

Engineering results can use **Auto (best fit)** to select a practical SI-family unit. Explicit output-unit choices always win. Inputs with tolerances show nominal and endpoint worst-case ranges; this is interval analysis, not statistical uncertainty.

## Engineering coverage

- **Electrical:** DC relationships, divider, multi-component R/L/C networks, PCB traces/vias, wire sizing and voltage drop, E-series values, LED resistor, battery runtime, RMS/peak, three-phase power, reactance/RLC/filter response, decibels, dissipation/derating, and differential impedance estimates.
- **Mechanical:** force/energy/springs, shafts, hydraulics, gears, belts, bearings, bolt preload torque/stress, and safety factor.
- **Structural:** stress/strain, section properties, bending, combined and principal/von-Mises stress, reactions, beam deflection, and Euler buckling.
- **Fluids:** hydrostatics, Bernoulli, Reynolds/Haaland, Darcy–Weisbach, pump/hydraulic power, orifice flow, Cv/Kv, and choked ideal-gas flow.
- **Thermal:** sensible heat, conduction/convection/radiation, expansion, thermal-resistance networks, heatsinks, junction temperature, and enclosure rise.
- **Propulsion:** isentropic state ratios, nozzle exit state, thrust, specific impulse, exhaust velocity, mass flow, mixture ratio, and a compact 0–11 km standard-atmosphere model.

The `ⓘ` control exposes formula, description, assumptions, and a source label where a specific standard/model applies. Presets are stored in the `PRESETS` mapping in `engineering.py`, descriptions in `DESCRIPTIONS`, and source labels in `REFERENCES`, making them straightforward to review or edit.

These tools are engineering aids, not certification or code-compliance software. PCB, wire, structural, pressure-flow, thermal, fastener, and component calculations expose simplified-model limitations; verify safety-critical work against applicable standards, manufacturer data, and qualified review.

Primary references used for conventions and model choices include the [BIPM SI Brochure](https://www.bipm.org/en/publications/si-brochure), [NIST Guide to the SI](https://www.nist.gov/pml/special-publication-811), [IEC 60063 preferred component series](https://webstore.iec.ch/en/publication/22011), and [NASA Glenn compressible-flow equations](https://www.grc.nasa.gov/www/k-12/airplane/isentrop.html).

## Bind it to a shortcut

### KDE Plasma Wayland

Run `./install.sh`, then open **System Settings → Keyboard → Shortcuts**. Add or select **Conversions Calculator** and assign the desired key. Plasma supports application launchers as global shortcuts; the desktop entry enables startup activation so KWin can grant focus under Wayland.

Do not set `GDK_BACKEND=x11`: leaving the backend unset lets GTK use native Wayland in a Wayland session and X11 in an X11 session.

### Linux Mint Cinnamon

Open **System Settings → Keyboard → Shortcuts → Custom Shortcuts**, add a shortcut using:

```text
/home/ethan/.config/conversions_calculator/launch.sh
```

Then assign F16. The program starts only when invoked and exits when dismissed; no background service is required.
