from pyHalo.Halos.halo_base import Halo
from pyHalo.defaults import *
from pyHalo.Halos.lens_cosmo import LensCosmo
from pyHalo.Cosmology.cosmology import Cosmology
from pyHalo.Cosmology.lensing_mass_function import LensingMassFunction
from pyHalo.Rendering.Main.SHMF_normalizations import *
from pyHalo.Halos.HaloModels.NFW import NFWSubhhalo, NFWFieldHalo
from pyHalo.Halos.HaloModels.TNFW import TNFWFieldHalo, TNFWSubhhalo
from pyHalo.Halos.HaloModels.PsuedoJaffe import PJaffeSubhalo
from pyHalo.Halos.HaloModels.PTMass import PTMass

from copy import deepcopy

def realization_at_z(realization, z, angular_coordinate_x=None, angular_coordinate_y=None, max_range=None):
    """

    :param realization: an instance of Realization
    :param z: the redshift where we want to extract halos
    :param angular_coordinate_x: if max_range is specified, will only keep halos within
    max_range of (angular_coordinate_x, angular_coordinate_y)
    :param angular_coordinate_y:
    :param max_range: radius in arcseconds where we want to keep halos. If None, will return a new realization class
     that contains all halos at redshift z contained in the input realization class
    :return: a new instance of Realization
    """

    _halos, _indexes = realization.halos_at_z(z)
    halos = []
    indexes = []

    if max_range is not None:
        for i, halo in enumerate(_halos):
            dx, dy = halo.x - angular_coordinate_x, halo.y - angular_coordinate_y
            dr = (dx ** 2 + dy ** 2) ** 0.5
            if dr < max_range:
                halos.append(halo)
                indexes.append(i)
    else:
        halos = _halos
        indexes = _indexes

    return Realization.from_halos(halos, realization.halo_mass_function,
                                  realization._prof_params, realization._mass_sheet_correction,
                                  realization.rendering_classes), indexes

