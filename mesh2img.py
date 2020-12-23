# -*- coding: utf-8 -*-
"""
A script for creating image previews of PLY and STL files.

This is meant to be called from Blender, not Python directly. If Blender is on your PATH, you should be able to do
something like this from the command line:

`$ blender --background -P mesh2img.py -- --paths /some/stl/files /just/one/item.ply --dimensions 1024,768`

There's a lot of command line arguments but there's still probably a lot of things that can't be done just using this
script on the command line as-is. I've tried to comment this script to be easy to change to suit your purposes.

:copyright: 2016 by Phillip Stromberg
:license:   MIT

"""
#to run the program for now type "blender -b -P mesh2img.py -- --paths C:\first_try --dimensions 1080 -x 7" in the cmd

from bpy import context, data, ops
import bpy
import argparse
from datetime import datetime
import logging
import math
import os
import sys


# some default colors for adding a stamp to your render (Red, Green, Blue, Opacity)
WATERMARK_WHITE = (255, 255, 255, 1)
WATERMARK_TRANSLUCENT_WHITE = (255, 255, 255, .75)
WATERMARK_BLACK = (0, 0, 0, 1)
WATERMARK_TRANSLUCENT_BLACK = (0, 0, 0, .75)


class Mesh2Img(object):
    """
    A class for setting up a image-conversion batch.

    Add paths to folders/files to it by using self.filepaths.append('/your/path/here')
    Add desired output images by using add_job_template. (i.e. `add_job_template((800, 600), '{basename}_{width}.{ext}')`)
    When it's ready, use the .start() function to process the directories and output the specified images for each
    STL or PLY file it finds.
    """

    DEFAULT_CAMERA_COORDS = (0, 0, 10.0)  # by default our camera sits 10 units above the origin
    DEFAULT_CAMERA_ROTATION = (0, 0, 0)  # the camera points down on our mesh
    DEFAULT_OUTPUT_TEMPLATE = "{filepath}_{width}.{ext}"  # this will generate the image next to the original mesh file
    IMAGE_FORMATS = {
        # file extensions with their render.image_settings.file_format string counterpart
        'bmp': 'BMP',
        'jpg': 'JPEG',
        'png': 'PNG',
        'tif': 'TIFF'
    }
    MESH_TYPES = {
        # here are the functions that open the given file extensions
        '.stl': bpy.ops.import_mesh.stl,    #ops.import_mesh.stl if it doesn't work for some reason replace them with this
        '.ply': bpy.ops.import_mesh.ply,    #ops.import_mesh.ply
    }

