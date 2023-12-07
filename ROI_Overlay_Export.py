#!/usr/bin/env python
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------

#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.

#   You should have received a copy of the GNU General Public License along
#   with this program; if not, write to the Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# ------------------------------------------------------------------------------

"""This script exports an overlay of ROI outlines \
      for images in OMERO"""

import omero.scripts as scripts
from omero.gateway import BlitzGateway
from omero.rtypes import rlong, rstring, robject
import ezomero
from PIL import Image, ImageDraw
from io import BytesIO
import mimetypes

# Temporary measure for ezomero v1.1.1 which assumes stroke width, 
# which QuPath does not provide
from ezomero.rois import Point, Line, Rectangle, Ellipse, \
                         Polygon, Polyline, Label


def _int_to_rgba(omero_val, is_fill):
    """ Helper function returning the color as an Integer in RGBA encoding """
    if omero_val:
        if omero_val < 0:
            omero_val = omero_val + (2**32)
        r = omero_val >> 24
        g = omero_val - (r << 24) >> 16
        b = omero_val - (r << 24) - (g << 16) >> 8
        a = omero_val - (r << 24) - (g << 16) - (b << 8)
        return (r, g, b, a)
    else:
        if is_fill:
            return (0, 0, 0, 0)
        else:
            return (255, 255, 0, 255)


def my_omero_shape_to_shape(omero_shape):
    """ Helper function to convert ezomero shapes into omero shapes"""
    shape_type = omero_shape.ice_id().split("::omero::model::")[1]
    try:
        z_val = omero_shape.theZ
    except AttributeError:
        z_val = None
    try:
        c_val = omero_shape.theC
    except AttributeError:
        c_val = None
    try:
        t_val = omero_shape.theT
    except AttributeError:
        t_val = None
    try:
        text = omero_shape.textValue
    except AttributeError:
        text = None
    try:
        mk_start = omero_shape.markerStart
    except AttributeError:
        mk_start = None
    try:
        mk_end = omero_shape.markerEnd
    except AttributeError:
        mk_end = None

    if shape_type == "Point":
        x = omero_shape.x
        y = omero_shape.y
        shape = Point(x, y, z_val, c_val, t_val, text)
    elif shape_type == "Line":
        x1 = omero_shape.x1
        x2 = omero_shape.x2
        y1 = omero_shape.y1
        y2 = omero_shape.y2
        shape = Line(x1, y1, x2, y2, z_val, c_val, t_val,
                     mk_start, mk_end, text)
    elif shape_type == "Rectangle":
        x = omero_shape.x
        y = omero_shape.y
        width = omero_shape.width
        height = omero_shape.height
        shape = Rectangle(x, y, width, height, z_val, c_val, t_val, text)
    elif shape_type == "Ellipse":
        x = omero_shape.x
        y = omero_shape.y
        radiusX = omero_shape.radiusX
        radiusY = omero_shape.radiusY
        shape = Ellipse(x, y, radiusX, radiusY, z_val, c_val, t_val, text)
    elif shape_type == "Polygon":
        omero_points = omero_shape.points.split()
        points = []
        for point in omero_points:
            coords = point.split(',')
            points.append((float(coords[0]), float(coords[1])))
        shape = Polygon(points, z_val, c_val, t_val, text)
    elif shape_type == "Polyline":
        omero_points = omero_shape.points.split()
        points = []
        for point in omero_points:
            coords = point.split(',')
            points.append((float(coords[0]), float(coords[1])))
        shape = Polyline(points, z_val, c_val, t_val, text)
    elif shape_type == "Label":
        x = omero_shape.x
        y = omero_shape.y
        fsize = omero_shape.getFontSize().getValue()
        shape = Label(x, y, text, fsize, z_val, c_val, t_val)
    else:
        err = 'The shape passed for the roi is not a valid shape type'
        raise TypeError(err)

    fill_color = _int_to_rgba(omero_shape.getFillColor(), is_fill=True)
    stroke_color = _int_to_rgba(omero_shape.getStrokeColor(), is_fill=False)
    try:
        stroke_width = omero_shape.getStrokeWidth().getValue()
    except AttributeError:
        stroke_width = 1

    return shape, fill_color, stroke_color, stroke_width


