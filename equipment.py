import numpy as np
from abc import ABC, abstractmethod

# Standard particle size representation in microns (Coarse to Ultra-Fine)
# Bins: [>2000, 1000-2000, 500-1000, 250-500, 120-250, 74-120, 40-74, 20-40, 10-20, <10]
PARTICLE_BINS = np.array([2000, 1000, 500, 250, 120, 74, 40, 20, 10, 2])

class SolidControlEquipment(ABC):
    def __init__(self, name: str, base_cost: float, chem_penalty: float, base_loc: float, d50_microns: float, sharpness: float):
        self.name = name
        self.base_cost = base_cost
        self.chem_penalty = chem_penalty
        self.loc_ratio = base_loc       # Equipment-specific Liquid on Cuttings (bbl liquid / bbl solid)
        self.d50 = d50_microns          # 50% cut-point (separation efficiency threshold)
        self.m = sharpness              # Separation curve sharpness (Tromp curve)

    def calculate_separation_curve(self):
        """Calculates the discard probability for each particle size using the Tromp Curve."""
        if self.d50 == 0: 
            return np.zeros_like(PARTICLE_BINS, dtype=float)

        # Exponential separation model based on API standards
        prob = 1.0 - np.exp(-0.693 * (PARTICLE_BINS / self.d50)**self.m)
        return np.clip(prob, 0.0, 1.0)

    def process_fluid(self, psd_in_array):
        """
        Receives an array of particle volumes, applies the separation cut, 
        and returns the passed particles, discarded solids, and lost mud (LOC).
        """
        separation_curve = self.calculate_separation_curve()

        # Array of discarded particle volumes
        psd_discarded = psd_in_array * separation_curve

        # Array of particle volumes passing to the next equipment (Cascade effect)
        psd_passed = psd_in_array - psd_discarded

        # Scalar calculations for Mass Balance accounting
        solid_vol_discarded = np.sum(psd_discarded)
        mud_lost = solid_vol_discarded * self.loc_ratio

        return psd_passed, solid_vol_discarded, mud_lost

# --- SPECIFIC EQUIPMENT CLASSES ---

class ShaleShaker(SolidControlEquipment):
    def __init__(self, api_mesh=120):
        # API 120 roughly corresponds to a D50 of 116 microns. High LOC (Wet discharge).
        d50_approx = 14000 / api_mesh if api_mesh > 0 else 0 
        super().__init__(name=f"Shale Shaker (API {api_mesh})", base_cost=500.0, chem_penalty=0.0, base_loc=1.2, d50_microns=d50_approx, sharpness=3.0)

class Desander(SolidControlEquipment):
    def __init__(self):
        # Cuts sand particles (>40 microns). Very high LOC if used without an underflow screen.
        super().__init__(name="Desander", base_cost=300.0, chem_penalty=200.0, base_loc=2.0, d50_microns=40.0, sharpness=2.0)

class Desilter(SolidControlEquipment):
    def __init__(self):
        # Cuts silt particles (>20 microns). High LOC.
        super().__init__(name="Desilter", base_cost=400.0, chem_penalty=300.0, base_loc=1.5, d50_microns=20.0, sharpness=2.5)

class MudCleaner(SolidControlEquipment):
    def __init__(self):
        # Hydrocyclones positioned over a shaker screen. Recovers more fluid than a standard desilter.
        super().__init__(name="Mud Cleaner", base_cost=800.0, chem_penalty=150.0, base_loc=0.8, d50_microns=15.0, sharpness=3.0)

class Centrifuge(SolidControlEquipment):
    def __init__(self, rpm=2500):
        # Cuts ultra-fine/colloidal particles (~ 5 microns). Low LOC (Dry/Paste discharge).
        d50_approx = max(2.0, 15.0 - (rpm / 500.0))
        super().__init__(name=f"Centrifuge ({rpm} RPM)", base_cost=1500.0, chem_penalty=1200.0, base_loc=0.4, d50_microns=d50_approx, sharpness=1.5)

# --- EQUIPMENT SYSTEM MANAGER ---

class EquipmentSystemManager:
    def __init__(self, equipment_list):
        """
        Initializes the manager with a sequential list of solid control equipment.
        Example: [ShaleShaker(120), Desander(), Centrifuge(2500)]
        """
        self.equipments = equipment_list

    def process_system(self, initial_psd_volume_array):
        """
        Simulates the flow of drilling fluid through the entire equipment cascade.
        Returns the residual fluid and the aggregated mechanical and financial metrics.
        """
        current_psd = initial_psd_volume_array.copy()

        total_system_discarded = 0.0
        total_system_mud_lost = 0.0
        total_chem_penalty = 0.0
        total_daily_cost = 0.0

        # Fluid cascades sequentially from one machine to the next
        for eq in self.equipments:
            current_psd, discarded_vol, mud_lost = eq.process_fluid(current_psd)

            # Accumulate system-wide metrics
            total_system_discarded += discarded_vol
            total_system_mud_lost += mud_lost
            total_chem_penalty += eq.chem_penalty
            total_daily_cost += eq.base_cost

        # The remaining 'current_psd' represents the LGS that failed to be removed
        return {
            "retained_psd_array": current_psd,
            "total_solids_discarded": total_system_discarded,
            "total_mud_lost": total_system_mud_lost,
            "total_daily_cost": total_daily_cost,
            "total_chem_penalty": total_chem_penalty
        }

# --- OOP FACTORY ADAPTER ---

def build_and_evaluate_equipment(shaker_meshes, ds_on, dl_on, mc_on, cf_rpms):
    """
    Factory function: Translates raw UI parameters into instantiated physics objects,
    runs a theoretical cascade preview, and returns the metrics for the UI dashboard.
    """
    equipment_objects = []
    labels = []

    # 1. Instantiate Primary Shakers
    if shaker_meshes:
        for mesh in sorted(shaker_meshes):
            equipment_objects.append(ShaleShaker(api_mesh=mesh))
            labels.append(f"Sh({mesh})")

    # 2. Instantiate Hydrocyclones
    if ds_on:
        equipment_objects.append(Desander())
        labels.append("DS")
    if dl_on:
        equipment_objects.append(Desilter())
        labels.append("DL")
    if mc_on:
        equipment_objects.append(MudCleaner())
        labels.append("MC")

    # 3. Instantiate Centrifuges
    if cf_rpms:
        for rpm in sorted(cf_rpms):
            equipment_objects.append(Centrifuge(rpm=rpm))
            labels.append(f"CF({rpm})")

    manager = EquipmentSystemManager(equipment_objects)

    # Theoretical PSD mock-up to generate preview metrics for the UI sidebar
    mock_psd_in = np.array([10.0] * len(PARTICLE_BINS), dtype=float)
    total_input_volume = np.sum(mock_psd_in)

    cascade_results = manager.process_system(mock_psd_in)
    
    total_discarded = cascade_results["total_solids_discarded"]
    daily_cost = cascade_results["total_daily_cost"]
    chem_pen = cascade_results["total_chem_penalty"]

    effective_mech_X = total_discarded / total_input_volume if total_input_volume > 0 else 0

    # Synergy Discount for Dual Centrifuges
    if len(cf_rpms) >= 2:
        chem_pen *= 0.40  
        labels.append("[Barite Rec.]")

    return effective_mech_X, daily_cost, chem_pen, labels, equipment_objects
