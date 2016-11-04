import click
from mod_pbxproj import XcodeProject
import os
from glob import glob

stderr = click.get_text_stream('stderr')

def lazyprop(fn):
    attr_name = '_lazy_' + fn.__name__
    @property
    def _lazyprop(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)
    return _lazyprop

class XCOrphans(object):

    def __init__(self, path, extensions=["m", "mm", "swift"]):
        super(XCOrphans, self).__init__()
        self.pbxproj_path = path
        self.source_extensions = extensions

    def analyse(self):
        self.loadProjectFile()
        for pbx01File in self.not_build_source_files:
            print("PBX01 source file referenced in project but not in any targets: %s" % pbx01File['path'])
        for pbx02File in self.build_not_project_source_files:
            print "PBX02 source file referenced in target but not in project: ref# %s" % (pbx02File)

    # TODO: build full relative path to file for comparison with source files from filesystem
    # TODO: need to check headers too for filesystem
    # TODO: what about folder references?


    def loadProjectFile(self):
        project_document = XcodeProject.Load(self.pbxproj_path)
        if project_document is None:
            stderr.write("Could not open project at %s\r\n" % self.pbxproj_path)
            exit(1)
        self.project_document = project_document

    @lazyprop
    def not_build_source_files(self):
        not_build_source_files = []
        for file in self.not_build_files:
            path = file['path']
            extension = os.path.splitext(path)[1][1:]
            if extension in self.source_extensions:
                not_build_source_files.append(file)
        return not_build_source_files

    @lazyprop
    def build_not_project_source_files(self):
        file_refs = []
        for build_file_ref in self.build_file_refs:
            matches = [f for f in self.project_document.objects.items() if f[0] == build_file_ref]
            if len(matches) == 0:
                file_refs.append(build_file_ref)
        return file_refs

    @lazyprop
    def not_build_files(self):
        not_build_files = []
        for ref in self.not_build_file_refs:
            file = [f for f in self.project_document.objects.items() if f[0] == ref][0][1]
            not_build_files.append(file)
        return not_build_files

    @lazyprop
    def not_build_file_refs(self):
        unique_build_file_refs = set(self.build_file_ref_refs)
        unique_file_refs = set(self.all_file_refs)
        return unique_file_refs.difference(unique_build_file_refs)

    @lazyprop
    def all_filesystem_files(self):
        # result = [y for x in os.walk(PATH) for y in glob(os.path.join(x[0], '*.txt'))]
        # root = "/Users/alex/code/fanduel/core-ios/"
        root = "/Volumes/Fast/code/fanduel/core-ios/"
        result = [os.path.relpath(os.path.join(dp, f), root) for dp, dn, filenames in os.walk(root) for f in filenames if os.path.splitext(f)[1][1:] in self.source_extensions]
        return result

    def path(self, fileRef):
        matches = [f for f in self.project_document.objects.items() if f[0] == fileRef]
        if len(matches) == 0:
            return None
        path = []
        match = matches[0]
        sourceTree = match[1]['sourceTree']
        ref = match[0]
        path.append(match[1]['path'])
        while sourceTree == "<group>":
            matches = [f for f in self.project_document.objects.items() if f[1].get('isa') == 'PBXGroup' and ref in f[1].get('children')]
            if len(matches) == 0:
                return None
            match = matches[0]
            sourceTree = match[1]['sourceTree']
            if sourceTree == 'SOURCE_ROOT':
                path.append(match[1]['path'])
                break
            ref = match[0]
            pathElement = match[1].get('path')
            if pathElement != None:
                path.append(pathElement)
            else:
                break

        path.reverse()
        return os.path.join(*path)

    @lazyprop
    def all_file_refs(self):
        return [f[0] for f in self.project_document.objects.items() if f[1].get('isa') == 'PBXFileReference']

    @lazyprop
    def build_file_ref_refs(self):
        build_file_ref_refs = []
        for build_file_ref in self.build_file_refs:
            matches = [f for f in self.project_document.objects.items() if f[0] == build_file_ref]
            if len(matches) > 0:
                build_file = matches[0][1]
                file_ref_ref = build_file.get('fileRef')
                build_file_ref_refs.append(file_ref_ref)
        return build_file_ref_refs

    @lazyprop
    def build_file_refs(self):
        build_file_refs = []
        for source_build_phase in self.source_build_phases:
            file_refs = source_build_phase.get('files')
            build_file_refs.extend(file_refs)
        return build_file_refs

    @lazyprop
    def source_build_phases(self):
        source_build_phases = []
        for build_phase_ref in self.build_phase_refs:
            build_phase = [f for f in self.project_document.objects.items() if f[0] == build_phase_ref][0][1]
            if build_phase.get('isa') == 'PBXSourcesBuildPhase':
                source_build_phases.append(build_phase)
        return source_build_phases

    @lazyprop
    def build_phase_refs(self):
        build_phase_refs = []
        for target_ref in self.target_refs:
            target = [f for f in self.project_document.objects.items() if f[0]==target_ref][0][1]
            build_phase_refs.extend(target.get('buildPhases'))
        return build_phase_refs

    @lazyprop
    def target_refs(self):
        project = [f for f in self.project_document.objects.items() if f[1].get('isa') == 'PBXProject'][0][1]
        return project.get('targets')


@click.command()
@click.option('--pbxproj', help='Location of Xcode project file.', required=False)
@click.option('--projroot', help='Location of project root folder.', required=False)
def xcorphans(pbxproj, projroot):
    """Orphaned Files analyses the Xcode project file to find files which are located in the project folder but
    not used by the project, as well as source files which are referenced in the project but not compiled by any
    of the build targets."""

    # if pbxproj

    orphAnalyser = XCOrphans(pbxproj)
    # orphAnalyser.analyse()
    orphAnalyser.loadProjectFile()
    # print projroot
    # print orphAnalyser.all_filesystem_files
    fileRefs = orphAnalyser.all_file_refs
    for fileRef in fileRefs:
        print orphAnalyser.path(fileRef=fileRef)

    # project_document = XcodeProject.Load(pbxproj)
    # if project_document is None:
    #     stderr.write("Could not open project at %s\r\n" % pbxproj)
    #     exit(1)

if __name__ == '__main__':
    xcorphans()