#when your ready to put the material paramter put this below 'material=None'.
    def __init__(self, paths=None, dimensions=None, image_format=None, verbose=False,
                 output_template=DEFAULT_OUTPUT_TEMPLATE, max_dim=7.0, camera_coords=DEFAULT_CAMERA_COORDS,
                 camera_rotation=DEFAULT_CAMERA_ROTATION, jpeg_quality=80):
        """
        Creates a new batch job. Does not start processing paths until you call .start(). You don't have to pass
        anything in at creation time, but at least one path and one set of image dimensions are required for anything
        to actually happen.

        :param paths: paths to directories containing mesh files or the paths to the files themselves
        :param dimensions: a list of (width, height) tuples to specify image sizes to generate
        :param material: the material name as a string to apply to the imported mesh
        :param image_format: the output format for all output images. For finer control, use add_job_template instead
        :param output_template: output image file name pattern (where they'll go and how they're named)
        :param max_dim: the maximum length of any axis of the mesh (the mesh will be scaled up/down to this)
        :param camera_coords: an (X, Y, Z) tuple to define where the camera should be positioned
        :param camera_rotation: an (X, Y, Z) tuple to define the rotation of the camera in degrees
        :param jpeg_quality: if JPEG is the output format, this determines the quality of the compression (1-100)
        """
        if paths is not None:
            if isinstance(paths, str):  # if they gave us just 1 path instead of a list of paths
                paths = [paths]
        else:
            paths = []
        self.filepaths = paths
        #self.materials = [mat_name.strip() for mat_name in material.split(',')]
        self._job_templates = []
        self.verbose = self._verbose = bool(verbose)
        self.max_dim = max_dim
        self.camera_coords = camera_coords
        self.camera_rotation = camera_rotation
        self.execute_time = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        if dimensions:
            for d in dimensions:
                self.add_job_template(d, output_template=output_template, image_format=image_format,
                                      jpeg_quality=jpeg_quality)

    @property
    def verbose(self):
        return self._verbose

    @verbose.setter
    def verbose(self, value):
        self._verbose = bool(value)
        if value:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.WARNING)

    def add_job_template(self, dimensions, output_template=DEFAULT_OUTPUT_TEMPLATE, image_format='png',
                         jpeg_quality=80):
        """
        For each mesh found when start() is called, each job template is called. You can call this function multiple
        times to define multiple file sizes and types for each mesh.
        For example, let's say you have 20 meshes and you add three jobs (maybe one for thumbnail, one for medium, and
        one for large). When the script is finished, you will have 3 images of each of the 20 meshes (or 60 images
        total).

        See also JobTemplate.__init__
        """
        logging.debug("Adding job template as %s" % locals())
        self._job_templates.append(JobTemplate(dimensions, output_template, image_format, jpeg_quality=jpeg_quality))

    @classmethod
    def open_mesh(cls, filepath):
        """
        Opens a mesh file using the function defined in Mesh2Img.MESH_TYPES and returns the object. Makes sure that
        all other objects have been deselected except the new mesh object. It also centers the mesh object to the
        origin.

        :param filepath: the path to the mesh file
        :return: the object representing the newly imported mesh
        """
        print(filepath)
        logging.info("Opening mesh from %s" % filepath)
        ext = os.path.splitext(filepath)[1].lower()

        cls.MESH_TYPES[ext](filepath=filepath)  # calls the function associated with this extension
        mesh = context.selected_objects[0]
        for obj in bpy.context.selected_objects:   # deselect EVERYTHING
            obj.select_set(False)
        mesh.select_set(state=True)  # ok now just select our mesh
        bpy.context.view_layer.objects.active = mesh
        ops.object.origin_set(type='GEOMETRY_ORIGIN')  # center the mesh at the origin point
        return mesh

    def start(self):
        """
        Begin processing the given paths and job templates.
        """
        if not self.filepaths:
            raise ValueError("No filepaths were given. I have no idea what you want me to convert.")
        if not self._job_templates:
            raise ValueError("No jobs given so there's nothing for me to do with these meshes. "
                             "Try calling `add_job_template` first to define image sizes and output locations.")

        # prepare the scene
        delete_object_by_name("Cube", ignore_errors=True)  # factory default Blender has a cube in the default scene
        camera_params = self.camera_coords + self.camera_rotation
        set_camera(*camera_params)  # take picture from 10 units away

        for filepath in self.filepaths:
            if os.path.isdir(filepath):
                self._process_dir(filepath)
            else:
                self._process_file(filepath)

    def _process_dir(self, filepath):
        """
        Given the path to a folder, recursively enters each directory in the tree to process every mesh file defined
        in MESH_TYPES.

        :param filepath: a full path to the directory to recurse through
        """
        for folder, subfolders, filenames in os.walk(filepath):  # recurse directory
            logging.debug("Entering %s", folder)
            for filename in filenames:  # for each file in this directory
                ext = os.path.splitext(filename)[1].lower()
                if ext in self.MESH_TYPES:  # if this is a known mesh file type
                    file = os.path.join(folder, filename)  # this is the full path to that file
                    self._process_file(file)  # process this file now

    def _process_file(self, filepath, leave_mesh_open=False):
        """
        Imports and scales the mesh and then saves one image per job template defined.

        :param filepath: the path to a mesh file
        :param leave_mesh_open: by default, the mesh object is removed from the scene after the image is saved
        """
        mesh = self.open_mesh(filepath)
        scale_mesh(mesh, max_dim=self.max_dim)
        #if self.materials:
            #self._apply_material(mesh, self.materials)

        for jt in self._job_templates:
            logging.debug("Applying %s to %s", jt, filepath)
            output_path = jt.get_output_path(filepath, exec_time=self.execute_time)
            self.save_image(output_path, width=jt.width, height=jt.height, file_format=jt.image_format,
                            jpeg_quality=jt.jpeg_quality)
        if not leave_mesh_open:
            self._delete_mesh(mesh)


    @staticmethod
    def _delete_mesh(mesh):
        """
        Given a Blender object, removes it from the scene.
        :param mesh: the Blender object
        """
        name = mesh.name
        print(name)
        print(ops.object)
        delete_object_by_name(name)


    @classmethod
    def command_line(cls):
        """
        Implements the Python argparse module to process the command line arguments. The arguments are returned as a
        dictionary that can be fed directly to the Mesh2Img.__init__ function using Python's **kwargs feature.

        :return: a dictionary containing the arguments from the command line
        """
        try:
            index = sys.argv.index("--") + 1  # ignore anything before the '--' in the blender.exe invocation
        except ValueError:
            index = len(sys.argv)

        parser = argparse.ArgumentParser('Mesh2Img',
                                         description="A utility for generating image previews of STL and PLY files "
                                                     "using Blender's Python scripting engine.")
        parser.add_argument('-d', '--dimensions', type=str, nargs='+', required=True,
                            help='Provide either at least 1 dimension or pair of dimensions to specify the size of the '
                                 'images to generate. i.e. `-d 400 800,600 2048` would create a 400x400, 800x600, and '
                                 '2048x2048 image for each STL or PLY file found.')
        parser.add_argument('-p', '--paths', type=str, nargs='+', required=True,
                            help='The path(s) to the mesh file(s). If a directory is given, all PLY and STL files in '
                                 'the entire directory tree are processed. A mixed list of file paths and folder paths '
                                 'can be given.')
        parser.add_argument('-v', '--verbose', action='store_true',
                            help="See more output logging to the command line.")
        parser.add_argument('-i', '--image-format', default='png', choices=cls.IMAGE_FORMATS.keys(), type=str,
                            help="Specify what image format to output as.")
        parser.add_argument('--jpeg-quality', default=80, type=int,
                            help="The JPEG quality if `jpg` was chosen as the image-format.")
        parser.add_argument('-o', '--output-template', default=cls.DEFAULT_OUTPUT_TEMPLATE, type=str,
                            help="Define how you'd like output images to be named and where to put them. Valid "
                                 "placeholders include: {basename} (filename without extension), {date} (exact time "
                                 "that particular image was made as YYYY-mm-dd_HHMMSS), {exec_time} (the time this "
                                 "script began. Good for a folder name.), {ext} (image format extension)"
                                 " {filepath} (the full path of the input file except the extension), {height} (height "
                                 "of the output image in pixels), {src_ext} (the extension of the input file), "
                                 "{width} (width of the output image in pixels)")
        parser.add_argument('-x', '--max-dim', default=9.0, type=float,
                            help="Limit the size of the mesh to not exceed this length on any axis. Setting it too "
                                 "high will make it too large to fit in the image. Setting it too low will leave a lot "
                                 "of empty margin in the image.")
        parser.add_argument('-c', '--camera-coords', default='0.0,0.0,10.0', type=str,
                            help="Where to position the camera. X,Y,Z separated by commas.")
        parser.add_argument('-r', '--camera-rotation', default='0.0,0.0,0.0', type=str,
                            help='The rotation of the camera in degrees for X,Y,Z.')
        #parser.add_argument('-m', '--material', type=str,
                            #help="One or more names of materials to apply to the mesh before rendering. "
                                 #"Material must exist in your default scene already. Separate names by comma.")

        args = parser.parse_args(sys.argv[index:]).__dict__

        # we're going to fix up the dimensions list real quick
        dimensions = []
        for d in args['dimensions']:
            split = d.split(',')  # is a pair
            if len(split) == 1:  # is it just one element?
                dimensions.append(split[0])  # just put the one element in there
            else:
                dimensions.append(split)  # put it in as an (width, height) pair
        args['dimensions'] = dimensions  # replace with the new list we just made

        args['camera_coords'] = [float(c) for c in args['camera_coords'].split(',')]
        args['camera_rotation'] = [float(c) for c in args['camera_rotation'].split(',')]

        return args

    @classmethod
    def save_image(cls, filepath, width, height=None, file_format='png', antialiasing_samples=16,
                   resolution_percentage=100, jpeg_quality=100, pngcompression=100, color_depth=8,
                   allow_transparency=True, watermark=None, watermark_size=18, watermark_metadata=False,
                   watermark_foreground=WATERMARK_WHITE, watermark_background=WATERMARK_TRANSLUCENT_BLACK):
        """
        Saves an image of the current scene at the specified size, format, and location.

        :param filepath: the file path to save this image file to
        :param width: the width of the output image in pixels
        :param height: the height of the output image in pixels (if not provided, will use width to make a square image)
        :param file_format: the type of image file to make (such as jpg, png, tiff, or bmp)
        :param antialiasing_samples: valid numbers are 5, 8, 11, and 16 or None to turn off antialiasing
        :param resolution_percentage: valid numbers are > 0. Render the scene at this percentage of the actual output
                                      image's resolution (100% or more for best results).
        :param jpeg_quality: valid numbers are 0-100. JPEG quality is the trade off of image quality and file size
        :param pngcompression: valid numbers are 0-100. The higher the number, the more time will be spent compressing
                               the PNG. The quality is always lossless.
        :param color_depth: valid numbers are 8 or 16. The number of bits to use per color channel.
        :param allow_transparency: if a PNG, sets the mode from RGB to RGBA (RGB + Alpha)
        :param watermark: enter a string here to have it stamped on the output image
        :param watermark_size: the size of the watermark font
        :param watermark_metadata: if True, metadata is stamped on the image as well as the custom string
        :param watermark_foreground: the color of the text of the watermark. This should be a tuple of the
                                     form: (Red, Green, Blue, Opacity)
        :param watermark_background: the color to put behind the text of the watermark. This should be a tuple
                                     of the form: (Red, Green, Blue, Opacity)
        """
        logging.info("Saving image %s", filepath)
        logging.debug("... with arguments: %s" % str(locals()))
        render = data.scenes['Scene'].render
        render.filepath = filepath
        render.resolution_percentage = resolution_percentage
        render.resolution_x = width
        render.resolution_y = height if height is not None else width
        settings = render.image_settings
        try:
            settings.file_format = cls.IMAGE_FORMATS[file_format]
        except KeyError:
            raise ValueError("%s was not an expected image format." % file_format)
        settings.quality = jpeg_quality
        settings.compression = pngcompression
        settings.color_depth = str(color_depth)
        color_mode = 'RGBA' if allow_transparency and file_format == 'png' else 'RGB'
        settings.color_mode = color_mode
        render.use_stamp = watermark is not None
        if watermark:
            render.stamp_background = watermark_background
            render.stamp_foreground = watermark_foreground
            render.stamp_font_size = watermark_size
            for attr in dir(render):
                if attr.startswith('use_stamp_'):
                    setattr(render, attr, watermark_metadata)
            render.use_stamp_note = True
            render.stamp_note_text = watermark
        ops.render.render(write_still=True)


