from pyHalo.Cosmology.cosmology import Cosmology
from colossus.halo.concentration import concentration
import numpy

class LensCosmo(object):

    def __init__(self,z_lens,z_source):

        self.cosmo = Cosmology()
        self.z_lens, self.z_source = z_lens, z_source

        # critical density for lensing in units M_sun * Mpc ^ -2
        self.epsilon_crit = self.get_epsiloncrit(z_lens, z_source)
        # critical density for lensing in units M_sun * arcsec ^ -2 at lens redshift
        self.sigmacrit = self.epsilon_crit * (0.001) ** 2 * self.cosmo.kpc_per_asec(z_lens) ** 2
        # critical density of the universe in M_sun Mpc^-3
        self.rhoc = self.cosmo.astropy.critical_density0.value * self.cosmo.density_to_MsunperMpc
        # lensing distances
        self.D_d, self.D_s, self.D_ds = self.cosmo.D_A(0, z_lens), self.cosmo.D_A(0, z_source), self.cosmo.D_A(z_lens, z_source)
        # hubble distance in Mpc
        self._d_hubble = self.cosmo.c * self.cosmo.Mpc * 0.001 * (self.cosmo.h * 100)

    def get_epsiloncrit(self,z1,z2):

        D_ds = self.cosmo.D_A(z1, z2)
        D_d = self.cosmo.D_A(0, z1)
        D_s = self.cosmo.D_A(0, z2)

        epsilon_crit = (self.cosmo.c**2*(4*numpy.pi*self.cosmo.G)**-1)*(D_s*D_ds**-1*D_d**-1)

        return epsilon_crit

    def rhoc_comoving(self, z):

        Ez = self.cosmo.E_z(z)
        return self.rhoc * Ez ** 2

    def get_sigmacrit(self,z):

        return self.get_epsiloncrit(z,self.z_source)*(0.001)**2*self.cosmo.kpc_per_asec(z)**2

    def get_sigmacrit_z1z2(self,zlens,zsrc):

        return self.get_epsiloncrit(zlens,zsrc)*(0.001)**2*self.cosmo.kpc_per_asec(zlens)**2

    def vdis_to_Rein(self,zd,zsrc,vdis):

        return 4 * numpy.pi * (vdis * (0.001 * self.cosmo.c * self.cosmo.Mpc) ** -1) ** 2 * \
               self.cosmo.D_A(zd, zsrc) * self.cosmo.D_A(0,zsrc) ** -1 * self.cosmo.arcsec ** -1

    def vdis_to_Reinkpc(self,zd,zsrc,vdis):

        return self.cosmo.kpc_per_asec(zd)*self.cosmovdis_to_Rein(zd,zsrc,vdis)

    def beta(self,z,zmain,zsrc):

        D_12 = self.cosmo.D_A(zmain, z)
        D_os = self.cosmo.D_A(0, zsrc)
        D_1s = self.cosmo.D_A(zmain, zsrc)
        D_o2 = self.cosmo.D_A(0, z)

        return D_12 * D_os * (D_o2 * D_1s) ** -1

    def nfw_physical2angle(self, M, c, z):
        """
        converts the physical mass and concentration parameter of an NFW profile into the lensing quantities
        :param M: mass enclosed 200 \rho_crit
        :param c: NFW concentration parameter (r200/r_s)
        :return: theta_Rs (observed bending angle at the scale radius, Rs_angle (angle at scale radius) (in units of arcsec)
        """
        D_d = self.cosmo.D_A(0, z)
        rho0, Rs, r200 = self._nfwParam_physical_Mpc(M, c, z)
        Rs_angle = Rs / D_d / self.cosmo.arcsec  # Rs in arcsec
        theta_Rs = rho0 * (4 * Rs ** 2 * (1 + numpy.log(1. / 2.)))
        eps_crit = self.get_epsiloncrit(z, self.z_source)
        return Rs_angle, theta_Rs / eps_crit / self.D_d / self.cosmo.arcsec

    def _nfwParam_physical_Mpc(self, M, c, z):
        """
        returns the NFW parameters in physical units
        :param M: physical mass in M_sun
        :param c: concentration
        :return:
        """
        h = self.cosmo.h
        a_z = self.cosmo.scale_factor(z)

        r200 = self.r200_M(M * h) * a_z / h   # physical radius r200
        rho0 = self.rho0_c(c) * h**2 / a_z**3 # physical density in M_sun/Mpc**3
        Rs = r200/c
        return rho0, Rs, r200

    def NFW_params_physical(self, M, c, z):

        rho0, Rs, r200 = self._nfwParam_physical_Mpc(M, c, z)

        return rho0 * 1000 ** -3, Rs * 1000, r200 * 1000

    def NFW_truncation(self,M,c,r3d,z,zlens):

        if z == zlens:
            return (0.5 * M * r3d ** 2 / self.sigmacrit) ** (1. / 3)

        else:
            _, _, r200_kpc = self.NFW_params_physical(M, c, z)

            r200_arcsec = r200_kpc * self.cosmo.kpc_per_asec(z) ** -1

            return r200_arcsec

    def rho0_c(self, c):
        """
        computes density normalization as a function of concentration parameter
        :return: density normalization in h^2/Mpc^3 (comoving)
        """

        return 200. / 3 * self.rhoc * c ** 3 / (numpy.log(1 + c) - c / (1 + c))

    def r200_M(self, M):
        """
        computes the radius R_200 of a halo of mass M in comoving distances M/h
        :param M: halo mass in M_sun/h
        :type M: float or numpy array
        :return: radius R_200 in comoving Mpc/h
        """

        return (3 * M / (4 * numpy.pi * self.rhoc * 200)) ** (1. / 3.)

    def point_mass_fac(self,z):
        """
        This factor times sqrt(M) gives the einstein radius for a point mass in arcseconds
        :param z:
        :return:
        """
        const = 4 * self.cosmo.G * self.cosmo.c ** -2 * self.D_A(z, self.z_source) * (self.D_A(z) * self.D_s) ** -1
        return self.cosmo.arcsec ** -1 * const ** .5

    def NFW_concentration(self,M,z,model='bullock01',mdef='200c',logmhm=0,
                                scatter=True,g1=None,g2=None):

        # WDM relation adopted from Ludlow et al

        def zfunc(z_val):
            return 0.026*z_val - 0.04

        if isinstance(M, float) or isinstance(M, int):
            c = concentration(M*self.cosmo.h,mdef=mdef,model=model,z=z)
        else:
            con = []
            for i,mi in enumerate(M):

                con.append(concentration(mi*self.cosmo.h,mdef=mdef,model=model,z=z[i]))
            c = numpy.array(con)

        if logmhm != 0:

            mhm = 10**logmhm
            concentration_factor = (1+g1*mhm*M**-1)**g2
            redshift_factor = (1+z)**zfunc(z)
            rescale = redshift_factor * concentration_factor

            c = c * rescale

        # scatter from Dutton, maccio et al 2014
        if scatter:

            if isinstance(c, float) or isinstance(c, int):
                c = numpy.random.lognormal(numpy.log(c),0.13)
            else:
                con = []
                for i, ci in enumerate(c):
                    con.append(numpy.random.lognormal(numpy.log(ci),0.13))
                c = numpy.array(con)
        return c

    def convert_fsub_to_norm(self, fsub, cone_diameter, plaw_index, mlow, mhigh):

        R = cone_diameter*0.5
        area = numpy.pi*R**2

        # convergence is approximately 1/2 at the Einstein radius, this paramterization assumes
        # f_darkmatter >> f_baryon at Einstein radius, so convergence fraction in substructure = 0.5 * fsub
        kappa_sub = 0.5 * fsub

        power = 2 + plaw_index
        integral = power / (mhigh ** power - mlow ** power)

        return area * kappa_sub * self.sigmacrit * integral


