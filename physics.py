import numpy as np
from equipment import EquipmentSystemManager 

class APIMassBalanceAnalyzer:
    def __init__(self, mud_price_bbl=85.0, disposal_price_bbl=18.0):
        self.mud_price = mud_price_bbl
        self.disposal_price = disposal_price_bbl

    def calculate_interval(self, hole_in, length_ft, washout, target_lgs_frac, lithology, active_equipment_list: list):
        """
        Calculates theoretical interval metrics based on ASME Shale Shaker Committee guidelines.
        """
        v_c_total = 0.000971 * (hole_in**2) * length_ft * washout
        v_h = v_c_total  

        if lithology == "Reactive Clay":
            initial_psd_fractions = np.array([0.01, 0.04, 0.10, 0.15, 0.20, 0.20, 0.10, 0.10, 0.05, 0.05])
        elif lithology == "Sandstone":
            initial_psd_fractions = np.array([0.15, 0.25, 0.30, 0.15, 0.05, 0.05, 0.02, 0.02, 0.01, 0.0])
        else: 
            initial_psd_fractions = np.array([0.05, 0.15, 0.25, 0.20, 0.15, 0.10, 0.05, 0.03, 0.01, 0.01])
            
        current_psd = initial_psd_fractions * v_c_total

        manager = EquipmentSystemManager(active_equipment_list)
        cascade_results = manager.process_system(current_psd)

        total_solids_discarded = cascade_results["total_solids_discarded"]
        total_mud_lost = cascade_results["total_mud_lost"]
        total_daily_rent = cascade_results["total_daily_cost"]
        v_c_retained = np.sum(cascade_results["retained_psd_array"])

        v_m_volumetric = v_h + total_mud_lost
        v_m_dilution = v_c_retained / target_lgs_frac if target_lgs_frac > 0 else v_m_volumetric

        v_m_actual = max(v_m_volumetric, v_m_dilution)
        v_lw = max(0.0, v_m_actual - v_m_volumetric)   
        v_sw = total_solids_discarded + total_mud_lost 

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

class AdvancedDrillingPhysics:
    def __init__(self, t600, t300, t200, t100, t6, t3):
        """
        Initializes baseline fluid properties based on API RP 13D standards.
        """
        # API RP 13D Bingham Plastic Calculation
        self.base_pv = t600 - t300
        self.base_yp = t300 - self.base_pv
        
        # Base tau_y approximation for internal YPL referencing
        self.base_tau_y = t3 
        
        self.surface_temp = 80.0 
        self.geo_gradient = 1.6  

    def get_temp_at_depth(self, tvd_ft):
        return self.surface_temp + (self.geo_gradient * (tvd_ft / 100.0))

    def calculate_actual_density(self, base_mw, lgs_pct):
        # 21.7 ppg is the specific gravity of standard drill solids (API RP 13C)
        return round((base_mw * (1.0 - (lgs_pct/100.0))) + (21.7 * (lgs_pct/100.0)), 2)

    def calculate_rheology(self, lgs_pct, temp_f):
        """
        Calculates degraded rheology using Krieger-Dougherty (Caenn & Darley)
        and back-calculates API 13D Fann reading projections.
        """
        phi = lgs_pct / 100.0
        phi_m = 0.60
        intrinsic_visc = 2.5
        
        # Krieger-Dougherty equation for relative viscosity
        # Capped safely to prevent mathematical overflow at 60% solids
        if phi < 0.55:
            rel_visc = (1.0 - (phi / phi_m)) ** (-intrinsic_visc * phi_m)
        else:
            rel_visc = 50.0 

        # Degraded PV and YP based on literature
        actual_pv = self.base_pv * rel_visc
        actual_yp = self.base_yp * (1.0 + (1.5 * phi)) # Yield Point scales linearly with surface area of fines
        actual_tau_y = self.base_tau_y * (1.0 + (2.0 * phi))

        # Back-calculate API RP 13D Fann Dial Readings
        r300 = actual_pv + actual_yp
        r600 = actual_pv + r300
        
        # Recalculate Power Law (API RP 13D section 4) metrics for hydraulics
        n_api = 3.32 * np.log10(r600 / r300) if r300 > 0 else 1.0
        k_api = r300 / (511 ** n_api) if n_api > 0 else 0.0

        return (round(n_api, 3), round(k_api, 3), round(actual_tau_y, 1), 
                round(actual_pv, 1), round(actual_yp, 1), round(r600, 1), round(r300, 1))

    def calculate_hydraulics(self, n, K, tau_y, actual_mw_ppg, depth_ft, hole, dp, gpm, pp, rop_max):
        """
        Calculates Equivalent Circulating Density (ECD) via Annular Pressure Loss.
        """
        annular_cap = (hole**2 - dp**2) / 1029.4
        vel_ft_min = gpm / annular_cap
        
        gamma_a = (2.4 * vel_ft_min / (hole - dp)) * ((2 * n + 1) / (3 * n)) if hole > dp and n > 0 else 10.0
        tau_w_lb100 = 1.066 * (tau_y + K * (gamma_a ** n))
        
        ecd = actual_mw_ppg + (tau_w_lb100 / (15.6 * (hole - dp)) if hole > dp else 0)
        rop = rop_max * np.exp(-0.3 * max(0, ecd - pp))
        
        return round(ecd, 2), round(rop, 1)