class JobTemplate(object):
    def __init__(self, dimensions, output_template, image_format='png', jpeg_quality=80):
        """
        Defines 1 way a mesh will be converted to an image. Create multiple JobTemplates to define multiple output
        images of various sizes and formats per mesh.

        :param dimensions: the dimensions of output file. This can either be a tuple (width, height) or a single
                           positive integer specfiying the width and height of a square image.
        :param output_template: the format of the output file path. Use placeholders to define where output images
                                should go and how they should be named.
        :param image_format: valid strings here are keys in the `Mesh2Img.IMAGE_FORMATS` dictionary ('png', 'jpg', etc.)
        :param jpeg_quality: if 'jpg' is not the image_format this has no effect. Valid numbers are 0-100
        """
        if not image_format:
            image_format = 'png'
        try:
            width, height = dimensions  # a tuple with width and height
        except ValueError:
            width = height = dimensions  # just a single dimension (square output image)
        self.width = int(width)
        self.height = int(height)
        self.output_template = output_template
        self.image_format = image_format
        self.jpeg_quality = jpeg_quality

    def get_output_path(self, input_filepath, exec_time=None):
        """
        Given the input filepath, returns an output filepath based on this template object's template string.

        :param input_filepath: the path to the source file that will need a destination path based on its name
        :param exec_time: the time at which the program was started (passed in by the script)
        :return: an output path string based on the template defined in this JobTemplate
        """
        date = datetime.now().strftime('%Y-%m-%d_%H%M%S')  # the current time in the format `YYYY-mm-dd_HHMMSS`
        if not exec_time:
            exec_time = date
        filepath, src_ext = os.path.splitext(input_filepath)
        basename = os.path.basename(filepath)
        ext = self.image_format.lower()
        return self.output_template.format(basename=basename, date=date, exec_time=exec_time, ext=ext,
                                           filepath=filepath, height=self.height, src_ext=src_ext, width=self.width)

    def __str__(self):
        return "JobTemplate(%s)" % str(self.__dict__)