def my_get_shape(conn, shape_id, across_groups=True):
    """Get an ezomero shape object from an OMERO Shape id

    Parameters
    ----------
    conn : ``omero.gateway.BlitzGateway`` object
        OMERO connection.
    shape_id : int
        ID of shape to get.
    across_groups : bool, optional
        Defines cross-group behavior of function - set to
        ``False`` to disable it.

    Returns
    -------
    shape : obj
        An object of one of ezomero shape classes
    fill_color: tuple
        Tuple of format (r, g, b, a) containing the shape fill color.
    stroke_color: tuple
        Tuple of format (r, g, b, a) containing the shape stroke color.
    stroke_width: float
        Shape stroke width, in pixels
    Examples
    --------
    >>> shape = get_shape(conn, 634443)

    """
    if not isinstance(shape_id, int):
        raise TypeError('Shape ID must be an integer')
    omero_shape = conn.getObject('Shape', shape_id)
    return my_omero_shape_to_shape(omero_shape)

# End temporary measure for ezomero v1.1.1


def log(data):
    """Handle logging or printing in one place."""
    print(data)


def make_black_transparent(img):
    img = img.convert("RGBA")
    datas = img.getdata()

    newData = []
    for item in datas:
        if item[0] == 0 and item[1] == 0 and item[2] == 0:
            newData.append((255, 255, 255, 0))
        else:
            newData.append(item)

    img.putdata(newData)
    return(img)


def draw_shape(shape_tuple, draw, scale):
    shape, fill_color, stroke_color, stroke_width = shape_tuple
    """Draw shape on overlay in place"""
    if isinstance(shape, ezomero.rois.Rectangle):
        draw.rectangle(xy=((round(shape.x/scale), round(shape.y/scale)),
                           (round((shape.x+shape.width)/scale),
                            round((shape.y+shape.height)/scale))),
                       fill=fill_color, outline=stroke_color,
                       width=round(stroke_width))
    if isinstance(shape, ezomero.rois.Ellipse):
        x0, y0 = (round((shape.x-shape.x_rad)/scale),
                  round((shape.y-shape.y_rad)/scale))
        x1, y1 = (round((shape.x+shape.x_rad)/scale),
                  round((shape.y+shape.y_rad)/scale))
        draw.ellipse(xy=((x0, y0), (x1, y1)), fill=fill_color,
                     outline=stroke_color,
                     width=round(stroke_width))
    if isinstance(shape, ezomero.rois.Line):
        draw.line(xy=((round(shape.x1/scale), round(shape.y1/scale)),
                      (round(shape.x2/scale), round(shape.y2/scale))),
                  fill=stroke_color,
                  width=round(stroke_width))
    if isinstance(shape, ezomero.rois.Polyline):
        points = [(round(p[0]/scale), round(p[1]/scale)) for p in shape.points]
        draw.line(xy=points,
                  fill=stroke_color,
                  width=round(stroke_width))
    if isinstance(shape, ezomero.rois.Polygon):
        points = [(round(p[0]/scale), round(p[1]/scale)) for p in shape.points]
        draw.polygon(xy=points,
                     fill=fill_color, outline=stroke_color,
                     width=round(stroke_width))
    if isinstance(shape, ezomero.rois.Point):
        draw.point(xy=(round(shape.x/scale), round(shape.y/scale)),
                   fill=stroke_color)
        draw.ellipse(xy=((round((shape.x)/scale-3), round((shape.y)/scale-3)),
                         (round((shape.x)/scale+3), round((shape.y)/scale)+3)),
                     outline=stroke_color)


def get_images_from_plate(plate):
    imgs = []
    for well in plate.listChildren():
        for ws in well.listChildren():
            imgs.append(ws.image())
    return imgs


