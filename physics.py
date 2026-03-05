import numpy as np
from equipment import EquipmentSystemManager # Assuming equipment.py is in the src folder

class APIMassBalanceAnalyzer:
    def __init__(self, mud_price_bbl=85.0, disposal_price_bbl=18.0):
        self.mud_price = mud_price_bbl
        self.disposal_price = disposal_price_bbl

    def calculate_interval(self, hole_in, length_ft, washout, target_lgs_frac, lithology, active_equipment_list: list):
        """
        Calculates the volumetric mass balance and economics for a specific drilling interval.
        Integrates with EquipmentSystemManager to cascade fluid through solid control machinery.
        """
        # 1. Calculate Total Generated Cuttings Volume
        v_c_total = 0.000971 * (hole_in**2) * length_ft * washout
        v_h = v_c_total  

        # 2. Lithology Penalty & Initial PSD Generation
        # Reactive clay creates a heavier burden of ultrafine particles compared to sandstone
        if lithology == "Reactive Clay":
            initial_psd_fractions = np.array([0.01, 0.04, 0.10, 0.15, 0.20, 0.20, 0.10, 0.10, 0.05, 0.05])
        elif lithology == "Sandstone":
            initial_psd_fractions = np.array([0.15, 0.25, 0.30, 0.15, 0.05, 0.05, 0.02, 0.02, 0.01, 0.0])
        else: # Normal Firm Shale
            initial_psd_fractions = np.array([0.05, 0.15, 0.25, 0.20, 0.15, 0.10, 0.05, 0.03, 0.01, 0.01])
            
        current_psd = initial_psd_fractions * v_c_total

        # 3. EXECUTE CASCADE ALGORITHM VIA MANAGER
        manager = EquipmentSystemManager(active_equipment_list)
        cascade_results = manager.process_system(current_psd)

        # Retrieve exact cascade metrics
        total_solids_discarded = cascade_results["total_solids_discarded"]
        total_mud_lost = cascade_results["total_mud_lost"]
        total_daily_rent = cascade_results["total_daily_cost"]
        
        # EXACT volume of solids failing to be removed by the entire system
        v_c_retained = np.sum(cascade_results["retained_psd_array"])

        # 4. Economics & Dilution Calculations
        v_m_volumetric = v_h + total_mud_lost
        
        # How much fresh mud is needed to dilute the retained fines back to target LGS?
        v_m_dilution = v_c_retained / target_lgs_frac if target_lgs_frac > 0 else v_m_volumetric

        v_m_actual = max(v_m_volumetric, v_m_dilution)
        v_lw = max(0.0, v_m_actual - v_m_volumetric)   # Liquid waste due to dilution
        v_sw = total_solids_discarded + total_mud_lost # Total physical surface waste

        cost_mud = v_m_actual * self.mud_price
        cost_disposal = (v_sw + v_lw) * self.disposal_price
        
        # Actual LGS % remaining in the active mud system
        actual_lgs_pct = (v_c_retained / v_m_actual) * 100 if v_m_actual > 0 else 0
        system_efficiency = (total_solids_discarded / v_c_total) * 100 if v_c_total > 0 else 0

        return {
            "v_mud_actual": v_m_actual,
            "v_surface_waste": v_sw,
            "v_liquid_waste": v_lw,
            "system_efficiency_pct": system_efficiency,
            "cost_mud": cost_mud,
            "cost_disposal": cost_disposal,
            "total_equip_rent": total_daily_rent,
            "actual_lgs_pct": actual_lgs_pct
        }

class AdvancedDrillingPhysics:
    def __init__(self, t600, t300, t200, t100, t6, t3):
        """
        Initializes the Herschel-Bulkley fluid model from Fann 35 viscometer readings.
        Includes strict mathematical protections against division by zero.
        """
        self.base_tau_y = max(0.1, t3)  
        denominator = max(0.1, t300 - self.base_tau_y)
        numerator = max(0.1, t600 - self.base_tau_y)
        
        ratio = numerator / denominator
        self.base_n = max(0.1, min(3.32 * np.log10(ratio), 1.2)) # Flow Behavior Index (n)
        self.base_K = denominator / (511 ** self.base_n)         # Consistency Index (K)
        
        self.surface_temp = 80.0 
        self.geo_gradient = 1.6  

    def get_temp_at_depth(self, tvd_ft):
        """Calculates formation temperature at a specific True Vertical Depth."""
        return self.surface_temp + (self.geo_gradient * (tvd_ft / 100.0))

    def calculate_actual_density(self, base_mw, lgs_pct):
        """Calculates actual mud weight factoring in the accumulation of LGS."""
        lgs_sg_ppg = 21.7 # Specific gravity of standard drill solids in ppg
        return round((base_mw * (1.0 - (lgs_pct/100.0))) + (lgs_sg_ppg * (lgs_pct/100.0)), 2)

    def calculate_rheology(self, lgs_pct, temp_f):
        """
        Calculates dynamic rheology shifts based on LGS accumulation (Krieger-Dougherty)
        and thermal degradation (Arrhenius equation).
        """
        temp_diff = temp_f - 120.0
        thermal_factor = np.exp(-0.005 * temp_diff) 
        
        # Prevent division by zero asymptote at max packing fraction (0.60)
        phi = min(0.59, lgs_pct / 100.0)
        rel_visc = (1 - (phi / 0.60)) ** (-2.5 * 0.60)
        
        actual_K = self.base_K * thermal_factor * rel_visc
        actual_tau_y = (self.base_tau_y + (0.8 * lgs_pct)) * (1.0 + (0.001 * temp_diff))
        
        # Simulate new Fann 35 readings based on degraded properties
        r600 = actual_tau_y + actual_K * (1022 ** self.base_n)
        r300 = actual_tau_y + actual_K * (511 ** self.base_n)
        
        return (round(self.base_n, 3), round(actual_K, 3), round(actual_tau_y, 1), 
                round(r600 - r300, 1), round((2*r300)-r600, 1), round(r600, 1), round(r300, 1))

    def calculate_hydraulics(self, n, K, tau_y, actual_mw_ppg, depth_ft, hole, dp, gpm, pp, rop_max):
        """
        Calculates Equivalent Circulating Density (ECD) using Yield-Power Law fluid flow equations.
        Restricts Rate of Penetration (ROP) based on ECD overbalance.
        """
        annular_cap = (hole**2 - dp**2) / 1029.4
        vel_ft_min = gpm / annular_cap
        
        gamma_a = (2.4 * vel_ft_min / (hole - dp)) * ((2 * n + 1) / (3 * n)) if hole > dp and n > 0 else 10.0
        tau_w_lb100 = 1.066 * (tau_y + K * (gamma_a ** n))
        
        ecd = actual_mw_ppg + (tau_w_lb100 / (15.6 * (hole - dp)) if hole > dp else 0)
        
        # ROP reduction due to chip hold-down effect (overbalance)
        rop = rop_max * np.exp(-0.3 * max(0, ecd - pp))
        
        return round(ecd, 2), round(rop, 1)
