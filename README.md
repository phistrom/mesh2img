# mesh2img.py

**mesh2img.py** is a Python script for Blender that converts STL and PLY mesh files into images.

  - Convert a whole directory of mesh files into images for easy previewing
  - Specify multiple sets of dimensions and image formats for each mesh file (a 200x200 jpg and an 800x600 png per mesh? no problem)
  - No dependencies other than Blender 2.5+ and its bundled Python 3 interpreter.

## Installation
  - For easy usage, make sure your Blender directory is in your operating system's PATH variable.
  - Place this Python script anywhere
  - Use `blender -P /path/to/mesh2img.py` to execute. See **Usage** below for more details.

## Usage
### Preface
```sh
# Don't do this
$ python mesh2img.py  # doesn't work
```
Because this Python script is not meant to be called directly, but rather by Blender's built-in Python interpreter, **you must execute the script like this**:
```sh
/path/to/blender -b -P /path/to/mesh2img.py -- [mesh2img.py arguments here]
```
  - The `-b` flag will tell Blender not to launch the user interface and operate only here on the command line.
  - The `-P` flag gives Blender a path to a Python script. That's what *this* is!
  - The `--` in the middle tells Blender to not look at the rest of the flags. They're only for mesh2img.py at this point.
  - Some `mesh2img.py` arguments are covered below

#### Convert a directory of STL or PLY files into 200x200 PNG thumbnails
After this runs, each mesh file will have a PNG in the same folder with the same name and `_200` appended to it.
```sh
blender -b -P mesh2img.py -- --paths /all/my/meshes_folder --dimensions 200
```
#### Convert a single mesh file to three different sized JPEGs (200x200, 800x600, 2048x2048)
```sh
blender -b -P mesh2img.py -- --paths /some/mesh/file.stl --dimensions 200 800,600 2048 -i jpg
```

#### Convert a single mesh file to a 300x300 PNG and apply a material named "gold"
```sh
blender -b -P mesh2img.py -- --paths /some/mesh/file.stl --dimensions 300 -m gold
```

#### Convert 2 folders into 200x200 PNGs that go into one output folder by date/time the program ran
```sh
blender -b -P mesh2img.py -- --paths /half/my/meshes "/other/meshes folder" \
  --dimensions 200 -o "/some/output/folder/{exec_time}/{basename}_{width}.{ext}"
```

#### List all flags
```sh
blender -b -P mesh2img.py -- --help
```

### Use in your own Blender scripts
Several functions and the Mesh2Img class can be imported from this script into your own Python scripts. Just place this script in the same directory as your script or in the `2.XX/python/lib` folder of your Blender directory.
```python
from mesh2img import delete_object_by_name, Mesh2Img, scale_mesh
```

### Version
0.1

### TODO
 - More testing
 - More control via the command line

License
----
MIT
