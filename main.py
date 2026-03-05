import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Flat folder imports (No 'src.' prefix)
from physics import AdvancedDrillingPhysics
from economics import EconomicsAnalyzer
from equipment import (
    EquipmentSystemManager, PARTICLE_BINS, build_and_evaluate_equipment
)

# =============================================================================
# HELPER FUNCTION
# =============================================================================
@st.cache_data
def generate_dynamic_log(start_d, end_d, pp_base, fg_base, rop_base, step_ft=100):
    """Generates synthetic depth data points for simulation logging."""
    log = []
    points = np.arange(start_d + step_ft, end_d, step_ft)
    if len(points) == 0 or points[-1] != end_d: 
        points = np.append(points, end_d)
        
    for d in points:
        log.append((round(d, 1), round(9.0 + (d/2000.0), 2), round(pp_base + (d/3000.0), 2), round(fg_base + (d/2000.0), 2), rop_base))
    return log

# =============================================================================
# STREAMLIT FRONT-END UI
# =============================================================================
st.set_page_config(page_title="Drilling & Solid Control Simulator", layout="wide")

if "num_scenarios" not in st.session_state: st.session_state.num_scenarios = 2
if "sim_done" not in st.session_state: st.session_state.sim_done = False

for i in range(10):
    sn = f"Scenario {chr(65+i)}"
    if f"num_sh_{sn}" not in st.session_state: st.session_state[f"num_sh_{sn}"] = 1
    if f"num_cf_{sn}" not in st.session_state: st.session_state[f"num_cf_{sn}"] = 0 if i == 0 else 1

st.title("API First-Principles Drilling Simulator")
st.markdown("Engineering-grade modeling featuring **OOP PSD Tromp Curves, Formation Lithology**, and Mass Balance.")

st.sidebar.header("Global Configurations")

with st.sidebar.expander("Base Rig & Fluid Economics", expanded=False):
    rig_rate = st.number_input("Rig Lease Rate ($/Day)", value=35000.0, step=1000.0)
    mud_price = st.number_input("Fresh Mud Cost ($/bbl)", value=85.0, step=5.0)
    disp_price = st.number_input("Waste Disposal Cost ($/bbl)", value=18.0, step=2.0)
    target_lgs_des = st.number_input("Target LGS (Max Limit %)", value=6.0, step=0.5)

    st.markdown("**Fresh Mud Baseline (0% LGS) - Fann 35**")
    c1, c2 = st.columns(2)
    t600 = c1.number_input("600 RPM", value=55.0, step=1.0)
    t300 = c2.number_input("300 RPM", value=35.0, step=1.0)
    t200 = c1.number_input("200 RPM", value=28.0, step=1.0)
    t100 = c2.number_input("100 RPM", value=20.0, step=1.0)
    t6 = c1.number_input("6 RPM", value=8.0, step=1.0)
    t3 = c2.number_input("3 RPM", value=6.0, step=1.0)

with st.sidebar.expander("Well Trajectory & Lithology", expanded=False):
    st.markdown("**Section 1 (17.5\") - Surface**")
    len_sec1 = st.number_input("Length (ft) Sec 1", value=1250.0, step=100.0)
    gpm1 = st.number_input("GPM Sec 1", value=1050.0, step=50.0)
    lith1 = st.selectbox("Lithology Sec 1", ["Reactive Clay", "Firm Shale", "Sandstone"], index=0)

    st.markdown("**Section 2 (12.25\") - Intermediate**")
    len_sec2 = st.number_input("Length (ft) Sec 2", value=3500.0, step=100.0)
    gpm2 = st.number_input("GPM Sec 2", value=850.0, step=50.0)
    lith2 = st.selectbox("Lithology Sec 2", ["Reactive Clay", "Firm Shale", "Sandstone"], index=1)

    st.markdown("**Section 3 (8.5\") - Production**")
    len_sec3 = st.number_input("Length (ft) Sec 3", value=3350.0, step=100.0)
    gpm3 = st.number_input("GPM Sec 3", value=450.0, step=50.0)
    lith3 = st.selectbox("Lithology Sec 3", ["Reactive Clay", "Firm Shale", "Sandstone"], index=2)

d1 = len_sec1; d2 = d1 + len_sec2; d3 = d2 + len_sec3

st.sidebar.divider()
st.sidebar.header("Dynamic Equipment Builder")

