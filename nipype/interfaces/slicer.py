'''
Created on 22 Jun 2010

@author: filo
'''
from nipype.interfaces.base import CommandLine, CommandLineInputSpec,\
    DynamicTraitedSpec
import xml.dom.minidom
import enthought.traits.api as traits
import os
from nipype.interfaces.traits import File
from nipype.utils.misc import isdefined
from enthought.traits.trait_base import Undefined


path = "/home/filo/tmp/slicer/Slicer3-build/lib/Slicer3/Plugins"

class SlicerCommandLineInputSpec(DynamicTraitedSpec, CommandLineInputSpec):
    module = traits.Str()

class SlicerCommandLine(CommandLine):
    input_spec = SlicerCommandLineInputSpec
    output_spec = DynamicTraitedSpec
        
    
    def _grab_xml(self):
        cmd = CommandLine(command = self.cmd, args="--xml")
        ret = cmd.run()
        return xml.dom.minidom.parseString(ret.runtime.stdout)
    
    def __init__(self, module, **inputs):
        super(SlicerCommandLine, self).__init__(command= os.path.join(path, module), name= module, **inputs)
        dom = self._grab_xml()
        self._outputs_filenames = {}
        
        self._outputs_nodes = []
        
        undefined_traits = {}
        
        for paramGroup in dom.getElementsByTagName("parameters"):
            for param in paramGroup.childNodes:
                if param.nodeName in ['label', 'description', '#text', '#comment']:
                    continue
                traitsParams = {}
                
                name = param.getElementsByTagName('name')[0].firstChild.nodeValue
                
                longFlagNode = param.getElementsByTagName('longflag')
                if longFlagNode:
                    traitsParams["argstr"] = "--" + longFlagNode[0].firstChild.nodeValue + " " 
                else:
                    traitsParams["argstr"] = "--" + name + " "
                    
                    
                argsDict = {'file': '%s', 'integer': "%d", 'double': "%f", 'float': "%f", 'image': "%s", 'transform': "%s", 'boolean': '', 'string-enumeration': '%s', 'string': "%s"}
                    
                if param.nodeName.endswith('-vector'):
                    traitsParams["argstr"] += argsDict[param.nodeName[:-7]]
                else:
                    traitsParams["argstr"] += argsDict[param.nodeName]
                
                index = param.getElementsByTagName('index')
                if index:
                    traitsParams["position"] = index[0].firstChild.nodeValue
                    
                desc = param.getElementsByTagName('description')
                if index:
                    traitsParams["desc"] = desc[0].firstChild.nodeValue
                
                name = param.getElementsByTagName('name')[0].firstChild.nodeValue
                
                typesDict = {'integer': traits.Int, 'double': traits.Float, 'float': traits.Float, 'image': File, 'transform': File, 'boolean': traits.Bool, 'string': traits.Str, 'file':File}
                            
                if param.nodeName == 'string-enumeration':
                    type = traits.Enum
                    values = [el.firstChild.nodeValue for el in param.getElementsByTagName('element')]
                elif param.nodeName.endswith('-vector'):
                    type = traits.List
                    values = [typesDict[param.nodeName[:-7]]]
                    traitsParams["sep"] = ','
                else:
                    values = []
                    type = typesDict[param.nodeName]
                
                if param.nodeName in ['file', 'directory', 'image', 'transform'] and param.getElementsByTagName('channel')[0].firstChild.nodeValue == 'output':
                    self.inputs.add_trait(name, traits.Either(traits.Bool, File, **traitsParams))
                    undefined_traits[name] = Undefined
                    
                    traitsParams["exists"] = True
                    self._outputs_filenames[name] = self._gen_filename_from_param(param)
                    self._outputs().add_trait(name, File(*values, **traitsParams))
                    self._outputs_nodes.append(param)
                else:
                    if param.nodeName in ['file', 'directory', 'image', 'transform']:
                        traitsParams["exists"] = True
                    self.inputs.add_trait(name, type(*values, **traitsParams))
                    undefined_traits[name] = Undefined
                
        self.inputs.trait_set(trait_change_notify=False, **undefined_traits)
        
    def _gen_filename(self, name):
        if name in self._outputs_filenames:
            return self._outputs_filenames[name]
        return None
    
    def _gen_filename_from_param(self,param):
        base = param.getElementsByTagName('name')[0].firstChild.nodeValue
        fileExtensions = param.getAttribute("fileExtensions")
        if fileExtensions:
            ext = fileExtensions
        else:
            ext = {'image': '.nii', 'transform': '.txt', 'file': ''}[param.nodeName]
        return os.path.abspath(base + ext)
    
    def _list_outputs(self):
        outputs = self.output_spec().get()
        for output_node in self._outputs_nodes:
            name = output_node.getElementsByTagName('name')[0].firstChild.nodeValue
            outputs[name] = getattr(self.inputs, name)
            if isdefined(outputs[name]) and isinstance(outputs[name], bool):
                if outputs[name]:
                    outputs[name] = self._gen_filename(name)
                else:
                    outputs[name] = Undefined
        return outputs
    
    def _format_arg(self, name, spec, value):
        if name in [output_node.getElementsByTagName('name')[0].firstChild.nodeValue for output_node in self._outputs_nodes]:
            if isinstance(value, bool):
                fname = self._gen_filename(name)
            else:
                fname = value
            return spec.argstr % fname
        return super(SlicerCommandLine, self)._format_arg(name, spec, value)
        
if __name__ == "__main__":
    test = SlicerCommandLine(module="BRAINSFit")
    test.inputs.fixedVolume = "/home/filo/workspace/fmri_tumour/data/pilot1/10_co_COR_3D_IR_PREP.nii"
    test.inputs.movingVolume = "/home/filo/workspace/fmri_tumour/data/pilot1/2_line_bisection.nii"
    test.inputs.outputTransform = True
    test.inputs.transformType = ["Affine"]
    print test.cmdline
    #print test.inputs
    print test._outputs()
    #ret = test.run()
    
#    test = SlicerCommandLine(name="BRAINSResample")
#    test.inputs.referenceVolume = "/home/filo/workspace/fmri_tumour/data/pilot1/10_co_COR_3D_IR_PREP.nii"
#    test.inputs.inputVolume = "/home/filo/workspace/fmri_tumour/data/pilot1/2_line_bisection.nii"
#    test.inputs.outputVolume = True
#    test.inputs.warpTransform = "/home/filo/workspace/nipype/nipype/interfaces/outputTransform.mat"
#    print test.cmdline
#    ret = test.run()
#    print ret.runtime.stderr
#    print ret.runtime.returncode