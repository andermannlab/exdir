from enum import Enum
import os
import yaml
import warnings
from . import filename_validation

from . import exdir_object
from .attribute import Attribute

# metadata
EXDIR_METANAME = "exdir"
TYPE_METANAME = "type"
VERSION_METANAME = "version"

# filenames
META_FILENAME = "exdir.yaml"
ATTRIBUTES_FILENAME = "attributes.yaml"
RAW_FOLDER_NAME = "__raw__"

# typenames
DATASET_TYPENAME = "dataset"
GROUP_TYPENAME = "group"
FILE_TYPENAME = "file"


def _assert_valid_name(name, container):
    """Check if name (dataset or group) is valid."""
    container.validate_name(container.directory, name)


def _create_object_directory(directory, typename):
    """
    Create object directory and meta file if directory
    don't already exist.
    """
    if os.path.exists(directory):
        raise IOError("The directory '" + directory + "' already exists")
    valid_types = [DATASET_TYPENAME, FILE_TYPENAME, GROUP_TYPENAME]
    if typename not in valid_types:
        raise ValueError("{typename} is not a valid typename".format(typename=typename))
    os.mkdir(directory)
    meta_filename = _metafile_from_directory(directory)
    with open(meta_filename, "w") as meta_file:
        metadata = {
            EXDIR_METANAME: {
                TYPE_METANAME: typename,
                VERSION_METANAME: 1}
        }
        yaml.safe_dump(metadata,
                       meta_file,
                       default_flow_style=False,
                       allow_unicode=True)


def _metafile_from_directory(directory):
    return os.path.join(directory, META_FILENAME)


def is_exdir_object(directory):
    """
    WARNING: Does not test if inside exdir directory,
    only if the object can be an exdir object (i.e. a directory).
    """
    return os.path.isdir(directory)


def is_nonraw_object_directory(directory):
    meta_filename = os.path.join(directory, META_FILENAME)
    if not os.path.exists(meta_filename):
        return False
    with open(meta_filename, "r") as meta_file:
        meta_data = yaml.safe_load(meta_file)

        if not isinstance(meta_data, dict):
            return False

        if EXDIR_METANAME not in meta_data:
            return False
        if TYPE_METANAME not in meta_data[EXDIR_METANAME]:
            return False
        valid_types = [DATASET_TYPENAME, FILE_TYPENAME, GROUP_TYPENAME]
        if meta_data[EXDIR_METANAME][TYPE_METANAME] not in valid_types:
            return False
    return True


def is_raw_object_directory(directory):
    return is_exdir_object(directory) and not is_nonraw_object_directory(directory)


def root_directory(path):
    """
    Iterates upwards until a exdir.File object is found.

    returns: path to exdir.File or None if not found.
    """
    path = os.path.abspath(path)
    found = False
    while not found:
        if os.path.dirname(path) == path:  # parent is self
            return None
        valid = is_nonraw_object_directory(path)
        if not valid:
            path = os.path.dirname(os.path.abspath(path))
            continue

        meta_filename = _metafile_from_directory(path)
        with open(meta_filename, "r") as meta_file:
            meta_data = yaml.load(meta_file)
        if EXDIR_METANAME not in meta_data:
            path = os.path.dirname(os.path.abspath(path))
            continue
        exdir_meta = meta_data[EXDIR_METANAME]
        if TYPE_METANAME not in exdir_meta:
            path = os.path.dirname(os.path.abspath(path))
            continue
        if FILE_TYPENAME != exdir_meta[TYPE_METANAME]:
            path = os.path.dirname(os.path.abspath(path))
            continue
        found = True
    return path


def is_inside_exdir(path):
    path = os.path.abspath(path)
    return root_directory(path) is not None


def assert_inside_exdir(path):
    path = os.path.abspath(path)
    if not is_inside_exdir(path):
        raise FileNotFoundError("Path " + path + " is not inside an Exdir repository.")


def open_object(path):
    from . import exdir_file
    path = os.path.abspath(path)
    assert_inside_exdir(path)
    root_dir = root_directory(path)
    object_name = os.path.relpath(path, root_dir)
    object_name = object_name.replace(os.sep, "/")
    exdir_file = exdir_file.File(root_dir)
    if object_name == ".":
        return exdir_file
    return exdir_file[object_name]

# NOTE This is in a separate file only because of circular imports between Object and Raw otherwise
# TODO move this back to Object once circular imports are figured out


class Object():
    """
    Parent class for exdir Group and exdir dataset objects
    """
    class OpenMode(Enum):
        READ_WRITE = 1
        READ_ONLY = 2

    def __init__(self, root_directory, parent_path, object_name, io_mode=None,
                 validate_name=None):
        self.root_directory = root_directory
        self.object_name = object_name
        self.parent_path = parent_path
        self.relative_path = os.path.join(self.parent_path, self.object_name)
        self.name = "/" + self.relative_path
        self.io_mode = io_mode

        validate_name = validate_name or filename_validation.thorough

        if isinstance(validate_name, str):
            if validate_name == 'simple':
                validate_name = filename_validation.thorough
            elif validate_name == 'strict':
                validate_name = filename_validation.strict
            elif validate_name == 'none':
                validate_name = filename_validation.none
            else:
                raise ValueError('IO name rule "' + validate_name + '" not recognized,' +
                                 'name rule must be one of "strict", "simple", ' +
                                 '"thorough", "none"')

            warnings.warn(
                "WARNING: validate_name should be set to one of the functions in " +
                "the filename_validation module. " +
                "Defining naming rule by string is no longer supported."
            )

        self.validate_name = validate_name

    @property
    def directory(self):
        return os.path.join(self.root_directory, self.relative_path)
        
    @property
    def attrs(self):
        return Attribute(self, mode=Attribute.Mode.ATTRIBUTES,
                         io_mode=self.io_mode)

    @attrs.setter
    def attrs(self, value):
        self.attrs._set_data(value)

    @property
    def meta(self):
        return Attribute(self, mode=Attribute.Mode.METADATA,
                         io_mode=self.io_mode)

    @property
    def attributes_filename(self):
        return os.path.join(self.directory, ATTRIBUTES_FILENAME)

    @property
    def meta_filename(self):
        return _metafile_from_directory(self.directory)

    def create_raw(self, name):
        from . import raw
        _assert_valid_name(name, self)
        directory_name = os.path.join(self.directory, name)
        if os.path.exists(directory_name):
            raise FileExistsError("Raw directory " + directory_name + " already exists.")
        os.mkdir(directory_name)
        return raw.Raw(self.root_directory,
                       self.parent_path,
                       name,
                       io_mode=self.io_mode)

    def require_raw(self, name):
        directory_name = os.path.join(self.directory, name)
        if os.path.exists(directory_name):
            if exdir_object.is_nonraw_object_directory(directory_name):
                raise FileExistsError("Directory '" + directory_name + "' already exists, but is not raw.")
            return directory_name

        return self.create_raw(name)