btn_col1, btn_col2 = st.sidebar.columns(2)
if btn_col1.button("➕ Add Scenario"): st.session_state.num_scenarios = min(10, st.session_state.num_scenarios + 1)
if btn_col2.button("➖ Remove Scenario"): st.session_state.num_scenarios = max(1, st.session_state.num_scenarios - 1)

scenario_configs = {}
for i in range(st.session_state.num_scenarios):
    sc_name = f"Scenario {chr(65+i)}" 
    with st.sidebar.expander(f"🛠️ {sc_name} Builder", expanded=(i==0)):

        st.markdown("**1. Primary Shakers**")
        s_col1, s_col2 = st.columns(2)
        if s_col1.button("➕ Add Shaker", key=f"add_sh_{sc_name}"): st.session_state[f"num_sh_{sc_name}"] += 1; st.rerun()
        if s_col2.button("➖ Remove Shaker", key=f"rem_sh_{sc_name}") and st.session_state[f"num_sh_{sc_name}"] > 0: st.session_state[f"num_sh_{sc_name}"] -= 1; st.rerun()

        shaker_meshes = []
        for j in range(st.session_state[f"num_sh_{sc_name}"]):
            mesh = st.slider(f"Mesh Size (Shaker {j+1})", 40, 300, 80 if j == 0 else (120 if j == 1 else 200), 10, key=f"sl_sh_{sc_name}_{j}")
            shaker_meshes.append(mesh)

        st.markdown("**2. Hydrocyclones**")
        h_col1, h_col2 = st.columns(2)
        with h_col1: ds_on = st.checkbox("Desander", value=False, key=f"ds_{sc_name}")
        with h_col2: dl_on = st.checkbox("Desilter", value=False, key=f"dl_{sc_name}")
        mc_on = st.checkbox("Mud Cleaner", value=(i>0), key=f"mc_{sc_name}")

        st.markdown("**3. Centrifuges**")
        c_col1, c_col2 = st.columns(2)
        if c_col1.button("➕ Add CF", key=f"add_cf_{sc_name}"): st.session_state[f"num_cf_{sc_name}"] += 1; st.rerun()
        if c_col2.button("➖ Remove CF", key=f"rem_cf_{sc_name}") and st.session_state[f"num_cf_{sc_name}"] > 0: st.session_state[f"num_cf_{sc_name}"] -= 1; st.rerun()

        cf_rpms = []
        for j in range(st.session_state[f"num_cf_{sc_name}"]):
            rpm = st.slider(f"Bowl Speed RPM (CF {j+1})", 1500, 3500, 1800 if j == 0 else 3000, 100, key=f"sl_cf_{sc_name}_{j}")
            cf_rpms.append(rpm)

        eff_X, cost, chem_pen, eq_labels, active_equipment_list = build_and_evaluate_equipment(shaker_meshes, ds_on, dl_on, mc_on, cf_rpms)

        st.caption(f"**Mock-up Base Efficiency: {eff_X*100:.1f}%** | Rent: ${cost:,.0f}/d")
        scenario_configs[sc_name] = {"cost": cost, "chem": chem_pen, "labels": eq_labels, "equipment_objects": active_equipment_list}

SCENARIO_COLORS = ['#e74c3c', '#3498db', '#2ecc71', '#f1c40f', '#9b59b6', '#e67e22', '#1abc9c']

