#!/usr/bin/python3 -i
#
# Copyright 2013-2021 The Khronos Group Inc.
# SPDX-License-Identifier: Apache-2.0

from generator import GeneratorOptions, OutputGenerator, regSortFeatures, noneStr, write

class DocGeneratorOptions(GeneratorOptions):
    """DocGeneratorOptions - subclass of GeneratorOptions for
    generating declaration snippets for the spec.

    Shares many members with CGeneratorOptions, since
    both are writing C-style declarations."""

    def __init__(self,
                 prefixText="",
                 apicall='',
                 apientry='',
                 apientryp='',
                 indentFuncProto=True,
                 indentFuncPointer=False,
                 alignFuncParam=0,
                 secondaryInclude=False,
                 expandEnumerants=True,
                 extEnumerantAdditions=False,
                 extEnumerantFormatString=" (Added by the {} extension)",
                 **kwargs):
        """Constructor.

        Since this generator outputs multiple files at once,
        the filename is just a "stamp" to indicate last generation time.

        Shares many parameters/members with CGeneratorOptions, since
        both are writing C-style declarations:

        - prefixText - list of strings to prefix generated header with
        (usually a copyright statement + calling convention macros).
        - apicall - string to use for the function declaration prefix,
        such as APICALL on Windows.
        - apientry - string to use for the calling convention macro,
        in typedefs, such as APIENTRY.
        - apientryp - string to use for the calling convention macro
        in function pointer typedefs, such as APIENTRYP.
        - indentFuncProto - True if prototype declarations should put each
        parameter on a separate line
        - indentFuncPointer - True if typedefed function pointers should put each
        parameter on a separate line
        - alignFuncParam - if nonzero and parameters are being put on a
        separate line, align parameter names at the specified column

        Additional parameters/members:

        - expandEnumerants - if True, add BEGIN/END_RANGE macros in enumerated
        type declarations
        - secondaryInclude - if True, add secondary (no xref anchor) versions
        of generated files
        """
        GeneratorOptions.__init__(self, **kwargs)
        self.prefixText = prefixText
        """list of strings to prefix generated header with (usually a copyright statement + calling convention macros)."""

        self.apicall = apicall
        """string to use for the function declaration prefix, such as APICALL on Windows."""

        self.apientry = apientry
        """string to use for the calling convention macro, in typedefs, such as APIENTRY."""

        self.apientryp = apientryp
        """string to use for the calling convention macro in function pointer typedefs, such as APIENTRYP."""

        self.indentFuncProto = indentFuncProto
        """True if prototype declarations should put each parameter on a separate line"""

        self.indentFuncPointer = indentFuncPointer
        """True if typedefed function pointers should put each parameter on a separate line"""

        self.alignFuncParam = alignFuncParam
        """if nonzero and parameters are being put on a separate line, align parameter names at the specified column"""

        self.secondaryInclude = secondaryInclude
        """if True, add secondary (no xref anchor) versions of generated files"""

        self.expandEnumerants = expandEnumerants
        """if True, add BEGIN/END_RANGE macros in enumerated type declarations"""

