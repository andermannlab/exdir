import numbers
import exdir

import numpy as np

from . import exdir_object as exob


def _prepare_write(data):
    attrs = {}
    meta = {}
    for plugin in exdir.core.plugin.dataset_plugins:
        data, plugin_attrs, plugin_meta = plugin.prepare_write(data)
        attrs.update(plugin_attrs)
        if plugin_meta["required"]:
            meta[plugin.IDENTIFIER] = plugin_meta

    if isinstance(data, (numbers.Number, tuple, str)):
        data = np.asarray(data, order="C")

    return data, attrs, meta


def _dataset_filename(dataset_directory):
    return dataset_directory / "data.npy"


class Dataset(exob.Object):
    """
    Dataset class

    Warning: This class modifies the view, which is different from h5py.
    Warning: Possible to overwrite existing dataset.
             This differs from the h5py API. However,
             it should only cause issues with existing
             code if said code expects this to fail."
    """
    def __init__(self, root_directory, parent_path, object_name, io_mode=None,
                 validate_name=None):
        super(Dataset, self).__init__(
            root_directory=root_directory,
            parent_path=parent_path,
            object_name=object_name,
            io_mode=io_mode,
            validate_name=validate_name
        )
        self._data_memmap = None
        if self.io_mode == self.OpenMode.READ_ONLY:
            self._mmap_mode = "r"
        else:
            self._mmap_mode = "r+"

        self.data_filename = str(_dataset_filename(self.directory))

    def __getitem__(self, args):
        if len(self._data.shape) == 0:
            values = self._data
        else:
            values = self._data[args]

        enabled_plugins = [plugin.IDENTIFIER for plugin in exdir.core.plugin.dataset_plugins]
        for plugin_name in self.meta["plugins"].keys():
            if not plugin_name in enabled_plugins:
                raise Exception(
                    ("Plugin '{}' was used to write '{}', "
                    "but is not enabled.").format(plugin_name, self.name)
                )

        for plugin in exdir.core.plugin.dataset_plugins:
            values = plugin.prepare_read(values, self.attrs)


        return values

    def __setitem__(self, args, value):
        if self.io_mode == self.OpenMode.READ_ONLY:
            raise IOError('Cannot write data to file in read only ("r") mode')

        value, attrs, meta = _prepare_write(value)
        self.attrs.update(attrs)
        self.meta["plugins"] = meta

        self._data[args] = value

    def _reload_data(self):
        self._data_memmap = np.load(self.data_filename, mmap_mode=self._mmap_mode)

    def _reset_data(self, value):
        value, attrs, meta = _prepare_write(value)

        np.save(self.data_filename, value)

        self.attrs.update(attrs)
        self.meta["plugins"] = meta
        self._reload_data()
        return

    def set_data(self, data):
        raise DeprecationWarning(
            "set_data is deprecated. Use `dataset.value = data` instead."
        )
        self.value = data

    @property
    def data(self):
        return self[:]

    @data.setter
    def data(self, value):
        self.value = value

    @property
    def shape(self):
        return self[:].shape

    @property
    def size(self):
        return self[:].size

    @property
    def dtype(self):
        return self[:].dtype

    @property
    def value(self):
        return self[:]

    @value.setter
    def value(self, value):
        if self._data.shape != value.shape:
            self._reset_data(value)
            return

        self[:] = value

    def __len__(self):
        """ The size of the first axis.  TypeError if scalar."""
        if len(self.shape) == 0:
            raise TypeError("Attempt to take len() of scalar dataset")
        return self.shape[0]

    def __iter__(self):
        """Iterate over the first axis.  TypeError if scalar.
        WARNING: Modifications to the yielded data are *NOT* written to file.
        """

        if len(self.shape) == 0:
            raise TypeError("Can't iterate over a scalar dataset")

        for i in range(self.shape[0]):
            yield self[i]

    @property
    def _data(self):
        if self._data_memmap is None:
            self._reload_data()
        return self._data_memmap
