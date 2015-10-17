# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
from builtins import range

from ....interfaces import fsl as fsl          # fsl
from ....interfaces import utility as util     # utility
from ....pipeline import engine as pe          # pypeline engine

from .... import LooseVersion


def create_modelfit_workflow(name='modelfit', f_contrasts=False):
    """Create an FSL individual modelfitting workflow

    Example
    -------

    >>> modelfit = create_modelfit_workflow()
    >>> modelfit.base_dir = '.'
    >>> info = dict()
    >>> modelfit.inputs.inputspec.session_info = info
    >>> modelfit.inputs.inputspec.interscan_interval = 3.
    >>> modelfit.inputs.inputspec.film_threshold = 1000
    >>> modelfit.run() #doctest: +SKIP

    Inputs::

         inputspec.session_info : info generated by modelgen.SpecifyModel
         inputspec.interscan_interval : interscan interval
         inputspec.contrasts : list of contrasts
         inputspec.film_threshold : image threshold for FILM estimation
         inputspec.model_serial_correlations
         inputspec.bases

    Outputs::

         outputspec.copes
         outputspec.varcopes
         outputspec.dof_file
         outputspec.pfiles
         outputspec.zfiles
         outputspec.parameter_estimates
    """

    version = 0
    if fsl.Info.version() and \
            LooseVersion(fsl.Info.version()) > LooseVersion('5.0.6'):
        version = 507

    modelfit = pe.Workflow(name=name)

    """
    Create the nodes
    """

    inputspec = pe.Node(util.IdentityInterface(fields=['session_info',
                                                       'interscan_interval',
                                                       'contrasts',
                                                       'film_threshold',
                                                       'functional_data',
                                                       'bases',
                                                       'model_serial_correlations']),
                        name='inputspec')
    level1design = pe.Node(interface=fsl.Level1Design(), name="level1design")
    modelgen = pe.MapNode(interface=fsl.FEATModel(), name='modelgen',
                          iterfield=['fsf_file', 'ev_files'])
    if version < 507:
        modelestimate = pe.MapNode(interface=fsl.FILMGLS(smooth_autocorr=True,
                                                         mask_size=5),
                                   name='modelestimate',
                                   iterfield=['design_file', 'in_file'])
    else:
        if f_contrasts:
            iterfield = ['design_file', 'in_file', 'tcon_file', 'fcon_file']
        else:
            iterfield = ['design_file', 'in_file', 'tcon_file']
        modelestimate = pe.MapNode(interface=fsl.FILMGLS(smooth_autocorr=True,
                                                         mask_size=5),
                                   name='modelestimate',
                                   iterfield=iterfield)

    if version < 507:
        if f_contrasts:
            iterfield = ['tcon_file', 'fcon_file', 'param_estimates',
                         'sigmasquareds', 'corrections',
                         'dof_file']
        else:
            iterfield = ['tcon_file', 'param_estimates',
                         'sigmasquareds', 'corrections',
                         'dof_file']
        conestimate = pe.MapNode(interface=fsl.ContrastMgr(), name='conestimate',
                                 iterfield=['tcon_file', 'fcon_file', 'param_estimates',
                                            'sigmasquareds', 'corrections',
                                            'dof_file'])

    if f_contrasts:
        iterfield = ['in1', 'in2']
    else:
        iterfield = ['in1']
    merge_contrasts = pe.MapNode(interface=util.Merge(2), name='merge_contrasts',
                                 iterfield=iterfield)
    ztopval = pe.MapNode(interface=fsl.ImageMaths(op_string='-ztop',
                                                  suffix='_pval'),
                         nested=True,
                         name='ztop',
                         iterfield=['in_file'])
    outputspec = pe.Node(util.IdentityInterface(fields=['copes', 'varcopes',
                                                        'dof_file', 'pfiles',
                                                        'zfiles',
                                                        'parameter_estimates']),
                         name='outputspec')


    """
    Setup the connections
    """

    modelfit.connect([
        (inputspec, level1design, [('interscan_interval', 'interscan_interval'),
                                   ('session_info', 'session_info'),
                                   ('contrasts', 'contrasts'),
                                   ('bases', 'bases'),
                                   ('model_serial_correlations',
                                    'model_serial_correlations')]),
        (inputspec, modelestimate, [('film_threshold', 'threshold'),
                                    ('functional_data', 'in_file')]),
        (level1design, modelgen, [('fsf_files', 'fsf_file'),
                                ('ev_files', 'ev_files')]),
        (modelgen, modelestimate, [('design_file', 'design_file')]),

        (merge_contrasts, ztopval,[('out', 'in_file')]),
        (ztopval, outputspec, [('out_file', 'pfiles')]),
        (merge_contrasts, outputspec,[('out', 'zfiles')]),
        (modelestimate, outputspec, [('param_estimates', 'parameter_estimates'),
                                     ('dof_file', 'dof_file')]),
        ])
    if version < 507:
        modelfit.connect([
            (modelgen, conestimate, [('con_file', 'tcon_file'),
                                     ('fcon_file', 'fcon_file')]),
            (modelestimate, conestimate, [('param_estimates', 'param_estimates'),
                                        ('sigmasquareds', 'sigmasquareds'),
                                        ('corrections', 'corrections'),
                                        ('dof_file', 'dof_file')]),
            (conestimate, merge_contrasts, [('zstats', 'in1'),
                                            ('zfstats', 'in2')]),
            (conestimate, outputspec, [('copes', 'copes'),
                                       ('varcopes', 'varcopes')]),
            ])
    else:
        modelfit.connect([
            (modelgen, modelestimate, [('con_file', 'tcon_file'),
                                       ('fcon_file', 'fcon_file')]),
            (modelestimate, merge_contrasts, [('zstats', 'in1'),
                                              ('zfstats', 'in2')]),
            (modelestimate, outputspec, [('copes', 'copes'),
                                       ('varcopes', 'varcopes')]),
            ])
    return modelfit


