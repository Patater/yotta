# standard library modules, , ,
import string
import os
import logging

# fsutils, , misc filesystem utils, internal
import fsutils

CMakeLists_Template = string.Template(
'''#
#
# NOTE: This file is generated by yotta: changes will be overwritten!
#
#
cmake_minimum_required(VERSION 2.8)

# toolchain file for $target_name
set(CMAKE_TOOLCHAIN_FILE $toolchain_file)

project($component_name)

# include own root directory
$include_own_dir

# include root directories of all components we depend on
$include_root_dirs

# Some components (I'm looking at you, libc), need to export system header
# files with no prefix
include_directories(SYSTEM $${YOTTA_SYSTEM_INCLUDE_DIRS})

# recurse into dependencies that aren't built elsewhere
$add_depend_subdirs

# recurse into subdirectories for this component, using the two-argument
# add_subdirectory because the directories referred to here exist in the source
# tree, not the working directory
$add_own_subdirs

'''
)

Ignore_Subdirs = set(('build',))

class CMakeGen(object):
    def __init__(self, directory, target):
        super(CMakeGen, self).__init__()
        self.buildroot = directory
        logging.info("generate for target: %s" % target)
        self.target = target

    def generateRecursive(self, component, builddir=None, available_components=None, search_dirs=None):
        ''' generate top-level CMakeLists for this component and its
            dependencies: the CMakeLists are all generated in self.buildroot,
            which MUST be out-of-source

            !!! NOTE: experimenting with a slightly different way of doing
            things here, this function is a generator that yields any errors
            produced, so the correct use is:

            for error in gen.generateRecursive(...):
                print error
        '''
        if builddir is None:
            builddir = self.buildroot
        if available_components is None:
            available_components = dict()
        if search_dirs is None:
            search_dirs = []
        if not self.target:
            yield 'Target "%s" is not a valid build target' % self.target

        logging.debug('generate build files: %s' % component)
        dependencies = component.getDependencies(available_components, search_dirs, target=self.target)
        for name, dep in dependencies.items():
            if not dep:
                yield 'Required dependency "%s" of "%s" is not installed.' % (name, component)
        new_dependencies = {name:c for name,c in dependencies.items() if c and not name in available_components}
        self.generate(builddir, component, new_dependencies, dependencies)

        available_components.update(new_dependencies)
        search_dirs.append(component.modulesPath())
        for name, c in new_dependencies.items():
            for error in self.generateRecursive(c, os.path.join(builddir, name), available_components, search_dirs):
                yield error


    def generate(self, builddir, component, active_dependencies, all_dependencies):
        ''' active_dependencies is the dictionary of components that need to be
            built for this component, but will not already have been built for
            another component.
        '''

        include_own_dir = string.Template(
            'include_directories("$path")\n'
        ).substitute(path=component.path)

        include_root_dirs = ''
        for name, c in all_dependencies.items():
            include_root_dirs += string.Template(
                'include_directories("$path")\n'
            ).substitute(path=c.path)

        add_depend_subdirs = ''
        for name, c in active_dependencies.items():
            add_depend_subdirs += string.Template(
                'add_subdirectory("$working_dir/$component_name")\n'
            ).substitute(
                working_dir=builddir,
                component_name=name
            )

        add_own_subdirs = ''
        for f in os.listdir(component.path):
            if f in Ignore_Subdirs:
                continue
            if os.path.isfile(os.path.join(component.path, f, 'CMakeLists.txt')):
                add_own_subdirs += string.Template(
                    '''add_subdirectory(
    "$component_source_dir/$subdir_name"
    "$working_dir/$subdir_name"
)
'''
                ).substitute(
                    component_source_dir=component.path,
                    working_dir=builddir,
                    subdir_name=f
                )

        file_contents = CMakeLists_Template.substitute(
            target_name=self.target.getName(),
            toolchain_file=self.target.getToolchainFile(),
            component_name=component.getName(),
            include_own_dir=include_own_dir,
            include_root_dirs=include_root_dirs,
            add_depend_subdirs=add_depend_subdirs,
            add_own_subdirs=add_own_subdirs
        )
        fsutils.mkDirP(builddir)
        with open(os.path.join(builddir, 'CMakeLists.txt'), 'w') as f:
            f.write(file_contents)


        
