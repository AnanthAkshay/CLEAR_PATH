# ClearPath Dashboard Screenshots Manifest

This directory stores visual screenshot assets referenced throughout [DASHBOARD_GUIDE.md](../DASHBOARD_GUIDE.md) and [DEMO_SCRIPT.md](../DEMO_SCRIPT.md).

## Required Screenshot Images

1. `overview_grid.png`
   - **View:** Full dashboard view showing the 2D road network, junction signal dots (Green, Yellow, Red), civilian vehicles (blue/gray dots), and hospital facility markers.
   - **Trigger:** Initial dashboard state after clicking `Reset` or advancing a few ticks.

2. `emergency_corridor.png`
   - **View:** Active emergency preemption corridor with thick orange polyline overlay (`#f0883e`), gold ambulance star marker (`AMB_1`), preemption halo rings, and coordinated green wave signals along the route.
   - **Trigger:** Scenario: "Valid emergency" with Preemption enabled.

3. `security_blocked_banner.png`
   - **View:** High-contrast security alert banner at top of dashboard showing `🚫 BLOCKED | Attack: Bad Signature` with `Reasons: TOKEN` and risk score.
   - **Trigger:** Scenario: "Spoofed request", Attack: "Bad Signature", clicking `🚨 Inject Attack`.

4. `kpi_metrics_row.png`
   - **View:** 5-card metric row showing Ambulance Transit Time, Cross-Traffic Delay, Attack Block Rate (100.0%), False-Positive Rate (0.0%), and Ambulance Stops (0).
   - **Trigger:** Post-run evaluation of the emergency preemption scenario.

5. `guidance_feed_tab.png`
   - **View:** Tabbed inspector showing the **Guidance & Advisories** rolling table with vehicle IDs, directional instructions ("Clear lane 0", "Slow down"), severity tags (CRITICAL, WARN, INFO), and VMS board status.
   - **Trigger:** Active emergency corridor running in high demand.

6. `hospital_triage_tab.png`
   - **View:** Tabbed inspector showing the **Hospital Triage Database** table with 4 regional hospitals, bed availability counts, specialty units, and calculated multi-criteria scores.
   - **Trigger:** Any dispatched emergency request.

