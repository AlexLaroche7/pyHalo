import numpy as numpy
from colossus.halo.concentration import concentration, peaks
from pyHalo.Halos.halo_util import *
from scipy.optimize import minimize

import warnings
warnings.filterwarnings("ignore")

class HaloStructure(object):

    def __init__(self, lens_cosmo):

        self._lens_cosmo = lens_cosmo

    @staticmethod
    def _penalty_func(rt, rho_mean_host, subhalo_density_function, profile_args):
        rho_mean_sub = mean_density(rt, subhalo_density_function, profile_args)
        return np.absolute(rho_mean_host - rho_mean_sub)

    def truncation_mean_density_NFW_host(self, msub, csub, mhost, r_sub_3d,
                                         z_sub_eval, z_host_eval, r_ein_kpc, subhalo_density_function,
                                         subhalo_args, initial_guess):

        rho_sub, rs_sub, _ = self._lens_cosmo.NFW_params_physical(msub, csub, z_sub_eval)
        if r_sub_3d < r_ein_kpc:
            return 0.1 * rs_sub

        rho_host, rs_host, _ = self._lens_cosmo.NFW_params_physical_fromM(mhost, z_host_eval)

        host_mean_density = mean_density(r_sub_3d, rho_nfw, (rs_host, rho_host))

        args = (host_mean_density, subhalo_density_function, subhalo_args)
        opt = minimize(self._penalty_func, initial_guess, args, method='Nelder-Mead')
        return opt['x'][0]

    def truncation_mean_density_isothermal_host(self, msub, csub, mhost, r_sub_3d, z_sub_eval, z_host_eval,
                                                r_ein_kpc, sigmacrit_kpc, subhalo_density_function, subhalo_args,
                                                initial_guess):

        rho_sub, rs_sub, _ = self._lens_cosmo.NFW_params_physical(msub, csub, z_sub_eval)
        if r_sub_3d < r_ein_kpc:
            return 0.1 * rs_sub

        rho_host, rs_host, _ = self._lens_cosmo.NFW_params_physical_fromM(mhost, z_host_eval)

        host_mean_density = mean_density(r_sub_3d, rho_composite, (rs_host, r_ein_kpc, sigmacrit_kpc))

        args = (host_mean_density, subhalo_density_function, subhalo_args)

        opt = minimize(self._penalty_func, initial_guess, args, method='Nelder-Mead')

        return opt['x'][0]

    def truncation_roche(self, M, r3d, z, k, nu):

        """
        :param M: m200
        :param r3d: 3d radial position in the halo (kpc)
        :return: Equation 2 in Gilman et al 2019 (expressed in arcsec)
        (k tuned to match output of truncation roche exact)
        """

        exponent = nu * 3 ** -1
        rtrunc_kpc = k*(M / 10**6) ** (1./3) * (r3d * 100 ** -1) ** (exponent)

        return numpy.round(rtrunc_kpc * self._lens_cosmo.cosmo.kpc_per_asec(z) ** -1, 3)

    def LOS_truncation(self, M, z, N):
        """
        Truncate LOS halos at r50
        :param M:
        :param c:
        :param z:
        :param N:
        :return:
        """
        a_z = (1 + z) ** -1
        h = self._lens_cosmo.cosmo.h

        rN_physical_Mpc = self._lens_cosmo.rN_M_nfw_comoving(M * h, N) * a_z / h
        rN_physical_kpc = rN_physical_Mpc * 1000
        r_trunc_arcsec = rN_physical_kpc * self._lens_cosmo.cosmo.kpc_per_asec(z) ** -1

        return r_trunc_arcsec

    def _NFW_concentration(self, M, z, model, mdef, logmhm,
                          scatter, c_scale, c_power, scatter_amplitude):

        if isinstance(model, dict):

            assert 'custom' in model.keys()

            if isinstance(M, float) or isinstance(M, int):
                c = self._NFW_concentration_custom(M, z, model, scatter, scatter_amplitude)
            else:

                if isinstance(z, numpy.ndarray) or isinstance(z, list):
                    assert len(z) == len(M)
                    c = [self._NFW_concentration_custom(float(mi), z[i], model, scatter, scatter_amplitude)
                         for i, mi in enumerate(M)]
                else:
                    c = [self._NFW_concentration_custom(float(mi), z, model, scatter, scatter_amplitude)
                         for i, mi in enumerate(M)]

            return numpy.array(c)

        else:

            if isinstance(M, float) or isinstance(M, int):

                c = self._NFW_concentration_colossus(M, z, model, mdef, logmhm, scatter, c_scale, c_power,
                                                     scatter_amplitude)
                return c

            else:

                if isinstance(z, numpy.ndarray) or isinstance(z, list):
                    assert len(z) == len(M)
                    c = [self._NFW_concentration_colossus(float(mi), z[i], model, mdef, logmhm, scatter, c_scale,
                                                          c_power, scatter_amplitude)
                         for i, mi in enumerate(M)]
                else:
                    c = [self._NFW_concentration_colossus(float(mi), z, model, mdef, logmhm, scatter, c_scale, c_power,
                                                          scatter_amplitude)
                         for i, mi in enumerate(M)]

                return numpy.array(c)

    def _NFW_concentration_custom(self, M, z, args, scatter, scatter_amplitude):

        M_h = M * self._lens_cosmo.cosmo.h
        Mref_h = 10 ** 8 * self._lens_cosmo.cosmo.h
        nu = peaks.peakHeight(M_h, z)
        nu_ref = peaks.peakHeight(Mref_h, 0)

        assert args['beta'] >= 0, 'beta values < 0 are unphysical.'
        assert args['c0'] > 0, 'negative normalizations are unphysical.'

        c = args['c0'] * (1 + z) ** (args['zeta']) * (nu / nu_ref) ** (-args['beta'])

        if scatter:
            c += numpy.random.lognormal(numpy.log(c), scatter_amplitude)

        return c

    def _NFW_concentration_colossus(self, M, z, model, mdef, logmhm,
                                    scatter, c_scale, c_power, scatter_amplitude):

        # WDM relation adopted from Ludlow et al
        # use diemer19?
        def zfunc(z_val):
            return 0.026 * z_val - 0.04

        if isinstance(M, float) or isinstance(M, int):
            c = concentration(M * self._lens_cosmo.cosmo.h, mdef=mdef, model=model, z=z)
        else:
            con = []
            for i, mi in enumerate(M):
                con.append(concentration(mi * self._lens_cosmo.cosmo.h, mdef=mdef, model=model, z=z[i]))
            c = numpy.array(con)

        if logmhm != 0:
            mhm = 10 ** logmhm
            concentration_factor = (1 + c_scale * mhm * M ** -1) ** c_power
            redshift_factor = (1 + z) ** zfunc(z)
            rescale = redshift_factor * concentration_factor

            c = c * rescale

        # scatter from Dutton, maccio et al 2014
        if scatter:

            if isinstance(c, float) or isinstance(c, int):
                c = numpy.random.lognormal(numpy.log(c), 0.13)
            else:
                con = []
                for i, ci in enumerate(c):
                    con.append(numpy.random.lognormal(numpy.log(ci), scatter_amplitude))
                c = numpy.array(con)
        return c