class Realization(object):

    def __init__(self, masses, x, y, r3d, mdefs, z, subhalo_flag, halo_mass_function,
                 halos=None, halo_profile_args={}, mass_sheet_correction=True, dynamic=False,
                 rendering_classes=None):

        """

        This class is the main class that stores information regarding realizations of dark matter halos. It is not
        intended to be created directly by the user. Instances of this class are created through the class
        pyHalo or pyHalo_dynamic.

        :param masses: an array of halo masses (units solar mass)
        :param x: an array of halo x-coordinates (units arcsec)
        :param y: an array of halo y-coordinates (units arcsec)
        :param r2d: an array of halo 2-d distances from lens center (units kpc / (kpc/arsec), or arcsec,
        at halo redshift)
        :param r3d: an array of halo 2-d distances from lens center (units kpc / (kpc/arsec), or arcsec,
        at halo redshift)
        :param mdefs: mass definition of each halo
        :param z: halo redshift
        :param subhalo_flag: whether each halo is a subhalo or a regular halo
        :param halo_mass_function: an instance of LensingMassFunction (see Cosmology.LensingMassFunction)
        :param halos: a list of halo class instances
        :param halo_profile_args: kwargs for the realiztion
        :param mass_sheet_correction: whether to apply a mass sheet correction
        :param dynamic: whether the realization is rendered with pyhalo_dynamic or not
        :param rendering_classes: a list of rendering class instances
        """

        self.apply_mass_sheet_correction = mass_sheet_correction

        self.halo_mass_function = halo_mass_function
        self.geometry = halo_mass_function.geometry
        self.lens_cosmo = LensCosmo(self.geometry._zlens, self.geometry._zsource,
                                    self.geometry._cosmo)

        self.halos = []
        self._loaded_models = {}
        self._has_been_shifted = False

        self._prof_params = set_default_kwargs(halo_profile_args, dynamic, self.geometry._zsource)

        if halos is None:

            for mi, xi, yi, r3di, mdefi, zi, sub_flag in zip(masses, x, y, r3d,
                           mdefs, z, subhalo_flag):

                unique_tag = np.random.rand()
                model = self._load_halo_model(mi, xi, yi, r3di, mdefi, zi, sub_flag, self.lens_cosmo,
                                              self._prof_params, unique_tag)
                self.halos.append(model)


        else:

            self.halos = halos

        self._reset()

        self.set_rendering_classes(rendering_classes)

    @classmethod
    def from_halos(cls, halos, halo_mass_function, prof_params, msheet_correction, rendering_classes):

        """

        :param halos: a list of halo class instances
        :param halo_mass_function: an instance of LensingMassFunction (see Cosmology.LensingMassFunction)
        :param prof_params: keyword arguments for the realization
        :param msheet_correction: whether or not to apply a mass sheet correction
        :param rendering_classes: a list of rendering classes
        :return: an instance of Realization created directly from the halo class instances
        """

        realization = Realization(None, None, None, None, None, None, None, halo_mass_function,
                                  halos=halos, halo_profile_args=prof_params,
                                  mass_sheet_correction=msheet_correction,
                                  rendering_classes=rendering_classes)

        return realization

    def filter(self, aperture_radius_front,
               aperture_radius_back,
               log_mass_allowed_in_aperture_front,
               log_mass_allowed_in_aperture_back,
               log_mass_allowed_global_front,
               log_mass_allowed_global_back,
               interpolated_x_angle, interpolated_y_angle,
               zmin=None, zmax=None):

        """

        :param aperture_radius_front: the radius of a circular window around each light ray where halos are halo kept
        if they are more massive than log_mass_allowed_in_aperture_front (applied for z < z_lens)
        :param aperture_radius_back: the radius of a circular window around each light ray where halos are halo kept
        if they are more massive than log_mass_allowed_in_aperture_back (applied for z < z_lens)
        :param log_mass_allowed_in_aperture_front: the minimum halo mass to be kept inside the tube around each light ray
        in the foreground
        :param log_mass_allowed_in_aperture_back: the minimum halo mass to be kept inside the tube around each light ray
        in the background
        :param log_mass_allowed_global_front: The minimum mass to be kept everywhere in the foreground (if this is smaller
        than log_mass_allowed_in_aperture_front, then the argument aperture_radius_front will have no effect)
        :param log_mass_allowed_global_back: The minimum mass to be kept everywhere in the background (if this is smaller
        than log_mass_allowed_in_aperture_back, then the argument aperture_radius_back will have no effect)
        :param interpolated_x_angle: a list of scipy.interp1d that retuns the x angular position of a ray in
        arcsec given a comoving distance
        :param interpolated_y_angle: a list of scipy.interp1d that retuns the y angular position of a ray in
        arcsec given a comoving distance
        :param zmin: only keep halos at z > zmin
        :param zmax: only keep halos at z < zmax
        :return: A new instance of Realization with the cuts on position and mass applied
        """
        halos = []

        if zmax is None:
            zmax = self.geometry._zsource
        if zmin is None:
            zmin = 0

        for plane_index, zi in enumerate(self.unique_redshifts):

            plane_halos, _ = self.halos_at_z(zi)
            inds_at_z = np.where(self.redshifts == zi)[0]
            x_at_z = self.x[inds_at_z]
            y_at_z = self.y[inds_at_z]
            masses_at_z = self.masses[inds_at_z]

            if zi < zmin:
                continue
            if zi > zmax:
                continue

            comoving_distance_z = self.lens_cosmo.cosmo.D_C_z(zi)

            if zi <= self.geometry._zlens:

                minimum_mass_everywhere = deepcopy(log_mass_allowed_global_front)
                minimum_mass_in_window = deepcopy(log_mass_allowed_in_aperture_front)
                position_cut_in_window = deepcopy(aperture_radius_front)

            else:

                minimum_mass_everywhere = deepcopy(log_mass_allowed_global_back)
                minimum_mass_in_window = deepcopy(log_mass_allowed_in_aperture_back)
                position_cut_in_window = deepcopy(aperture_radius_back)

            keep_inds_mass = np.where(masses_at_z >= 10 ** minimum_mass_everywhere)[0]

            inds_m_low = np.where(masses_at_z < 10 ** minimum_mass_everywhere)[0]

            keep_inds_dr = []
            for idx in inds_m_low:
                for k, (interp_x, interp_y) in enumerate(zip(interpolated_x_angle, interpolated_y_angle)):

                    dx = x_at_z[idx] - interp_x(comoving_distance_z)
                    dy = y_at_z[idx] - interp_y(comoving_distance_z)
                    dr = np.sqrt(dx ** 2 + dy ** 2)
                    if dr <= position_cut_in_window:
                        keep_inds_dr.append(idx)
                        break

            keep_inds = np.append(keep_inds_mass, np.array(keep_inds_dr)).astype(int)

            tempmasses = masses_at_z[keep_inds]
            keep_inds = keep_inds[np.where(tempmasses >= 10 ** minimum_mass_in_window)[0]]

            for halo_index in keep_inds:
                halos.append(plane_halos[halo_index])

        return Realization.from_halos(halos, self.halo_mass_function, self._prof_params,
                                      self.apply_mass_sheet_correction, self.rendering_classes)

    def set_rendering_classes(self, rendering_classes):

        if not isinstance(rendering_classes, list):
            rendering_classes = [rendering_classes]
        self.rendering_classes = rendering_classes

    def join(self, real):
        """

        :param real: another realization, possibly a filtered version of self
        :return: a new realization with all unique halos from self and real
        """
        halos = []

        tags = self._tags(self.halos)
        real_tags = self._tags(real.halos)
        if len(tags) >= len(real_tags):
            long, short = tags, real_tags
            halos_long, halos_short = self.halos, real.halos
        else:
            long, short = real_tags, tags
            halos_long, halos_short = real.halos, self.halos

        for halo in halos_short:
            halos.append(halo)

        for i, tag in enumerate(long):

            if tag not in short:
                halos.append(halos_long[i])

        return Realization.from_halos(halos, self.halo_mass_function, self._prof_params,
                                      self.apply_mass_sheet_correction, self.rendering_classes)

    def shift_background_to_source(self, ray_interp_x, ray_interp_y):

        """

        :param ray_interp_x: instance of scipy.interp1d, returns the angular position of a ray
        fired through the lens center given a comoving distance
        :param ray_interp_y: same but for the y coordinate
        :return:
        """

        # add all halos in front of main deflector with positions unchanged
        halos = []

        if self._has_been_shifted:
            return self

        for halo in self.halos:

            comoving_distance_z = self.lens_cosmo.cosmo.D_C_z(halo.z)

            xshift, yshift = ray_interp_x(comoving_distance_z), ray_interp_y(comoving_distance_z)
            new_halo = deepcopy(halo)
            new_halo.x += xshift
            new_halo.y += yshift
            halos.append(new_halo)

        new_realization = Realization.from_halos(halos, self.halo_mass_function, self._prof_params,
                                                 self.apply_mass_sheet_correction,
                                                 rendering_classes=self.rendering_classes)

        new_realization._has_been_shifted = True

        return new_realization

    def lensing_quantities(self, add_mass_sheet_correction=True, z_mass_sheet_max=None):

        """

        :param return_kwargs: return the lens_model_list, kwrargs_list, etc. as keyword arguments in a dict
        :param add_mass_sheet_correction: include sheets of negative convergence to correct for mass added subhalos/field halos
        :param z_mass_sheet_max: don't include negative convergence sheets at z>z_mass_sheet_max (this does nothing
        if the previous argument is False

        :return: the lens_model_list, redshift_list, kwargs_lens, and numerical_alpha_class keywords that can be plugged
        directly into a lenstronomy LensModel class
        """

        kwargs_lens = []
        lens_model_list = []
        redshift_array = []
        kwargs_lensmodel = None

        for i, halo in enumerate(self.halos):

            lens_model_name = halo.lenstronomy_ID
            kwargs_halo, numerical_interp = halo.lenstronomy_params

            lens_model_list.append(lens_model_name)
            kwargs_lens.append(kwargs_halo)
            redshift_array += [halo.z]

        if self.apply_mass_sheet_correction and add_mass_sheet_correction:

            if self.rendering_classes is None:
                raise Exception('if applying a convergence sheet correction, must specify '
                                'the rendering classes.')

            kwargs_mass_sheets, profile_list, z_sheets = self._mass_sheet_correction(self.rendering_classes,
                                                                                     z_mass_sheet_max)
            kwargs_lens += kwargs_mass_sheets
            lens_model_list += profile_list
            redshift_array = np.append(redshift_array, z_sheets)

        return lens_model_list, redshift_array, kwargs_lens, kwargs_lensmodel

    def halo_comoving_coordinates(self, halos):

        """
        :param halos: a list of halos
        :return: the comoving (x, y) position, mass, and redshift of each halo in the realization
        """
        xcoords, ycoords, masses, redshifts = [], [], [], []

        for halo in halos:
            D = self.lens_cosmo.cosmo.D_C_transverse(halo.z)
            x_arcsec, y_arcsec = halo.x, halo.y
            x_comoving, y_comoving = D * x_arcsec, D * y_arcsec
            xcoords.append(x_comoving)
            ycoords.append(y_comoving)
            masses.append(halo.mass)
            redshifts.append(halo.z)

        return np.array(xcoords), np.array(ycoords), np.log10(masses), np.array(redshifts)

    def split_at_z(self, z):

        halos_1, halos_2 = [], []
        for halo in self.halos:
            if halo.z <= z:
                halos_1.append(halo)
            else:
                halos_2.append(halo)

        realization_1 = Realization.from_halos(halos_1, self.halo_mass_function,
                                               self._prof_params, self.apply_mass_sheet_correction, self.rendering_classes)
        realization_2 = Realization.from_halos(halos_2, self.halo_mass_function,
                                               self._prof_params, self.apply_mass_sheet_correction, self.rendering_classes)

        return realization_1, realization_2

    def halos_at_z(self,z):

        halos = []
        index = []
        for i, halo in enumerate(self.halos):
            if halo.z != z:
                continue
            halos.append(halo)
            index.append(i)

        return halos, index

    def mass_at_z_exact(self, z):

        inds = np.where(self.redshifts == z)
        m_exact = np.sum(self.masses[inds])
        return m_exact

    def number_of_halos_before_redshift(self, z):
        n = 0
        for halo in self.halos:
            if halo.z < z:
                n += 1
        return n

    def number_of_halos_after_redshift(self, z):
        n = 0
        for halo in self.halos:
            if halo.z > z:
                n += 1
        return n

    def number_of_halos_at_redshift(self, z):

        n = 0
        for halo in self.halos:
            if halo.z == z:
                n += 1
        return n

    def _mass_sheet_correction(self, rendering_classes, z_mass_sheet_max):

        """
        This routine adds the negative mass sheet corrections along the LOS and in the main lens plane.
        The actual physics that determines the amount of negative convergence to add is encoded in the rendering_classes
        (see for example Rendering.Field.PowerLaw.powerlaw_base.py)

        :param rendering_classes: the rendering class associated with each realization
        :param z_mass_sheet_max: don't include convergence sheets at redshift > z_mass_sheet_max
        :return: the kwargs_lens, lens_model_list, and redshift_list of the mass sheets that can be plugged into lenstronomy
        """

        kwargs_mass_sheets = []

        redshifts = []

        profiles = []

        if self._prof_params['subtract_exact_mass_sheets']:

            for zi in self.unique_redshifts:
                area = self.geometry.angle_to_physical_area(0.5 * self.geometry.cone_opening_angle, zi)
                kwargs_mass_sheets = [{'kappa_ext': -self.mass_at_z_exact(zi) / self.lens_cosmo.sigma_crit_mass(zi, area)}]

            redshifts = self.unique_redshifts

            profiles = ['CONVERGENCE'] * len(kwargs_mass_sheets)

        else:

            for rendering_class in rendering_classes:

                kwargs_new, profiles_new, redshifts_new = \
                    rendering_class.negative_kappa_sheets_theory()

                kwargs_mass_sheets += kwargs_new
                redshifts += redshifts_new
                profiles += profiles_new

        if z_mass_sheet_max is None:
            return kwargs_mass_sheets, profiles, redshifts

        else:

            kwargs_mass_sheets_out = []
            profiles_out = []
            redshifts_out = []

            inds_keep = np.where(np.array(redshifts) <= z_mass_sheet_max)[0]

            for i in range(0, len(kwargs_mass_sheets)):
                if i in inds_keep:
                    kwargs_mass_sheets_out.append(kwargs_mass_sheets[i])
                    profiles_out.append(profiles[i])
                    redshifts_out.append(redshifts[i])

            return kwargs_mass_sheets_out, profiles_out, redshifts_out

    def _load_halo_model(self, mass, x, y, r3d, mdef, z, is_subhalo,
                         lens_cosmo_instance, args, unique_tag):

        """
        Loads the halo model for each object based on the mass definition
        :param halo: an instance of Halo
        :return: the class
        """

        if mdef == 'NFW':

            if is_subhalo:
                model = NFWSubhhalo(mass, x, y, r3d, mdef, z, is_subhalo,
                                    lens_cosmo_instance, args, unique_tag)
            else:
                model = NFWFieldHalo(mass, x, y, r3d, mdef, z, is_subhalo,
                                    lens_cosmo_instance, args, unique_tag)


        elif mdef == 'TNFW':

            if is_subhalo:
                model = TNFWSubhhalo(mass, x, y, r3d, mdef, z, is_subhalo,
                                     lens_cosmo_instance, args, unique_tag)

            else:
                model = TNFWFieldHalo(mass, x, y, r3d, mdef, z, is_subhalo,
                                      lens_cosmo_instance, args, unique_tag)

        elif mdef == 'PT_MASS':

            model = PTMass(mass, x, y, r3d, mdef, z, is_subhalo,
                           lens_cosmo_instance, args, unique_tag)

        elif mdef == 'PJAFFE':

            model = PJaffeSubhalo(mass, x, y, r3d, mdef, z, is_subhalo,
                                  lens_cosmo_instance, args, unique_tag)

        else:
            raise ValueError('halo profile ' + str(mdef) + ' not recongnized.')

        return model

    def _tags(self, halos=None):

        if halos is None:
            halos = self.halos
        tags = []

        for halo in halos:

            tags.append(halo.unique_tag)

        return tags

    def _reset(self):

        self.x = []
        self.y = []
        self.masses = []
        self.redshifts = []
        self.r3d = []
        self.mdefs = []
        self._halo_tags = []
        self.subhalo_flags = []

        for halo in self.halos:
            self.masses.append(halo.mass)
            self.x.append(halo.x)
            self.y.append(halo.y)
            self.redshifts.append(halo.z)
            self.r3d.append(halo.r3d)
            self.mdefs.append(halo.mdef)
            self._halo_tags.append(halo.unique_tag)
            self.subhalo_flags.append(halo.is_subhalo)

        self.masses = np.array(self.masses)
        self.x = np.array(self.x)
        self.y = np.array(self.y)
        self.r3d = np.array(self.r3d)
        self.redshifts = np.array(self.redshifts)

        self.unique_redshifts = np.unique(self.redshifts)

    def __eq__(self, other_reealization):

        tags = self._tags(self.halos)
        other_tags = other_reealization._tags()
        for tag in other_tags:
            if tag not in tags:
                return False
        else:
            return True