def delete_object_by_name(name, ignore_errors=False):
    """
    Attempts to find an object by the name given and deletes it from the scene.

    :param name: the name of this object
    :param ignore_errors: if True, no exception is raised when the object is deleted. Otherwise, you will get a
                          KeyError if no object by that name exists.
    :return: True if the object was found and deleted successfully
    """
    try:
        logging.debug("Attempting to delete object '%s'" % name)
        obj = data.objects[name]
    except KeyError as ex:
        if ignore_errors:  # are we ignoring errors?
            logging.debug("Didn't delete '%s'. Probably didn't exist. Error ignored." % name)
            return False  # just report that we weren't successful
        raise ex  # object doesn't exist so raise this exception
    ops.object.select_all(action='DESELECT')
    obj.select_set(state=True)
    context.view_layer.objects.active = obj
    bpy.ops.object.delete()



def scale_mesh(mesh, max_dim=9.0):
    """
    Scales the given object so that it's longest dimension on any axis is exactly the number of units specified by
    max_dim. This is useful for scaling objects to a consistent size.

    If an object's maximum dimension is 0, no action is performed.

    :param mesh: the object to scale to be exactly `max_dim` units at it's longest side
    :param max_dim: the limit to how big an object can be on any axis
    """
    logging.debug("Scaling mesh %s to a maximum of %s in any direction" % (mesh.name, max_dim))
    max_length = max(mesh.dimensions)
    print('=================================================',max_length)
    if max_length == 0:
        logging.debug("No scaling for %s because its dimensions are %s" % (mesh.name, repr(mesh.dimensions)))
        return  # skip scaling
    scale_factor = 1 / (max_length / max_dim)
    mesh.scale = (scale_factor, scale_factor, scale_factor)
    x, y, z = [i for i in mesh.dimensions]  # for pretty dimension formatting
    new_dimensions = "X=%s, Y=%s, Z=%s" % (x, y, z)
    logging.debug("Scale factor for mesh %s is %s. Its new dimensions are %s",
                  mesh.name, scale_factor, [i for i in new_dimensions])


