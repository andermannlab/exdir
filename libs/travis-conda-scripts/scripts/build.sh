mkdir -p "$CONDA_BLD_PATH"
conda config --set anaconda_upload no
conda build . $EXTRA_CONDA_CHANNELS --python "$PYTHON_VERSION" --dirty --old-build-string
