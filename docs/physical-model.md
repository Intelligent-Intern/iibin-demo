# Physical model — lcc-1.0.1

## Units, reference and sign

Internal units are seconds, coulombs, volts, amperes, joules, watts, farads and ohms. Display controls declare their units explicitly and convert once at the model boundary. Elementary charge is 1.602176634 × 10⁻¹⁹ C. Positive conventional current increases positive suit charge. Electron collection is negative; emission of escaping electrons is positive.

The suit is a constant lumped capacitance to a fixed reference: Q = CV and E = Q²/(2C). The separate environment and lander potentials describe external reservoirs. A change in environment potential changes the collection law; it does not silently reset the suit voltage or capacitance. Attached cable/contact capacitances are present from the start, not switched in without charge-sharing work. Select either initial voltage or charge; the other follows from the total capacitance. Internal harvester input charge and voltage use the same mutually exclusive selection.

## Plasma

Electron and ion saturation currents are ±e A Φ. Repulsive collection is attenuated by exp(−|ΔV|/T), with particle energy in electron-volts numerically equivalent to the voltage scale. Attractive currents saturate at the supplied flux; orbit-limited collection enhancement, secondary emission and spatial sheaths are omitted. Sunlit photoemission is a positive source attenuated for a positive suit; it vanishes in shade. The charge equation uses a bracketed backward-Euler step with a monotone current law, so stiff input values do not cause explicit-Euler runaway. This is a first-order lumped charging model, not a particle-in-cell solver.

Plasma work is the exact field-energy change assigned to its integrated current. It is signed electrical work, not a claim that the total kinetic energy of the ambient plasma can be harvested. The model does not solve the plasma's thermal energy balance.

## Contact and sole constructions

Each complete step transfers a prescribed reference charge scaled by contact area, square-root force, contact/release saturation, electrical coupling, regolith factor, contact-material factor and sole construction factor. These factors are assumptions, not measured material constants. Reference area/force are 180 cm² and 140 N; contact/release time constants are 0.10/0.05 s. Sole factors are 1.0, 0.65, 0.50, 0.65 and 0.20 for insulating, multilayer, electrode, generator and optimized constructions. Contact-material factors are 1.0 (polymer), 0.75 (composite), 0.40 (conductive). Users can vary the reference transfer and regolith/coupling terms rather than treating these values as a material database.

A prescribed contact charge is reduced when its positive field-energy cost would exceed available mechanical step work. The step ledger accounts for mechanical input, field change, internal generator extraction and residual dissipation. The internal generator uses a separate fraction of mechanical work; enabling it does not, by itself, remove external charge. An optimized or conductive contact also enables an explicit resistive path to the ground reference during the contact portion of the step. Conductivity is represented as an effective contact resistance, not a resolved material conductivity tensor.

## Harvesters

1. **Isolated HV converter:** draws from a separate internal capacitor, limited by input power and bus-voltage floor. External suit charge remains unchanged. The initial internal energy is included in total initial energy.
2. **Capacitive sharing:** two internal capacitors exchange charge through the configured transfer resistance. The differential mode decays analytically; lost field energy becomes heat. This internal circuit is not a neutralization path for the complete suit.
3. **Multistage converter:** the isolated converter with per-stage efficiency raised to the number of stages. No fabricated voltage gain or energy multiplication.
4. **Internal tribogenerator:** converts only the allocated step work after external field work. It is distinct from the net external transfer per step.
5. **Plasma collector with return:** an explicit idealized second electrode/reservoir at environment potential. Charge can cross the suit boundary. Reference work and released differential field energy are booked separately. Collector accessibility, space-charge limits and physical electrode geometry are not solved.

