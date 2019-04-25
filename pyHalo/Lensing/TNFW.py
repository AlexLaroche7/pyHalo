import numpy as np
from pyHalo.Halos.Profiles.tnfw import TNFW

class TNFWLensing(object):

    hybrid = False

    lenstronomy_ID = 'TNFW'

    def __init__(self,lens_cosmo):

        self.lens_cosmo = TNFW(lens_cosmo)

    def params(self, x, y, mass, concentration, redshift, r_trunc,  D_d = None, epscrit = None):

        Rs_angle, theta_Rs = self.lens_cosmo.tnfw_physical2angle(mass, concentration,
                                                                 r_trunc, redshift,
                                                                D_d=D_d, epscrit=epscrit)

        kwargs = {'theta_Rs':theta_Rs, 'Rs': Rs_angle,
                  'center_x':x, 'center_y':y, 'r_trunc':r_trunc}

        return kwargs, None

    def mass_finite(self, m200, c, z, tau):

        rho, Rs, r200 = self.lens_cosmo.NFW_params_physical(m200, c, z)

        t2 = tau ** 2

        return 4 * np.pi * Rs ** 3 * rho * t2 * (t2 + 1) ** -2 * (
                (t2 - 1) * np.log(tau) + np.pi * tau - (t2 + 1))