class SingleHalo(Realization):

    """
    Useful for generating a realization with a single or a few
    user-specified halos.
    """

    def __init__(self, halo_mass, x, y, r3d, mdef, z, zlens, zsource, subhalo_flag=True,
                 cone_opening_angle=6, log_mlow=6, log_mhigh=10,
                 kwargs_halo={}, cosmo=None):

        if cosmo is None:
            cosmo = Cosmology()
        halo_mass_function = LensingMassFunction(cosmo, 10**log_mlow, 10**log_mhigh,
                                                 zlens, zsource, cone_opening_angle, use_lookup_table=True)

        kwargs_halo.update({'cone_opening_angle': cone_opening_angle})
        super(SingleHalo, self).__init__([halo_mass], [x], [y],
                                         [r3d], [mdef], [z], [subhalo_flag], halo_mass_function,
                                         halo_profile_args=kwargs_halo, mass_sheet_correction=False)

def add_core_collapsed_subhalos(f_collapsed, realization):

    """

    :param f_collapsed: fraction of subhalos that become isothermal profiles
    :param realization: an instance of Realization
    :return: A new instance of Realization where a fraction f_collapsed of the subhalos
    in the original realization have their mass definitions changed to Jaffe profiles
    with isothermal density profiles same total mass as the original NFW profile.

    Note: this functionality is new and not very well tested
    """

    halos = realization.halos

    for index, halo in enumerate(halos):
        if halo.is_subhalo:
            u = np.random.rand()
            if u < f_collapsed:
                # change mass definition
                new_halo = Halo.change_profile_definition(halo, 'PJAFFE')
                halos[index] = new_halo

    halo_mass_function = realization.halo_mass_function
    prof_params = realization._prof_params
    msheet_correction = realization._mass_sheet_correction
    rendering_classes = realization.rendering_classes

    return Realization.from_halos(halos, halo_mass_function, prof_params,
                                  msheet_correction, rendering_classes)


