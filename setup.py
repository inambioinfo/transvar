#!/usr/bin/env python

# The MIT License
# 
# Copyright (c) 2011 Seoul National University
# Copyright (c) 2014, 2015 The University of Texas MD Anderson Cancer Center
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Contact: Wanding Zhou <zhouwanding@gmail.com>

import os
import sys
import subprocess
from setuptools import setup, Extension
from setuptools.command.install import install
from distutils.command.build import build

BASEPATH=os.path.dirname(os.path.abspath(__file__))

class TransVarBuild(build):

    def run(self):

        # run original build code
        build.run(self)

        # build samtools
        build_path = os.path.abspath(self.build_temp)
        
        cmd = ['make', '-C', 'external/samtools']

        def compile():
            subprocess.check_call(cmd)

        self.execute(compile, [], 'Compile samtools')

class TransVarInstall(install):

    def run(self):

        install.run(self)
        import shutil
        shutil.copy2('external/samtools/samtools',
                     os.path.join(self.install_lib, 'transvar'))
        shutil.copy2('external/samtools/htslib-1.2.1/tabix',
                     os.path.join(self.install_lib, 'transvar'))
            
def main():
    if float(sys.version[:3])<2.6 or float(sys.version[:3])>=2.8:
        sys.stderr.write("CRITICAL: Python version must be 2.6 or 2.7!\n")
        sys.exit(1)
        
    ext_modules = [
        Extension("transvar.tabix",
                  sources = [
                      "external/pytabix/bgzf.c", "external/pytabix/bgzip.c",
                      "external/pytabix/index.c", "external/pytabix/knetfile.c",
                      "external/pytabix/kstring.c", "external/pytabix/tabixmodule.c"
                  ],
                  include_dirs=["external/pytabix"],
                  libraries=["z"],
                  define_macros=[("_FILE_OFFSET_BITS", 64), ("_USE_KNETFILE", 1)],
                  extra_compile_args=["-w"],
              ),
        Extension("transvar._sswlib",
                  sources = ['external/ssw/ssw.c', 'external/ssw/encode.c'],
                  include_dirs = ['external/ssw'],
                  extra_compile_args = ['-W', '-Wall', '-O2', '-finline-functions', '-fPIC', '-shared', '-Wl,-soname,sswlib'],
              ),
    ]


    setup(
        name = "TransVar",
        version = "2.0",
        description = "Transcript-based Variant annotator",
        url = "https://bitbucket.org/wanding/transvar",
        author = "Wanding Zhou",
        author_email = "zhouwanding@gmail.com",
        license = "MIT",
        keywords = ["bioinformatics", "genomics"],
        scripts = ['bin/transvar'],
        packages = ['transvar', 'transvar.ssw'],
        ext_modules = ext_modules,
        classifiers = [
            "Programming Language :: Python",
            "Development Status :: 4 - Beta",
            "Intended Audience :: Developers",
            "Intended Audience :: Science/Research",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
            'Operating System :: POSIX',
            "Programming Language :: C",
            "Topic :: Scientific/Engineering :: Bioinformatics"
        ],
        cmdclass = {
            'build': TransVarBuild,
            'install': TransVarInstall,
        }
        # long_description = """ """
        # install_requires=['numpy>=1.6']
    )

if __name__ == '__main__':
    main()
