import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Memanggil mesin kalkulasi dari file terpisah (Modular)
from physics import API_MassBalanceAnalyzer, AdvancedDrillingPhysics, generate_dynamic_log
from economics import EconomicsAnalyzer
from equipment import calculate_dynamic_system

st.set_page_config(page_title="Drilling & Solid Control Simulator", layout="wide")

if "num_scenarios" not in st.session_state: st.session_state.num_scenarios = 2
if "sim_done" not in st.session_state: st.session_state.sim_done = False

for i in range(10):
    sn = f"Scenario {chr(65+i)}"
    if f"num_sh_{sn}" not in st.session_state: st.session_state[f"num_sh_{sn}"] = 1
    if f"num_cf_{sn}" not in st.session_state: st.session_state[f"num_cf_{sn}"] = 0 if i == 0 else 1

st.title("API First-Principles Drilling Simulator")
st.markdown("Engineering-grade modeling featuring **Dynamic Assembly, Formation Lithology**, and API Mass Balance.")

# --- SIDEBAR CONFIGURATION ---
st.sidebar.header("Global Configurations")
with st.sidebar.expander("Base Rig & Fluid Economics", expanded=False):
    rig_rate = st.number_input("Rig Lease Rate ($/Day)", value=35000.0, step=1000.0)
    mud_price = st.number_input("Fresh Mud Cost ($/bbl)", value=85.0, step=5.0)
    disp_price = st.number_input("Waste Disposal Cost ($/bbl)", value=18.0, step=2.0)
    target_lgs_des = st.number_input("Target LGS (Max Limit %)", value=6.0, step=0.5)
    
    st.markdown("**Fresh Mud Baseline (0% LGS)**")
    c1, c2 = st.columns(2)
    t600 = c1.number_input("600 RPM", value=55.0, step=1.0)
    t300 = c2.number_input("300 RPM", value=35.0, step=1.0)
    t200 = c1.number_input("200 RPM", value=28.0, step=1.0)
    t100 = c2.number_input("100 RPM", value=20.0, step=1.0)
    t6 = c1.number_input("6 RPM", value=8.0, step=1.0)
    t3 = c2.number_input("3 RPM", value=6.0, step=1.0)

# INPUT LITHOLOGY
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

# DYNAMIC EQUIPMENT BUILDER
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

        eff_X, cost, chem_pen, eq_labels = calculate_dynamic_system(shaker_meshes, ds_on, dl_on, mc_on, cf_rpms)
        st.caption(f"**Total SRE (X): {eff_X*100:.1f}%** | Rent: ${cost:,.0f}/d | Chem Loss: ${chem_pen:,.0f}/d")
        scenario_configs[sc_name] = {"mech_X": eff_X, "cost": cost, "chem": chem_pen, "labels": eq_labels}

SCENARIO_COLORS = ['#e74c3c', '#3498db', '#2ecc71', '#f1c40f', '#9b59b6', '#e67e22', '#1abc9c']

