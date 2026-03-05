class APIMassBalanceAnalyzer:
    def __init__(self, mud_price_bbl=85.0, disposal_price_bbl=18.0):
        self.mud_price = mud_price_bbl
        self.disposal_price = disposal_price_bbl

    def calculate_interval(self, hole_in, length_ft, washout, target_lgs_frac, active_equipment: list):
        """
        Calculates the volumetric mass balance and economics for a specific drilling interval
        by pushing the generated cuttings through a sequential cascade of solid control equipment.
        """
        # 1. Calculate Total Generated Cuttings Volume
        v_c_total = 0.000971 * (hole_in**2) * length_ft * washout
        v_h = v_c_total  
        
        # 2. Initialize Formation Cuttings Distribution (Assumption: Coarse to Fine)
        initial_psd_fractions = np.array([0.05, 0.15, 0.25, 0.20, 0.15, 0.10, 0.05, 0.03, 0.01, 0.01])
        current_psd = initial_psd_fractions * v_c_total
        
        total_mud_lost = 0.0
        total_solids_discarded = 0.0
        total_daily_rent = 0.0
        
        # 3. CASCADE ALGORITHM (Equipment Synergy)
        for eq in active_equipment:
            current_psd, solid_discarded, mud_lost = eq.process_fluid(current_psd)
            
            total_solids_discarded += solid_discarded
            total_mud_lost += mud_lost
            total_daily_rent += eq.base_cost
            
        # Solids failing to be removed by ALL equipment become the Low Gravity Solids (LGS) burden
        v_c_retained = np.sum(current_psd) 
        
        # 4. Economics & Dilution Calculations
        v_m_volumetric = v_h + total_mud_lost
        v_m_dilution = v_c_retained / target_lgs_frac if target_lgs_frac > 0 else v_m_volumetric
        
        v_m_actual = max(v_m_volumetric, v_m_dilution)
        v_lw = max(0.0, v_m_actual - v_m_volumetric)   # Liquid waste due to dilution requirements
        v_sw = total_solids_discarded + total_mud_lost # Total surface waste
        
        cost_mud = v_m_actual * self.mud_price
        cost_disposal = (v_sw + v_lw) * self.disposal_price
        
        system_efficiency = (total_solids_discarded / v_c_total) * 100 if v_c_total > 0 else 0
        
        return {
            "v_mud_actual": v_m_actual,
            "v_surface_waste": v_sw,
            "v_liquid_waste": v_lw,
            "system_efficiency_pct": system_efficiency,
            "cost_mud": cost_mud,
            "cost_disposal": cost_disposal,
            "total_equip_rent": total_daily_rent
        }
class Fann35Machine:
    def __init__(self):
        self.k_gamma = 1.703; self.k_tau = 0.511    

class AdvancedDrillingPhysics:
    def __init__(self, t600, t300, t200, t100, t6, t3):
        self.base_tau_y = t3  
        try:
            ratio = (t600 - self.base_tau_y) / (t300 - self.base_tau_y)
            self.base_n = 3.32 * np.log10(max(ratio, 0.001))
        except:
            self.base_n = 1.0
        self.base_n = max(0.1, min(self.base_n, 1.2)) 
        self.base_K = (t300 - self.base_tau_y) / (511 ** self.base_n)
        self.surface_temp = 80.0 
        self.geo_gradient = 1.6  
    def get_temp_at_depth(self, tvd_ft):
        return self.surface_temp + (self.geo_gradient * (tvd_ft / 100.0))

    def calculate_generated_lgs(self, prev_lgs, hole_diam_in, rop_fph, gpm, target_lgs, sre_multiplier, lithology):
        hole_cap = (hole_diam_in ** 2) / 1029.4
        cuttings_bbl_hr = hole_cap * rop_fph
        mud_bbl_hr = (gpm * 60) / 42.0
        lgs_concentration = (cuttings_bbl_hr / (mud_bbl_hr * 0.8)) * 100.0

        if lithology == "Reactive Clay":
            dispersion_penalty = 1.8; variance_mult = 1.5
        elif lithology == "Sandstone":
            dispersion_penalty = 0.4; variance_mult = 0.5
        else: 
            dispersion_penalty = 1.0; variance_mult = 1.0

        penalty = lgs_concentration * sre_multiplier * dispersion_penalty
        equilibrium_lgs = target_lgs + (penalty * 3.0) 
        
        approach_rate = 0.15 
        new_base_lgs = prev_lgs + approach_rate * (equilibrium_lgs - prev_lgs)
        
        variance_factor = 0.15 * sre_multiplier * variance_mult
        noise = np.random.normal(0, variance_factor * new_base_lgs)
        
        measured_lgs = max(0.0, new_base_lgs + noise)
        return new_base_lgs, min(measured_lgs, 25.0) 

    def calculate_actual_density(self, base_mw, lgs_pct):
        return round((base_mw * (1.0 - (lgs_pct/100.0))) + (21.7 * (lgs_pct/100.0)), 2)

    def calculate_rheology(self, lgs_pct, temp_f):
        temp_diff = temp_f - 120.0
        thermal_factor = max(0.6, 1.0 - (0.005 * temp_diff))
        phi = lgs_pct / 100.0
        rel_visc = (1 - (phi / 0.60)) ** (-2.5 * 0.60) if phi < 0.60 else 50.0
        actual_K = self.base_K * thermal_factor * rel_visc
        actual_tau_y = (self.base_tau_y + (0.8 * lgs_pct)) * (1.0 + (0.001 * temp_diff))
        actual_n = self.base_n 
        r600 = actual_tau_y + actual_K * (1022 ** actual_n)
        r300 = actual_tau_y + actual_K * (511 ** actual_n)
        return round(actual_n, 3), round(actual_K, 3), round(actual_tau_y, 1), round(r600 - r300, 1), round((2*r300)-r600, 1), round(r600, 1), round(r300, 1)

    def calculate_hydraulics(self, n, K, tau_y, actual_mw_ppg, depth_ft, hole, dp, gpm, pp, rop_max):
        annular_cap = (hole**2 - dp**2) / 1029.4
        vel_ft_min = gpm / annular_cap
        gamma_a = (2.4 * vel_ft_min / (hole - dp)) * ((2 * n + 1) / (3 * n)) if hole > dp and n > 0 else 10.0
        tau_w_lb100 = 1.066 * (tau_y + K * (gamma_a ** n))
        ecd = actual_mw_ppg + (tau_w_lb100 / (15.6 * (hole - dp)) if hole > dp else 0)
        rop = rop_max * np.exp(-0.3 * max(0, ecd - pp))
        return round(ecd, 2), round(rop, 1)

def generate_dynamic_log(start_d, end_d, pp_base, fg_base, rop_base, step_ft=500):
    log = []
    points = np.arange(start_d + step_ft, end_d, step_ft)
    if len(points) == 0 or points[-1] != end_d: points = np.append(points, end_d)
    for d in points:
        log.append((round(d, 1), round(9.0 + (d/2000.0), 2), round(pp_base + (d/3000.0), 2), round(fg_base + (d/2000.0), 2), rop_base))
    return log