class DocOutputGenerator(OutputGenerator):
    """DocOutputGenerator - subclass of OutputGenerator.

    Generates AsciiDoc includes with C-language API interfaces, for reference
    pages and the corresponding specification. Similar to COutputGenerator,
    but each interface is written into a different file as determined by the
    options, only actual C types are emitted, and none of the boilerplate
    preprocessor code is emitted."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Keep track of all extension numbers
        self.extension_numbers = set()

    def beginFile(self, genOpts):
        OutputGenerator.beginFile(self, genOpts)

    def endFile(self):
        OutputGenerator.endFile(self)

    def beginFeature(self, interface, emit):
        # Start processing in superclass
        OutputGenerator.beginFeature(self, interface, emit)
        # Verify that each <extension> has a unique number during doc
        # generation
        if interface.tag == 'extension':
            extension_number = interface.get('number')
            if extension_number is not None and extension_number != "0":
                if extension_number in self.extension_numbers:
                    self.logMsg('error', 'Duplicate extension number ', extension_number, ' detected in feature ', interface.get('name'), '\n')
                    exit(1)
                else:
                    self.extension_numbers.add(extension_number)

    def endFeature(self):
        # Finish processing in superclass
        OutputGenerator.endFeature(self)

    def writeInclude(self, directory, basename, contents):
        """Generate an include file.

        - directory - subdirectory to put file in
        - basename - base name of the file
        - contents - contents of the file (Asciidoc boilerplate aside)"""
        # Create subdirectory, if needed
        directory = self.genOpts.directory + '/' + directory
        self.makeDir(directory)

        # Create file
        filename = directory + '/' + basename + '.txt'
        self.logMsg('diag', '# Generating include file:', filename)
        fp = open(filename, 'w', encoding='utf-8')

        # Asciidoc anchor
        write(self.genOpts.conventions.warning_comment, file=fp)
        write('[[{0},{0}]]'.format(basename), file=fp)
        write('[source,c++]', file=fp)
        write('----', file=fp)
        write(contents, file=fp)
        write('----', file=fp)
        fp.close()

        if self.genOpts.secondaryInclude:
            # Create secondary no cross-reference include file
            filename = directory + '/' + basename + '.no-xref.txt'
            self.logMsg('diag', '# Generating include file:', filename)
            fp = open(filename, 'w', encoding='utf-8')

            # Asciidoc anchor
            write(self.genOpts.conventions.warning_comment, file=fp)
            write('// Include this no-xref version without cross reference id for multiple includes of same file', file=fp)
            write('[source,c++]', file=fp)
            write('----', file=fp)
            write(contents, file=fp)
            write('----', file=fp)
            fp.close()

    def genType(self, typeinfo, name, alias):
        "Generate type."
        OutputGenerator.genType(self, typeinfo, name, alias)
        typeElem = typeinfo.elem
        # If the type is a struct type, traverse the embedded <member> tags
        # generating a structure. Otherwise, emit the tag text.
        category = typeElem.get('category')

        body = ''
        if category in ('struct', 'union'):
            # If the type is a struct type, generate it using the
            # special-purpose generator.
            self.genStruct(typeinfo, name, alias)
        else:
            if alias:
                # If the type is an alias, just emit a typedef declaration
                body = 'typedef ' + alias + ' ' + name + ';\n'
                self.writeInclude(OutputGenerator.categoryToPath[category],
                                  name, body)
            else:
                # Replace <apientry /> tags with an APIENTRY-style string
                # (from self.genOpts). Copy other text through unchanged.
                # If the resulting text is an empty string, don't emit it.
                body = noneStr(typeElem.text)
                for elem in typeElem:
                    if elem.tag == 'apientry':
                        body += self.genOpts.apientry + noneStr(elem.tail)
                    else:
                        body += noneStr(elem.text) + noneStr(elem.tail)

                if body:
                    if category in OutputGenerator.categoryToPath:
                        self.writeInclude(OutputGenerator.categoryToPath[category],
                                          name, body + '\n')
                    else:
                        self.logMsg('diag', '# NOT writing include file for type:',
                                    name, '- bad category: ', category)
                else:
                    self.logMsg('diag', '# NOT writing empty include file for type', name)

    def genStruct(self, typeinfo, typeName, alias):
        """Generate struct."""
        OutputGenerator.genStruct(self, typeinfo, typeName, alias)

        typeElem = typeinfo.elem

        if alias:
            body = 'typedef ' + alias + ' ' + typeName + ';\n'
        else:
            body = 'typedef ' + typeElem.get('category') + ' ' + typeName + ' {\n'

            targetLen = self.getMaxCParamTypeLength(typeinfo)
            for member in typeElem.findall('.//member'):
                body += self.makeCParamDecl(member, targetLen + 4)
                body += ';\n'
            body += '} ' + typeName + ';'

        self.writeInclude('structs', typeName, body)

    def genGroup(self, groupinfo, groupName, alias):
        """Generate group (e.g. C "enum" type)."""
        OutputGenerator.genGroup(self, groupinfo, groupName, alias)

        if alias:
            # If the group name is aliased, just emit a typedef declaration
            # for the alias.
            body = 'typedef ' + alias + ' ' + groupName + ';\n'
        else:
            expand = self.genOpts.expandEnumerants
            (_, body) = self.buildEnumCDecl(expand, groupinfo, groupName)

        self.writeInclude('enums', groupName, body)

    def genEnum(self, enuminfo, name, alias):
        """Generate enumerant."""
        OutputGenerator.genEnum(self, enuminfo, name, alias)
        self.logMsg('diag', '# NOT writing compile-time constant', name)

        # (_, strVal) = self.enumToValue(enuminfo.elem, False)
        # body = '#define ' + name.ljust(33) + ' ' + strVal
        # self.writeInclude('consts', name, body)

    def genCmd(self, cmdinfo, name, alias):
        "Generate command."
        OutputGenerator.genCmd(self, cmdinfo, name, alias)

        return_type = cmdinfo.elem.find('proto/type')
        if self.genOpts.conventions.requires_error_validation(return_type):
            # This command returns an API result code, so check that it
            # returns at least the required errors.
            # TODO move this to consistency_tools
            required_errors = set(self.genOpts.conventions.required_errors)
            errorcodes = cmdinfo.elem.get('errorcodes').split(',')
            if not required_errors.issubset(set(errorcodes)):
                self.logMsg('error', 'Missing required error code for command: ', name, '\n')
                exit(1)

        decls = self.makeCDecls(cmdinfo.elem)
        self.writeInclude('protos', name, decls[0])
