import math

class EconomicsAnalyzer:
    def __init__(self, rig_rate_per_day: float, bit_cost=25000.0, bit_life_hrs=150.0):
        """
        Initializes the AFE (Authority for Expenditure) calculator.
        bit_life_hrs: Average drilling hours before a bit becomes dull and requires replacement.
        """
        self.rig_rate = rig_rate_per_day
        self.bit_cost = bit_cost
        self.bit_life_hrs = bit_life_hrs 

    def calculate_time_cost(self, avg_rop: float, length_ft: float, actual_lgs_pct: float, target_lgs_pct: float, daily_equip_cost: float, daily_chem_penalty: float):
        """
        Evaluates the total time required for an interval and computes macroscopic costs.
        Applies continuous scaling for mud conditioning and calculates bit wear logistics.
        """
        # 1. Pure Drilling Time
        drilling_hrs = (length_ft / avg_rop) if avg_rop > 0 else 9999.0

        # 2. Bit Consumption & Tripping Mechanics
        # Calculate how many bits are destroyed based on total drilling hours
        bits_used = math.ceil(drilling_hrs / self.bit_life_hrs) if drilling_hrs < 9999.0 else 1
        total_bit_cost = bits_used * self.bit_cost

        # Tripping time: Assume ~1000 ft/hr tripping speed. 
        # Multiply by bits_used because every broken bit requires a full round trip (POOH + RIH).
        tripping_hrs = bits_used * (2.0 * (length_ft / 1000.0))

        # 3. Dynamic Mud Conditioning Penalty (Continuous Scale)
        # If LGS exceeds the target, add 2.5 hours of circulation/conditioning time for every 1% over the limit.
        lgs_overage = max(0.0, actual_lgs_pct - target_lgs_pct)
        conditioning_hrs = lgs_overage * 2.5 

        # Total Days on Well
        t_days = (drilling_hrs + tripping_hrs + conditioning_hrs) / 24.0

        # 4. Macroscopic Financials (AFE)
        rig_cost = self.rig_rate * t_days
        chem_cost = daily_chem_penalty * t_days
        equip_rent_cost = daily_equip_cost * t_days

        total_afe_cost = rig_cost + total_bit_cost + equip_rent_cost + chem_cost

        return {
            "total_days": round(t_days, 2),
            "drilling_hrs": round(drilling_hrs, 1),
            "tripping_hrs": round(tripping_hrs, 1),
            "conditioning_hrs": round(conditioning_hrs, 1),
            "bits_used": bits_used,
            "rig_cost": rig_cost,
            "bit_cost": total_bit_cost,
            "chem_penalty_cost": chem_cost,
            "total_afe_cost": total_afe_cost
        }