def create_overlay_workflow(name='overlay'):
    """Setup overlay workflow
    """

    overlay = pe.Workflow(name='overlay')
    overlaystats = pe.MapNode(interface=fsl.Overlay(), name="overlaystats",
                              iterfield=['stat_image'])
    overlaystats.inputs.show_negative_stats = True
    overlaystats.inputs.auto_thresh_bg = True

    slicestats = pe.MapNode(interface=fsl.Slicer(),
                            name="slicestats",
                            iterfield=['in_file'])
    slicestats.inputs.all_axial = True
    slicestats.inputs.image_width = 512

    overlay.connect(overlaystats, 'out_file', slicestats, 'in_file')
    return overlay


def create_fixed_effects_flow(name='fixedfx'):
    """Create a fixed-effects workflow

    This workflow is used to combine registered copes and varcopes across runs
    for an individual subject

    Example
    -------

    >>> fixedfx = create_fixed_effects_flow()
    >>> fixedfx.base_dir = '.'
    >>> fixedfx.inputs.inputspec.copes = [['cope1run1.nii.gz', 'cope1run2.nii.gz'], ['cope2run1.nii.gz', 'cope2run2.nii.gz']] # per contrast
    >>> fixedfx.inputs.inputspec.varcopes = [['varcope1run1.nii.gz', 'varcope1run2.nii.gz'], ['varcope2run1.nii.gz', 'varcope2run2.nii.gz']] # per contrast
    >>> fixedfx.inputs.inputspec.dof_files = ['dofrun1', 'dofrun2'] # per run
    >>> fixedfx.run() #doctest: +SKIP

    Inputs::

         inputspec.copes : list of list of cope files (one list per contrast)
         inputspec.varcopes : list of list of varcope files (one list per
                              contrast)
         inputspec.dof_files : degrees of freedom files for each run

    Outputs::

         outputspec.res4d : 4d residual time series
         outputspec.copes : contrast parameter estimates
         outputspec.varcopes : variance of contrast parameter estimates
         outputspec.zstats : z statistics of contrasts
         outputspec.tstats : t statistics of contrasts
    """

    fixed_fx = pe.Workflow(name=name)

    inputspec = pe.Node(util.IdentityInterface(fields=['copes',
                                                       'varcopes',
                                                       'dof_files'
                                                       ]),
                        name='inputspec')

    """
    Use :class:`nipype.interfaces.fsl.Merge` to merge the copes and
    varcopes for each condition
    """

    copemerge = pe.MapNode(interface=fsl.Merge(dimension='t'),
                           iterfield=['in_files'],
                           name="copemerge")

    varcopemerge = pe.MapNode(interface=fsl.Merge(dimension='t'),
                           iterfield=['in_files'],
                           name="varcopemerge")

    """
    Use :class:`nipype.interfaces.fsl.L2Model` to generate subject and condition
    specific level 2 model design files
    """

    level2model = pe.Node(interface=fsl.L2Model(),
                          name='l2model')

    """
    Use :class:`nipype.interfaces.fsl.FLAMEO` to estimate a second level model
    """

    flameo = pe.MapNode(interface=fsl.FLAMEO(run_mode='fe'), name="flameo",
                        iterfield=['cope_file', 'var_cope_file'])

    def get_dofvolumes(dof_files, cope_files):
        import os
        import nibabel as nb
        import numpy as np
        img = nb.load(cope_files[0])
        if len(img.get_shape()) > 3:
            out_data = np.zeros(img.get_shape())
        else:
            out_data = np.zeros(list(img.get_shape()) + [1])
        for i in range(out_data.shape[-1]):
            dof = np.loadtxt(dof_files[i])
            out_data[:, :, :, i] = dof
        filename = os.path.join(os.getcwd(), 'dof_file.nii.gz')
        newimg = nb.Nifti1Image(out_data, None, img.get_header())
        newimg.to_filename(filename)
        return filename

    gendof = pe.Node(util.Function(input_names=['dof_files', 'cope_files'],
                                   output_names=['dof_volume'],
                                   function=get_dofvolumes),
                     name='gendofvolume')

    outputspec = pe.Node(util.IdentityInterface(fields=['res4d',
                                                        'copes', 'varcopes',
                                                        'zstats', 'tstats']),
                         name='outputspec')

    fixed_fx.connect([(inputspec, copemerge, [('copes', 'in_files')]),
                      (inputspec, varcopemerge, [('varcopes', 'in_files')]),
                      (inputspec, gendof, [('dof_files', 'dof_files')]),
                      (copemerge, gendof, [('merged_file', 'cope_files')]),
                      (copemerge, flameo, [('merged_file', 'cope_file')]),
                      (varcopemerge, flameo, [('merged_file',
                                               'var_cope_file')]),
                      (level2model, flameo, [('design_mat', 'design_file'),
                                            ('design_con', 't_con_file'),
                                            ('design_grp', 'cov_split_file')]),
                      (gendof, flameo, [('dof_volume', 'dof_var_cope_file')]),
                      (flameo, outputspec, [('res4d', 'res4d'),
                                            ('copes', 'copes'),
                                            ('var_copes', 'varcopes'),
                                            ('zstats', 'zstats'),
                                            ('tstats', 'tstats')
                                            ])
                      ])
    return fixed_fx
