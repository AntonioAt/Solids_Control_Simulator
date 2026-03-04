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