Finite storage capacity, storage leakage and user loads are active. The regulated output is an ideal, lossless output stage at the selected voltage; actual delivered load power is limited by remaining storage. Output current follows delivered power divided by output voltage. Converter switching and output regulation dynamics are not resolved. Conversion excess at the full storage voltage is dissipated. The intermediate bus voltage limits the simplified buck-converter input range; no detailed switching converter or maximum-power-point tracking is modeled. Every source of recovered energy is limited by its actual source reservoir or step work. The plotted accumulated harvested energy is an accounting counter, not additional stored energy to add again.

## Electron emitter

Escaping current equals commanded current × extraction efficiency × escape fraction. Returning electrons produce no net transfer. A hysteretic on/off voltage controller operates only for a negatively charged suit; it stops at the configured negative off threshold. Electrical power comes from the finite storage and is separately counted as emitter consumption. If power is unavailable, emission is reduced. A configured fault stops emission. Field-energy release from departing electrons is assigned to escaping-particle energy, not credited to storage. Extraction, escape fraction and power are independent idealized assumptions; field emission, space charge and return trajectories require a more detailed emission model.

## Lander discharge

The reference case follows the [NASA Tournament Lab challenge specification](https://work.crowdplat.com/challenge/lunar-grounding-challenge): 200 pF, an initial −100 kV suit, approximately +100 V lander, at most 1 mA with a design target ≤0.2 mA, at most 30 s, and a mass strictly below 20 kg.

The transfer solves d(ΔV)/dt = −clip(ΔV/R, ±I_limit)/C analytically. Above I_limit R, voltage falls linearly; below it, decay is exponential. Charge transferred to or from the lander, signed work V_lander ΔQ and the reduction of differential field energy are tracked separately. Recovery converts only a fraction of that released differential energy; remaining energy is dissipated. The numeric completion threshold defaults to |V_suit−V_lander| ≤10 V, an explicit experimental stopping assumption rather than a challenge requirement. Current peaks are evaluated before the transfer, not hidden by time-averaged samples. Interruptions open the contact at a deterministic time.

An ideal RC connection says nothing about pre-contact flashover, dust-enhanced arcing, dielectric withstand, astronaut current paths, contact mechanics, qualification or thermal endurance. The UI reports electrical limits and model completion; it does not label an untested physical contact as safe.

## Integrated EVA and spatial representation

A common 120 s example visits illumination, permanent shadow, return and lander contact. Phase boundaries are 18 %, 38 %, 65 % and 75 % of configured duration. Walking ends at contact. The integrated reference uses 300 MΩ with the explicit 0.2 mA current limiter, so the continued ambient plasma current does not prevent the 10 V completion threshold. The stand-alone passive-resistance reference remains 600 MΩ. Shadow changes environment potential and electron/ion flux factors and removes photoemission. All active components share one charge state, one storage state and one energy ledger. The stand-alone harvester has an explicit collector source but not the ambient collection law; use plasma or integrated modes for ambient exposure.

The scene has terrain geometry, PBR surfaces, directional lighting and cast shadows. The suit, lander and internal components are explorable. Particle counts, the charge shell and schematic motion illustrate calculated current/phase; they are not a field solution or calibrated particle-density rendering. Regolith charging, mechanical walking and surface morphology are prescribed rather than coupled granular dynamics.

## Conservation and numerics

Charge residual = Q_final − Q_initial − Σ transferred charge for plasma, contact, collector, emission, lander, ground leakage and auxiliary sources.

Energy residual = E_field + E_internal + E_storage + E_loss + E_load + E_emitter + E_escaping_particles − E_initial − (W_plasma + W_mechanical + W_reference + W_auxiliary).

Reference/auxiliary work can be negative. Recoverable energy, energy already stored, consumed energy and cumulative harvested energy are not counted twice. Residuals are shown directly. The fixed step is 0.02 s with exact boundaries for steps, EVA changes, failures and interrupted contact. Rendering schedules accumulate requested time without introducing fractional wall-clock steps. Plasma integration is first-order; the fixed model version and timestep belong to each reproducible experiment. Model assumptions and calculated results remain distinct from experimental measurements.