# =============================================================================
# CORE SIMULATION ENGINE TRIGGER (Dynamic PSD & API 13C Mass Balance)
# =============================================================================
if st.sidebar.button("Run Physics & Mass Balance", type="primary", use_container_width=True):
    with st.spinner("Executing API RP 13C Volume Additivity & Dynamic PSD Routing..."):

        target_lgs_frac = target_lgs_des / 100.0
        
        scenarios = {}
        for sc_name, config in scenario_configs.items():
            scenarios[sc_name] = {
                "daily_eq_cost": config["cost"], "chem_penalty": config["chem"], 
                "equipment_objects": config["equipment_objects"],
                "sections": [
                    {"hole": 17.5, "dp": 5.0, "len": len_sec1, "gpm": gpm1, "wash": 1.15, "lith": lith1, "log": generate_dynamic_log(0, d1, 8.6, 11.5, 90, 100)},
                    {"hole": 12.25, "dp": 5.0, "len": len_sec2, "gpm": gpm2, "wash": 1.10, "lith": lith2, "log": generate_dynamic_log(d1, d2, 9.2, 12.8, 65, 100)},
                    {"hole": 8.5, "dp": 4.0, "len": len_sec3, "gpm": gpm3, "wash": 1.05, "lith": lith3, "log": generate_dynamic_log(d2, d3, 10.4, 14.8, 45, 100)}
                ]
            }

        engine = AdvancedDrillingPhysics(t600, t300, t200, t100, t6, t3)
        econ = EconomicsAnalyzer(rig_rate)

        sim_res = {k: {"depth":[],"hole":[], "rop":[],"ecd":[],"pp":[],"fg":[],"lgs":[],"total_solids":[],"lithology":[],
                       "base_mw":[],"actual_mw":[],"pv":[],"yp":[],"r600":[],"r300":[], "hb_n":[], "hb_k":[], "hb_tau":[],
                       "cost":0,"days":0,"equip_invest":0, "mud_cost":0, "disp_cost":0, "chem_cost":0, "total_vm":0, "total_waste":0, "api_et_avg":0} for k in scenarios}

        for sc_name, sc_data in scenarios.items():
            manager = EquipmentSystemManager(sc_data["equipment_objects"])
            
            t_cost = 0; t_days = 0; t_invest = 0; t_mud_c = 0; t_disp_c = 0; t_chem_c = 0; t_vm = 0; t_waste = 0
            total_solids_drilled_bbl = 0
            total_solids_discarded_bbl = 0

            # --- API RP 13C MASS BALANCE INITIALIZATION ---
            v_active = 1000.0 # Standard active pit volume (bbl)
            base_mw = sc_data["sections"][0]["log"][0][1] 
            
            # Initial Mud Composition (Water + Barite)
            f_hgs_base = (base_mw - 8.33) / (35.0 - 8.33)
            v_hgs = f_hgs_base * v_active
            v_lgs = 0.0
            v_water = v_active - v_hgs

            for sec in sc_data["sections"]:
                avg_rop = 0
                prev_depth = sec['log'][0][0] - 100.0 if len(sec['log']) > 0 else 0.0
                
                # --- DYNAMIC LITHOLOGY SELECTION ---
                if sec['lith'] == "Reactive Clay":
                    lith_psd_frac = np.array([0.01, 0.04, 0.10, 0.15, 0.20, 0.20, 0.10, 0.10, 0.05, 0.05])
                elif sec['lith'] == "Sandstone":
                    lith_psd_frac = np.array([0.15, 0.25, 0.30, 0.15, 0.05, 0.05, 0.02, 0.02, 0.01, 0.0])
                else: # Firm Shale
                    lith_psd_frac = np.array([0.05, 0.15, 0.25, 0.20, 0.15, 0.10, 0.05, 0.03, 0.01, 0.01])

                for step_data in sec['log']:
                    d, step_base_mw, pp, fg, rop_max = step_data
                    delta_depth = d - prev_depth
                    prev_depth = d

                    # 1. GENERATE CUTTINGS VOLUME
                    v_c_step = ((sec['hole']**2) / 1029.4) * delta_depth * sec['wash']
                    total_solids_drilled_bbl += v_c_step
                    
                    # 2. APPLY LITHOLOGY TO PSD ARRAY
                    current_psd = lith_psd_frac * v_c_step

                    # 3. DYNAMIC EQUIPMENT ROUTING (Tromp Curve Physics)
                    cascade_results = manager.process_system(current_psd)
                    v_discarded_step = cascade_results["total_solids_discarded"]
                    v_mud_lost_step = cascade_results["total_mud_lost"]
                    v_retained_step = np.sum(cascade_results["retained_psd_array"])
                    
                    total_solids_discarded_bbl += v_discarded_step
                    t_waste += (v_discarded_step + v_mud_lost_step)

                    # 4. VOLUME ADDITIVITY & PIT MANAGEMENT
                    v_lgs += v_retained_step
                    v_new_total = v_active + v_retained_step - v_mud_lost_step
                    
                    if v_new_total > v_active:
                        # Tank Overflow - Mud is dumped (carrying old LGS/HGS with it)
                        v_overflow = v_new_total - v_active
                        ratio_buang = v_overflow / v_new_total
                        v_lgs *= (1.0 - ratio_buang)
                        v_hgs *= (1.0 - ratio_buang)
                        v_water *= (1.0 - ratio_buang)
                        t_waste += v_overflow
                    elif v_new_total < v_active:
                        # Mud Level Dropped - Add Fresh Make-up Mud
                        v_makeup = v_active - v_new_total
                        v_hgs += f_hgs_base * v_makeup
                        v_water += (1.0 - f_hgs_base) * v_makeup
                        t_vm += v_makeup
                        t_mud_c += v_makeup * mud_price

                    # Calculate Actual Concentrations
                    lgs_pct = (v_lgs / v_active) * 100.0
                    hgs_pct = (v_hgs / v_active) * 100.0
                    total_solids_pct = lgs_pct + hgs_pct

                    # 5. SAFETY DILUTION TRIGGER (if LGS exceeds 6%)
                    if lgs_pct > target_lgs_des:
                        v_excess_lgs = v_lgs - (target_lgs_frac * v_active)
                        phi_lgs = v_lgs / v_active
                        v_dump = v_excess_lgs / phi_lgs if phi_lgs > 0 else 0
                        
                        # Remove dumped mud
                        v_lgs -= v_dump * phi_lgs
                        v_hgs -= v_dump * (v_hgs / v_active)
                        v_water -= v_dump * (v_water / v_active)
                        
                        # Replace with fresh mud
                        v_hgs += v_dump * f_hgs_base
                        v_water += v_dump * (1.0 - f_hgs_base)
                        
                        t_waste += v_dump
                        t_vm += v_dump
                        t_mud_c += v_dump * mud_price
                        t_disp_c += v_dump * disp_price
                        
                        # Update after dilution
                        lgs_pct = (v_lgs / v_active) * 100.0
                        hgs_pct = (v_hgs / v_active) * 100.0
                        total_solids_pct = lgs_pct + hgs_pct

                    # 6. RHEOLOGY & HYDRAULICS (Bourgoyne et al.)
                    temp = engine.get_temp_at_depth(d)
                    actual_mw = engine.calculate_actual_density(step_base_mw, lgs_pct, hgs_pct)
                    hb_n, hb_k, hb_tau, pv, yp, r600, r300 = engine.calculate_rheology(lgs_pct, temp)
                    ecd, rop = engine.calculate_hydraulics(hb_n, hb_k, hb_tau, actual_mw, d, sec['hole'], sec['dp'], sec['gpm'], pp, rop_max)

                    # LOGGING
                    sim_res[sc_name]["hole"].append(sec['hole']); sim_res[sc_name]["lithology"].append(sec['lith'])
                    sim_res[sc_name]["depth"].append(d); sim_res[sc_name]["rop"].append(rop)
                    sim_res[sc_name]["ecd"].append(ecd); sim_res[sc_name]["pp"].append(pp); sim_res[sc_name]["fg"].append(fg)
                    sim_res[sc_name]["lgs"].append(lgs_pct); sim_res[sc_name]["total_solids"].append(total_solids_pct)
                    sim_res[sc_name]["base_mw"].append(step_base_mw); sim_res[sc_name]["actual_mw"].append(actual_mw)
                    sim_res[sc_name]["hb_n"].append(hb_n); sim_res[sc_name]["hb_k"].append(hb_k); sim_res[sc_name]["hb_tau"].append(hb_tau)
                    sim_res[sc_name]["pv"].append(pv); sim_res[sc_name]["yp"].append(yp)
                    sim_res[sc_name]["r600"].append(r600); sim_res[sc_name]["r300"].append(r300)

                    avg_rop += rop

                # Macro Economics for the Section
                econ_res = econ.calculate_time_cost(
                    avg_rop=avg_rop/len(sec['log']), length_ft=sec['len'], 
                    actual_lgs_pct=lgs_pct, target_lgs_pct=target_lgs_des,
                    daily_equip_cost=sc_data["daily_eq_cost"], daily_chem_penalty=sc_data["chem_penalty"]
                )
                
                t_days += econ_res["total_days"]
                t_invest += (sc_data["daily_eq_cost"] * econ_res["total_days"])
                t_chem_c += econ_res["chem_penalty_cost"]
                t_cost += econ_res["total_afe_cost"] 

            # Calculate Actual System Efficiency for the dashboard
            final_efficiency = (total_solids_discarded_bbl / total_solids_drilled_bbl) * 100.0 if total_solids_drilled_bbl > 0 else 0
            
            sim_res[sc_name].update({
                "api_et_avg": final_efficiency,
                "cost": t_cost + t_mud_c + t_disp_c, 
                "days": t_days, "equip_invest": t_invest, 
                "mud_cost": t_mud_c, "disp_cost": t_disp_c, "chem_cost": t_chem_c, 
                "total_vm": t_vm, "total_waste": t_waste
            })

        st.session_state['sim_res'] = sim_res
        st.session_state['saved_configs'] = scenario_configs
        st.session_state.sim_done = True