# --- ENGINE TRIGGER ---
if st.sidebar.button("Run Physics & Mass Balance", type="primary", use_container_width=True):
    with st.spinner("Processing formation lithology and fluid mechanics..."):
        
        target_lgs_frac = target_lgs_des / 100.0
        scenarios = {}
        for sc_name, config in scenario_configs.items():
            scenarios[sc_name] = {
                "daily_eq_cost": config["cost"], "chem_penalty": config["chem"], "mech_X": config["mech_X"],
                "sections": [
                    {"hole": 17.5, "dp": 5.0, "len": len_sec1, "gpm": gpm1, "wash": 1.15, "lith": lith1, "log": generate_dynamic_log(0, d1, 8.6, 11.5, 90, 500)},
                    {"hole": 12.25, "dp": 5.0, "len": len_sec2, "gpm": gpm2, "wash": 1.10, "lith": lith2, "log": generate_dynamic_log(d1, d2, 9.2, 12.8, 65, 500)},
                    {"hole": 8.5, "dp": 4.0, "len": len_sec3, "gpm": gpm3, "wash": 1.05, "lith": lith3, "log": generate_dynamic_log(d2, d3, 10.4, 14.8, 45, 500)}
                ]
            }
        
        engine = AdvancedDrillingPhysics(t600, t300, t200, t100, t6, t3)
        econ = EconomicsAnalyzer(rig_rate)
        mass_bal = API_MassBalanceAnalyzer(mud_price, disp_price)
        
        sim_res = {k: {"depth":[],"hole":[], "rop":[],"ecd":[],"pp":[],"fg":[],"lgs":[],"total_solids":[],"lithology":[],
                       "base_mw":[],"actual_mw":[],"pv":[],"yp":[],"r600":[],"r300":[], "hb_n":[], "hb_k":[], "hb_tau":[],
                       "cost":0,"days":0,"equip_invest":0, "mud_cost":0, "disp_cost":0, "chem_cost":0, "total_vm":0, "total_waste":0, "api_et_avg":0} for k in scenarios}

        for sc_name, sc_data in scenarios.items():
            t_cost = 0; t_days = 0; t_invest = 0; t_mud_c = 0; t_disp_c = 0; t_chem_c = 0; t_vm = 0; t_waste = 0; et_sum = 0
            mech_X = sc_data["mech_X"]
            sre_mult = 1.0 - mech_X  
            current_true_lgs = 0.0 
            
            for sec in sc_data["sections"]:
                avg_rop = 0; lgs_sum = 0
                vm, vsw, vlw, api_et, c_mud, c_disp = mass_bal.calculate_interval(sec['hole'], sec['len'], sec['wash'], mech_X, target_lgs_frac)
                t_vm += vm; t_waste += (vsw + vlw); et_sum += api_et
                t_mud_c += c_mud; t_disp_c += c_disp
                
                for d, base_mw, pp, fg, rop_max in sec['log']:
                    temp = engine.get_temp_at_depth(d)
                    
                    # PANGGIL FUNGSI LITHOLOGY DARI ENGINE FISIKA
                    current_true_lgs, measured_lgs = engine.calculate_generated_lgs(
                        current_true_lgs, sec['hole'], rop_max, sec['gpm'], 
                        target_lgs_des, sre_mult, sec['lith']
                    )
                    
                    actual_mw = engine.calculate_actual_density(base_mw, measured_lgs)
                    base_solids_pct = max(0.0, ((base_mw - 8.33) / (35.0 - 8.33)) * 100.0)
                    total_solids_pct = measured_lgs + base_solids_pct
                    
                    hb_n, hb_k, hb_tau, pv, yp, r600, r300 = engine.calculate_rheology(measured_lgs, temp)
                    ecd, rop = engine.calculate_hydraulics(hb_n, hb_k, hb_tau, actual_mw, d, sec['hole'], sec['dp'], sec['gpm'], pp, rop_max)
                    
                    sim_res[sc_name]["hole"].append(sec['hole']); sim_res[sc_name]["lithology"].append(sec['lith'])
                    sim_res[sc_name]["depth"].append(d); sim_res[sc_name]["rop"].append(rop)
                    sim_res[sc_name]["ecd"].append(ecd); sim_res[sc_name]["pp"].append(pp); sim_res[sc_name]["fg"].append(fg)
                    sim_res[sc_name]["lgs"].append(measured_lgs); sim_res[sc_name]["total_solids"].append(total_solids_pct)
                    sim_res[sc_name]["base_mw"].append(base_mw); sim_res[sc_name]["actual_mw"].append(actual_mw)
                    sim_res[sc_name]["hb_n"].append(hb_n); sim_res[sc_name]["hb_k"].append(hb_k); sim_res[sc_name]["hb_tau"].append(hb_tau)
                    sim_res[sc_name]["pv"].append(pv); sim_res[sc_name]["yp"].append(yp)
                    sim_res[sc_name]["r600"].append(r600); sim_res[sc_name]["r300"].append(r300)
                    
                    avg_rop += rop; lgs_sum += measured_lgs
                
                sec_avg_lgs = lgs_sum / len(sec['log'])
                days, base_cost, rig_c, chem_c = econ.calculate_time_cost(avg_rop/len(sec['log']), sec['len'], sec_avg_lgs, sc_data["daily_eq_cost"], sc_data["chem_penalty"])
                t_days += days; t_invest += (sc_data["daily_eq_cost"] * days); t_chem_c += chem_c
                t_cost += base_cost + c_mud + c_disp
                
            sim_res[sc_name].update({"cost": t_cost, "days": t_days, "equip_invest": t_invest, "mud_cost": t_mud_c, "disp_cost": t_disp_c, "chem_cost": t_chem_c, "total_vm": t_vm, "total_waste": t_waste, "api_et_avg": et_sum / len(sc_data["sections"])})
        
        st.session_state['sim_res'] = sim_res
        st.session_state['saved_configs'] = scenario_configs
        st.session_state.sim_done = True

# --- DASHBOARD VISUAL ---
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
        fig.update_xaxes(title_text="<b>10. API Efficiency (Et)</b>", side='bottom', row=5, col=2)

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
        summary_data = {"Metric": ["Equipment Configured", "Mud Built (Vm) bbls", "Waste Disposed (Vt) bbls", "API Efficiency (Et)", "1. Mud Cost ($)", "2. Disposal Cost ($)", "3. Barite/Chem Pen. ($)", "4. SRE Capex ($)", "TOTAL AFE COST ($)"]}
        for sc_name, data in sim_res.items():
            labels = saved_configs[sc_name]["labels"]
            eq_str = " + ".join(labels) if labels else "Bypass (No Control)"
            summary_data[sc_name] = [eq_str, f"{data['total_vm']:,.0f}", f"{data['total_waste']:,.0f}", f"{data['api_et_avg']:.1f}%", f"${data['mud_cost']:,.0f}", f"${data['disp_cost']:,.0f}", f"${data['chem_cost']:,.0f}", f"${data['equip_invest']:,.0f}", f"${data['cost']:,.0f}"]
        st.table(summary_data)

    with tab3:
        st.subheader(f"Mud Rheology Report (at TD)")
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
                "Hole (\")": data["hole"], 
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
    st.info("👈 Konfigurasi parameter sumur dan pengaturan alat di menu samping, lalu klik tombol 'Run Physics & Mass Balance'.")
