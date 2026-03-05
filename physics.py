import numpy as np

class AdvancedDrillingPhysics:
    def __init__(self, t600, t300, t200, t100, t6, t3):
        """
        Initializes baseline fluid properties using API RP 13D Bingham Plastic standards.
        """
        self.base_pv = max(1.0, t600 - t300)
        self.base_yp = max(1.0, t300 - self.base_pv)
        self.base_tau_y = max(0.1, t3) 

        self.surface_temp = 80.0 
        self.geo_gradient = 1.6  

    def get_temp_at_depth(self, tvd_ft):
        return self.surface_temp + (self.geo_gradient * (tvd_ft / 100.0))

    def calculate_actual_density(self, base_mw, lgs_pct, hgs_pct):
        """
        Calculates fluid density dynamically using Volume Additivity.
        Water = 8.33 ppg, LGS = 21.7 ppg, HGS (Barite) = 35.0 ppg
        """
        water_pct = max(0.0, 100.0 - lgs_pct - hgs_pct)
        return round((8.33 * (water_pct/100.0)) + (21.7 * (lgs_pct/100.0)) + (35.0 * (hgs_pct/100.0)), 2)

    def calculate_rheology(self, lgs_pct, temp_f):
        """
        Calculates degraded rheology using Bourgoyne et al. (Applied Drilling Engineering)
        exponential model, preventing infinite mathematical explosion.
        """
        phi = lgs_pct / 100.0

        # Empirical constants for particle friction (Kp) and electrochemical attraction (Ky)
        Kp = 4.0 
        Ky = 6.0 

        # Exponential growth based on LGS volume fraction
        actual_pv = self.base_pv * np.exp(Kp * phi)
        actual_yp = self.base_yp * np.exp(Ky * phi)
        actual_tau_y = self.base_tau_y * np.exp(Ky * phi)

        # Thermal degradation (Arrhenius Equation)
        temp_diff = temp_f - 120.0
        thermal_factor = np.exp(-0.002 * temp_diff) 

        actual_pv *= thermal_factor
        actual_yp *= thermal_factor

        # Back-calculate API RP 13D Fann Dial Readings to reflect reality
        r300 = actual_pv + actual_yp
        r600 = actual_pv + r300

        # Power Law metrics for Hydraulics
        n_api = 3.32 * np.log10(r600 / r300) if r300 > 0 else 1.0
        k_api = r300 / (511 ** n_api) if n_api > 0 else 0.0

        return (round(n_api, 3), round(k_api, 3), round(actual_tau_y, 1), 
                round(actual_pv, 1), round(actual_yp, 1), round(r600, 1), round(r300, 1))

    def calculate_hydraulics(self, n, K, tau_y, actual_mw_ppg, depth_ft, hole, dp, gpm, pp, rop_max):
        annular_cap = (hole**2 - dp**2) / 1029.4
        vel_ft_min = gpm / annular_cap

        gamma_a = (2.4 * vel_ft_min / (hole - dp)) * ((2 * n + 1) / (3 * n)) if hole > dp and n > 0 else 10.0
        tau_w_lb100 = 1.066 * (tau_y + K * (gamma_a ** n))

        ecd = actual_mw_ppg + (tau_w_lb100 / (15.6 * (hole - dp)) if hole > dp else 0)
        rop = rop_max * np.exp(-0.3 * max(0, ecd - pp))

        return round(ecd, 2), round(rop, 1)