import numpy as np
from pyHalo.Halos.Profiles.nfw import NFW

class NFWLensing(object):

    hybrid = False

    lenstronomy_ID = 'NFW'

    def __init__(self, lens_cosmo = None, zlens = None, z_source = None):

        if lens_cosmo is None:
            from pyHalo.Cosmology.lens_cosmo import LensCosmo
            lens_cosmo = LensCosmo(zlens, z_source)

        self.lens_cosmo = NFW(lens_cosmo)

    def params(self, x, y, mass, concentration, redshift,  D_d = None, epscrit = None):

        Rs_angle, theta_Rs = self.lens_cosmo.nfw_physical2angle(mass, concentration, redshift,
                                                                D_d=D_d, epscrit=epscrit)

        kwargs = {'theta_Rs':theta_Rs, 'Rs': Rs_angle,
                  'center_x':x, 'center_y':y}

        return kwargs, None

    def M_physical(self, m, c, z):
        """
        :param m200: m200
        :return: physical mass corresponding to m200
        """
        rho0, Rs, r200 = self.lens_cosmo.NFW_params_physical(m,c,z)
        return 4*np.pi*rho0*Rs**3*(np.log(1+c)-c*(1+c)**-1)