def set_camera(x=0, y=0, z=10, rotation_x=0, rotation_y=0, rotation_z=0, camera_name='Camera'):
    """
    Sets the camera named by `camera_name` to the given coordinates.
    :param x: the X position of the camera
    :param y: the Y position of the camera
    :param z: the Z position of the camera
    :param rotation_x: the X rotation of the camera in degrees
    :param rotation_y: the Y rotation of the camera in degrees
    :param rotation_z: the Z rotation of the camera in degrees
    :param camera_name: the name of the camera object to be moved
    """
    camera = data.objects[camera_name]
    camera.location = (x, y, z)
    # convert the angles given into radians because that's what Blender operates on
    rx, ry, rz = math.radians(rotation_x), math.radians(rotation_y), math.radians(rotation_z)
    camera.rotation_euler = (rx, ry, rz)

def size_object(object):
    object.select_set(state=True)
    bpy.context.view_layer.objects.active = object
    x, y, z = bpy.context.active_object.dimensions
    return x, y, z

def distance(p1, p2):
    return sqrt((p1[0]-p2[0])**2+(p1[1]-p2[1])**2+(p1[2]-p2[2])**2)

if __name__ == "__main__":  # start execution here
    old_level = logging.getLogger().level
    cliargs = Mesh2Img.command_line()
    Mesh2Img(**cliargs).start()  # pass in all the paths given on the command line
    logging.getLogger().setLevel(old_level)
