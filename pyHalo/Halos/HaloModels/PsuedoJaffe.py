from pyHalo.Halos.halo_base import Halo
from pyHalo.Halos.concentration import Concentration
import numpy as np


class PJaffeSubhalo(Halo):

    def __init__(self, mass, x, y, r3d, mdef, z,
                 sub_flag, lens_cosmo_instance, args, unique_tag):

        self._lens_cosmo = lens_cosmo_instance
        self._concentration = Concentration(lens_cosmo_instance)

        super(PJaffeSubhalo, self).__init__(mass, x, y, r3d, mdef, z, sub_flag,
                                            lens_cosmo_instance, args, unique_tag)

    @property
    def lenstronomy_params(self):

        if not hasattr(self, '_lenstronomy_args'):
            (concentration) = self.profile_args
            _, rs_kpc, r200_kpc = self._lens_cosmo.NFW_params_physical(self.mass, concentration, self.z)

            r_a_kpc = 0.001 * rs_kpc
            Sigma0 = self.mass/rs_kpc/(2*np.pi*r_a_kpc) # units M_sun / kpc^2

            sigma_crit_Mpc = self._lens_cosmo.get_sigma_crit_lensing(self.z, self._lens_cosmo.z_source)
            sigma_crit_kpc = sigma_crit_Mpc * 1000 ** -2
            sigma_0 = Sigma0/sigma_crit_kpc

            kpc_to_arcsec = 1/self._lens_cosmo.cosmo.kpc_proper_per_asec(self.z)
            r_trunc_arcsec = rs_kpc * kpc_to_arcsec
            r_a_arcsec = r_a_kpc * kpc_to_arcsec

            self._lenstronomy_args = {'center_x': self.x, 'center_y': self.y, 'Ra': r_a_arcsec,
                'Rs': r_trunc_arcsec, 'sigma0': sigma_0}

        return self._lenstronomy_args, None

    @property
    def lenstronomy_ID(self):
        return 'PJAFFE'

    @property
    def profile_args(self):

        if not hasattr(self, '_profile_args'):

            if self._args['evaluate_mc_at_zlens']:
                z_eval = self.z
            else:
                z_eval = self.z_infall

            concentration = self._concentration.NFW_concentration(self.mass,
                                                                  z_eval,
                                                                  self._args['mc_model'],
                                                                  self._args['mc_mdef'],
                                                                  self._args['log_mc'],
                                                                  self._args['c_scatter'],
                                                                  self._args['c_scale'],
                                                                  self._args['c_power'],
                                                                  self._args['c_scatter_dex'])

            self._profile_args = (concentration)

        return self._profile_args