# =============================================================================
# DASHBOARD VISUALIZATION
# =============================================================================
if st.session_state.sim_done:
    sim_res = st.session_state['sim_res']
    saved_configs = st.session_state['saved_configs']

    tab1, tab2, tab3, tab4 = st.tabs(["Interactive Dashboard", "API Mass Balance & AFE", "Rheology Report", "Detailed Data Logs"])

    with tab1:
        st.subheader("Multi-Scenario Performance Comparison")
        fig = make_subplots(rows=5, cols=2, horizontal_spacing=0.15, vertical_spacing=0.12)
        costs_x = []; costs_y = []; eff_y = []; bar_colors = []; bar_texts = []; eff_texts = []

        for idx, (sc_name, data) in enumerate(sim_res.items()):
            c = SCENARIO_COLORS[idx % len(SCENARIO_COLORS)]

            fig.add_trace(go.Scatter(x=data["rop"], y=data["depth"], name=sc_name, line=dict(color=c, width=2.5), mode='lines+markers'), row=1, col=1)
            fig.add_trace(go.Scatter(x=data["actual_mw"], y=data["depth"], name=f"{sc_name} (MW)", line=dict(color=c, width=2.5), mode='lines+markers', showlegend=False), row=1, col=2)
            fig.add_trace(go.Scatter(x=data["ecd"], y=data["depth"], name=f"{sc_name} (ECD)", line=dict(color=c, width=2.5), mode='lines+markers', showlegend=False), row=2, col=1)
            fig.add_trace(go.Scatter(x=data["lgs"], y=data["depth"], mode='lines+markers', marker=dict(color=c, size=6), line=dict(color=c, width=1.5), showlegend=False), row=2, col=2)
            fig.add_trace(go.Scatter(x=data["total_solids"], y=data["depth"], mode='lines+markers', marker=dict(color=c, size=6), line=dict(color=c, width=1.5), showlegend=False), row=3, col=1)
            fig.add_trace(go.Scatter(x=data["pv"], y=data["depth"], mode='lines+markers', marker=dict(color=c, size=6), line=dict(color=c, width=1.5), showlegend=False), row=3, col=2)
            fig.add_trace(go.Scatter(x=data["yp"], y=data["depth"], mode='lines+markers', marker=dict(color=c, size=6), line=dict(color=c, width=1.5), showlegend=False), row=4, col=1)
            fig.add_trace(go.Scatter(x=data["hb_n"], y=data["depth"], line=dict(color=c, width=2.5), mode='lines+markers', showlegend=False), row=4, col=2)

            costs_x.append(sc_name); costs_y.append(data["cost"]); eff_y.append(data["api_et_avg"])
            bar_colors.append(c); bar_texts.append(f'${data["cost"]/1e6:.2f}M'); eff_texts.append(f'{data["api_et_avg"]:.1f}%')

        # --- DRAW THE TARGET LGS ANALYTICAL BENCHMARK LINE ---
        max_drilled_depth = max([max(data["depth"]) for data in sim_res.values()]) if sim_res else d3
        fig.add_trace(go.Scatter(
            x=[target_lgs_des, target_lgs_des], 
            y=[0, max_drilled_depth], 
            mode='lines', 
            line=dict(color='red', width=2, dash='dashdot'), 
            name='Target LGS Limit'
        ), row=2, col=2)

        for r in range(1, 5): 
            for c_idx in range(1, 3):
                fig.update_yaxes(autorange="reversed", row=r, col=c_idx)
                fig.update_xaxes(side='top', row=r, col=c_idx)

        fig.update_yaxes(title=dict(text="<b>Depth (ft)</b>", standoff=15), row=1, col=1)
        fig.update_yaxes(title=dict(text="<b>Depth (ft)</b>", standoff=15), row=2, col=1)
        fig.update_yaxes(title=dict(text="<b>Depth (ft)</b>", standoff=15), row=3, col=1)
        fig.update_yaxes(title=dict(text="<b>Depth (ft)</b>", standoff=15), row=4, col=1)

        fig.update_xaxes(title_text="<b>1. ROP (ft/hr)</b>", row=1, col=1)
        fig.update_xaxes(title_text="<b>2. Actual Mud Weight (ppg)</b>", row=1, col=2)
        fig.update_xaxes(title_text="<b>3. Equivalent Circ. Density (ppg)</b>", row=2, col=1)
        fig.update_xaxes(title_text="<b>4. LGS Accumulation (%)</b>", row=2, col=2)
        fig.update_xaxes(title_text="<b>5. Total Solids (%)</b>", row=3, col=1)
        fig.update_xaxes(title_text="<b>6. Plastic Viscosity (cP)</b>", row=3, col=2)
        fig.update_xaxes(title_text="<b>7. Yield Point (lb/100ft2)</b>", row=4, col=1)
        fig.update_xaxes(title_text="<b>8. Flow Behavior Index (n)</b>", row=4, col=2)

        fig.add_trace(go.Bar(x=costs_x, y=costs_y, marker_color=bar_colors, text=bar_texts, textposition='auto', showlegend=False), row=5, col=1)
        fig.add_trace(go.Bar(x=costs_x, y=eff_y, marker_color=bar_colors, text=eff_texts, textposition='auto', showlegend=False), row=5, col=2)
        fig.update_xaxes(title_text="<b>9. Total Project Cost</b>", side='bottom', row=5, col=1)
        fig.update_xaxes(title_text="<b>10. Final System Efficiency (Et)</b>", side='bottom', row=5, col=2)

        fig.update_layout(
            height=2400, hovermode="y unified", margin=dict(t=120, l=80, r=40, b=50), 
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), 
            paper_bgcolor='white', plot_bgcolor='white', font=dict(color='black', size=12) 
        )
        fig.update_xaxes(showline=True, linewidth=1, linecolor='black', gridcolor='lightgrey', zerolinecolor='lightgrey')
        fig.update_yaxes(showline=True, linewidth=1, linecolor='black', gridcolor='lightgrey', zerolinecolor='lightgrey')
        st.plotly_chart(fig, use_container_width=True, theme=None)

    with tab2:
        st.subheader("Mass Balance & AFE Economics (API Standard)")
        summary_data = {"Metric": ["Equipment Configured", "Mud Built (Vm) bbls", "Waste Disposed (Vt) bbls", "Final System Eff. (Et)", "1. Mud Cost ($)", "2. Disposal Cost ($)", "3. Barite/Chem Pen. ($)", "4. SRE Capex ($)", "TOTAL AFE COST ($)"]}
        for sc_name, data in sim_res.items():
            labels = saved_configs[sc_name]["labels"]
            eq_str = " + ".join(labels) if labels else "Bypass (No Control)"
            summary_data[sc_name] = [eq_str, f"{data['total_vm']:,.0f}", f"{data['total_waste']:,.0f}", f"{data['api_et_avg']:.1f}%", f"${data['mud_cost']:,.0f}", f"${data['disp_cost']:,.0f}", f"${data['chem_cost']:,.0f}", f"${data['equip_invest']:,.0f}", f"${data['cost']:,.0f}"]
        st.table(summary_data)

    with tab3:
        st.subheader(f"Mud Rheology Report (at TD: {d3:,.0f} ft)")
        rheo_data = {"Parameter": ["Actual Generated LGS (%)", "Total Solids (%)", "Plastic Viscosity (cP)", "Yield Point (lb/100ft2)"]}
        for sc_name, data in sim_res.items():
            rheo_data[sc_name] = [f"{data['lgs'][-1]:.1f}", f"{data['total_solids'][-1]:.1f}", f"{data['pv'][-1]:.1f}", f"{data['yp'][-1]:.1f}"]
        st.table(rheo_data)

    with tab4:
        st.subheader("Comprehensive Section & Depth Logs")
        for sc_name, data in sim_res.items():
            st.markdown(f"**{sc_name} Data**")
            df = pd.DataFrame({
                "Depth (ft)": data["depth"], 
                "Lithology": data["lithology"],
                'Hole (")': data["hole"], 
                "Gen. LGS (%)": data["lgs"], 
                "Total Solids (%)": data["total_solids"],
                "Base MW (ppg)": data["base_mw"], 
                "Actual MW (ppg)": data["actual_mw"], 
                "HB 'n'": data["hb_n"], 
                "HB 'K'": data["hb_k"], 
                "HB 'Tau_y'": data["hb_tau"],
                "PV (cP)": data["pv"], 
                "YP (lb/100ft2)": data["yp"], 
                "Fann 600": data["r600"], 
                "Fann 300": data["r300"]
            })
            st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("👈 Configure your well parameters on the left panel, and press run.")