def roi_overlay_export(conn, script_params):
    """Main entry point. Get images, process them and return result."""
    images = []

    dtype = script_params['Data_Type']
    ids = script_params['IDs']
    if dtype == "Image":
        images = list(conn.getObjects("Image", ids))
    elif dtype == "Dataset":
        for dataset in conn.getObjects("Dataset", ids):
            images.extend(list(dataset.listChildren()))
    elif dtype == "Project":
        for project in conn.getObjects("Project", ids):
            for dataset in project.listChildren():
                images.extend(list(dataset.listChildren()))
    elif dtype == "Plate":
        for plate in conn.getObjects("Plate", ids):
            images.extend(get_images_from_plate(plate))
    elif dtype == "Screen":
        for screen in conn.getObjects("Screen", ids):
            for plate in screen.listChildren():
                images.extend(get_images_from_plate(plate))

    log("Processing {} images...".format(len(images)))
    if len(images) == 0:
        return None

    overlay_size = script_params['Size']
    if overlay_size > 5000:
        log("Large overlay size might crash server, setting to 5000px")
        overlay_size = 5000
    exclude_image = script_params['Exclude_Image']
    filename = script_params['File_Name']
    file_ann = None
    for image in images:
        scale = max(image.getSizeX(), image.getSizeY())/overlay_size
        # Create a blank image
        if exclude_image:
            overlay = Image.new('RGB', (round(image.getSizeX()/scale),
                                        round(image.getSizeY()/scale)))
        else:
            pix = image.getThumbnail(size=(round(image.getSizeX()/scale),
                                           round(image.getSizeY()/scale)),
                                     direct=True)
            overlay = Image.open(BytesIO(pix))
        draw = ImageDraw.Draw(overlay, "RGBA")
        roi_ids = ezomero.get_roi_ids(conn, image.id)
        log("Image ID {} has {} ROIs".format(image.id, len(roi_ids)))
        if len(roi_ids) == 0:
            log("Not saving an overlay for Image ID {}".format(image.id))
            continue
        for roi_id in roi_ids:
            shape_ids = ezomero.get_shape_ids(conn, roi_id)
            for shape_id in shape_ids:
                shape = my_get_shape(conn, shape_id)
                draw_shape(shape, draw, scale)
        if exclude_image:
            overlay = make_black_transparent(overlay)

        if "{}" in filename:
            filename = filename.format(image.id)
        overlay.save(filename)
        mimetype = mimetypes.guess_type(filename)[0]
        file_ann = conn.createFileAnnfromLocalFile(filename,
                                                   mimetype=mimetype)

        image.linkAnnotation(file_ann)

    message = "Created jpeg overlays for {} images".format(len(images))
    return file_ann, message


def run_script():
    """The main entry point of the script, as called by the client."""
    data_types = [rstring(s) for s in
                  ['Screen', 'Plate', 'Project', 'Dataset', 'Image']]

    client = scripts.client(
        'ROI_overlay_export.py',
        """Export ROI overlay for Image IDs.""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="The data you want to work with.", values=data_types,
            default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Dataset IDs or Image IDs").ofType(rlong(0)),

        scripts.String(
            "File_Name", grouping="3",
            description="File name for output overlay image - \
                         {} will be replaced with image ID",
            default="roi_overlay_{}.png"),

        scripts.Long(
            "Size", optional=False, grouping="4",
            description="Maximum pixel size of resulting overlay",
            default=500),

        scripts.Bool(
            "Exclude_Image", optional=False, grouping="5",
            description="Produce transparent overlay without image background",
            default=False),

        authors=["Kiya Govek"],
        institutions=["The Jackson Laboratory"],
        contact="kiya.govek@jax.org",
        )

    try:
        conn = BlitzGateway(client_obj=client)

        script_params = client.getInputs(unwrap=True)
        log("script_params:")
        log(script_params)

        # call the main script
        result = roi_overlay_export(conn, script_params)

        # Return message and file_annotation to client
        if result is None:
            message = "No images found"
        else:
            file_ann, message = result
            if file_ann is not None:
                client.setOutput("File_Annotation", robject(file_ann._obj))

        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
