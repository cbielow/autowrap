# encoding: utf-8

from __future__ import print_function

__license__ = """

Copyright (c) 2012-2014, Uwe Schmitt, all rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

Redistributions in binary form must reproduce the above copyright notice, this
list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

Neither the name of the ETH Zurich nor the names of its contributors may be
used to endorse or promote products derived from this software without specific
prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import os
import sys
import glob
import autowrap.version
import autowrap.Code
import autowrap
import optparse

"""
The autowrap process consists of two steps:

    i) parsing of files (done by DeclResolver, which in turn uses the PXDParser
        to parse files)

    ii) generating the code (CodeGenerator)

this is both done by the call autowrap.parse_and_generate_code in the
__init__.py file.

See below in main() how parse_and_generate_code is used.


For better understanding, see tests/testMain.py and the corresponding files

   tests/test_files/pxds/*       (declaring methods to wrap)
   tests/test_files/addons/*     (self written wrapper code as addition to
                                  code generated by autowrap)
   tests/test_files/converters*  (specific type convertes)
"""


def main():
    _main(sys.argv[1:])


def _main(argv):
    parser = optparse.OptionParser(version=("%d.%d.%d" % autowrap.version))
    parser.add_option("--addons", action="append", metavar="addon")
    parser.add_option("--converters", action="append", metavar="converter")
    parser.add_option("--out", action="store", nargs=1, metavar="pyx file")

    options, input_ = parser.parse_args(argv)

    assert options.out is not None, "need --out argument"
    out = options.out
    __, out_ext = os.path.splitext(out)

    if out_ext != ".pyx":
        parser.exit(1, "\nout file has wrong extension: '.pyx' required\n")

    def collect(from_, extension):
        collected = []
        if from_ is None:
            return collected
        for item in from_:
            if os.path.isdir(item):
                for basename in os.listdir(item):
                    collected.append((os.path.join(item, basename)))
            else:
                found = glob.glob(item)
                if found:
                    collected.extend(found)
                else:
                    print("WARNING!  '%s' did not match any file" % item)
        collected = sorted(set(collected))
        result = []
        for item in collected:
            __, ext = os.path.splitext(item)
            if ext != extension:
                print("WARNING: ignore %s" % item)
            else:
                result.append(item)
        return result

    pxds = collect(input_, ".pxd")
    if not pxds:
        parser.exit(1, "\nno pxd input files specified\n")
    addons = collect(options.addons, ".pyx")
    converters = options.converters or []
    print("\n")
    print("STATUS:")
    print("   %5d pxd input files to parse" % len(pxds))
    print("   %5d add on files to process" % len(addons))
    print("   %5d type converter files to consider" % len(converters))
    print("\n")

    run(pxds, addons, converters, out)


def collect_manual_code(addons):
    # collect code which is manually generated and will be added to the
    # wrapper code by autowrap:
    manual_code = dict()
    cimports = []
    for name in addons:
        clz_name, __ = os.path.splitext(os.path.basename(name))
        line_iter = open(name, "r")
        for line in line_iter:
            if line and line.strip() not in "\n\r\t ":
                cimports.append(line)
            else:
                break
        remainder = "".join(line_iter)
        manual_code.setdefault(clz_name, autowrap.Code.Code()).add(remainder)
    return cimports, manual_code


def register_converters(converters):
    # register converters
    # we import all modules described by pathes, given by 'converters'
    # and call top level 'register_converter' function in these modules
    for mod_path in converters:
        head, tail = os.path.split(os.path.abspath(mod_path))
        sys.path.insert(0, head)
        try:
            mod = __import__(tail)
        except ImportError as e:
            print("tried import from ", sys.path[0])
            print("module I tried to import: ", tail)
            raise ImportError(str(e) + ", maybe __init__.py files are missing")

        if not hasattr(mod, "register_converters"):
            print("\n")
            print("sys.path     = ", sys.path)
            print("\n")
            print("dir(mod)     = ", dir(mod))
            print("\n")
            print("mod          = ", mod)
            print("mod.__path__ = ", mod.__path__)
            print("mod.__file__ = ", mod.__file__)
            print("\n")
            raise ImportError("no register_converters in %s" % mod_path)

        mod.register_converters()
        sys.path.pop(0)


def run_cython(inc_dirs, extra_opts, out, warn_level=1):
    from Cython.Compiler.Main import compile, CompilationOptions
    import Cython.Compiler.Errors

    Cython.Compiler.Errors.LEVEL = warn_level

    # Try to get directive_defaults (API differs from 0.25 on)
    try:
        from Cython.Compiler.Options import directive_defaults
    except ImportError:
        # Cython 0.25
        import Cython.Compiler.Options

        directive_defaults = Cython.Compiler.Options.get_directive_defaults()

    # TODO merge these options, if compiler_directives is given in extra_opts? Otherwise they are overwritten
    directive_defaults["binding"] = False  # For backwards-compat to Cython 0.X
    directive_defaults["boundscheck"] = False
    directive_defaults["wraparound"] = False
    directive_defaults["language_level"] = sys.version_info.major

    options = dict(include_path=inc_dirs, compiler_directives=directive_defaults, cplus=True)
    if extra_opts is not None:
        options.update(extra_opts)
    options = CompilationOptions(**options)
    compile(out, options=options)


def create_wrapper_code(
    decls,
    instance_map,
    addons,
    converters,
    out,
    extra_inc_dirs,
    extra_opts,
    include_boost=True,
    allDecl=[],
):
    cimports, manual_code = collect_manual_code(addons)
    register_converters(converters)
    inc_dirs = autowrap.generate_code(
        decls,
        instance_map=instance_map,
        target=out,
        debug=False,
        manual_code=manual_code,
        extra_cimports=cimports,
        include_boost=include_boost,
        all_decl=allDecl,
    )

    if extra_inc_dirs is not None:
        inc_dirs += extra_inc_dirs

    run_cython(inc_dirs, extra_opts, out)
    return inc_dirs


def run(pxds, addons, converters, out, extra_inc_dirs=None, extra_opts=None):
    decls, instance_map = autowrap.parse(pxds, ".")
    return create_wrapper_code(
        decls, instance_map, addons, converters, out, extra_inc_dirs, extra_opts
    )
